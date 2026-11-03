import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.models.enums import ExperienceLevel, ResumeType
from app.schemas.resume_sections import SectionCatalogRead, SectionSuggestions
from app.services.sections.catalog import get_catalog
from app.services.sections.layout import section_requirements
from app.services.sections.service import RoleNotVisibleError, SectionService

router = APIRouter(prefix="/resume-sections", tags=["resume sections"])


@router.get("", response_model=SectionCatalogRead)
async def section_catalog(_: CurrentUser) -> SectionCatalogRead:
    """Every section kind: its standard heading, editor field labels and hints."""
    catalog = get_catalog()
    return SectionCatalogRead(kinds=catalog.kinds, profile_links=catalog.profile_links)


@router.get("/suggestions", response_model=SectionSuggestions)
async def section_suggestions(
    user: CurrentUser,
    session: SessionDep,
    target_role_id: uuid.UUID | None = None,
    experience_level: ExperienceLevel | None = None,
    type: Annotated[ResumeType, Query()] = ResumeType.RESUME,
) -> SectionSuggestions:
    """Sections to show for this role, career stage and document type, in order."""
    try:
        layout, role = await SectionService(session).suggest(
            user, role_id=target_role_id, level=experience_level, resume_type=type
        )
    except RoleNotVisibleError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Target role not found") from exc
    required = [k for r in section_requirements(experience_level, role) for k in r.kinds[:1]]
    return SectionSuggestions(
        sections=layout, required=required, role_name=role.role_name if role else None
    )
