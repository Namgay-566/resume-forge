import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ContentSource, ResumeTemplate, SkillImportance


class IndustryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str


class IndustrySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    # The resume template suited to this field.
    recommended_template: ResumeTemplate = ResumeTemplate.CLASSIC
    # Profile links to suggest on resumes ("LinkedIn", "ORCID"...), from the industry's data.
    profile_links: list[str] = []


class TargetRoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    # "ai_generated" roles were drafted by the AI from a job title the user typed.
    source: ContentSource = ContentSource.CURATED


class TargetRoleRead(TargetRoleSummary):
    description: str
    seniority: str
    industry: IndustrySummary


class RoleSkillRead(BaseModel):
    name: str
    importance: SkillImportance


class TargetRoleDetail(TargetRoleRead):
    skills: list[RoleSkillRead]


class CustomRoleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=2, max_length=80)]
    # Optional hint; when omitted the AI picks the closest industry.
    industry: str | None = Field(default=None, max_length=64)

    @field_validator("title")
    @classmethod
    def clean_title(cls, title: str) -> str:
        cleaned = " ".join(title.split())
        if len(cleaned) < 2:
            raise ValueError("enter a job title")
        return cleaned


class CustomRoleResult(BaseModel):
    role: TargetRoleDetail
    # False when the title matched a role that already exists, so nothing was generated.
    created: bool
