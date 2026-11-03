"""Review non-code evidence (a portfolio page, a work sample, a publication) the way an
experienced professional in the candidate's field would."""

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.context import CandidateContext
from app.ai.prompts import TrustedText, render_prompt
from app.ai.proof_review import ReviewedSkill
from app.ai.types import ImageInput

EvidenceKind = Literal["portfolio", "work_sample", "publication"]
# Used when the role's industry has no reviewer persona.
DEFAULT_PERSONA = "an experienced professional who hires for this kind of role"


class EvidenceReview(BaseModel):
    # False if this isn't real work at all (blank, a meme, unrelated, a login page).
    is_relevant: bool
    # What the reviewer takes it to be, e.g. "a social media campaign report".
    kind: str = Field(default="", max_length=120)
    summary: str = Field(max_length=1200)
    skills: list[ReviewedSkill] = Field(default_factory=list, max_length=10)
    strengths: list[str] = Field(default_factory=list, max_length=6)
    red_flags: list[str] = Field(default_factory=list, max_length=6)
    suggestions: list[str] = Field(default_factory=list, max_length=6)
    score: int = Field(ge=0, le=100)


async def review_evidence(
    ai: AIClient,
    *,
    kind: EvidenceKind,
    skills: list[str],
    persona: str | None,
    context: CandidateContext,
    text: str | None,
    image: bytes | None = None,
    details: dict[str, str] | None = None,
) -> EvidenceReview:
    """`details` are short labelled facts gathered before the review (page title, venue...)."""
    return await ai.generate_structured(
        render_prompt(
            "evidence_review_user",
            kind=kind,
            skills=skills,
            ctx=context,
            text=text,
            details=details or {},
        ),
        EvidenceReview,
        # The persona comes from our own industry data, not from the user.
        system=render_prompt(
            "evidence_review_system", persona=TrustedText(persona or DEFAULT_PERSONA)
        ),
        task=f"evidence_review_{kind}",
        max_tokens=4000,
        images=(ImageInput(data=image, media_type="image/jpeg"),) if image else (),
    )
