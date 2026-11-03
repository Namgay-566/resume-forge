"""ATS analysis report. Stored in ats_analyses.report (JSONB) and returned by the API."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CategoryKey = Literal["formatting", "keywords", "impact", "completeness"]
# Editor sections a finding can point at (matches ResumeData fields).
SectionKey = Literal[
    "personal_info",
    "summary",
    "experience",
    "education",
    "projects",
    "skills",
    "certifications",
    "achievements",
]
CheckStatus = Literal["pass", "warn", "fail"]


class Location(BaseModel):
    """Where in the editor a finding lives, so the UI can jump to it."""

    # "personal_info", a core section, or a section id ("clinical_experience", "custom-x1").
    section: Annotated[str, Field(max_length=40)]
    item_index: int | None = None
    # The section's heading as the user sees it, when it isn't a standard SectionKey.
    label: str | None = None


class CheckResult(BaseModel):
    id: str
    category: CategoryKey
    status: CheckStatus
    title: str
    detail: str
    # Relative importance inside its category.
    weight: float
    location: Location | None = None
    # Score points (0-100 scale) this check currently costs the overall score.
    points_lost: float = 0


class KeywordHit(BaseModel):
    keyword: str
    importance: Literal["required", "preferred"] = "required"
    # Share of the keyword score (critical role skills weigh more than nice-to-haves).
    weight: float = 1
    matched_as: str | None = None  # which alias matched, e.g. "postgres" for "PostgreSQL"


class KeywordReport(BaseModel):
    # Where the keywords came from. None: no JD and no target role, so not scored.
    source: Literal["job_description", "target_role"] | None
    # For JDs: "ai" extraction, or "catalog" (skills-catalog scan) when AI was unavailable.
    extraction: Literal["ai", "catalog", "target_role"] | None = None
    matched: list[KeywordHit] = []
    missing: list[KeywordHit] = []


class CategoryScore(BaseModel):
    key: CategoryKey
    label: str
    # None when the category can't be scored (keywords without a JD or target role).
    score: int | None
    # Share of the overall score, after redistributing unscored categories.
    weight: float


class SectionFeedback(BaseModel):
    section: SectionKey
    rating: Literal["strong", "ok", "weak"]
    feedback: str
    suggestions: list[str] = []


class AIReview(BaseModel):
    overall: str
    sections: list[SectionFeedback]


class Fix(BaseModel):
    priority: int
    severity: Literal["high", "medium", "low"]
    title: str
    detail: str
    source: Literal["check", "keywords", "ai"]
    location: Location | None = None
    # Estimated overall-score points recovered by fixing this (None for AI suggestions).
    points: float | None = None


class AtsReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: Annotated[int, Field(ge=0, le=100)]
    categories: list[CategoryScore]
    checks: list[CheckResult]
    keywords: KeywordReport
    ai_review: AIReview | None = None
    # skipped: review not requested (deterministic re-check); rate_limited: AI budget used up.
    ai_status: Literal["ok", "unavailable", "failed", "skipped", "rate_limited"]
    fixes: list[Fix]


class AtsAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_description: Annotated[str, Field(max_length=20_000)] | None = None
    # False: re-score only (deterministic checks + keywords), no AI review and no AI cost.
    review: bool = True


class AtsPrevious(BaseModel):
    """The analysis before this one, for showing what changed."""

    score: int
    categories: list[CategoryScore]
    created_at: datetime


class AtsAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    resume_id: uuid.UUID
    job_description: str | None
    score: int
    report: AtsReport
    created_at: datetime
    previous: AtsPrevious | None = None
