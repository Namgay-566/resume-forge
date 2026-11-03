"""The resume section catalog: every section kind's heading, the headings ATS systems
recognise for it, editor field labels, and the presets and requirements that depend on
career stage and document type. Loaded from catalog.json and validated on first use."""

from functools import cache
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from app.models.enums import ExperienceLevel
from app.schemas.section_kind import CORE_SECTION_KINDS, SectionKind

CATALOG_PATH = Path(__file__).with_name("catalog.json")
Severity = Literal["fail", "warn"]


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FieldSpec(CatalogModel):
    label: str
    placeholder: str | None = None


class EntryFields(CatalogModel):
    """Which generic entry fields a kind shows in the editor, and their labels.
    A missing field is hidden; `dates` is a start-end range or a single date."""

    title: FieldSpec
    organization: FieldSpec | None = None
    location: FieldSpec | None = None
    dates: Literal["range", "single"] | None = None
    description: FieldSpec | None = None
    bullets: FieldSpec | None = None
    link: FieldSpec | None = None


class KindSpec(CatalogModel):
    kind: SectionKind
    heading: str
    # Lowercase headings ATS parsers recognise for this kind. A renamed section outside
    # this list gets a warning.
    standard_headings: list[str]
    hint: str | None = None
    # What a strong bullet in this section shows, for the AI "Improve" button.
    bullet_guidance: str | None = None
    item_label: str = "entry"
    # Counted in years of experience and treated like a job by the ATS checks.
    counts_as_experience: bool = False
    # "inline" prints entries on one line ("Spanish (Fluent), French (Basic)").
    layout: Literal["entries", "inline"] = "entries"
    repeatable: bool = False
    # Generic entry fields; only for non-core kinds (core kinds have bespoke forms).
    fields: EntryFields | None = None

    @model_validator(mode="after")
    def check_fields(self) -> Self:
        if self.kind in CORE_SECTION_KINDS and self.fields is not None:
            raise ValueError(f"core section {self.kind} can't define generic fields")
        if self.kind not in CORE_SECTION_KINDS and self.fields is None:
            raise ValueError(f"section {self.kind} needs fields")
        return self


class Preset(CatalogModel):
    """Sections to move (or add) right after the summary, and to the end."""

    first: list[SectionKind] = []
    last: list[SectionKind] = []


class RequirementOverride(CatalogModel):
    add_kinds: list[SectionKind] = []
    severity: Severity | None = None
    advice: str | None = None


class Requirement(CatalogModel):
    id: str
    label: str
    # Any of these, with content, satisfies the requirement.
    kinds: list[SectionKind]
    advice: str
    severity: Severity = "fail"
    levels: dict[ExperienceLevel, RequirementOverride] = {}


class RoleRequirement(CatalogModel):
    """Sections a role or industry requires; `{role}` and `{heading}` are filled in."""

    advice: str
    severity: Severity = "fail"
    levels: dict[ExperienceLevel, RequirementOverride] = {}


class ProfileLinkType(CatalogModel):
    """A kind of profile link people add (LinkedIn, ORCID...). Industries pick which to
    suggest in their seed data."""

    label: str
    placeholder: str


class SectionCatalog(CatalogModel):
    kinds: list[KindSpec]
    default_layout: Annotated[list[SectionKind], Field(min_length=1)]
    type_presets: dict[Literal["resume", "cv"], Preset] = {}
    level_presets: dict[ExperienceLevel, Preset] = {}
    requirements: list[Requirement]
    role_requirement: RoleRequirement
    # A role whose critical skills include one of these categories requires the
    # Licenses & Certifications section.
    licence_skill_categories: list[str] = []
    profile_links: list[ProfileLinkType] = []

    _by_kind: dict[SectionKind, KindSpec] = PrivateAttr(default_factory=dict)

    def model_post_init(self, context: object) -> None:
        self._by_kind.update({k.kind: k for k in self.kinds})

    @model_validator(mode="after")
    def check_bullet_guidance(self) -> Self:
        missing = [
            k.kind.value for k in self.kinds if self.has_bullets(k.kind) and not k.bullet_guidance
        ]
        if missing:
            raise ValueError(f"sections with bullets need bullet_guidance: {missing}")
        return self

    @model_validator(mode="after")
    def check_every_kind_once(self) -> Self:
        listed = [k.kind for k in self.kinds]
        if sorted(listed) != sorted(SectionKind):
            missing = set(SectionKind) - set(listed)
            raise ValueError(f"catalog must describe every section kind once; missing {missing}")
        return self

    def spec(self, kind: SectionKind) -> KindSpec:
        return self._by_kind[kind]

    def heading(self, kind: SectionKind) -> str:
        return self.spec(kind).heading

    def has_bullets(self, kind: SectionKind) -> bool:
        """Whether entries of this kind have bullet points (so "Improve" applies)."""
        if kind in CORE_BULLET_KINDS:
            return True
        fields = self.spec(kind).fields
        return fields is not None and fields.bullets is not None


# Core sections whose entries (or rows, for achievements) are bullet points.
CORE_BULLET_KINDS = frozenset(
    {SectionKind.EXPERIENCE, SectionKind.EDUCATION, SectionKind.PROJECTS, SectionKind.ACHIEVEMENTS}
)


@cache
def get_catalog() -> SectionCatalog:
    return SectionCatalog.model_validate_json(CATALOG_PATH.read_text(encoding="utf-8"))
