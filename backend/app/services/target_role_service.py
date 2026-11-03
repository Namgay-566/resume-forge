"""Target roles: the curated library, plus roles the AI drafts from a job title a user typed."""

import re
import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import AIClient
from app.ai.role_profile import RoleProfile, RoleProfileSkill, draft_role_profile
from app.models import Industry, RoleSkill, Skill, TargetRole, User
from app.models.enums import ContentSource, SkillImportance
from app.repositories.skill_repository import SkillRepository
from app.repositories.target_role_repository import (
    IndustryRepository,
    SkillGroupRepository,
    TargetRoleRepository,
)
from app.schemas.target_role import CustomRoleCreate
from app.services.proofs.rules import get_rules

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_SPACES = re.compile(r"\s+")
_RANK = {SkillImportance.CRITICAL: 0, SkillImportance.IMPORTANT: 1, SkillImportance.NICE_TO_HAVE: 2}


class TargetRoleNotFoundError(Exception):
    pass


class UnknownIndustryError(Exception):
    pass


class NotAJobTitleError(Exception):
    """The AI judged the typed text not to be a job (gibberish, an instruction...)."""


class AIBudgetExhaustedError(Exception):
    """The user's shared AI budget is used up (reported as 429 like other AI endpoints)."""


def slugify(text: str, max_length: int = 80) -> str:
    return _NON_SLUG.sub("-", text.lower()).strip("-")[:max_length].strip("-") or "role"


def alias(text: str) -> str:
    return _SPACES.sub(" ", text.strip().lower())


class TargetRoleService:
    def __init__(self, session: AsyncSession, ai: AIClient | None = None) -> None:
        self.session = session
        self.ai = ai
        self.roles = TargetRoleRepository(session)
        self.industries = IndustryRepository(session)
        self.skills = SkillRepository(session)

    async def list_industries(self) -> list[Industry]:
        return await self.industries.list_all()

    async def list_roles(
        self, user: User, *, q: str | None = None, industry: str | None = None
    ) -> list[TargetRole]:
        return await self.roles.list_visible(user.id, q=q, industry=industry)

    async def get_role(self, user: User, role_id: uuid.UUID) -> TargetRole:
        role = await self.roles.get_visible(role_id, user.id)
        if role is None:
            raise TargetRoleNotFoundError
        return role

    async def create_custom_role(
        self, user: User, body: CustomRoleCreate, *, consume_ai_budget: Callable[[], bool]
    ) -> tuple[TargetRole, bool]:
        """Returns (role, created). A title that matches a role the user can already see
        returns that role without calling the AI."""
        if existing := await self.roles.find_by_title(body.title, user.id):
            return await self.get_role(user, existing.id), False

        industries = await self.industries.list_all()
        by_slug = {i.slug: i for i in industries}
        if body.industry is not None and body.industry not in by_slug:
            raise UnknownIndustryError

        assert self.ai is not None, "create_custom_role needs an AI client"
        if not consume_ai_budget():
            raise AIBudgetExhaustedError
        profile = await draft_role_profile(
            self.ai,
            title=body.title,
            industries=[(i.slug, i.name) for i in industries],
            industry_hint=body.industry,
        )
        if not profile.is_job_title:
            raise NotAJobTitleError

        # The AI may have tidied the title into one that exists ("rn" -> "Registered Nurse").
        if profile.name.lower() != body.title.lower() and (
            existing := await self.roles.find_by_title(profile.name, user.id)
        ):
            return await self.get_role(user, existing.id), False

        role = await self._save(user, profile, by_slug[profile.industry])
        await self.session.commit()
        return await self.get_role(user, role.id), True

    async def _save(self, user: User, profile: RoleProfile, industry: Industry) -> TargetRole:
        role = await self.roles.add(
            TargetRole(
                name=profile.name,
                slug=await self._unique_role_slug(profile.name),
                seniority=profile.seniority,
                description=profile.description.strip(),
                industry_id=industry.id,
                source=ContentSource.AI_GENERATED,
                created_by_user_id=user.id,
            )
        )
        # Several AI skills can land on one catalog skill ("CPR", "First Aid"): keep the
        # most important mention.
        importance: dict[uuid.UUID, SkillImportance] = {}
        for item in profile.skills:
            skill = await self._catalog_skill(item, industry)
            current = importance.get(skill.id)
            if current is None or _RANK[item.importance] < _RANK[current]:
                importance[skill.id] = item.importance
        for skill_id, level in importance.items():
            self.session.add(
                RoleSkill(
                    role_id=role.id,
                    skill_id=skill_id,
                    importance=level,
                    weight=level.default_weight,
                )
            )
        await self.session.flush()
        return role

    async def _catalog_skill(self, item: RoleProfileSkill, industry: Industry) -> Skill:
        """The existing skill this AI skill names (by name or alias), or a new AI-generated
        skill. Reusing catalog skills keeps learning resources and verification working."""
        terms = list(dict.fromkeys(alias(t) for t in [item.name, *item.aliases] if t.strip()))
        matches = await self.skills.find_by_aliases(terms)
        if matches:
            # Prefer a match on the name itself, then curated skills.
            name = alias(item.name)
            matches.sort(
                key=lambda s: (name not in s.aliases, s.source is not ContentSource.CURATED)
            )
            return matches[0]
        group = await SkillGroupRepository(self.session).for_category(industry.id, item.category)
        base = f"ai-{slugify(item.name, 100)}"
        taken = await self.skills.slugs_taken([base])
        slug = base if not taken else f"{base}-{uuid.uuid4().hex[:6]}"
        return await self.skills.add(
            Skill(
                slug=slug,
                name=" ".join(item.name.split()),
                category=item.category,
                aliases=terms,
                source=ContentSource.AI_GENERATED,
                proof_types=[
                    t.value
                    for t in get_rules().proof_types(
                        slug=slug, category=item.category, industry=industry.slug
                    )
                ],
                group_id=group.id if group else None,
            )
        )

    async def _unique_role_slug(self, name: str) -> str:
        base = f"custom-{slugify(name)}"
        while True:
            slug = f"{base}-{uuid.uuid4().hex[:8]}"
            if not await self.roles.slug_taken(slug):
                return slug
