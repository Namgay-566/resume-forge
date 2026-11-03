import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient
from app.models import Resume, User
from app.models.enums import PlanStatus
from app.repositories.resume_repository import ResumeRepository
from app.repositories.score_history_repository import ScoreHistoryRepository
from app.schemas.dashboard import DashboardResume, DashboardSummary, ScorePoint
from app.schemas.roadmap import Roadmap, RoadmapItem
from app.schemas.target_role import TargetRoleSummary
from app.services.dashboard.next_action import next_action
from app.services.roadmap.service import RoadmapService

MAX_RESUMES = 12  # cards on the home screen; the rest are on My Resumes
HISTORY_POINTS = 30


def _never() -> bool:
    return False


class DashboardService:
    """Home screen summary. Never calls the AI: inferred skills come from cache only."""

    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.resumes = ResumeRepository(session)
        self.history = ScoreHistoryRepository(session)
        self.roadmaps = RoadmapService(session, ai)

    async def summary(self, user: User) -> DashboardSummary:
        resumes = await self.resumes.list_for_user(user.id)  # most recently edited first
        shown = resumes[:MAX_RESUMES]
        current = next((r for r in resumes if r.target_role_id), None)

        roadmap: Roadmap | None = None
        if current is not None:
            roadmap = await self.roadmaps.roadmap(
                user, current.id, consume_ai_budget=_never, allow_ai=False
            )
        readiness: dict[uuid.UUID, int] = (
            {current.id: roadmap.readiness} if current and roadmap else {}
        )
        for r in shown:
            if r.target_role_id and r.id not in readiness:
                report = await self.roadmaps.gaps.report(
                    user, r.id, consume_ai_budget=_never, allow_ai=False
                )
                readiness[r.id] = report.readiness

        # Read after the reports above, which record a point whenever readiness changed.
        ats = await self.history.ats_history([r.id for r in shown], HISTORY_POINTS)
        ready = await self.history.readiness_history(
            [(r.id, r.target_role_id) for r in shown if r.target_role_id], HISTORY_POINTS
        )
        cards = [
            DashboardResume(
                id=r.id,
                title=r.title,
                type=r.type,
                target_role=TargetRoleSummary.model_validate(r.target_role)
                if r.target_role
                else None,
                ats_score=r.ats_score,
                readiness=readiness.get(r.id),
                updated_at=r.updated_at,
                ats_history=_points(ats.get(r.id, [])),
                readiness_history=_points(ready.get(r.id, [])),
            )
            for r in shown
        ]
        focus = current or _first(resumes)
        return DashboardSummary(
            resume_id=focus.id if focus else None,
            resume_title=focus.title if focus else None,
            role=roadmap.role if roadmap else None,
            readiness=roadmap.readiness if roadmap else None,
            ats_score=focus.ats_score if focus else None,
            totals=roadmap.totals if roadmap else None,
            next_up=_next_up(roadmap),
            next_action=next_action(_first(resumes), current, roadmap),
            resumes=cards,
            resume_count=len(resumes),
        )


def _first(resumes: list[Resume]) -> Resume | None:
    return resumes[0] if resumes else None


def _next_up(roadmap: Roadmap | None) -> RoadmapItem | None:
    if roadmap is None:
        return None
    return next(
        (i for i in roadmap.items if i.plan_status is PlanStatus.IN_PROGRESS),
        next((i for i in roadmap.items if i.plan_status is PlanStatus.NOT_STARTED), None),
    )


def _points(rows: list[tuple[datetime, int]]) -> list[ScorePoint]:
    return [ScorePoint(at=at, score=score) for at, score in rows]
