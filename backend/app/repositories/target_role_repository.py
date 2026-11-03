import uuid

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models import Industry, RoleSkill, Skill, SkillGroup, TargetRole
from app.models.enums import ContentSource


def visible_to(user_id: uuid.UUID) -> ColumnElement[bool]:
    """Curated roles, plus AI-generated roles the user created themselves."""
    return or_(
        TargetRole.source == ContentSource.CURATED,
        TargetRole.created_by_user_id == user_id,
    )


class IndustryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Industry]:
        stmt = select(Industry).order_by(Industry.sort_order, Industry.name)
        return list(await self.session.scalars(stmt))


class SkillGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_category(self, industry_id: uuid.UUID, category: str) -> SkillGroup | None:
        """The industry's group for this generic category, else the shared one."""
        return await self.session.scalar(
            select(SkillGroup)
            .where(
                SkillGroup.categories.any(category),
                (SkillGroup.industry_id == industry_id) | SkillGroup.industry_id.is_(None),
            )
            .order_by(SkillGroup.industry_id.is_(None), SkillGroup.sort_order)
            .limit(1)
        )


class TargetRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_visible(
        self, user_id: uuid.UUID, *, q: str | None = None, industry: str | None = None
    ) -> list[TargetRole]:
        stmt = (
            select(TargetRole)
            .join(TargetRole.industry)
            .where(visible_to(user_id))
            .options(joinedload(TargetRole.industry))
            .order_by(Industry.sort_order, TargetRole.name)
        )
        if industry:
            stmt = stmt.where(Industry.slug == industry)
        if q:
            stmt = stmt.where(TargetRole.name.icontains(q, autoescape=True))
        return list(await self.session.scalars(stmt))

    async def get_visible(self, role_id: uuid.UUID, user_id: uuid.UUID) -> TargetRole | None:
        return await self.session.scalar(
            select(TargetRole)
            .where(TargetRole.id == role_id, visible_to(user_id))
            .options(
                joinedload(TargetRole.industry),
                selectinload(TargetRole.role_skills).joinedload(RoleSkill.skill),
            )
        )

    async def find_by_title(self, title: str, user_id: uuid.UUID) -> TargetRole | None:
        """A visible role with this exact title (case-insensitive), curated ones first."""
        return await self.session.scalar(
            select(TargetRole)
            .where(func.lower(TargetRole.name) == title.lower(), visible_to(user_id))
            .order_by(TargetRole.source)  # enum order: curated before ai_generated
            .limit(1)
        )

    async def is_visible(self, role_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        found = await self.session.scalar(
            select(TargetRole.id).where(TargetRole.id == role_id, visible_to(user_id))
        )
        return found is not None

    async def get_with_industry(self, role_id: uuid.UUID) -> TargetRole | None:
        return await self.session.scalar(
            select(TargetRole)
            .where(TargetRole.id == role_id)
            .options(joinedload(TargetRole.industry))
        )

    async def slug_taken(self, slug: str) -> bool:
        found = await self.session.scalar(select(TargetRole.id).where(TargetRole.slug == slug))
        return found is not None

    async def add(self, role: TargetRole) -> TargetRole:
        self.session.add(role)
        await self.session.flush()
        return role

    async def role_skills(self, role_id: uuid.UUID) -> list[RoleSkill]:
        return list(
            await self.session.scalars(
                select(RoleSkill)
                .where(RoleSkill.role_id == role_id)
                .options(joinedload(RoleSkill.skill).joinedload(Skill.group))
                .order_by(RoleSkill.weight.desc())
            )
        )
