import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import try_consume_ai_budget
from app.api.deps import CurrentUser, SessionDep
from app.repositories.skill_repository import SkillRepository
from app.schemas.learning import LearningResourceRead, SkillResources
from app.schemas.proof import SkillCatalogItem
from app.schemas.skill_gap import SkillGapReport
from app.services.learning import search_phrase
from app.services.resume_service import ResumeNotFoundError
from app.services.skill_gap.service import NoTargetRoleError, SkillGapService

router = APIRouter(tags=["skill gap"])


@router.get("/resumes/{resume_id}/skill-gap", response_model=SkillGapReport)
async def skill_gap(
    request: Request,
    resume_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    ai: Annotated[AIClient, Depends(get_ai_client)],
) -> SkillGapReport:
    """Compare the resume against its target role's skills.

    AI inference only runs when the resume text changed since the last run, and then counts
    toward the AI budget; if that's used up the report is still returned without inferences.
    """
    try:
        return await SkillGapService(session, ai).report(
            user, resume_id, consume_ai_budget=lambda: try_consume_ai_budget(request)
        )
    except ResumeNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resume not found") from exc
    except NoTargetRoleError as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Choose a target role for this resume first."
        ) from exc


@router.get("/skills/{skill_id}/learning-resources", response_model=SkillResources)
async def learning_resources(
    skill_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> SkillResources:
    """Curated resources for a skill, from the learning_resources table only."""
    repo = SkillRepository(session)
    skill = await repo.get(skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill not found")
    return SkillResources(
        skill_id=skill.id,
        skill_name=skill.name,
        resources=[
            LearningResourceRead.model_validate(r) for r in await repo.learning_resources(skill.id)
        ],
        search_phrase=search_phrase(skill.name, skill.category),
    )


@router.get("/skills", response_model=list[SkillCatalogItem])
async def list_skills(user: CurrentUser, session: SessionDep) -> list[SkillCatalogItem]:
    """The skills catalog (e.g. for choosing which skills a proof covers)."""
    return [SkillCatalogItem.model_validate(s) for s in await SkillRepository(session).list_all()]
