import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import PlanStatus, ProofType, SkillImportance
from app.schemas.learning import LearningResourceRead
from app.schemas.project_idea import ProjectIdea
from app.schemas.skill_gap import SkillStatus
from app.schemas.target_role import TargetRoleSummary


class ProofRequirement(BaseModel):
    """What to upload so the skill can be verified. Deterministic, not AI."""

    # Best first; must_include describes the first.
    accepted: list[ProofType]
    must_include: list[str]


class Hours(BaseModel):
    learn: float
    project: float
    total: float


class RoadmapItem(BaseModel):
    skill_id: uuid.UUID
    name: str
    slug: str
    category: str
    importance: SkillImportance
    weight: int
    gap_status: SkillStatus  # from the skill gap engine
    plan_status: PlanStatus  # set by the user
    resources: list[LearningResourceRead]
    # When `resources` is empty: a phrase to search for (no invented links).
    search_phrase: str
    proof: ProofRequirement
    project: ProjectIdea | None
    hours: Hours


class RoadmapTotals(BaseModel):
    items: int
    done: int
    in_progress: int
    hours_total: float
    hours_remaining: float


class Roadmap(BaseModel):
    resume_id: uuid.UUID
    role: TargetRoleSummary
    readiness: int
    items: list[RoadmapItem]
    totals: RoadmapTotals


class PlanStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PlanStatus


class PlanItemRead(BaseModel):
    skill_id: uuid.UUID
    status: PlanStatus
    updated_at: datetime
