"""Shared pieces of the proof analysis pipeline: dependencies, progress stages, the review
context (role, field, reviewer persona), reading uploads and checking links."""

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.client import AIClient
from app.ai.context import CandidateContext
from app.models import Industry, Proof, Resume, TargetRole, User
from app.models.enums import ProofType
from app.schemas.proof_report import UploadInfo, UrlCheck
from app.services.email.sender import EmailSender, get_email_sender
from app.services.github.client import GitHubAPI
from app.services.proofs.certificates import appears_in, read_docx, read_pdf
from app.services.storage.files import FileStorage
from app.services.web.fetch import (
    BlockedUrlError,
    Fetcher,
    FetchFailedError,
    normalize_url,
    parse_page,
)


@dataclass(frozen=True)
class AnalysisDeps:
    session_factory: async_sessionmaker[AsyncSession]
    github: GitHubAPI
    ai: AIClient
    storage: FileStorage
    fetcher: Fetcher
    # Tells the user the result, if they want proof emails (Settings).
    email: EmailSender = field(default_factory=get_email_sender)


# The real steps of each analysis, shown to the user as a stepper while it runs.
STAGES: dict[ProofType, tuple[str, ...]] = {
    ProofType.GITHUB_REPO: ("fetching", "commits", "reviewing", "writing"),
    ProofType.CERTIFICATE: ("reading", "matching", "checking_link", "writing"),
    ProofType.LIVE_LINK: ("fetching", "linking", "writing"),
    ProofType.PROFESSIONAL_LICENSE: ("reading", "matching", "checking_register", "writing"),
    ProofType.PORTFOLIO_LINK: ("fetching", "reviewing", "writing"),
    ProofType.WORK_SAMPLE: ("reading", "reviewing", "writing"),
    ProofType.PUBLICATION: ("resolving", "matching", "reviewing", "writing"),
    ProofType.REFERENCE_LETTER: ("reading", "matching", "writing"),
    ProofType.EXPERIENCE_LETTER: ("reading", "matching", "writing"),
}


async def stage(session: AsyncSession, proof: Proof, name: str) -> None:
    """Record (and commit) the step a running analysis has reached, for the progress UI."""
    assert name in STAGES[proof.type]
    proof.progress = name
    await session.commit()


@dataclass(frozen=True)
class ReviewContext:
    role: str | None
    industry: str | None
    persona: str | None
    experience_level: str | None = None
    impact_language: str | None = None

    @property
    def candidate(self) -> CandidateContext:
        return CandidateContext(
            target_role=self.role,
            industry=self.industry,
            experience_level=self.experience_level,
            impact_language=self.impact_language,
        )


async def review_context(session: AsyncSession, user: User) -> ReviewContext:
    """Who the review is for: the target role of the most recently edited resume, its field,
    and that field's reviewer persona (a senior nurse, a marketing director...)."""
    row = (
        await session.execute(
            select(
                TargetRole.name,
                Industry.name,
                Industry.reviewer_persona,
                Resume.experience_level,
                Industry.impact_language,
            )
            .join(Resume, Resume.target_role_id == TargetRole.id)
            .join(Industry, Industry.id == TargetRole.industry_id)
            .where(Resume.user_id == user.id)
            .order_by(Resume.updated_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return ReviewContext(None, None, None)
    return ReviewContext(
        role=row[0],
        industry=row[1],
        persona=row[2] or None,
        experience_level=row[3].value if row[3] else None,
        impact_language=row[4] or None,
    )


MAX_REVIEW_CHARS = 30_000  # bounds every prompt built from an uploaded document
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class UploadContent:
    text: str | None  # set when the file has a text layer
    image: bytes | None  # set otherwise (photos, scans), already downscaled


async def read_upload(storage: FileStorage, proof: Proof, upload: UploadInfo) -> UploadContent:
    data = await storage.read(proof.file_path or "")
    if upload.content_type == "application/pdf":
        pdf = read_pdf(data, pages=10)
        if pdf.first_page_image is None:
            upload.text_source = "pdf_text"
            return UploadContent(pdf.text[:MAX_REVIEW_CHARS], None)
        upload.text_source = "vision"
        return UploadContent(None, pdf.first_page_image)
    if upload.content_type == DOCX_TYPE:
        upload.text_source = "docx_text"
        return UploadContent(read_docx(data)[:MAX_REVIEW_CHARS], None)
    upload.text_source = "vision"
    return UploadContent(None, data)  # images were re-encoded and downscaled at upload


async def check_link(
    fetcher: Fetcher, url: str, *, trust: Callable[[str], bool], needles: list[str | None]
) -> UrlCheck:
    """Fetch a verification or register link: is it up, is it on a trusted site, and does
    it show any of the `needles` (a credential or licence number, a name)?"""
    check = UrlCheck(url=normalize_url(url))
    try:
        result = await fetcher.fetch(check.url)
    except (BlockedUrlError, FetchFailedError) as exc:
        check.detail = str(exc)
        return check
    check.final_url, check.status_code = result.final_url, result.status_code
    check.reachable = result.status_code < 400
    if not check.reachable:
        check.detail = f"The page returned HTTP {result.status_code}."
        return check
    check.on_trusted_domain = trust(result.final_url)
    page = parse_page(result.text)
    haystack = f"{page.title} {page.description} {page.text}"
    check.details_on_page = any(appears_in(n, haystack) for n in needles if n)
    check.detail = "Reachable" + (
        " on a trusted domain" if check.on_trusted_domain else " but not on a trusted domain"
    )
    return check
