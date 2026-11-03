"""Map free-form resume text onto our resume model.

The AI output schema (ParsedResume) is intentionally loose: plain strings and lists, no length
or format rules, so structured output stays simple for the model. `to_resume_data()` then
normalises it into the strict ResumeData model (dates, emails, lengths).
"""

import re
import secrets
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from pydantic import EmailStr as _EmailStr

from app.ai.client import AIClient
from app.ai.prompts import render_prompt
from app.schemas.resume_data import (
    MAX_BULLETS,
    MAX_CERTIFICATIONS,
    MAX_EDUCATION,
    MAX_ENTRIES,
    MAX_PROFILE_LINKS,
    MAX_SECTIONS,
    MAX_SKILLS,
    MAX_TOOLS,
    CertificationItem,
    EducationItem,
    ExperienceItem,
    PersonalInfo,
    ProfileLink,
    ProjectItem,
    ResumeData,
    ResumeSkill,
    SectionConfig,
    SectionItem,
)
from app.schemas.section_kind import SectionKind
from app.services.sections.catalog import get_catalog

# --- AI output schema -------------------------------------------------------------


class ParsedLink(BaseModel):
    label: str = Field(
        description="The site's name, e.g. 'LinkedIn', 'ORCID', 'Behance', 'Website'"
    )
    url: str


class ParsedPersonalInfo(BaseModel):
    full_name: str = ""
    headline: str = Field("", description="Professional title, e.g. 'Registered Nurse'")
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    profile_links: list[ParsedLink] = []


class ParsedExperience(BaseModel):
    company: str = ""
    title: str = ""
    location: str | None = None
    start_date: str | None = Field(None, description="YYYY-MM")
    end_date: str | None = Field(None, description="YYYY-MM; null if current")
    is_current: bool = False
    bullets: list[str] = []
    tools_and_skills: list[str] = []


class ParsedEducation(BaseModel):
    institution: str = ""
    degree: str = ""
    field_of_study: str | None = None
    grade: str | None = None
    start_date: str | None = Field(None, description="YYYY-MM")
    end_date: str | None = Field(None, description="YYYY-MM")
    is_current: bool = False
    bullets: list[str] = []


class ParsedProject(BaseModel):
    name: str = ""
    description: str = ""
    bullets: list[str] = []
    tools_and_skills: list[str] = []
    link: str | None = None


class ParsedCertification(BaseModel):
    name: str = ""
    issuer: str | None = None
    issue_date: str | None = Field(None, description="YYYY-MM")
    credential_url: str | None = None


# Every non-core kind, "custom" included. Core kinds have their own fields above.
ExtraKind = Literal[tuple(k.value for k in SectionKind if not k.is_core)]  # type: ignore[valid-type]


class ParsedEntry(BaseModel):
    title: str = Field("", description="Role, publication title, award, language, course...")
    organization: str = Field("", description="Where or who: hospital, journal, school, issuer")
    location: str | None = None
    start_date: str | None = Field(None, description="YYYY-MM (the date, for one-date entries)")
    end_date: str | None = Field(None, description="YYYY-MM; null if current")
    is_current: bool = False
    description: str = ""
    bullets: list[str] = []
    link: str | None = Field(None, description="URL or DOI, exactly as written")


class ParsedSection(BaseModel):
    kind: ExtraKind  # type: ignore[valid-type]
    heading: str = Field(description="The section's heading exactly as written in the document")
    entries: list[ParsedEntry] = []


class ParsedResume(BaseModel):
    document_type: Literal["resume", "cv"] = "resume"
    personal_info: ParsedPersonalInfo = ParsedPersonalInfo()
    summary: str = ""
    experience: list[ParsedExperience] = []
    education: list[ParsedEducation] = []
    projects: list[ParsedProject] = []
    skills: list[str] = []
    certifications: list[ParsedCertification] = []
    achievements: list[str] = []
    # Every other section: clinical placements, publications, languages... and anything
    # unrecognised as "custom" under its own heading, so nothing is dropped.
    sections: list[ParsedSection] = []


def section_guide() -> list[dict[str, object]]:
    """What the parser is told about each non-core kind, straight from the catalog."""
    guide: list[dict[str, object]] = []
    for spec in get_catalog().kinds:
        if spec.kind.is_core or spec.fields is None:
            continue
        fields = spec.fields
        labels = {
            name: getattr(fields, name).label
            for name in ("title", "organization", "location", "description", "bullets", "link")
            if getattr(fields, name) is not None
        }
        if fields.dates:
            labels["start_date"] = "date" if fields.dates == "single" else "start date"
            if fields.dates == "range":
                labels["end_date"] = "end date"
        guide.append(
            {
                "kind": spec.kind.value,
                "heading": spec.heading,
                "headings": spec.standard_headings,
                "fields": labels,
            }
        )
    return guide


async def parse_resume_text(ai: AIClient, text: str) -> ParsedResume:
    return await ai.generate_structured(
        render_prompt("resume_parse_user", resume_text=text),
        ParsedResume,
        system=render_prompt("resume_parse_system", sections=section_guide()),
        task="resume_parse",
    )


# --- normalisation into the strict resume model ------------------------------------------

_YEAR_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_YEAR = re.compile(r"^(\d{4})$")
_email = TypeAdapter(_EmailStr)


def _clip(value: str | None, limit: int = 200) -> str:
    return (value or "").strip()[:limit]


def _opt(value: str | None, limit: int = 200) -> str | None:
    return _clip(value, limit) or None


def _date(value: str | None) -> str | None:
    value = (value or "").strip()
    if _YEAR_MONTH.match(value):
        return value
    if match := _YEAR.match(value):
        return f"{match.group(1)}-01"
    return None


def _email_or_none(value: str | None) -> str | None:
    try:
        return str(_email.validate_python((value or "").strip()))
    except ValidationError:
        return None


def _bullets(values: list[str], limit: int = MAX_BULLETS) -> list[str]:
    cleaned = (v.strip().lstrip("•-*–·▪ ").strip() for v in values)
    return [v[:500] for v in cleaned if v][:limit]


def _names(values: list[str], limit: int = MAX_TOOLS) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        name = _clip(value)
        if name and name.lower() not in seen:
            seen[name.lower()] = name
    return list(seen.values())[:limit]


def _dates(start: str | None, end: str | None, is_current: bool) -> dict[str, object]:
    begin, finish = _date(start), None if is_current else _date(end)
    if begin and finish and finish < begin:
        finish = None  # contradictory range from the source; keep the start date only
    return {"start_date": begin, "end_date": finish, "is_current": is_current}


def _entry(e: ParsedEntry) -> SectionItem:
    return SectionItem(
        title=_clip(e.title),
        organization=_clip(e.organization),
        location=_opt(e.location),
        description=_clip(e.description, 1000),
        bullets=_bullets(e.bullets),
        link=_opt(e.link),
        **_dates(e.start_date, e.end_date, e.is_current),  # type: ignore[arg-type]
    )


def _custom_id(heading: str, taken: set[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")[:24].strip("-")
    base = f"custom-{slug}" if slug else f"custom-{secrets.token_hex(4)}"
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def extra_sections(parsed: ParsedResume) -> list[SectionConfig]:
    """Non-core sections in document order. Same-kind sections are merged (two "Awards"
    lists become one); custom ones keep their original heading, merged by heading."""
    by_id: dict[str, SectionConfig] = {}
    custom_ids: dict[str, str] = {}
    for section in parsed.sections:
        entries = [x for x in (_entry(e) for e in section.entries) if x.has_content()]
        if not entries:
            continue
        kind = SectionKind(section.kind)
        heading = _clip(section.heading, 200)
        if kind is SectionKind.CUSTOM:
            heading = heading or "Additional Information"
            key = heading.lower()
            if key not in custom_ids:
                custom_ids[key] = _custom_id(heading, set(by_id))
            section_id = custom_ids[key]
        else:
            section_id = kind.value
        if section_id in by_id:
            current = by_id[section_id]
            merged = [*current.entries, *entries][:MAX_ENTRIES]
            by_id[section_id] = current.model_copy(update={"entries": merged})
        elif len(by_id) < MAX_SECTIONS:
            by_id[section_id] = SectionConfig(
                id=section_id,
                kind=kind,
                title=heading if kind is SectionKind.CUSTOM else None,
                entries=entries[:MAX_ENTRIES],
            )
    return list(by_id.values())


def to_resume_data(parsed: ParsedResume) -> ResumeData:
    p = parsed.personal_info
    return ResumeData(
        personal_info=PersonalInfo(
            full_name=_clip(p.full_name),
            headline=_clip(p.headline),
            email=_email_or_none(p.email),
            phone=_opt(p.phone, 40),
            location=_opt(p.location),
            profile_links=[
                ProfileLink(label=_clip(link.label, 40), url=_clip(link.url))
                for link in p.profile_links[:MAX_PROFILE_LINKS]
                if link.label.strip() and link.url.strip()
            ],
        ),
        summary=_clip(parsed.summary, 2000),
        experience=[
            ExperienceItem(
                company=_clip(e.company),
                title=_clip(e.title),
                location=_opt(e.location),
                bullets=_bullets(e.bullets),
                tools_and_skills=_names(e.tools_and_skills),
                **_dates(e.start_date, e.end_date, e.is_current),  # type: ignore[arg-type]
            )
            for e in parsed.experience
            if e.company.strip() or e.title.strip()
        ][:MAX_ENTRIES],
        education=[
            EducationItem(
                institution=_clip(e.institution),
                degree=_clip(e.degree),
                field_of_study=_opt(e.field_of_study),
                grade=_opt(e.grade, 40),
                bullets=_bullets(e.bullets),
                **_dates(e.start_date, e.end_date, e.is_current),  # type: ignore[arg-type]
            )
            for e in parsed.education
            if e.institution.strip() or e.degree.strip()
        ][:MAX_EDUCATION],
        projects=[
            ProjectItem(
                name=_clip(pr.name),
                description=_clip(pr.description, 1000),
                bullets=_bullets(pr.bullets),
                tools_and_skills=_names(pr.tools_and_skills),
                link=_opt(pr.link),
            )
            for pr in parsed.projects
            if pr.name.strip() or pr.description.strip()
        ][:MAX_ENTRIES],
        skills=[ResumeSkill(name=name) for name in _names(parsed.skills, MAX_SKILLS)],
        certifications=[
            CertificationItem(
                name=_clip(c.name),
                issuer=_opt(c.issuer),
                issue_date=_date(c.issue_date),
                credential_url=_opt(c.credential_url),
            )
            for c in parsed.certifications
            if c.name.strip()
        ][:MAX_CERTIFICATIONS],
        achievements=_bullets(parsed.achievements, MAX_ENTRIES),
        sections=extra_sections(parsed),
    )
