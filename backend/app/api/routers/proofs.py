import contextlib
import logging
import uuid
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import ai_rate_limit, referee_rate_limit, upload_rate_limit
from app.api.deps import CurrentUser, SessionDep
from app.db.session import get_session_factory
from app.jobs.queue import ProofQueue, QueueUnavailableError, build_proof_queue
from app.models import Proof
from app.models.enums import ProofType
from app.schemas.proof import ProofCreate, ProofDetail, ProofRead, SkillRef
from app.schemas.referee import RefereeRequestCreate
from app.services.email.sender import EmailSender, get_email_sender
from app.services.github.client import GitHubAPI, get_github_client
from app.services.github.urls import InvalidRepoUrlError
from app.services.proofs.certificates import MAX_UPLOAD_BYTES, CertificateFileError
from app.services.proofs.methods import method_label
from app.services.proofs.service import (
    AnalysisDeps,
    InvalidProofError,
    ProofNotFoundError,
    ProofService,
    UnknownSkillError,
    UnsupportedProofTypeError,
)
from app.services.storage.files import FileStorage, get_file_storage
from app.services.verification.referees import RefereeError, RefereeService
from app.services.web.fetch import Fetcher, get_fetcher

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proofs", tags=["proofs"])

AIDep = Annotated[AIClient, Depends(get_ai_client)]
GitHubDep = Annotated[GitHubAPI, Depends(get_github_client)]
FactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
StorageDep = Annotated[FileStorage, Depends(get_file_storage)]
FetcherDep = Annotated[Fetcher, Depends(get_fetcher)]
EmailDep = Annotated[EmailSender, Depends(get_email_sender)]


def _deps(
    factory: FactoryDep,
    github: GitHubDep,
    ai: AIDep,
    storage: StorageDep,
    fetcher: FetcherDep,
    email: EmailDep,
) -> AnalysisDeps:
    return AnalysisDeps(factory, github, ai, storage, fetcher, email)


DepsDep = Annotated[AnalysisDeps, Depends(_deps)]


def _queue(background: BackgroundTasks, deps: DepsDep) -> ProofQueue:
    return build_proof_queue(background, deps)


QueueDep = Annotated[ProofQueue, Depends(_queue)]


def _enqueue(queue: ProofQueue, proof_id: uuid.UUID) -> None:
    try:
        queue.enqueue(proof_id)
    except QueueUnavailableError as exc:
        logger.error("Could not queue proof %s: %s", proof_id, exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Your proof was saved, but analysis couldn't start. Use Re-run analysis in a minute.",
        ) from exc


_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Proof not found")


def _read(proof: Proof) -> ProofRead:
    level = proof.ai_report.verification_level if proof.ai_report else None
    return ProofRead(
        id=proof.id,
        type=proof.type,
        url=proof.url,
        status=proof.status,
        score=proof.score,
        skills=[SkillRef.model_validate(s) for s in proof.skills],
        verification_level=level,
        verification_method=method_label(proof.type, level, proof.ai_report),
        decision=proof.ai_report.decision if proof.ai_report else "",
        linked_proof_id=proof.linked_proof_id,
        file_name=_file_name(proof),
        progress=proof.progress,
        created_at=proof.created_at,
    )


def _file_name(proof: Proof) -> str | None:
    report = proof.ai_report
    info = (report.upload or report.certificate) if report else None
    return info.filename if info else None


def _detail(proof: Proof) -> ProofDetail:
    return ProofDetail(**_read(proof).model_dump(), report=proof.ai_report)


async def _detail_with_referee(
    session: AsyncSession, user: CurrentUser, proof: Proof
) -> ProofDetail:
    detail = _detail(proof)
    if proof.type is ProofType.REFEREE_CONFIRMATION:
        with contextlib.suppress(RefereeError):
            detail.referee = await RefereeService(session).info(user, proof.id)
    return detail


@router.post("", response_model=ProofDetail, status_code=status.HTTP_202_ACCEPTED)
@ai_rate_limit
async def create_proof(
    request: Request,  # required by the rate limiter
    body: ProofCreate,
    user: CurrentUser,
    session: SessionDep,
    queue: QueueDep,
) -> ProofDetail:
    """Submit a link: a GitHub repo, a live project (optionally linked to one of your repo
    proofs), a portfolio page or a publication (a DOI or link). Repos, portfolios and
    publications need 1-5 skills. Analysis runs in the background: poll GET /api/proofs/{id}."""
    try:
        proof = await ProofService(session).create(user, body)
    except UnsupportedProofTypeError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Upload certificates, licences, work samples and letters with POST /api/proofs/upload.",
        ) from exc
    except InvalidProofError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except InvalidRepoUrlError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except UnknownSkillError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown skill") from exc
    _enqueue(queue, proof.id)
    return _detail(proof)


UploadType = Literal[
    "certificate", "professional_license", "work_sample", "reference_letter", "experience_letter"
]  # fmt: skip


async def _upload(
    user: CurrentUser,
    session: AsyncSession,
    deps: AnalysisDeps,
    queue: ProofQueue,
    *,
    proof_type: ProofType,
    file: UploadFile,
    skill_ids: list[uuid.UUID],
    register_url: str | None = None,
) -> ProofDetail:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        proof = await ProofService(session).create_upload(
            user,
            proof_type=proof_type,
            filename=file.filename,
            content_type=file.content_type,
            data=data,
            skill_ids=skill_ids,
            storage=deps.storage,
            register_url=register_url,
        )
    except CertificateFileError as exc:
        code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if len(data) > MAX_UPLOAD_BYTES
            else (status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        )
        raise HTTPException(code, str(exc)) from exc
    except (InvalidProofError, UnknownSkillError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc) or "Unknown skill"
        ) from exc
    _enqueue(queue, proof.id)
    return _detail(proof)


@router.post("/upload", response_model=ProofDetail, status_code=status.HTTP_202_ACCEPTED)
@upload_rate_limit
@ai_rate_limit
async def upload_proof(
    request: Request,  # required by the rate limiter
    file: UploadFile,
    user: CurrentUser,
    session: SessionDep,
    deps: DepsDep,
    queue: QueueDep,
    type: Annotated[UploadType, Form()],
    skill_ids: Annotated[list[uuid.UUID], Form()] = [],  # noqa: B006  (FastAPI form default)
    register_url: Annotated[str | None, Form(max_length=2048)] = None,
) -> ProofDetail:
    """Upload a file proof (max 5 MB): a certificate or professional licence (PDF, JPG, PNG),
    or a work sample or reference/experience letter (also Word .docx). Work samples need 1-5
    skills; for the others they're optional (we map them). Licences can include a link to
    your entry on the issuing body's public register, which is how they get verified."""
    return await _upload(
        user,
        session,
        deps,
        queue,
        proof_type=ProofType(type),
        file=file,
        skill_ids=skill_ids,
        register_url=register_url,
    )


@router.post("/certificate", response_model=ProofDetail, status_code=status.HTTP_202_ACCEPTED)
@upload_rate_limit
@ai_rate_limit
async def upload_certificate(
    request: Request,  # required by the rate limiter
    file: UploadFile,
    user: CurrentUser,
    session: SessionDep,
    deps: DepsDep,
    queue: QueueDep,
    skill_ids: Annotated[list[uuid.UUID], Form()] = [],  # noqa: B006  (FastAPI form default)
) -> ProofDetail:
    """Upload a certificate (same as /upload with type=certificate)."""
    return await _upload(
        user,
        session,
        deps,
        queue,
        proof_type=ProofType.CERTIFICATE,
        file=file,
        skill_ids=skill_ids,
    )


@router.get("/{proof_id}/file")
async def proof_file(
    proof_id: uuid.UUID, user: CurrentUser, session: SessionDep, storage: StorageDep
) -> Response:
    """The uploaded file, to its owner only. Storage paths are never exposed."""
    try:
        data, content_type, name = await ProofService(session).file(user, proof_id, storage)
    except ProofNotFoundError as exc:
        raise _NOT_FOUND from exc
    safe_name = "".join(c for c in name if c.isalnum() or c in "._- ")[:100] or "certificate"
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("", response_model=list[ProofRead])
async def list_proofs(user: CurrentUser, session: SessionDep) -> list[ProofRead]:
    await RefereeService(session).expire_stale(user.id)
    return [_read(p) for p in await ProofService(session).list(user)]


@router.get("/{proof_id}", response_model=ProofDetail)
async def get_proof(proof_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProofDetail:
    await RefereeService(session).expire_stale(user.id)
    try:
        proof = await ProofService(session).get(user, proof_id)
    except ProofNotFoundError as exc:
        raise _NOT_FOUND from exc
    return await _detail_with_referee(session, user, proof)


@router.post("/referee", response_model=ProofDetail, status_code=status.HTTP_201_CREATED)
@referee_rate_limit
async def ask_referee(
    request: Request,  # required by the rate limiter
    body: RefereeRequestCreate,
    user: CurrentUser,
    session: SessionDep,
    email: EmailDep,
) -> ProofDetail:
    """Ask a referee to confirm a role, its dates and 1-5 skills. They get a one-time link
    (valid 14 days); you'll see the outcome, never their answers."""
    try:
        proof = await RefereeService(session).create(user, body, email)
    except RefereeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return await _detail_with_referee(
        session, user, await ProofService(session).get(user, proof.id)
    )


@router.post("/{proof_id}/referee/resend", response_model=ProofDetail)
@referee_rate_limit
async def resend_referee(
    request: Request,
    proof_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    email: EmailDep,
) -> ProofDetail:
    """Send the referee a reminder with a fresh link (48 hours apart, at most 3 emails)."""
    try:
        await ProofService(session).get(user, proof_id)
        await RefereeService(session).resend(user, proof_id, email)
    except ProofNotFoundError as exc:
        raise _NOT_FOUND from exc
    except RefereeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return await _detail_with_referee(
        session, user, await ProofService(session).get(user, proof_id)
    )


@router.post(
    "/{proof_id}/reanalyze", response_model=ProofDetail, status_code=status.HTTP_202_ACCEPTED
)
@ai_rate_limit
async def reanalyze_proof(
    request: Request,
    proof_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    queue: QueueDep,
) -> ProofDetail:
    """Run the analysis again (after pushing improvements, or if it was interrupted)."""
    try:
        proof = await ProofService(session).reset_for_reanalysis(user, proof_id)
    except ProofNotFoundError as exc:
        raise _NOT_FOUND from exc
    except InvalidProofError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    _enqueue(queue, proof.id)
    return _detail(proof)
