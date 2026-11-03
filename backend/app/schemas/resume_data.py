"""Shape of `resumes.data` (JSONB). The single source of truth for resume content."""

import uuid
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.section_kind import SectionKind

# "YYYY-MM", e.g. "2024-03". Month precision is what resumes use.
YearMonth = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]
ShortText = Annotated[str, Field(max_length=200)]
Bullet = Annotated[str, Field(min_length=1, max_length=500)]

# Caps keep a resume (and every AI prompt built from it) bounded. Far above any real resume.
MAX_BULLETS = 15
MAX_TOOLS = 30  # tools and skills per job or project
MAX_PROFILE_LINKS = 8
MAX_ENTRIES = 30  # experience, projects, achievements
MAX_EDUCATION = 15
MAX_SKILLS = 100
MAX_CERTIFICATIONS = 50
MAX_SECTIONS = 30
MAX_TOTAL_CHARS = 60_000  # all text in the resume together

# Where core sections go when a resume doesn't say (the order exports always used).
DEFAULT_SECTION_ORDER: tuple[SectionKind, ...] = (
    SectionKind.SUMMARY,
    SectionKind.SKILLS,
    SectionKind.EXPERIENCE,
    SectionKind.PROJECTS,
    SectionKind.EDUCATION,
    SectionKind.CERTIFICATIONS,
    SectionKind.ACHIEVEMENTS,
)

Bullets = Annotated[list[Bullet], Field(max_length=MAX_BULLETS)]
ToolList = Annotated[list[ShortText], Field(max_length=MAX_TOOLS)]


class ResumeSection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DateRange(ResumeSection):
    start_date: YearMonth | None = None
    end_date: YearMonth | None = None
    is_current: bool = False

    @model_validator(mode="after")
    def check_dates(self) -> Self:
        if self.is_current and self.end_date is not None:
            raise ValueError("end_date must be empty when is_current is true")
        # Zero-padded YYYY-MM strings compare correctly as text.
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class ProfileLink(ResumeSection):
    """A profile or portfolio link: LinkedIn, GitHub, Behance, ORCID, a personal site..."""

    label: Annotated[str, Field(min_length=1, max_length=40)]
    url: Annotated[str, Field(min_length=1, max_length=200)]


class PersonalInfo(ResumeSection):
    full_name: ShortText = ""
    headline: ShortText = ""
    email: EmailStr | None = None
    phone: Annotated[str, Field(max_length=40)] | None = None
    location: ShortText | None = None
    # Printed in this order after the contact details. Which ones are suggested depends on
    # the field (ORCID for research, Behance for design, GitHub for technology).
    profile_links: Annotated[list[ProfileLink], Field(max_length=MAX_PROFILE_LINKS)] = Field(
        default_factory=list
    )


class ExperienceItem(DateRange):
    company: ShortText
    title: ShortText
    location: ShortText | None = None
    bullets: Bullets = Field(default_factory=list)
    tools_and_skills: ToolList = Field(default_factory=list)


class EducationItem(DateRange):
    institution: ShortText
    degree: ShortText
    field_of_study: ShortText | None = None
    grade: Annotated[str, Field(max_length=40)] | None = None
    bullets: Bullets = Field(default_factory=list)


class ProjectItem(ResumeSection):
    name: ShortText
    description: Annotated[str, Field(max_length=1000)] = ""
    bullets: Bullets = Field(default_factory=list)
    tools_and_skills: ToolList = Field(default_factory=list)
    link: ShortText | None = None
    proof_id: uuid.UUID | None = None


class ResumeSkill(ResumeSection):
    name: ShortText
    # Links to the skills catalog when matched; verification status lives in user_skills.
    skill_id: uuid.UUID | None = None
    proof_id: uuid.UUID | None = None


class CertificationItem(ResumeSection):
    name: ShortText
    issuer: ShortText | None = None
    issue_date: YearMonth | None = None
    credential_id: Annotated[str, Field(max_length=100)] | None = None
    credential_url: ShortText | None = None
    proof_id: uuid.UUID | None = None


class SectionItem(DateRange):
    """One entry in a non-core section: a placement, publication, award, language...
    Which fields apply, and their labels, depend on the section kind (see the catalog)."""

    title: ShortText = ""
    organization: ShortText = ""
    location: ShortText | None = None
    description: Annotated[str, Field(max_length=1000)] = ""
    bullets: Bullets = Field(default_factory=list)
    link: ShortText | None = None
    proof_id: uuid.UUID | None = None

    def has_content(self) -> bool:
        return bool(
            self.title or self.organization or self.description or self.bullets or self.link
        )

    def text_parts(self) -> list[str]:
        return [self.title, self.organization, self.location or "", self.description, *self.bullets]


SectionId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")]


class SectionConfig(ResumeSection):
    """A section as the user arranged it: its kind, an optional renamed heading, and (for
    non-core kinds) its entries. The order of `ResumeData.sections` is the print order."""

    # Equal to the kind, except custom sections: "custom-<random>" so there can be several.
    id: SectionId
    kind: SectionKind
    # The user's heading; None uses the kind's standard heading.
    title: ShortText | None = None
    entries: Annotated[list[SectionItem], Field(max_length=MAX_ENTRIES)] = Field(
        default_factory=list
    )

    @field_validator("title")
    @classmethod
    def blank_title_is_default(cls, title: str | None) -> str | None:
        return title or None

    @model_validator(mode="after")
    def check_kind(self) -> Self:
        if self.kind is SectionKind.CUSTOM:
            if not self.id.startswith("custom-"):
                raise ValueError("custom section ids start with 'custom-'")
            if not self.title:
                raise ValueError("give the custom section a name")
        elif self.id != self.kind.value:
            raise ValueError(f"section id must be {self.kind.value!r}")
        if self.kind.is_core and self.entries:
            raise ValueError(f"the {self.kind.value} section keeps its content in its own field")
        return self

    def has_content(self) -> bool:
        return any(entry.has_content() for entry in self.entries)


class ResumeData(ResumeSection):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: Annotated[str, Field(max_length=2000)] = ""
    experience: Annotated[list[ExperienceItem], Field(max_length=MAX_ENTRIES)] = Field(
        default_factory=list
    )
    education: Annotated[list[EducationItem], Field(max_length=MAX_EDUCATION)] = Field(
        default_factory=list
    )
    projects: Annotated[list[ProjectItem], Field(max_length=MAX_ENTRIES)] = Field(
        default_factory=list
    )
    skills: Annotated[list[ResumeSkill], Field(max_length=MAX_SKILLS)] = Field(default_factory=list)
    certifications: Annotated[list[CertificationItem], Field(max_length=MAX_CERTIFICATIONS)] = (
        Field(default_factory=list)
    )
    achievements: Annotated[list[Bullet], Field(max_length=MAX_ENTRIES)] = Field(
        default_factory=list
    )
    # Adds a "Verified skills" line (skills backed by verified proofs, with their links).
    show_verified_skills: bool = False
    # Which sections appear, in what order, under what heading. Empty means the default
    # order of core sections (resumes saved before sections were configurable).
    sections: Annotated[list[SectionConfig], Field(max_length=MAX_SECTIONS)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def normalize_sections(self) -> Self:
        ids = [s.id for s in self.sections]
        if len(set(ids)) != len(ids):
            raise ValueError("each section can appear only once")
        if not self.sections:
            self.sections = [SectionConfig(id=k.value, kind=k) for k in DEFAULT_SECTION_ORDER]
        # Content is never hidden by a missing section: a core section that has content
        # (added by an import or a proof, say) joins the end of the list.
        listed = {s.kind for s in self.sections}
        for kind in DEFAULT_SECTION_ORDER:
            if kind not in listed and self.core_has_content(kind):
                self.sections.append(SectionConfig(id=kind.value, kind=kind))
        return self

    def core_has_content(self, kind: SectionKind) -> bool:
        content: dict[SectionKind, object] = {
            SectionKind.SUMMARY: self.summary.strip(),
            SectionKind.EXPERIENCE: self.experience,
            SectionKind.EDUCATION: self.education,
            SectionKind.SKILLS: self.skills,
            SectionKind.PROJECTS: self.projects,
            SectionKind.CERTIFICATIONS: self.certifications,
            SectionKind.ACHIEVEMENTS: self.achievements,
        }
        return bool(content.get(kind))

    def has_content(self, kind: SectionKind) -> bool:
        """Whether any section of this kind has something in it."""
        if kind.is_core:
            return self.core_has_content(kind)
        return any(s.has_content() for s in self.sections if s.kind is kind)

    def extra_sections(self) -> list[SectionConfig]:
        return [s for s in self.sections if not s.kind.is_core]

    def extra_text_parts(self) -> list[str]:
        """All text in non-core sections, for keyword and skill matching."""
        return [part for s in self.extra_sections() for e in s.entries for part in e.text_parts()]

    @model_validator(mode="after")
    def check_total_size(self) -> Self:
        if len(self.model_dump_json()) > MAX_TOTAL_CHARS:
            raise ValueError(f"The resume is too long (over {MAX_TOTAL_CHARS:,} characters).")
        return self
