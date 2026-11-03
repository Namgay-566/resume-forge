import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ExperienceLevel, ResumeTemplate, ResumeType
from app.schemas.resume_data import ResumeData
from app.schemas.target_role import TargetRoleSummary

Title = Annotated[str, Field(min_length=1, max_length=200)]


def _strip_title(title: str) -> str:
    if not (stripped := title.strip()):
        raise ValueError("title must not be blank")
    return stripped


class ResumeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    type: ResumeType = ResumeType.RESUME
    target_role_id: uuid.UUID | None = None
    # Where the person is in their career; tunes scoring and advice. Optional.
    experience_level: ExperienceLevel | None = None
    # Omit to use the template recommended for the target role's field.
    template: ResumeTemplate | None = None
    # Omit to start from an empty resume prefilled with the user's name and email.
    data: ResumeData | None = None

    _title = field_validator("title")(_strip_title)


class ResumeUpdate(BaseModel):
    """Partial update for autosave. Only fields present in the request are changed.

    `data` is always the whole document, so repeating the same request is harmless.
    Send `"target_role_id": null` or `"experience_level": null` to clear them.
    """

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    type: ResumeType | None = None
    target_role_id: uuid.UUID | None = None
    experience_level: ExperienceLevel | None = None
    template: ResumeTemplate | None = None
    data: ResumeData | None = None

    _title = field_validator("title")(_strip_title)

    @field_validator("type", "template", "data", "title", mode="before")
    @classmethod
    def reject_null(cls, value: object) -> object:
        # Only target_role_id and experience_level may be cleared; other nulls are client bugs.
        if value is None:
            raise ValueError("may not be null")
        return value


class ResumeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    type: ResumeType
    template: ResumeTemplate
    target_role: TargetRoleSummary | None
    experience_level: ExperienceLevel | None
    ats_score: int | None
    created_at: datetime
    updated_at: datetime


class ResumeRead(ResumeSummary):
    data: ResumeData


class ResumeImportResult(BaseModel):
    resume: ResumeRead
    # Catalog skills found on the resume and added to the user's skills (unverified).
    matched_skills: list[str]
    # Skills listed on the resume that aren't in the catalog yet.
    unmatched_skills: list[str]
