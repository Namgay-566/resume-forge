"""Format-neutral view of a resume. HTML/PDF and DOCX both render from this, so every
export has the same sections, order and date format. Sections print in the order the user
arranged them (ResumeData.sections), under their own heading or the catalog's.
Mirrored in the frontend preview (frontend/src/features/resumes/preview/document.ts):
keep the two in sync.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from app.models.enums import ResumeType
from app.schemas.resume_data import ResumeData, SectionConfig, SectionItem
from app.schemas.section_kind import SectionKind
from app.services.sections.catalog import get_catalog

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DASH = "–"  # en dash


@dataclass
class Entry:
    title: str
    date: str = ""
    subtitle: str = ""
    link: str = ""
    description: str = ""
    bullets: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


@dataclass
class Section:
    key: str  # the section's id: its kind, or "custom-..." for custom sections
    heading: str
    text: str = ""
    entries: list[Entry] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)  # extra plain lines, e.g. "Verified skills: ..."


class CitedProof(Protocol):
    """What the document needs from a proof: its plain-text link and whether it's verified."""

    display_url: str | None
    verified: bool
    method: str | None


@dataclass
class ResumeDocument:
    name: str
    headline: str
    contact: list[str]
    sections: list[Section]


def format_year_month(value: str | None) -> str:
    """'2024-03' -> 'Mar 2024'."""
    if not value:
        return ""
    year, month = value.split("-")
    return f"{MONTHS[int(month) - 1]} {year}"


def format_date_range(start: str | None, end: str | None, is_current: bool) -> str:
    begin = format_year_month(start)
    finish = "Present" if is_current else format_year_month(end)
    if begin and finish:
        return f"{begin} {DASH} {finish}"
    return begin or finish


def _join(*parts: str | None, sep: str = ", ") -> str:
    return sep.join(p for p in parts if p)


def _has_content(entry: Entry) -> bool:
    return any(
        [
            entry.title,
            entry.date,
            entry.subtitle,
            entry.link,
            entry.description,
            entry.bullets,
            entry.tools,
        ]
    )


def verified_skills_line(data: ResumeData, proofs: Mapping[str, CitedProof]) -> str:
    """'Verified skills: Food Safety (ehcert.example/verify/X), Teamwork (verified by referee)'."""
    cited = []
    for skill in data.skills:
        proof = proofs.get(str(skill.proof_id)) if skill.proof_id else None
        if skill.name and proof is not None and proof.verified:
            # A link is its own evidence; without one (a referee), say how it was verified.
            how = proof.display_url or (proof.method or "").lower() or None
            cited.append(f"{skill.name} ({how})" if how else skill.name)
    return f"Verified skills: {', '.join(cited)}" if cited else ""


def _generic(config: SectionConfig, proof_url: "ProofUrl") -> Section:
    """A non-core section (clinical experience, publications, languages...) from its
    generic entries. Laid out like experience: "Title, Organisation" with dates."""
    spec = get_catalog().spec(config.kind)
    items = [i for i in config.entries if i.has_content()]
    if spec.layout == "inline":  # "Spanish (Fluent), French (Conversational)"
        text = ", ".join(
            f"{i.title} ({i.organization})" if i.title and i.organization else i.title
            for i in items
            if i.title
        )
        return Section(config.id, "", text=text)
    single_date = spec.fields is not None and spec.fields.dates == "single"
    entries = [_generic_entry(i, single_date, proof_url) for i in items]
    return Section(config.id, "", entries=entries)


def _generic_entry(item: SectionItem, single_date: bool, proof_url: "ProofUrl") -> Entry:
    return Entry(
        title=_join(item.title, item.organization),
        date=format_year_month(item.start_date or item.end_date)
        if single_date
        else format_date_range(item.start_date, item.end_date, item.is_current),
        subtitle=item.location or "",
        link=item.link or proof_url(item.proof_id),
        description=item.description,
        bullets=item.bullets,
    )


class ProofUrl(Protocol):
    def __call__(self, proof_id: object) -> str: ...


def build_document(
    data: ResumeData, resume_type: ResumeType, proofs: Mapping[str, CitedProof] | None = None
) -> ResumeDocument:
    """proofs: citation links keyed by proof id, so proof-backed entries print their URL."""
    proofs = proofs or {}

    def proof_url(proof_id: object) -> str:
        proof = proofs.get(str(proof_id)) if proof_id else None
        return (proof.display_url or "") if proof else ""

    p = data.personal_info
    contact = [c for c in (p.email, p.phone, p.location) if c] + [
        link.url for link in p.profile_links
    ]

    experience = [
        Entry(
            title=_join(e.title, e.company),
            date=format_date_range(e.start_date, e.end_date, e.is_current),
            subtitle=e.location or "",
            bullets=e.bullets,
            tools=e.tools_and_skills,
        )
        for e in data.experience
    ]
    education = [
        Entry(
            title=e.institution,
            date=format_date_range(e.start_date, e.end_date, e.is_current),
            subtitle=_join(_join(e.degree, e.field_of_study, sep=" in "), e.grade),
            bullets=e.bullets,
        )
        for e in data.education
    ]
    projects = [
        Entry(
            title=pr.name,
            link=pr.link or proof_url(pr.proof_id),
            description=pr.description,
            bullets=pr.bullets,
            tools=pr.tools_and_skills,
        )
        for pr in data.projects
    ]
    certifications = [
        Entry(
            title=c.name,
            date=format_year_month(c.issue_date),
            subtitle=c.issuer or "",
            link=c.credential_url or proof_url(c.proof_id),
            description=f"Credential ID: {c.credential_id}" if c.credential_id else "",
        )
        for c in data.certifications
    ]

    core: dict[SectionKind, Section] = {
        SectionKind.SUMMARY: Section("summary", "", text=data.summary),
        SectionKind.SKILLS: Section(
            "skills",
            "",
            text=", ".join(s.name for s in data.skills if s.name),
            extra=[line]
            if data.show_verified_skills and (line := verified_skills_line(data, proofs))
            else [],
        ),
        SectionKind.EXPERIENCE: Section("experience", "", entries=experience),
        SectionKind.PROJECTS: Section("projects", "", entries=projects),
        SectionKind.EDUCATION: Section("education", "", entries=education),
        SectionKind.CERTIFICATIONS: Section("certifications", "", entries=certifications),
        SectionKind.ACHIEVEMENTS: Section(
            "achievements", "", items=[a for a in data.achievements if a]
        ),
    }
    catalog = get_catalog()
    sections = []
    for config in data.sections:
        section = core[config.kind] if config.kind.is_core else _generic(config, proof_url)
        section.heading = config.title or catalog.heading(config.kind)
        section.entries = [e for e in section.entries if _has_content(e)]
        if section.text or section.entries or section.items:
            sections.append(section)

    return ResumeDocument(name=p.full_name, headline=p.headline, contact=contact, sections=sections)


def plain_text(data: ResumeData, resume_type: ResumeType) -> str:
    """The resume as the recruiter (and the AI) reads it, in export order."""
    doc = build_document(data, resume_type)  # without proof links: AI prompts don't need them
    lines = [doc.name, doc.headline, " | ".join(doc.contact)]
    for section in doc.sections:
        lines += ["", section.heading.upper()]
        if section.text:
            lines.append(section.text)
        for entry in section.entries:
            lines.append(" | ".join(p for p in (entry.title, entry.date) if p))
            lines += [p for p in (entry.subtitle, entry.link, entry.description) if p]
            lines += [f"- {b}" for b in entry.bullets]
            if entry.tools:
                lines.append(f"Tools: {', '.join(entry.tools)}")
        lines += [f"- {item}" for item in section.items]
    return "\n".join(line for line in lines if line is not None).strip()
