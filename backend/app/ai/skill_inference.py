from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.context import NO_CONTEXT, CandidateContext
from app.ai.prompts import render_prompt


class InferredSkill(BaseModel):
    skill: str
    evidence: str


class InferredSkills(BaseModel):
    skills: list[InferredSkill] = Field(default_factory=list, max_length=40)


async def infer_skills(
    ai: AIClient,
    *,
    resume_text: str,
    candidates: list[str],
    context: CandidateContext = NO_CONTEXT,
) -> InferredSkills:
    return await ai.generate_structured(
        render_prompt(
            "skill_infer_user", resume_text=resume_text, candidates=candidates, ctx=context
        ),
        InferredSkills,
        system=render_prompt("skill_infer_system"),
        task="skill_inference",
        max_tokens=3000,
    )
