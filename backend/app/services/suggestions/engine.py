"""Turn verified proofs into resume suggestions. Pure: resume data + proofs + skills in,
suggestions out. Nothing is changed here; the editor applies what the user accepts."""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.models.enums import ProofStatus, ProofType
from app.schemas.proof_report import ProofReport
from app.schemas.resume_data import (
    CertificationItem,
    ProjectItem,
    ResumeData,
    SectionConfig,
    SectionItem,
)
from app.schemas.section_kind import SectionKind
from app.schemas.suggestions import BulletTarget, ProofLink, ResumeSuggestion
from app.services.ats.keywords import normalize
from app.services.proofs.methods import method_label
from app.services.resume_import.matching import term_variants
from app.services.sections.catalog import get_catalog

_YM = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])")


@dataclass(frozen=True)
class ProofView:
    id: uuid.UUID
    type: ProofType
    status: ProofStatus
    url: str | None
    report: ProofReport | None
    skill_ids: frozenset[uuid.UUID]
    created_order: int  # higher = newer


@dataclass(frozen=True)
class SkillView:
    id: uuid.UUID
    name: str
    aliases: frozenset[str]  # normalised, includes the name


def display_url(url: str | None) -> str | None:
    if not url:
        return None
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", url.strip(), flags=re.IGNORECASE).rstrip("/")


def proof_link(proof: ProofView) -> ProofLink:
    report = proof.report
    url = proof.url
    if proof.type is ProofType.CERTIFICATE:
        cert = report.certificate if report else None
        url = cert.verification_url if cert else None
    elif proof.type is ProofType.PROFESSIONAL_LICENSE:
        licence = report.license if report else None
        check = licence.register_check if licence else None
        # Cite the register entry only if it actually loaded.
        url = check.url if check and check.reachable else None
    elif proof.type is ProofType.PUBLICATION:
        publication = report.publication if report else None
        url = publication.url if publication else url
    elif proof.type.is_upload:
        url = None  # work samples and letters are private files, never printed
    level = report.verification_level if report else None
    return ProofLink(
        proof_id=proof.id,
        type=proof.type,
        url=url,
        display_url=display_url(url),
        verified=proof.status is ProofStatus.VERIFIED,
        level=level,
        method=method_label(proof.type, level, report),
    )


def _on_resume(skill: SkillView, data: ResumeData) -> int | None:
    """Index of the resume skill entry for this catalog skill, alias-aware."""
    for i, entry in enumerate(data.skills):
        if entry.skill_id == skill.id:
            return i
        if any(normalize(v) in skill.aliases for v in term_variants(entry.name)):
            return i
    return None


def _year_month(value: str | None) -> str | None:
    match = _YM.match(value or "")
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    year = re.match(r"^(\d{4})\b", value or "")
    return f"{year.group(1)}-01" if year else None


def _section(data: ResumeData, kind: SectionKind) -> SectionConfig | None:
    return next((s for s in data.sections if s.kind is kind), None)


def _already_listed(section: SectionConfig | None, proof_id: uuid.UUID, *keys: str | None) -> bool:
    """The proof, its link or its title is already in this section."""
    if section is None:
        return False

    def key(text: str | None) -> str:
        return normalize(text or "").rstrip(" .")

    wanted = {key(k) for k in keys if k}
    for entry in section.entries:
        if entry.proof_id == proof_id:
            return True
        found = {key(display_url(entry.link)), key(entry.title)} - {""}
        if found & wanted:
            return True
    return False


def _entry_suggestion(
    proof: ProofView, kind: SectionKind, entry: SectionItem, title: str, detail: str
) -> ResumeSuggestion:
    return ResumeSuggestion(
        id=f"entry:{proof.id}",
        kind="add_section_entry",
        proof_id=proof.id,
        level=proof.report.verification_level if proof.report else None,
        title=title,
        detail=detail,
        section_kind=kind,
        section_heading=get_catalog().heading(kind),
        entry=entry,
    )


def _publication(proof: ProofView, data: ResumeData) -> ResumeSuggestion | None:
    info = proof.report.publication if proof.report else None
    if info is None or not info.title:
        return None
    link = proof_link(proof).display_url
    if _already_listed(_section(data, SectionKind.PUBLICATIONS), proof.id, info.title, link):
        return None
    authors = ", ".join(info.authors[:12])
    entry = SectionItem(
        title=info.title[:200],
        organization=(info.venue or "")[:200],
        start_date=_year_month(info.published),
        description=authors[:1000],
        link=(link or None) and link[:200],
        proof_id=proof.id,
    )
    return _entry_suggestion(
        proof,
        SectionKind.PUBLICATIONS,
        entry,
        f"Add “{info.title[:80]}” to Publications?",
        "Verified publication. The DOI or link is printed as plain text." if link else "",
    )


def _portfolio(proof: ProofView, data: ResumeData) -> ResumeSuggestion | None:
    info = proof.report.portfolio if proof.report else None
    link = display_url((info.final_url or info.url) if info else proof.url)
    if not link:
        return None
    name = (info.title if info else "") or (info.site_name if info else "") or link
    if _already_listed(_section(data, SectionKind.PORTFOLIO), proof.id, name, link):
        return None
    entry = SectionItem(
        title=name[:200],
        description=(info.description if info else "")[:1000],
        link=link[:200],
        proof_id=proof.id,
    )
    return _entry_suggestion(
        proof,
        SectionKind.PORTFOLIO,
        entry,
        f"Add “{name[:80]}” to Portfolio?",
        "Verified portfolio piece. The link is printed as plain text.",
    )


_WORD = re.compile(r"[a-z][a-z0-9+#]{3,}")
_COMMON = frozenset(
    "with from that this their them have were work working worked team using used also "
    "into over under about each other more most very well good".split()
)


def _words(*texts: str) -> set[str]:
    """Word stems (first five letters), so "patients" meets "patient" and "assessed" meets
    "assessment". Crude, but enough to tell a nursing job from a shop job."""
    return {w[:5] for t in texts for w in _WORD.findall(t.lower()) if w not in _COMMON}


def _best_experience(data: ResumeData, wanted: set[str]) -> BulletTarget | None:
    """The job-like entry (Experience, or a section that counts as experience such as
    Clinical or Teaching Experience) sharing the most words with the work sample."""
    catalog = get_catalog()
    candidates: list[tuple[int, int, BulletTarget]] = []
    for i, job in enumerate(data.experience):
        text = _words(job.title, job.company, *job.bullets, *job.tools_and_skills)
        label = " at ".join(p for p in (job.title, job.company) if p)
        candidates.append(
            (
                len(text & wanted),
                -i,
                BulletTarget(
                    section_id="experience", item_index=i, item_title=job.title, label=label
                ),
            )
        )
    for section in data.sections:
        if section.kind.is_core or not catalog.spec(section.kind).counts_as_experience:
            continue
        for i, item in enumerate(section.entries):
            text = _words(*item.text_parts())
            label = " at ".join(p for p in (item.title, item.organization) if p)
            candidates.append(
                (
                    len(text & wanted),
                    -i,
                    BulletTarget(
                        section_id=section.id, item_index=i, item_title=item.title, label=label
                    ),
                )
            )
    best = max(candidates, key=lambda c: (c[0], c[1]), default=None)
    # Two shared words at least (a role, a ward, a subject...), or it's a guess.
    return best[2] if best and best[0] >= 2 else None


def _work_sample(
    proof: ProofView, data: ResumeData, skills: dict[uuid.UUID, str]
) -> ResumeSuggestion | None:
    report = proof.report
    info = report.work_sample if report else None
    if report is None or info is None or not info.kind:
        return None
    if any(p.proof_id == proof.id for p in data.projects):
        return None
    shown = [v.name for v in report.skills if v.verdict == "demonstrated"]
    shown = shown or [skills[i] for i in proof.skill_ids if i in skills]
    kind = info.kind.strip().rstrip(".")
    showing = " and ".join(filter(None, [", ".join(shown[:-1]), shown[-1] if shown else ""]))
    bullet = f"Produced {kind}" + (f", demonstrating {showing.lower()}" if showing else "")
    bullet = bullet[:500]
    existing = {normalize(b) for e in data.experience for b in e.bullets}
    existing |= {normalize(b) for s in data.sections for e in s.entries for b in e.bullets}
    existing |= {normalize(b) for p in data.projects for b in p.bullets}
    if normalize(bullet) in existing:
        return None
    level = report.verification_level
    private = "Work samples are private files, so no link is printed; describe it instead."
    upload = report.upload.filename if report.upload else ""
    target = _best_experience(data, _words(kind, upload, *shown, report.summary))
    if target is not None:
        return ResumeSuggestion(
            id=f"bullet:{proof.id}",
            kind="add_bullet",
            proof_id=proof.id,
            level=level,
            title=f"Add your verified {kind.removeprefix('a ').removeprefix('an ')} "
            f"to “{target.label or target.item_title}”?",
            detail=f"Adds a bullet you can edit. {private}",
            bullet=bullet,
            target=target,
        )
    name = kind.removeprefix("a ").removeprefix("an ").removeprefix("the ")
    return ResumeSuggestion(
        id=f"project:{proof.id}",
        kind="add_project",
        proof_id=proof.id,
        level=level,
        title=f"Add your verified {name} to Projects?",
        detail=f"None of your jobs mention it, so it fits Projects. {private}",
        project=ProjectItem(
            name=name[:1].upper() + name[1:200],
            bullets=[bullet],
            tools_and_skills=shown[:30],
            proof_id=proof.id,
        ),
    )


def suggest(
    data: ResumeData,
    proofs: Iterable[ProofView],
    verified_skills: Iterable[SkillView],
    dismissed: Iterable[str] = (),
) -> list[ResumeSuggestion]:
    proofs = sorted(proofs, key=lambda p: -p.created_order)
    verified_skills = list(verified_skills)
    verified_proofs = [p for p in proofs if p.status is ProofStatus.VERIFIED]
    verified_proof_ids = {p.id for p in verified_proofs}
    out: list[ResumeSuggestion] = []

    for skill in verified_skills:
        source = next((p for p in verified_proofs if skill.id in p.skill_ids), None)
        if source is None:
            continue
        index = _on_resume(skill, data)
        if index is None:
            out.append(
                ResumeSuggestion(
                    id=f"skill:{skill.id}",
                    kind="add_skill",
                    proof_id=source.id,
                    skill_id=skill.id,
                    skill_name=skill.name,
                    level="verified",
                    title=f"{skill.name} is now verified. Add it to Skills?",
                    detail="It's backed by a verified proof, so it's worth listing.",
                )
            )
        elif data.skills[index].proof_id not in verified_proof_ids:
            out.append(
                ResumeSuggestion(
                    id=f"skill:{skill.id}",
                    kind="link_skill_proof",
                    proof_id=source.id,
                    skill_id=skill.id,
                    skill_name=skill.name,
                    skill_index=index,
                    resume_skill_name=data.skills[index].name,
                    level="verified",
                    title=f"{skill.name} is verified. Link the proof?",
                    detail="Links your Skills entry to its proof, for the Verified skills line.",
                )
            )

    project_links = " ".join((p.link or "") for p in data.projects).lower()
    project_proofs = {p.proof_id for p in data.projects}
    for proof in verified_proofs:
        if proof.type is not ProofType.GITHUB_REPO or proof.id in project_proofs:
            continue
        repo = (
            proof.report.repo.full_name
            if proof.report and proof.report.repo
            else display_url(proof.url) or ""
        )
        if repo and repo.lower().removeprefix("github.com/") in project_links:
            continue
        out.append(
            ResumeSuggestion(
                id=f"project:{proof.id}",
                kind="add_project",
                proof_id=proof.id,
                repo_url=proof.url,
                level="verified",
                title="Add this project to your resume?",
                detail=f"{repo} is verified. We can draft a project entry you can edit first.",
            )
        )

    # Publications -> Publications, portfolio pieces -> Portfolio, work samples -> the job
    # they fit (or Projects).
    skill_names = {s.id: s.name for s in verified_skills}
    for proof in verified_proofs:
        found = None
        if proof.type is ProofType.PUBLICATION:
            found = _publication(proof, data)
        elif proof.type is ProofType.PORTFOLIO_LINK:
            found = _portfolio(proof, data)
        elif proof.type is ProofType.WORK_SAMPLE:
            found = _work_sample(proof, data, skill_names)
        if found:
            out.append(found)

    cert_proofs = {c.proof_id for c in data.certifications}
    cert_names = {normalize(c.name) for c in data.certifications}
    cert_ids = {normalize(c.credential_id) for c in data.certifications if c.credential_id}
    for proof in proofs:
        cert = proof.report.certificate if proof.report else None
        if (
            proof.type is not ProofType.CERTIFICATE
            or cert is None
            or not cert.course_name
            or proof.status in (ProofStatus.REJECTED, ProofStatus.PENDING, ProofStatus.ANALYZING)
            or proof.id in cert_proofs
            or normalize(cert.course_name) in cert_names
            or (cert.credential_id and normalize(cert.credential_id) in cert_ids)
        ):
            continue
        level = proof.report.verification_level if proof.report else None
        verification = (
            cert.verification_url if cert.url_check and cert.url_check.reachable else None
        )
        honesty = {
            "verified": "Verified on the issuer's site.",
            "partially_verified": "Partially verified: the link works, details unconfirmed.",
            "self_reported": "Self-reported: there's no verification link we could check.",
        }.get(level or "", "")
        out.append(
            ResumeSuggestion(
                id=f"cert:{proof.id}",
                kind="add_certification",
                proof_id=proof.id,
                level=level,
                title=f"Add “{cert.course_name}” to Certifications?",
                detail=honesty,
                certification=CertificationItem(
                    name=cert.course_name[:200],
                    issuer=(cert.issuer or None) and cert.issuer[:200],
                    issue_date=_year_month(cert.issue_date),
                    credential_id=(cert.credential_id or None) and cert.credential_id[:100],
                    credential_url=(verification or None) and verification[:200],
                    proof_id=proof.id,
                ),
            )
        )

    # Current licences belong in Licenses & Certifications too.
    for proof in proofs:
        licence = proof.report.license if proof.report else None
        if (
            proof.type is not ProofType.PROFESSIONAL_LICENSE
            or licence is None
            or licence.expired
            or not (licence.license_type or licence.issuing_body)
            or proof.status in (ProofStatus.REJECTED, ProofStatus.PENDING, ProofStatus.ANALYZING)
            or proof.id in cert_proofs
            or (licence.license_number and normalize(licence.license_number) in cert_ids)
        ):
            continue
        name = licence.license_type or f"{licence.issuing_body} licence"
        if normalize(name) in cert_names:
            continue
        level = proof.report.verification_level if proof.report else None
        check = licence.register_check
        honesty = {
            "verified": "Verified on the public register.",
            "partially_verified": "Partially verified: the register link works, not the details.",
            "self_reported": "Self-reported: employers can check it on the public register.",
        }.get(level or "", "")
        out.append(
            ResumeSuggestion(
                id=f"cert:{proof.id}",
                kind="add_certification",
                proof_id=proof.id,
                level=level,
                title=f"Add your “{name}” licence to Licenses & Certifications?",
                detail=honesty,
                certification=CertificationItem(
                    name=name[:200],
                    issuer=(licence.issuing_body or None) and licence.issuing_body[:200],
                    issue_date=_year_month(licence.issue_date),
                    credential_id=(licence.license_number or None) and licence.license_number[:100],
                    credential_url=check.url[:200] if check and check.reachable else None,
                    proof_id=proof.id,
                ),
            )
        )

    hidden = set(dismissed)
    return [s for s in out if s.id not in hidden]
