import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient
from app.ai.context import CandidateContext
from app.ai.project_ideas import generate_project_idea
from app.models import LearningPlanItem, LearningResource, User
from app.models.enums import PlanStatus
from app.repositories.learning_plan_repository import LearningPlanRepository
from app.repositories.resume_repository import ResumeRepository
from app.repositories.skill_repository import SkillRepository
from app.schemas.learning import LearningResourceRead
from app.schemas.project_idea import ProjectIdea
from app.schemas.roadmap import (
    Hours,
    Roadmap,
    RoadmapItem,
    RoadmapTotals,
)
from app.schemas.skill_gap import RoleSkillGap, SkillGapReport
from app.services.candidate_context import candidate_context
from app.services.learning import search_phrase
from app.services.roadmap.proof_requirements import proof_requirement
from app.services.skill_gap.service import SkillGapService

# Used when we have no better estimate (no resources listed / no project yet).
DEFAULT_LEARN_HOURS = 6.0
DEFAULT_PROJECT_HOURS = 8.0


class SkillNotInRoadmapError(Exception):
    pass


class AIBudgetExhaustedError(Exception):
    """The user's shared AI budget is used up (reported as 429 like other AI endpoints)."""


def learn_hours(gap: RoleSkillGap, resources: list[LearningResource]) -> float:
    """Missing skills need learning first: the starter (first-ranked) resource's hours.
    Skills already on the resume only need proving."""
    if gap.status in ("present_unverified", "present_verified"):
        return 0.0
    starter = next((r for r in resources if r.est_hours is not None), None)
    hours = (
        float(starter.est_hours)
        if starter and starter.est_hours is not None
        else DEFAULT_LEARN_HOURS
    )
    # Very long starter courses (e.g. 300h certifications) would swamp the plan; a small
    # proof project needs far less. Cap the learning estimate.
    return min(hours, 30.0)


def totals(items: list[RoadmapItem]) -> RoadmapTotals:
    total = sum(i.hours.total for i in items)
    remaining = sum(i.hours.total for i in items if i.plan_status is not PlanStatus.DONE)
    return RoadmapTotals(
        items=len(items),
        done=sum(i.plan_status is PlanStatus.DONE for i in items),
        in_progress=sum(i.plan_status is PlanStatus.IN_PROGRESS for i in items),
        hours_total=round(total, 1),
        hours_remaining=round(remaining, 1),
    )


class RoadmapService:
    def __init__(self, session: AsyncSession, ai: AIClient) -> None:
        self.session = session
        self.ai = ai
        self.gaps = SkillGapService(session, ai)
        self.plans = LearningPlanRepository(session)
        self.skills = SkillRepository(session)
        self.resumes = ResumeRepository(session)

    async def roadmap(
        self,
        user: User,
        resume_id: uuid.UUID,
        *,
        consume_ai_budget: Callable[[], bool],
        allow_ai: bool = True,
    ) -> Roadmap:
        report = await self.gaps.report(
            user, resume_id, consume_ai_budget=consume_ai_budget, allow_ai=allow_ai
        )
        return await self._build(user, report)

    async def _build(self, user: User, report: SkillGapReport) -> Roadmap:
        # Everything not yet verified is a gap (skill gap report is already ordered by
        # importance, then weight).
        gaps = [g for g in report.skills if g.status != "present_verified"]
        plans = await self.plans.for_user(user.id)
        resources = await self.skills.learning_resources_for([g.skill_id for g in gaps])

        items = []
        for gap in gaps:
            plan = plans.get(gap.skill_id)
            skill_resources = resources.get(gap.skill_id, [])
            project = plan.project if plan else None
            learn = learn_hours(gap, skill_resources)
            build = float(project.est_hours) if project else DEFAULT_PROJECT_HOURS
            items.append(
                RoadmapItem(
                    skill_id=gap.skill_id,
                    name=gap.name,
                    slug=gap.slug,
                    category=gap.category,
                    importance=gap.importance,
                    weight=gap.weight,
                    gap_status=gap.status,
                    plan_status=plan.status if plan else PlanStatus.NOT_STARTED,
                    resources=[LearningResourceRead.model_validate(r) for r in skill_resources],
                    search_phrase=search_phrase(gap.name, gap.category),
                    proof=proof_requirement(
                        gap.slug, gap.category, gap.name, [t.value for t in gap.proof_types]
                    ),
                    project=project,
                    hours=Hours(learn=learn, project=build, total=round(learn + build, 1)),
                )
            )
        return Roadmap(
            resume_id=report.resume_id,
            role=report.role,
            readiness=report.readiness,
            items=items,
            totals=totals(items),
        )

    async def set_status(
        self, user: User, skill_id: uuid.UUID, status: PlanStatus
    ) -> LearningPlanItem:
        if await self.skills.get(skill_id) is None:
            raise SkillNotInRoadmapError
        item = await self.plans.get_or_create(user.id, skill_id)
        now = datetime.now(UTC)
        if status is PlanStatus.IN_PROGRESS and item.started_at is None:
            item.started_at = now
        item.completed_at = now if status is PlanStatus.DONE else None
        item.status = status
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def project_idea(
        self,
        user: User,
        resume_id: uuid.UUID,
        skill_id: uuid.UUID,
        *,
        regenerate: bool,
        consume_ai_budget: Callable[[], bool],
    ) -> ProjectIdea:
        # Cheap path first: no AI inference needed to know which skills are gaps.
        report = await self.gaps.report(
            user, resume_id, consume_ai_budget=lambda: False, allow_ai=False
        )
        gap = next((g for g in report.skills if g.skill_id == skill_id), None)
        if gap is None:
            raise SkillNotInRoadmapError
        item = await self.plans.get_or_create(user.id, skill_id)
        if item.project and not regenerate and item.project.tailored_for == report.role.name:
            return item.project
        if not consume_ai_budget():
            raise AIBudgetExhaustedError
        known = [
            g.name for g in report.skills if g.status in ("present_verified", "present_unverified")
        ]
        resume = await self.resumes.get_for_user(resume_id, user.id)
        context = (
            await candidate_context(self.session, resume)
            if resume
            else CandidateContext(target_role=report.role.name)
        )
        idea = await generate_project_idea(
            self.ai,
            skill=gap.name,
            slug=gap.slug,
            category=gap.category,
            importance=gap.importance.value,
            context=context,
            already_listed=gap.status == "present_unverified",
            known_skills=known,
            proof_types=gap.proof_types,
        )
        item.project = idea
        await self.session.commit()
        return idea
