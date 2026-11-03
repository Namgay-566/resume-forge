"""Analysis of proof for every profession: licences, portfolios, work samples, publications
and reference/experience letters. Each returns (status, score, skill ids now verified).

The AI reads documents and reviews work as a professional in the candidate's field; the
verification level comes only from what we could check ourselves (see evidence.py)."""

import logging
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.document_reader import read_letter, read_license
from app.ai.errors import AIError, AIUnavailableError
from app.ai.evidence_review import EvidenceKind, EvidenceReview, review_evidence
from app.ai.safety import find_injection
from app.models import Proof, Skill, User
from app.models.enums import ProofStatus
from app.schemas.proof_report import (
    LetterInfo,
    LicenseInfo,
    MentionedSkill,
    PortfolioInfo,
    ProofReport,
    PublicationInfo,
    SkillVerdict,
    UploadInfo,
    WorkSampleInfo,
)
from app.services.proofs.certificates import (
    appears_in,
    match_name,
    trusted_register,
    url_appears_in,
)
from app.services.proofs.evidence import (
    Outcome,
    best_author_match,
    check_expiry,
    decide_letter,
    decide_license,
    decide_portfolio,
    decide_publication,
    decide_work_sample,
    parse_doi,
    portfolio_platform,
)
from app.services.proofs.pipeline import (
    AnalysisDeps,
    ReviewContext,
    check_link,
    read_upload,
    review_context,
    stage,
)
from app.services.proofs.publications import lookup_doi, page_publication
from app.services.web.fetch import BlockedUrlError, FetchFailedError, parse_page

logger = logging.getLogger(__name__)
Result = tuple[ProofStatus, int | None, set[uuid.UUID]]
MAX_PAGE_CHARS = 20_000


def _upload(report: ProofReport) -> UploadInfo:
    report.upload = report.upload or UploadInfo(filename="upload", content_type="application/pdf")
    return report.upload


async def _catalog(session: AsyncSession) -> list[Skill]:
    return list(await session.scalars(select(Skill).order_by(Skill.name)))


def _map_names(names: list[str], catalog: list[Skill]) -> list[Skill]:
    by_name = {s.name.lower(): s for s in catalog}
    return [by_name[n.lower()] for n in dict.fromkeys(names) if n.lower() in by_name]


def _attach(proof: Proof, skills: list[Skill]) -> None:
    have = {s.id for s in proof.skills}
    proof.skills.extend(s for s in skills if s.id not in have)


def _final(outcome: Outcome, report: ProofReport) -> ProofStatus:
    report.verification_level = outcome.level
    report.decision = outcome.reason
    if outcome.rejected:
        return ProofStatus.REJECTED
    return ProofStatus.VERIFIED if outcome.level == "verified" else ProofStatus.NEEDS_MORE


def _ai_failed(report: ProofReport, exc: AIError, what: str) -> None:
    unavailable = isinstance(exc, AIUnavailableError)
    report.ai_status = "unavailable" if unavailable else "failed"
    report.decision = (
        f"The {what} couldn't be read right now. Re-run the analysis later."
        if unavailable
        else f"The {what} couldn't be read. Try a clearer file or re-run the analysis."
    )


async def _review(
    deps: AnalysisDeps,
    report: ProofReport,
    context: ReviewContext,
    *,
    kind: EvidenceKind,
    claimed: list[Skill],
    text: str | None,
    image: bytes | None = None,
    details: dict[str, str] | None = None,
) -> EvidenceReview | None:
    """Field-expert review. Fills the report; None if the AI couldn't run."""
    report.reviewer = context.persona
    try:
        review = await review_evidence(
            deps.ai,
            kind=kind,
            skills=[s.name for s in claimed],
            persona=context.persona,
            context=context.candidate,
            text=text,
            image=image,
            details=details,
        )
    except AIError as exc:
        logger.warning("Evidence review (%s) failed: %s", kind, exc)
        report.ai_status = "unavailable" if isinstance(exc, AIUnavailableError) else "failed"
        return None
    report.ai_status = "ok"
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
    report.red_flags = review.red_flags
    report.suggestions = review.suggestions
    report.ai_score = review.score
    return review


# --- professional licences ------------------------------------------------------------------


async def analyze_license(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> Result:
    await stage(session, proof, "reading")
    content = await read_upload(deps.storage, proof, _upload(report))
    catalog = await _catalog(session)
    try:
        fields = await read_license(
            deps.ai, text=content.text, image=content.image, skills=[s.name for s in catalog]
        )
        report.ai_status = "ok"
    except AIError as exc:
        _ai_failed(report, exc, "licence")
        return ProofStatus.NEEDS_MORE, None, set()

    await stage(session, proof, "matching")
    text = content.text
    # With a text layer, hold the model to the page: numbers, names and links must be on it.
    number, holder, printed_url = fields.license_number, fields.holder_name, fields.register_url
    if text is not None:
        number = number if appears_in(number, text) else None
        holder = holder if appears_in(holder, text) else None
        printed_url = printed_url if url_appears_in(printed_url, text) else None
    info = LicenseInfo(
        is_license=fields.is_license,
        license_type=fields.license_type,
        holder_name=holder,
        license_number=number,
        issuing_body=fields.issuing_body,
        jurisdiction=fields.jurisdiction,
        issue_date=fields.issue_date,
        expiry_date=fields.expiry_date,
        register_url=proof.url or printed_url,
        register_source="user" if proof.url else ("document" if printed_url else None),
    )
    report.license = info
    info.name_match = match_name(holder, user.name, document="licence")
    check_expiry(info, date.today())
    mapped = _map_names(fields.skills, catalog)
    info.mapped_skills = [s.name for s in mapped]
    claimed_ids = {s.id for s in proof.skills}
    _attach(proof, mapped)

    await stage(session, proof, "checking_register")
    if info.register_url and info.is_license and not info.expired:
        body = info.issuing_body
        info.register_check = await check_link(
            deps.fetcher,
            info.register_url,
            trust=lambda url: trusted_register(url, body),
            needles=[number, holder],
        )

    await stage(session, proof, "writing")
    status = _final(decide_license(info), report)
    if info.expires_soon:
        report.suggestions.append(info.expiry_detail)
    if status is not ProofStatus.VERIFIED:
        return status, None, set()
    mapped_ids = {s.id for s in mapped}
    # The licence verifies what it covers: the claimed skills it maps to, or all mapped ones.
    verified = (
        (mapped_ids & claimed_ids) if claimed_ids and mapped_ids & claimed_ids else mapped_ids
    )
    return status, None, verified


# --- portfolios ------------------------------------------------------------------------------


async def analyze_portfolio(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> Result:
    info = PortfolioInfo(url=proof.url or "", platform=portfolio_platform(proof.url or ""))
    report.portfolio = info
    await stage(session, proof, "fetching")
    try:
        result = await deps.fetcher.fetch(info.url)
    except BlockedUrlError as exc:
        report.decision = str(exc)
        return ProofStatus.REJECTED, None, set()
    except FetchFailedError as exc:
        report.decision = f"{exc} Check the page is public, then re-run the analysis."
        return ProofStatus.NEEDS_MORE, None, set()
    info.final_url, info.status_code = result.final_url, result.status_code
    info.reachable = result.status_code < 400
    info.https = result.final_url.startswith("https://")
    if not info.reachable:
        return _final(decide_portfolio(info, [], False, False), report), None, set()

    page = parse_page(result.text)
    info.title, info.description, info.site_name = page.title, page.description, page.site_name
    info.name_on_page = appears_in(user.name, f"{page.title} {page.description} {page.text}")
    body = page.text[:MAX_PAGE_CHARS]
    info.text_chars = len(body)
    injected = bool(find_injection({"the page": f"{page.title}\n{page.description}\n{body}"}))

    await stage(session, proof, "reviewing")
    review = None
    if not injected:
        review = await _review(
            deps,
            report,
            await review_context(session, user),
            kind="portfolio",
            claimed=list(proof.skills),
            text=body or page.description or page.title,
            details={
                "Page title": page.title,
                "Site": info.platform or page.site_name or info.final_url or info.url,
            },
        )
    if len(body) < 200:
        report.suggestions.append(
            "The page has little readable text (sites built with heavy scripts often don't). "
            "Add short captions describing each piece and your role in it."
        )
    await stage(session, proof, "writing")
    outcome = decide_portfolio(info, report.skills, review is not None, injected)
    return _final(outcome, report), report.ai_score, set()  # a public page never verifies


# --- work samples ------------------------------------------------------------------------------


async def analyze_work_sample(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> Result:
    await stage(session, proof, "reading")
    upload = _upload(report)
    content = await read_upload(deps.storage, proof, upload)
    if content.text and find_injection({"the document": content.text}):
        report.work_sample = WorkSampleInfo(text_chars=len(content.text))
        report.verification_level = "self_reported"
        report.decision = (
            "The document contains text aimed at the AI reviewer, so it can't be reviewed. "
            "Remove it and upload the file again."
        )
        return ProofStatus.NEEDS_MORE, None, set()

    await stage(session, proof, "reviewing")
    review = await _review(
        deps,
        report,
        await review_context(session, user),
        kind="work_sample",
        claimed=list(proof.skills),
        text=content.text,
        image=content.image,
        details={"File": upload.filename},
    )
    if review is None:
        report.decision = "The work sample couldn't be reviewed right now. Re-run it later."
        return ProofStatus.NEEDS_MORE, None, set()
    info = WorkSampleInfo(
        is_work_sample=review.is_relevant,
        kind=review.kind or None,
        text_chars=len(content.text or ""),
    )
    report.work_sample = info
    await stage(session, proof, "writing")
    status = _final(decide_work_sample(info, report.skills), report)
    return status, report.ai_score if status is not ProofStatus.REJECTED else 0, set()


# --- publications ---------------------------------------------------------------------------------


async def analyze_publication(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> Result:
    raw = proof.url or ""
    doi = parse_doi(raw)
    info = PublicationInfo(input=raw, doi=doi, url=f"https://doi.org/{doi}" if doi else raw)
    report.publication = info
    await stage(session, proof, "resolving")
    page_text = ""
    try:
        if doi:
            meta = await lookup_doi(deps.fetcher, doi)
            if meta is not None:
                info.source, info.registered = "crossref", True
        else:
            result = await deps.fetcher.fetch(raw)
            if result.status_code >= 400:
                report.decision = f"The page returned HTTP {result.status_code}."
                return ProofStatus.NEEDS_MORE, None, set()
            meta, page_text = page_publication(result.text)
            info.url, info.source = result.final_url, "page"
    except BlockedUrlError as exc:
        report.decision = str(exc)
        return ProofStatus.REJECTED, None, set()
    except FetchFailedError as exc:
        report.decision = f"{exc} Re-run the analysis in a few minutes."
        return ProofStatus.NEEDS_MORE, None, set()
    if meta is None:  # a DOI the registry doesn't know
        return _final(decide_publication(info, []), report), None, set()

    info.title, info.venue, info.published = meta.title, meta.venue, meta.published
    info.authors = meta.authors
    await stage(session, proof, "matching")
    info.author_match, info.matched_author = best_author_match(meta.authors, user.name)
    if info.author_match.status in ("mismatch", "missing"):
        return _final(decide_publication(info, []), report), None, set()

    await stage(session, proof, "reviewing")
    excerpt = meta.abstract or page_text[:MAX_PAGE_CHARS]
    review = await _review(
        deps,
        report,
        await review_context(session, user),
        kind="publication",
        claimed=list(proof.skills),
        text=excerpt or None,
        details={
            k: v
            for k, v in {
                "Title": meta.title,
                "Published in": meta.venue,
                "Date": meta.published,
                "Authors": ", ".join(meta.authors[:10]),
            }.items()
            if v
        },
    )
    await stage(session, proof, "writing")
    outcome = decide_publication(info, report.skills)
    status = _final(outcome, report)
    if review is None:
        report.decision += " The skills couldn't be assessed right now; re-run the analysis."
        return ProofStatus.NEEDS_MORE, None, set()
    if status is not ProofStatus.VERIFIED:
        return status, report.ai_score, set()
    verified = {s.skill_id for s in report.skills if s.verdict == "demonstrated"}
    if not verified:
        report.decision += " It doesn't clearly show the skills you picked, so none were verified."
    return status, report.ai_score, verified


# --- reference and experience letters -----------------------------------------------------------


async def analyze_letter(
    session: AsyncSession, proof: Proof, user: User, deps: AnalysisDeps, report: ProofReport
) -> Result:
    await stage(session, proof, "reading")
    content = await read_upload(deps.storage, proof, _upload(report))
    catalog = await _catalog(session)
    try:
        fields = await read_letter(
            deps.ai, text=content.text, image=content.image, skills=[s.name for s in catalog]
        )
        report.ai_status = "ok"
    except AIError as exc:
        _ai_failed(report, exc, "letter")
        return ProofStatus.NEEDS_MORE, None, set()

    await stage(session, proof, "matching")
    text = content.text
    subject = fields.subject_name
    if text is not None and subject and not appears_in(subject, text):
        subject = None  # the name must be in the letter, not just in the model's answer
    mentioned = [
        m
        for m in fields.skills
        # Quotes must be the letter's own words when we have its text.
        if text is None or appears_in(m.quote[:60], text)
    ]
    mapped = _map_names([m.skill for m in mentioned], catalog)
    quotes = {m.skill.lower(): m.quote for m in mentioned}
    info = LetterInfo(
        is_letter=fields.is_letter,
        letter_kind=fields.letter_kind,
        writer_name=fields.writer_name,
        writer_title=fields.writer_title,
        organization=fields.organization,
        date=fields.date,
        subject_name=subject,
        relationship=fields.relationship,
        has_contact_details=fields.has_contact_details,
        name_match=match_name(subject, user.name, document="letter", relation="is about"),
        skills_mentioned=[
            MentionedSkill(name=s.name, quote=quotes[s.name.lower()]) for s in mapped
        ],
    )
    report.letter = info
    _attach(proof, mapped)  # linked as evidence; letters never verify a skill
    await stage(session, proof, "writing")
    return _final(decide_letter(info), report), None, set()
