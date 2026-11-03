import logging
import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.ai.client import AIClient, get_ai_client
from app.ai.errors import AIInvalidOutputError, AIRefusalError, AIUnavailableError
from app.ai.rate_limit import ai_rate_limit, export_rate_limit, upload_rate_limit
from app.api.deps import CurrentUser, SessionDep
from app.models import Resume
from app.models.enums import ResumeTemplate
from app.schemas.resume import (
    ResumeCreate,
    ResumeImportResult,
    ResumeRead,
    ResumeSummary,
    ResumeUpdate,
)
from app.services.export_service import ExportFormat, ExportService
from app.services.resume_import.extract import (
    MAX_UPLOAD_BYTES,
    FileTooLargeError,
    ImportFileError,
    UnsupportedFileError,
)
from app.services.resume_import.service import ResumeImportService
from app.services.resume_service import (
    ResumeNotFoundError,
    ResumeService,
    TargetRoleNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resumes", tags=["resumes"])

_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")
_UNKNOWN_ROLE = HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown target role")


def _read(resume: Resume) -> ResumeRead:
    return ResumeRead.model_validate(resume)


@router.get("", response_model=list[ResumeSummary])
async def list_resumes(user: CurrentUser, session: SessionDep) -> list[ResumeSummary]:
    resumes = await ResumeService(session).list_resumes(user)
    return [ResumeSummary.model_validate(r) for r in resumes]


@router.post("", response_model=ResumeRead, status_code=status.HTTP_201_CREATED)
async def create_resume(body: ResumeCreate, user: CurrentUser, session: SessionDep) -> ResumeRead:
    try:
        return _read(await ResumeService(session).create_resume(user, body))
    except TargetRoleNotFoundError as exc:
        raise _UNKNOWN_ROLE from exc


@router.post("/import", response_model=ResumeImportResult, status_code=status.HTTP_201_CREATED)
@upload_rate_limit
@ai_rate_limit
async def import_resume(
    request: Request,  # required by the rate limiter
    file: UploadFile,
    user: CurrentUser,
    session: SessionDep,
    ai: Annotated[AIClient, Depends(get_ai_client)],
) -> ResumeImportResult:
    """Create a resume from an uploaded PDF or DOCX (max 5 MB)."""
    # Read one byte past the limit so oversized files are rejected without loading them fully.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        outcome = await ResumeImportService(session, ai).import_file(
            user, filename=file.filename, content_type=file.content_type, content=content
        )
    except FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    except UnsupportedFileError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except ImportFileError as exc:  # scanned, unreadable, empty or too long
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except AIUnavailableError as exc:
        logger.warning("Resume import: AI unavailable: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Resume import is temporarily unavailable. Please try again later.",
        ) from exc
    except AIRefusalError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "This document couldn't be processed."
        ) from exc
    except AIInvalidOutputError as exc:
        logger.warning("Resume import: AI output unusable: %s", exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "We couldn't read the structure of this resume. Please try again.",
        ) from exc

    return ResumeImportResult(
        resume=_read(outcome.resume),
        matched_skills=outcome.matched_skills,
        unmatched_skills=outcome.unmatched_skills,
    )


@router.get("/{resume_id}", response_model=ResumeRead)
async def get_resume(resume_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ResumeRead:
    try:
        return _read(await ResumeService(session).get_resume(user, resume_id))
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: uuid.UUID, body: ResumeUpdate, user: CurrentUser, session: SessionDep
) -> ResumeRead:
    try:
        return _read(await ResumeService(session).update_resume(user, resume_id, body))
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
    except TargetRoleNotFoundError as exc:
        raise _UNKNOWN_ROLE from exc


@router.post(
    "/{resume_id}/duplicate", response_model=ResumeRead, status_code=status.HTTP_201_CREATED
)
async def duplicate_resume(
    resume_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ResumeRead:
    try:
        return _read(await ResumeService(session).duplicate_resume(user, resume_id))
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(resume_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    try:
        await ResumeService(session).delete_resume(user, resume_id)
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc


@router.get(
    "/{resume_id}/export",
    response_class=Response,
    responses={200: {"content": {m: {} for m in ("application/pdf", "application/octet-stream")}}},
)
@export_rate_limit
async def export_resume(
    request: Request,  # required by the rate limiter
    resume_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    format: Annotated[ExportFormat, Query()] = ExportFormat.PDF,  # noqa: A002  (public param name)
    template: Annotated[
        ResumeTemplate | None, Query(description="Defaults to the saved template")
    ] = None,
) -> Response:
    try:
        exported = await ExportService(session).export(user, resume_id, format, template)
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc

    ascii_name = exported.filename.encode("ascii", "ignore").decode() or f"resume.{format.value}"
    disposition = (
        f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(exported.filename)}"
    )
    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": disposition, "Cache-Control": "no-store"},
    )
