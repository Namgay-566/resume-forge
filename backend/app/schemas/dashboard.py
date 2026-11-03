import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.enums import ResumeType
from app.schemas.roadmap import RoadmapItem, RoadmapTotals
from app.schemas.target_role import TargetRoleSummary

NextActionKind = Literal[
    "create_resume",
    "choose_role",
    "continue_skill",
    "close_gap",
    "prove_skill",
    "run_ats",
    "improve_ats",
    "all_set",
]


class NextAction(BaseModel):
    """The single most useful thing to do next. Rule-based, never AI."""

    kind: NextActionKind
    title: str
    detail: str
    resume_id: uuid.UUID | None = None
    skill_id: uuid.UUID | None = None
    skill_slug: str | None = None


class ScorePoint(BaseModel):
    at: datetime
    score: int


class DashboardResume(BaseModel):
    id: uuid.UUID
    title: str
    type: ResumeType
    target_role: TargetRoleSummary | None
    ats_score: int | None
    readiness: int | None  # None without a target role
    updated_at: datetime
    ats_history: list[ScorePoint]  # oldest first
    readiness_history: list[ScorePoint]  # oldest first, current target role only


class DashboardSummary(BaseModel):
    """Home screen. The roadmap part is for the most recently edited resume with a target role."""

    resume_id: uuid.UUID | None
    resume_title: str | None
    role: TargetRoleSummary | None
    readiness: int | None
    ats_score: int | None
    totals: RoadmapTotals | None
    next_up: RoadmapItem | None
    next_action: NextAction
    resumes: list[DashboardResume]  # most recently edited first
    resume_count: int
