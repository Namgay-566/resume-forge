import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import try_consume_ai_budget
from app.api.ai_errors import ai_http_errors
from app.api.deps import CurrentUser, SessionDep
from app.schemas.project_idea import ProjectIdea
from app.schemas.roadmap import PlanItemRead, PlanStatusUpdate, Roadmap
from app.services.resume_service import ResumeNotFoundError
from app.services.roadmap.service import (
    AIBudgetExhaustedError,
    RoadmapService,
    SkillNotInRoadmapError,
)
from app.services.skill_gap.service import NoTargetRoleError

router = APIRouter(tags=["roadmap"])

AIDep = Annotated[AIClient, Depends(get_ai_client)]
_NO_ROLE = HTTPException(status.HTTP_409_CONFLICT, "Choose a target role for this resume first.")
_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found")


@router.get("/resumes/{resume_id}/roadmap", response_model=Roadmap)
async def get_roadmap(
    request: Request, resume_id: uuid.UUID, user: CurrentUser, session: SessionDep, ai: AIDep
) -> Roadmap:
    """Every unverified role skill, most important first, with curated resources, proof
    requirements, the saved project idea (if any), hour estimates and the user's progress."""
    try:
        return await RoadmapService(session, ai).roadmap(
            user, resume_id, consume_ai_budget=lambda: try_consume_ai_budget(request)
        )
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
    except NoTargetRoleError as exc:
        raise _NO_ROLE from exc


@router.put("/roadmap/{skill_id}", response_model=PlanItemRead)
async def set_plan_status(
    skill_id: uuid.UUID, body: PlanStatusUpdate, user: CurrentUser, session: SessionDep, ai: AIDep
) -> PlanItemRead:
    """Mark a skill as not started / in progress / done. Stored per user, across resumes."""
    try:
        item = await RoadmapService(session, ai).set_status(user, skill_id, body.status)
    except SkillNotInRoadmapError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found") from exc
    return PlanItemRead(skill_id=item.skill_id, status=item.status, updated_at=item.updated_at)


@router.post("/resumes/{resume_id}/roadmap/{skill_id}/project", response_model=ProjectIdea)
async def project_idea(
    request: Request,
    resume_id: uuid.UUID,
    skill_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    ai: AIDep,
    regenerate: bool = False,
) -> ProjectIdea:
    """AI portfolio-project idea proving this skill for the resume's target role. Saved and
    reused; pass regenerate=true for a new one (counts toward the AI budget)."""
    try:
        with ai_http_errors("project-idea"):
            return await RoadmapService(session, ai).project_idea(
                user,
                resume_id,
                skill_id,
                regenerate=regenerate,
                consume_ai_budget=lambda: try_consume_ai_budget(request),
            )
    except ResumeNotFoundError as exc:
        raise _NOT_FOUND from exc
    except NoTargetRoleError as exc:
        raise _NO_ROLE from exc
    except SkillNotInRoadmapError as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "That skill isn't part of this resume's target role."
        ) from exc
    except AIBudgetExhaustedError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've reached the limit for AI features. Please try again later.",
        ) from exc
