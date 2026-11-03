import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.ai.client import AIClient, get_ai_client
from app.ai.rate_limit import try_consume_ai_budget
from app.api.ai_errors import ai_http_errors
from app.api.deps import CurrentUser, SessionDep
from app.models import TargetRole
from app.schemas.target_role import (
    CustomRoleCreate,
    CustomRoleResult,
    IndustryRead,
    RoleSkillRead,
    TargetRoleDetail,
    TargetRoleRead,
)
from app.services.target_role_service import (
    AIBudgetExhaustedError,
    NotAJobTitleError,
    TargetRoleNotFoundError,
    TargetRoleService,
    UnknownIndustryError,
)

router = APIRouter(prefix="/target-roles", tags=["target roles"])
industries_router = APIRouter(prefix="/industries", tags=["target roles"])

AIDep = Annotated[AIClient, Depends(get_ai_client)]


def _detail(role: TargetRole) -> TargetRoleDetail:
    skills = sorted(role.role_skills, key=lambda rs: -rs.weight)
    return TargetRoleDetail.model_validate(
        {
            **TargetRoleRead.model_validate(role).model_dump(),
            "skills": [
                RoleSkillRead(name=rs.skill.name, importance=rs.importance) for rs in skills
            ],
        }
    )


@industries_router.get("", response_model=list[IndustryRead])
async def list_industries(_: CurrentUser, session: SessionDep) -> list[IndustryRead]:
    industries = await TargetRoleService(session).list_industries()
    return [IndustryRead.model_validate(i) for i in industries]


@router.get("", response_model=list[TargetRoleRead])
async def list_target_roles(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=80)] = None,
    industry: Annotated[str | None, Query(max_length=64)] = None,
) -> list[TargetRoleRead]:
    """Curated roles plus the caller's own AI-generated ones. `q` matches the title,
    `industry` is an industry slug."""
    roles = await TargetRoleService(session).list_roles(user, q=q, industry=industry)
    return [TargetRoleRead.model_validate(role) for role in roles]


@router.get("/{role_id}", response_model=TargetRoleDetail)
async def get_target_role(
    role_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> TargetRoleDetail:
    try:
        return _detail(await TargetRoleService(session).get_role(user, role_id))
    except TargetRoleNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target role not found") from exc


@router.post("/custom", response_model=CustomRoleResult)
async def create_custom_role(
    request: Request, body: CustomRoleCreate, user: CurrentUser, session: SessionDep, ai: AIDep
) -> CustomRoleResult:
    """A role for a job title that isn't in the library. The AI drafts its required skills;
    the role is saved as ai_generated and visible only to you. If the title already exists,
    that role is returned instead and no AI budget is spent."""
    try:
        with ai_http_errors("custom-role"):
            role, created = await TargetRoleService(session, ai).create_custom_role(
                user, body, consume_ai_budget=lambda: try_consume_ai_budget(request)
            )
    except UnknownIndustryError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown industry") from exc
    except NotAJobTitleError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "That doesn't look like a job title. Try the title as it appears in job ads.",
        ) from exc
    except AIBudgetExhaustedError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "You've reached the limit for AI features. Please try again later.",
        ) from exc
    return CustomRoleResult(role=_detail(role), created=created)
