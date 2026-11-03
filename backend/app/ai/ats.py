"""AI tasks for the ATS analyzer: JD keyword extraction and a recruiter-style review."""

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.client import AIClient
from app.ai.context import NO_CONTEXT, CandidateContext
from app.ai.prompts import render_prompt
from app.schemas.ats import SectionKey


class JdKeyword(BaseModel):
    keyword: str
    importance: Literal["required", "preferred"]


class JdKeywords(BaseModel):
    keywords: list[JdKeyword] = Field(max_length=40)


class ReviewSection(BaseModel):
    section: SectionKey
    rating: Literal["strong", "ok", "weak"]
    feedback: str
    suggestions: list[str] = Field(default_factory=list, max_length=5)


class RecruiterReview(BaseModel):
    overall: str
    sections: list[ReviewSection]


async def extract_jd_keywords(
    ai: AIClient, job_description: str, context: CandidateContext = NO_CONTEXT
) -> JdKeywords:
    return await ai.generate_structured(
        render_prompt("jd_keywords_user", job_description=job_description, ctx=context),
        JdKeywords,
        system=render_prompt("jd_keywords_system"),
        task="ats_jd_keywords",
        max_tokens=4000,
    )


async def review_resume(
    ai: AIClient,
    *,
    resume_text: str,
    job_description: str | None,
    context: CandidateContext = NO_CONTEXT,
) -> RecruiterReview:
    return await ai.generate_structured(
        render_prompt(
            "ats_review_user",
            resume_text=resume_text,
            job_description=job_description,
            ctx=context,
        ),
        RecruiterReview,
        system=render_prompt("ats_review_system"),
        task="ats_review",
        max_tokens=8000,
    )
