"""Kept free of model imports: the learning_plan_items model stores this as JSONB."""

from typing import Annotated

from pydantic import BaseModel, Field


class ProjectIdea(BaseModel):
    """AI-written proof project for one skill: a case study, sample campaign, lesson plan,
    certification path or repository, whatever suits the skill in its field. Stored with the
    plan item."""

    title: Annotated[str, Field(max_length=120)]
    summary: Annotated[str, Field(max_length=600)]
    steps: Annotated[list[Annotated[str, Field(max_length=300)]], Field(min_length=1, max_length=8)]
    reviewer_checks: Annotated[
        list[Annotated[str, Field(max_length=300)]], Field(min_length=1, max_length=8)
    ]
    est_hours: Annotated[int, Field(ge=1, le=40)]
    stretch: Annotated[str, Field(max_length=300)] | None = None
    # The kind of proof it produces (a ProofType value) and what gets uploaded at the end.
    # Optional: ideas saved before these existed have neither.
    proof_type: str | None = None
    deliverable: Annotated[str, Field(max_length=160)] | None = None
    # Which role it was tailored for, so a role change can prompt a fresh idea.
    tailored_for: str | None = None
