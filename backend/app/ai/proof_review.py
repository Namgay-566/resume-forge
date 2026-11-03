from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.prompts import render_prompt
from app.services.proofs.collect import Collected


class ReviewedSkill(BaseModel):
    skill: str
    verdict: Literal["demonstrated", "partially", "not_demonstrated"]
    evidence: list[str] = Field(default_factory=list, max_length=5)


class ProofReview(BaseModel):
    summary: str
    skills: list[ReviewedSkill]
    strengths: list[str] = Field(default_factory=list, max_length=6)
    code_quality: list[str] = Field(default_factory=list, max_length=8)
    red_flags: list[str] = Field(default_factory=list, max_length=8)
    score: int = Field(ge=0, le=100)
    suggestions: list[str] = Field(default_factory=list, max_length=8)


def _commit_messages(collected: Collected, limit: int = 20) -> list[str]:
    messages = []
    for commit in collected.recent_commits[:limit]:
        first_line = (commit.get("commit", {}).get("message") or "").splitlines()[:1]
        if first_line and first_line[0].strip():
            messages.append(first_line[0].strip()[:120])
    return messages


async def review_repo(
    ai: AIClient, *, collected: Collected, skills: list[str], target_role: str | None
) -> ProofReview:
    return await ai.generate_structured(
        render_prompt(
            "proof_review_user",
            skills=skills,
            target_role=target_role,
            facts=collected.facts,
            commit_messages=_commit_messages(collected),
            readme=collected.readme,
            tree=collected.tree_listing,
            config_files=collected.config_files,
            source_files=collected.source_files,
        ),
        ProofReview,
        system=render_prompt("proof_review_system"),
        task="proof_review",
        max_tokens=6000,
    )
