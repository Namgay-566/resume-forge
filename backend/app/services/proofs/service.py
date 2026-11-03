import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.certificate_reader import read_certificate
from app.ai.client import AIClient
from app.ai.errors import AIError, AIUnavailableError
from app.ai.proof_review import review_repo
from app.ai.safety import find_injection
from app.core.filenames import safe_filename
from app.models import Proof, Resume, Skill, TargetRole, User, UserSkill
from app.models.enums import ProofStatus, ProofType, UserSkillSource, VerificationStatus
from app.repositories.proof_repository import ProofRepository
from app.schemas.proof import ProofCreate
from app.schemas.proof_report import (
    CertificateInfo,
    LiveLinkInfo,
    ProofCheck,
    ProofReport,
    SkillVerdict,
    UploadInfo,
    UrlCheck,
    VerificationLevel,
)
from app.services.email.notifications import notify_proof_update
from app.services.github.client import GitHubAPI, GitHubError, RepoNotFoundError
from app.services.github.urls import InvalidRepoUrlError, parse_repo_url
from app.services.proofs.analysis import check_ownership, decide, hard_rejection, run_checks
from app.services.proofs.certificates import (
    TYPES,
    CertificateFileError,
    appears_in,
    decide_certificate,
    detect_file,
    match_name,
    prepare_image,
    read_pdf,
    trusted_host,
    url_appears_in,
)
from app.services.proofs.collect import collect
from app.services.proofs.evidence import parse_doi
from app.services.proofs.field_proofs import (
    analyze_letter,
    analyze_license,
    analyze_portfolio,
    analyze_publication,
    analyze_work_sample,
)
from app.services.proofs.live_links import decide_live, find_connection
from app.services.proofs.pipeline import STAGES, AnalysisDeps, check_link, stage
from app.services.storage.files import FileStorage, StorageError, new_key
from app.services.web.fetch import (
    BlockedUrlError,
    Fetcher,
    FetchFailedError,
    normalize_url,
    parse_page,
)

logger = logging.getLogger(__name__)

MAX_CLAIMED = 5


class ProofNotFoundError(Exception):
    pass


class UnsupportedProofTypeError(Exception):
    pass


class UnknownSkillError(Exception):
    pass


class InvalidProofError(Exception):
    """User-facing validation problem; `str(exc)` is safe to show."""


LETTERS = (ProofType.REFERENCE_LETTER, ProofType.EXPERIENCE_LETTER)
# What the proof is called in messages.
NOUNS = {
    ProofType.GITHUB_REPO: "repository",
    ProofType.LIVE_LINK: "site",
    ProofType.CERTIFICATE: "certificate",
    ProofType.PROFESSIONAL_LICENSE: "licence",
    ProofType.PORTFOLIO_LINK: "portfolio",
    ProofType.WORK_SAMPLE: "work sample",
    ProofType.PUBLICATION: "publication",
    ProofType.REFERENCE_LETTER: "reference letter",
    ProofType.EXPERIENCE_LETTER: "experience letter",
    ProofType.REFEREE_CONFIRMATION: "referee confirmation",
}
# The reviewer judges the work against the skills the user says it shows, so they must pick.
SKILLS_REQUIRED = frozenset(
    {
        ProofType.GITHUB_REPO,
        ProofType.PORTFOLIO_LINK,
        ProofType.WORK_SAMPLE,
        ProofType.PUBLICATION,
    }
)
FIELD_ANALYZERS = {
    ProofType.PROFESSIONAL_LICENSE: analyze_license,
    ProofType.PORTFOLIO_LINK: analyze_portfolio,
    ProofType.WORK_SAMPLE: analyze_work_sample,
    ProofType.PUBLICATION: analyze_publication,
    ProofType.REFERENCE_LETTER: analyze_letter,
    ProofType.EXPERIENCE_LETTER: analyze_letter,
}


def _valid_web_url(raw: str) -> str:
    url = normalize_url(raw)
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or "." not in (parts.hostname or ""):
        raise InvalidProofError("Enter a full website address, like https://myproject.dev.")
    return url


class ProofService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.proofs = ProofRepository(session)

    async def _skills(self, skill_ids: list[uuid.UUID]) -> list[Skill]:
        skills = list(await self.session.scalars(select(Skill).where(Skill.id.in_(skill_ids))))
        if len(skills) != len(set(skill_ids)):
            raise UnknownSkillError
        return skills

    async def create(self, user: User, body: ProofCreate) -> Proof:
        """Link proofs: repos, live sites, portfolios, publications, and now certificates/licences."""
        proof_type = body.type
        if proof_type.is_upload:
            raise UnsupportedProofTypeError  # files go through create_upload
        if proof_type is ProofType.REFEREE_CONFIRMATION:
            raise InvalidProofError("Ask a referee from the referee form instead.")
        skills = await self._skills(body.skill_ids)
        linked_id = None
        if proof_type in SKILLS_REQUIRED and not skills:
            raise InvalidProofError(f"Choose at least one skill this {NOUNS[proof_type]} proves.")
        if proof_type is ProofType.GITHUB_REPO:
            url = parse_repo_url(body.url).url  # raises InvalidRepoUrlError
        elif proof_type is ProofType.PUBLICATION:
            doi = parse_doi(body.url)
            url = f"https://doi.org/{doi}" if doi else _valid_web_url(body.url)
        else:
            # This now handles LIVE_LINK, PORTFOLIO_LINK, CERTIFICATE, and PROFESSIONAL_LICENSE
            url = _valid_web_url(body.url)
            
        if proof_type is ProofType.LIVE_LINK and body.linked_proof_id:
            linked = await self.proofs.get(body.linked_proof_id, user.id)
            if linked is None or linked.type is not ProofType.GITHUB_REPO:
                raise InvalidProofError("Link one of your own GitHub repository proofs.")
            linked_id = linked.id
        proof = await self.proofs.add(
            Proof(
                user_id=user.id,
                type=proof_type,
                url=url,
                skills=skills,
                linked_proof_id=linked_id,
                status=ProofStatus.PENDING,
            )
        )
        if proof_type is not ProofType.LIVE_LINK:
            await _mark_claimed(self.session, user.id, [s.id for s in skills])
        await self.session.commit()
        return await self.get(user, proof.id)

    async def create_upload(
        self,
        user: User,
        *,
        proof_type: ProofType,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        skill_ids: list[uuid.UUID],
        storage: FileStorage,
        register_url: str | None = None,
    ) -> Proof:
        """File proofs: certificates, licences, work samples and letters."""
        if not proof_type.is_upload:
            raise UnsupportedProofTypeError
        if len(skill_ids) > MAX_CLAIMED:
            raise InvalidProofError(f"Choose at most {MAX_CLAIMED} skills.")
        skills = await self._skills(skill_ids)
        if proof_type in SKILLS_REQUIRED and not skills:
            raise InvalidProofError(f"Choose at least one skill this {NOUNS[proof_type]} shows.")
        url = None
        if register_url and register_url.strip():
            if proof_type is not ProofType.PROFESSIONAL_LICENSE:
                raise InvalidProofError("Only licences take a register link.")
            url = _valid_web_url(register_url)
        noun = NOUNS[proof_type]
        # Work samples and letters are often Word documents; credentials are PDFs or photos.
        allow_docx = proof_type in (ProofType.WORK_SAMPLE, *LETTERS)
        kind = detect_file(content_type, data, allow_docx=allow_docx, noun=noun)
        if kind in ("pdf", "docx"):
            stored, stored_type, ext = data, TYPES[kind], kind
        else:
            # Store the re-encoded image: it drops EXIF/GPS metadata and anything appended.
            stored, stored_type, ext = prepare_image(data), "image/jpeg", "jpg"
        key = new_key(f"proofs/{user.id}", ext)
        await storage.save(key, stored, stored_type)
        display_name = safe_filename(filename, f"{noun.replace(' ', '-')}.{ext}")
        upload = UploadInfo(filename=display_name, content_type=stored_type)
        report = ProofReport(upload=upload)
        if proof_type is ProofType.CERTIFICATE:  # older clients read the name from here
            report.certificate = CertificateInfo(filename=display_name, content_type=stored_type)
        proof = await self.proofs.add(
            Proof(
                user_id=user.id,
                type=proof_type,
                url=url,
                file_path=key,
                skills=skills,
                status=ProofStatus.PENDING,
                ai_report=report,
            )
        )
        await _mark_claimed(self.session, user.id, [s.id for s in skills])
        await self.session.commit()
        return await self.get(user, proof.id)

    async def create_certificate(
        self,
        user: User,
        *,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        skill_ids: list[uuid.UUID],
        storage: FileStorage,
    ) -> Proof:
        return await self.create_upload(
            user,
            proof_type=ProofType.CERTIFICATE,
            filename=filename,
            content_type=content_type,
            data=data,
            skill_ids=skill_ids,
            storage=storage,
        )

    async def list(self, user: User) -> list[Proof]:
        return await self.proofs.list_for_user(user.id)

    async def get(self, user: User, proof_id: uuid.UUID) -> Proof:
        proof = await self.proofs.get(proof_id, user.id)
        if proof is None:
            raise ProofNotFoundError
        return proof

    async def file(
        self, user: User, proof_id: uuid.UUID, storage: FileStorage
    ) -> tuple[bytes, str, str]:
        """(bytes, content type, download name) of an uploaded proof file, owner only."""
        proof = await self.get(user, proof_id)
        if not proof.file_path:
            raise ProofNotFoundError
        report = proof.ai_report
        info = (report.upload or report.certificate) if report else None
        content_type = info.content_type if info else "application/octet-stream"
        name = info.filename if info else NOUNS[proof.type]
        try:
            return await storage.read(proof.file_path), content_type, name
        except StorageError as exc:
            raise ProofNotFoundError from exc

    async def reset_for_reanalysis(self, user: User, proof_id: uuid.UUID) -> Proof:
        proof = await self.get(user, proof_id)
        if proof.type is ProofType.REFEREE_CONFIRMATION:
            raise InvalidProofError(
                "A referee confirmation can't be re-run. Send a reminder instead."
            )
        proof.status = ProofStatus.PENDING
        if proof.type is not ProofType.LIVE_LINK:
            await _mark_claimed(self.session, user.id, [s.id for s in proof.skills])
        await self.session.commit()
        return await self.get(user, proof_id)


async def _mark_claimed(
    session: AsyncSession, user_id: uuid.UUID, skill_ids: list[uuid.UUID]
) -> None:
    """Claimed skills show as 'proof being reviewed' (never downgrading a verified skill)."""
    existing = {
        us.skill_id: us
        for us in await session.scalars(
            select(UserSkill).where(UserSkill.user_id == user_id, UserSkill.skill_id.in_(skill_ids))
        )
    }
    for skill_id in skill_ids:
        row = existing.get(skill_id)
        if row is None:
            session.add(
                UserSkill(
                    user_id=user_id,
                    skill_id=skill_id,
                    source=UserSkillSource.SELF_DECLARED,
                    verification_status=VerificationStatus.PENDING,
                )
            )
        elif row.verification_status is not VerificationStatus.VERIFIED:
            row.verification_status = VerificationStatus.PENDING


async def _settle_skills(
    session: AsyncSession, user_id: uuid.UUID, claimed: list[uuid.UUID], verified: set[uuid.UUID]
) -> None:
    """Verified skills become verified (creating the row if the skill was mapped rather than
    claimed, e.g. from a certificate's course); pending claims that weren't verified revert."""
    rows = {
        row.skill_id: row
        for row in await session.scalars(
            select(UserSkill).where(
                UserSkill.user_id == user_id, UserSkill.skill_id.in_(set(claimed) | verified)
            )
        )
    }
    now = datetime.now(UTC)
    for skill_id in verified - rows.keys():
        session.add(
            UserSkill(
                user_id=user_id,
                skill_id=skill_id,
                source=UserSkillSource.VERIFIED_PROOF,
                verification_status=VerificationStatus.VERIFIED,
                verified_at=now,
            )
        )
    for row in rows.values():
        if row.skill_id in verified:
            row.verification_status = VerificationStatus.VERIFIED
            row.source = UserSkillSource.VERIFIED_PROOF
            row.verified_at = now
        elif row.verification_status is VerificationStatus.PENDING:
            row.verification_status = VerificationStatus.UNVERIFIED


def _github_level(status: ProofStatus, report: ProofReport) -> VerificationLevel | None:
    if status is ProofStatus.VERIFIED:
        return "verified"
    if status is ProofStatus.REJECTED:
        return None
    confirmed = report.ownership is not None and report.ownership.status == "confirmed"
    return "partially_verified" if confirmed else "self_reported"


async def _stage(session: AsyncSession, proof: Proof, name: str) -> None:
    await stage(session, proof, name)


async def run_proof_analysis(
    proof_id: uuid.UUID, deps: AnalysisDeps, *, resume_interrupted: bool = False
) -> None:
    """Background job: pending -> analyzing -> verified / needs_more / rejected.

    Always ends in a final status, even if something unexpected goes wrong. A queue worker
    passes resume_interrupted=True so a retry after a crash also picks up a proof that was
    left 'analyzing'; finished proofs are never redone.
    """
    runnable = {ProofStatus.PENDING}
    if resume_interrupted:
        runnable.add(ProofStatus.ANALYZING)
    async with deps.session_factory() as session:
        repo = ProofRepository(session)
        proof = await repo.get(proof_id)
        if proof is None or proof.status not in runnable:
            return
        user = proof.user
        previous = proof.ai_report
        proof.status = ProofStatus.ANALYZING
        await session.commit()

        # Keep what we learned at upload (file name/type); everything else is recomputed.
        upload = previous.upload if previous else None
        if upload is None and previous and previous.certificate:  # uploaded before `upload`
            upload = UploadInfo(
                filename=previous.certificate.filename,
                content_type=previous.certificate.content_type,
            )
        report = ProofReport(
            upload=UploadInfo(filename=upload.filename, content_type=upload.content_type)
            if upload
            else None,
            certificate=CertificateInfo(filename=upload.filename, content_type=upload.content_type)
            if upload and proof.type is ProofType.CERTIFICATE
            else None,
        )
        verified: set[uuid.UUID] = set()
        try:
            if proof.type is ProofType.GITHUB_REPO:
                status, score = await _analyze(
                    session, proof, user, list(proof.skills), deps.github, deps.ai, report
                )
                if status is ProofStatus.VERIFIED:
                    verified = {s.skill_id for s in report.skills if s.verdict == "demonstrated"}
                report.verification_level = _github_level(status, report)
            elif proof.type is ProofType.CERTIFICATE:
                status, score, verified = await _analyze_certificate(
                    session, proof, user, deps, report
                )
            elif proof.type is ProofType.LIVE_LINK:
                status, score = await _analyze_live(session, proof, user, deps, report)
            else:
                analyze = FIELD_ANALYZERS[proof.type]
                status, score, verified = await analyze(session, proof, user, deps, report)
        except RepoNotFoundError as exc:
            status, score = ProofStatus.REJECTED, 0
            report.error = report.decision = str(exc)
        except GitHubError as exc:  # rate limit / outage: not the user's fault
            status, score = ProofStatus.NEEDS_MORE, None
            report.error = str(exc)
            report.decision = f"{exc} Then re-run the analysis."
        except (CertificateFileError, StorageError) as exc:
            status, score = ProofStatus.NEEDS_MORE, None
            report.error = report.decision = str(exc)
        except (InvalidRepoUrlError, ValueError, KeyError) as exc:
            logger.exception("Proof %s: unexpected data", proof_id)
            status, score = ProofStatus.NEEDS_MORE, None
            report.error = f"Analysis failed: {exc}"
            report.decision = "Something went wrong analysing this proof. Try re-running it."
        except Exception:  # never leave a proof stuck in "analyzing"
            logger.exception("Proof %s: analysis crashed", proof_id)
            status, score = ProofStatus.NEEDS_MORE, None
            report.error = "Analysis failed unexpectedly."
            report.decision = "Something went wrong analysing this proof. Try re-running it."

        report.analyzed_at = datetime.now(UTC)
        proof.ai_report = report
        proof.status = status
        proof.progress = None
        proof.score = score
        if proof.type is not ProofType.LIVE_LINK:  # a website alone never verifies skills
            await _settle_skills(session, user.id, [s.id for s in proof.skills], verified)
        await session.commit()
        await notify_proof_update(deps.email, user, proof)


async def _analyze_certificate(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> tuple[ProofStatus, int | None, set[uuid.UUID]]:
    info = report.certificate or CertificateInfo(
        filename="certificate", content_type="application/pdf"
    )
    report.certificate = info
    await _stage(session, proof, "reading")
    data = await deps.storage.read(proof.file_path or "")

    text: str | None = None
    image: bytes | None = None
    if info.content_type == "application/pdf":
        pdf = read_pdf(data)
        text, image = (
            (pdf.text, None) if pdf.first_page_image is None else (None, pdf.first_page_image)
        )
    else:
        image = data  # already re-encoded and downscaled at upload
    info.text_source = "pdf_text" if text else "vision"

    catalog = list(await session.scalars(select(Skill).order_by(Skill.name)))
    try:
        fields = await read_certificate(
            deps.ai, text=text, image=image, skills=[s.name for s in catalog]
        )
        report.ai_status = "ok"
    except AIUnavailableError as exc:
        logger.warning("Proof %s: AI unavailable: %s", proof.id, exc)
        report.ai_status = "unavailable"
        report.decision = "The certificate couldn't be read right now. Re-run the analysis later."
        return ProofStatus.NEEDS_MORE, None, set()
    except AIError as exc:
        logger.warning("Proof %s: certificate read failed: %s", proof.id, exc)
        report.ai_status = "failed"
        report.decision = (
            "The certificate couldn't be read. Try a clearer file or re-run the analysis."
        )
        return ProofStatus.NEEDS_MORE, None, set()

    # With a text layer we can hold the model to the page: IDs and links must appear in it.
    credential_id, verification_url = fields.credential_id, fields.verification_url
    if text is not None:
        credential_id = credential_id if appears_in(credential_id, text) else None
        verification_url = verification_url if url_appears_in(verification_url, text) else None
    await _stage(session, proof, "matching")
    info.is_certificate = fields.is_certificate
    info.issuer, info.recipient_name = fields.issuer, fields.recipient_name
    info.course_name, info.issue_date = fields.course_name, fields.issue_date
    info.credential_id, info.verification_url = credential_id, verification_url
    recipient = fields.recipient_name
    if text is not None and recipient and not appears_in(recipient, text):
        recipient = None  # the name must be on the page, not just in the model's answer
    info.recipient_name = recipient
    info.name_match = match_name(recipient, user.name)

    by_name = {s.name.lower(): s for s in catalog}
    mapped = [by_name[n.lower()] for n in dict.fromkeys(fields.skills) if n.lower() in by_name]
    info.mapped_skills = [s.name for s in mapped]
    claimed_ids = {s.id for s in proof.skills}
    for skill in mapped:
        if skill.id not in claimed_ids:
            proof.skills.append(skill)

    await _stage(session, proof, "checking_link")
    if verification_url and fields.is_certificate:
        info.url_check = await _check_verification_url(
            deps.fetcher,
            verification_url,
            fields.issuer,
            [credential_id, fields.recipient_name, user.name],
        )

    await _stage(session, proof, "writing")
    outcome = decide_certificate(info)
    report.verification_level = outcome.level
    report.decision = outcome.reason
    if outcome.level is None:
        return ProofStatus.REJECTED, 0, set()
    if outcome.level != "verified":
        return ProofStatus.NEEDS_MORE, None, set()
    # A certificate verifies the skills its course covers: the claimed ones, or all mapped
    # ones if the user didn't pick any.
    mapped_ids = {s.id for s in mapped}
    verified = (mapped_ids & claimed_ids) if claimed_ids else mapped_ids
    if not verified:
        report.decision += (
            " Its course doesn't clearly cover the skills you picked, so none were verified."
        )
    return ProofStatus.VERIFIED, None, verified


async def _check_verification_url(
    fetcher: Fetcher, url: str, issuer: str | None, needles: list[str | None]
) -> UrlCheck:
    return await check_link(
        fetcher, url, trust=lambda final: trusted_host(final, issuer), needles=needles
    )


async def _analyze_live(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> tuple[ProofStatus, int | None]:
    info = LiveLinkInfo(url=proof.url or "")
    report.live = info
    linked = (
        await ProofRepository(session).get(proof.linked_proof_id, user.id)
        if proof.linked_proof_id
        else None
    )
    if linked is not None:
        repo_facts = linked.ai_report.repo if linked.ai_report else None
        info.linked_repo = (
            repo_facts.full_name
            if repo_facts
            else (linked.url or "").removeprefix("https://github.com/")
        )
        info.linked_repo_verified = linked.status is ProofStatus.VERIFIED
    else:
        repo_facts = None

    await _stage(session, proof, "fetching")
    try:
        result = await deps.fetcher.fetch(info.url)
    except BlockedUrlError as exc:
        report.decision = str(exc)
        return ProofStatus.REJECTED, None
    except FetchFailedError as exc:
        report.decision = f"{exc} Check the site is up, then re-run the analysis."
        return ProofStatus.NEEDS_MORE, None

    info.final_url, info.status_code = result.final_url, result.status_code
    info.reachable = result.status_code < 400
    info.https = result.final_url.startswith("https://")
    info.response_ms = result.elapsed_ms
    await _stage(session, proof, "linking")
    if info.reachable:
        page = parse_page(result.text)
        info.title, info.description, info.site_name = page.title, page.description, page.site_name
        info.connection = find_connection(result.final_url, page, repo_facts)
    else:
        report.decision = f"The site returned HTTP {result.status_code}."
        return ProofStatus.NEEDS_MORE, None

    await _stage(session, proof, "writing")
    outcome = decide_live(info)
    report.verification_level = outcome.level
    report.decision = outcome.reason
    if not info.https:
        report.suggestions.append(
            "Serve the site over HTTPS; browsers warn visitors about plain HTTP."
        )
    return (ProofStatus.VERIFIED if outcome.level == "verified" else ProofStatus.NEEDS_MORE), None


async def _analyze(
    session: AsyncSession,
    proof: Proof,
    user: User,
    claimed: list[Skill],
    github: GitHubAPI,
    ai: AIClient,
    report: ProofReport,
) -> tuple[ProofStatus, int | None]:
    ref = parse_repo_url(proof.url or "")
    await _stage(session, proof, "fetching")
    collected = await collect(github, ref)
    await _stage(session, proof, "commits")
    report.repo = collected.facts
    report.ownership = check_ownership(collected.facts, collected.owner_login, user.github_username)
    report.checks = run_checks(collected.facts, report.ownership)
    injected = find_injection(
        {
            "the README": collected.readme,
            "the description": collected.facts.description,
            "commit messages": "\n".join(
                c.get("commit", {}).get("message", "") for c in collected.recent_commits
            ),
        },
        {**collected.config_files, **collected.source_files},
    )
    if injected:
        # A gate: the AI may be fooled, but the outcome can't be.
        report.checks.append(
            ProofCheck(
                id="no_reviewer_instructions",
                status="fail",
                title="No instructions aimed at the reviewer",
                detail=(
                    f"Found text that tries to instruct the AI reviewer in {', '.join(injected)}. "
                    "Remove it and re-run the analysis."
                ),
            )
        )

    if reason := hard_rejection(collected.facts, report.checks):
        report.decision = reason
        report.skills = [
            SkillVerdict(skill_id=s.id, name=s.name, verdict="not_demonstrated", evidence=[])
            for s in claimed
        ]
        return ProofStatus.REJECTED, 0

    # The role the review should judge against: from the most recently edited resume.
    role_name = await session.scalar(
        select(TargetRole.name)
        .join(Resume, Resume.target_role_id == TargetRole.id)
        .where(Resume.user_id == user.id)
        .order_by(Resume.updated_at.desc())
        .limit(1)
    )

    try:
        await _stage(session, proof, "reviewing")
        review = await review_repo(
            ai, collected=collected, skills=[s.name for s in claimed], target_role=role_name
        )
        report.ai_status = "ok"
    except AIUnavailableError as exc:
        logger.warning("Proof %s: AI unavailable: %s", proof.id, exc)
        report.ai_status = "unavailable"
        review = None
    except AIError as exc:
        logger.warning("Proof %s: AI review failed: %s", proof.id, exc)
        report.ai_status = "failed"
        review = None

    if review is not None:
        by_name = {r.skill.strip().lower(): r for r in review.skills}
        report.skills = [
            SkillVerdict(
                skill_id=s.id,
                name=s.name,
                verdict=by_name[s.name.lower()].verdict
                if s.name.lower() in by_name
                else "not_demonstrated",
                evidence=by_name[s.name.lower()].evidence if s.name.lower() in by_name else [],
            )
            for s in claimed  # only claimed skills; anything else the model mentions is ignored
        ]
        report.summary = review.summary
        report.strengths = review.strengths
        report.code_quality = review.code_quality
        report.red_flags = review.red_flags
        report.suggestions = review.suggestions
        report.ai_score = review.score

    await _stage(session, proof, "writing")
    outcome = decide(report.checks, report.skills, report.ai_score)
    report.decision = outcome.reason
    status = {
        "verified": ProofStatus.VERIFIED,
        "needs_more": ProofStatus.NEEDS_MORE,
        "rejected": ProofStatus.REJECTED,
    }[outcome.status]
    return status, report.ai_score