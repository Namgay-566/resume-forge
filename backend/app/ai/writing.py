"""AI writing help: bullet rewrites, summaries, and tailoring suggestions.

Outputs here are raw model suggestions. app/services/writing/ validates them against the real
resume and removes invented numbers before anything reaches the user.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.context import NO_CONTEXT, CandidateContext
from app.ai.prompts import render_prompt


class BulletOption(BaseModel):
    text: str
    rationale: str


class BulletOptions(BaseModel):
    options: list[BulletOption] = Field(min_length=1, max_length=3)


class SummaryOptions(BaseModel):
    options: list[str] = Field(min_length=1, max_length=2)


class BulletRef(BaseModel):
    section: Literal["experience", "projects"]
    item_index: int
    bullet_index: int


class BulletRewrite(BulletRef):
    text: str
    reason: str


class Highlight(BulletRef):
    reason: str


class SkillToAdd(BaseModel):
    name: str
    reason: str


class TailorPlan(BaseModel):
    bullet_rewrites: list[BulletRewrite] = Field(default_factory=list, max_length=8)
    highlights: list[Highlight] = Field(default_factory=list, max_length=6)
    featured_skills: list[str] = Field(default_factory=list, max_length=20)
    featured_skills_reason: str = ""
    skills_to_add: list[SkillToAdd] = Field(default_factory=list, max_length=10)
    gaps: list[str] = Field(default_factory=list, max_length=15)
    summary: str | None = None
    summary_reason: str = ""


@dataclass(frozen=True)
class BulletSection:
    """Which resume section the bullet is in, and what a strong bullet there shows."""

    heading: str
    guidance: str = ""


EXPERIENCE_SECTION = BulletSection("Experience")


async def improve_bullet(
    ai: AIClient,
    *,
    bullet: str,
    position: str,
    tools: list[str],
    section: BulletSection = EXPERIENCE_SECTION,
    context: CandidateContext = NO_CONTEXT,
) -> BulletOptions:
    return await ai.generate_structured(
        render_prompt(
            "bullet_improve_user",
            bullet=bullet,
            position=position,
            tools=tools,
            section=section,
            ctx=context,
        ),
        BulletOptions,
        system=render_prompt("bullet_improve_system"),
        task="writing_bullet",
        max_tokens=2000,
    )


async def generate_summary(
    ai: AIClient,
    *,
    resume_text: str,
    years: float | None,
    context: CandidateContext = NO_CONTEXT,
) -> SummaryOptions:
    return await ai.generate_structured(
        render_prompt("summary_user", resume_text=resume_text, years=years, ctx=context),
        SummaryOptions,
        system=render_prompt("summary_system"),
        task="writing_summary",
        max_tokens=2000,
    )


async def tailor(
    ai: AIClient,
    *,
    resume_text: str,
    job_description: str,
    context: CandidateContext = NO_CONTEXT,
) -> TailorPlan:
    return await ai.generate_structured(
        render_prompt(
            "tailor_user", resume_text=resume_text, job_description=job_description, ctx=context
        ),
        TailorPlan,
        system=render_prompt("tailor_system"),
        task="writing_tailor",
        max_tokens=8000,
    )
