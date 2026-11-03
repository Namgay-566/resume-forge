from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.ats import Location
from app.schemas.section_kind import SectionKind
from app.services.sections.catalog import get_catalog

ShortText = Annotated[str, Field(max_length=200)]


class BulletImproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Sent from the editor so unsaved edits are used.
    text: Annotated[str, Field(min_length=3, max_length=500)]
    # Any section with bullets: experience, clinical placements, volunteering, custom...
    section: SectionKind
    # The heading the user gave the section, if they renamed it (or a custom section's name).
    section_title: ShortText | None = None
    # The entry the bullet belongs to, e.g. "Staff Nurse at St Mary's Hospital".
    position: Annotated[str, Field(max_length=400)] = ""
    tools_and_skills: Annotated[list[ShortText], Field(max_length=30)] = []

    @field_validator("section")
    @classmethod
    def section_has_bullets(cls, kind: SectionKind) -> SectionKind:
        if not get_catalog().has_bullets(kind):
            raise ValueError(f"the {kind.value} section has no bullet points")
        return kind


class WritingOption(BaseModel):
    text: str
    rationale: str | None = None
    # Square-bracket placeholders the user must replace with real figures, e.g. "[X%]".
    placeholders: list[str] = []
    # Numbers the model added that weren't in your text; swapped for placeholders.
    replaced_numbers: list[str] = []


class WritingOptions(BaseModel):
    options: list[WritingOption]


class TailorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_description: Annotated[str, Field(min_length=20, max_length=20_000)]


SuggestionKind = Literal[
    "rewrite_bullet", "move_bullet_up", "rewrite_summary", "feature_skills", "add_skill"
]


class Suggestion(BaseModel):
    """One proposed change. Never applied by the server: the editor shows it as a diff and
    applies it only if the user accepts and the `before` content still matches."""

    id: str
    kind: SuggestionKind
    location: Location
    reason: str
    # Text changes (bullet or summary): before -> after. add_skill uses `after` only.
    before: str | None = None
    after: str | None = None
    # List changes (bullet order, skills order): before_items -> after_items.
    before_items: list[str] | None = None
    after_items: list[str] | None = None
    placeholders: list[str] = []


class TailorResult(BaseModel):
    suggestions: list[Suggestion]
    # Requirements with no evidence on the resume. Shown, never added.
    gaps: list[str]
