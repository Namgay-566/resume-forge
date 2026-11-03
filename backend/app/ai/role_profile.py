"""Draft a target-role profile (required skills and how much they matter) from a job title
that isn't in the curated library."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, create_model, field_validator, model_validator

from app.ai.client import AIClient
from app.ai.prompts import render_prompt
from app.models.enums import SkillImportance

SkillCategory = Literal[
    "soft_skill", "license", "certification", "tool", "practice", "concept", "language"
]
MIN_SKILLS, MAX_SKILLS = 6, 14
Alias = Annotated[str, Field(min_length=1, max_length=80)]


class RoleProfileSkill(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=80)]
    category: SkillCategory
    importance: SkillImportance
    # Other common spellings and abbreviations, e.g. ["rn license", "nclex"].
    aliases: Annotated[list[Alias], Field(max_length=6)] = []


class RoleProfile(BaseModel):
    # False for text that isn't a job (gibberish, a company name, an instruction).
    is_job_title: bool
    # The title as it would appear in a job ad, e.g. "Veterinary Nurse".
    name: Annotated[str, Field(min_length=2, max_length=120)]
    industry: str
    seniority: Literal["entry", "mid", "senior"]
    description: Annotated[str, Field(max_length=400)]
    skills: Annotated[list[RoleProfileSkill], Field(max_length=MAX_SKILLS)]

    @field_validator("name")
    @classmethod
    def tidy_name(cls, name: str) -> str:
        return " ".join(name.split())

    @model_validator(mode="after")
    def check_skills(self) -> "RoleProfile":
        if not self.is_job_title:
            return self  # nothing else matters; the caller refuses it
        if len(self.skills) < MIN_SKILLS:
            raise ValueError(f"list at least {MIN_SKILLS} skills")
        names = [s.name.strip().lower() for s in self.skills]
        if len(set(names)) != len(names):
            raise ValueError("skill names must be unique")
        critical = sum(s.importance is SkillImportance.CRITICAL for s in self.skills)
        if critical < 2:
            raise ValueError("mark at least 2 skills as critical")
        if not any(s.category == "soft_skill" for s in self.skills):
            raise ValueError("include at least one soft skill")
        return self


def profile_model(industry_slugs: list[str]) -> type[RoleProfile]:
    """RoleProfile whose `industry` must be one of the known slugs, so an invented industry
    fails validation (and gets the usual one retry) instead of reaching the database."""
    return create_model(
        "RoleProfile",
        __base__=RoleProfile,
        industry=(Literal[tuple(industry_slugs)], ...),  # type: ignore[valid-type]
    )


async def draft_role_profile(
    ai: AIClient,
    *,
    title: str,
    industries: list[tuple[str, str]],
    industry_hint: str | None,
) -> RoleProfile:
    """`industries` is [(slug, name)]; `industry_hint` a slug the user picked, if any."""
    return await ai.generate_structured(
        render_prompt(
            "role_profile_user",
            title=title,
            industries=industries,
            industry_hint=industry_hint,
        ),
        profile_model([slug for slug, _ in industries]),
        system=render_prompt("role_profile_system"),
        task="role_profile",
        max_tokens=3000,
    )
