"""Section suggestions and requirements for a resume's target role."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.enums import ExperienceLevel, ResumeType, SkillImportance
from app.repositories.target_role_repository import TargetRoleRepository
from app.schemas.section_kind import SectionKind
from app.services.sections.catalog import get_catalog
from app.services.sections.layout import RoleSections, suggest_layout


class RoleNotVisibleError(Exception):
    pass


def _kinds(values: list[str]) -> tuple[SectionKind, ...]:
    # Unknown values (a kind removed from the catalog) are skipped rather than failing.
    return tuple(SectionKind(v) for v in values if v in SectionKind._value2member_map_)


class SectionService:
    def __init__(self, session: AsyncSession) -> None:
        self.roles = TargetRoleRepository(session)

    async def role_sections(self, role_id: uuid.UUID | None) -> RoleSections | None:
        """The role's own layout, else its industry's. A role that critically needs a
        licence or certificate also requires the Licenses & Certifications section."""
        if role_id is None:
            return None
        role = await self.roles.get_with_industry(role_id)
        if role is None:
            return None
        required = [*_kinds(role.industry.required_sections), *_kinds(role.required_sections)]
        licence_categories = set(get_catalog().licence_skill_categories)
        if any(
            rs.importance is SkillImportance.CRITICAL and rs.skill.category in licence_categories
            for rs in await self.roles.role_skills(role.id)
        ):
            required.append(SectionKind.CERTIFICATIONS)
        return RoleSections(
            role_name=role.name,
            layout=_kinds(role.default_sections) or _kinds(role.industry.default_sections),
            required=tuple(dict.fromkeys(required)),
        )

    async def suggest(
        self,
        user: User,
        *,
        role_id: uuid.UUID | None,
        level: ExperienceLevel | None,
        resume_type: ResumeType,
    ) -> tuple[list[SectionKind], RoleSections | None]:
        if role_id is not None and not await self.roles.is_visible(role_id, user.id):
            raise RoleNotVisibleError
        role = await self.role_sections(role_id)
        return suggest_layout(resume_type, level, role), role
