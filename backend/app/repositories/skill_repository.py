import uuid

from sqlalchemy import case, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningResource, Skill, UserSkill
from app.models.enums import UserSkillSource, VerificationStatus


class SkillRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Skill]:
        return list(await self.session.scalars(select(Skill).order_by(Skill.name)))

    async def slugs_taken(self, slugs: list[str]) -> set[str]:
        return set(await self.session.scalars(select(Skill.slug).where(Skill.slug.in_(slugs))))

    async def add(self, skill: Skill) -> Skill:
        self.session.add(skill)
        await self.session.flush()
        return skill

    async def find_by_aliases(self, terms: list[str]) -> list[Skill]:
        """Skills whose aliases (lowercase, name included) contain any of the terms."""
        if not terms:
            return []
        return list(await self.session.scalars(select(Skill).where(Skill.aliases.overlap(terms))))

    async def add_user_skills_from_resume(
        self, user_id: uuid.UUID, skill_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Record skills found on a resume. Existing rows (e.g. already verified) are untouched.

        Returns the ids that were newly added.
        """
        if not skill_ids:
            return set()
        stmt = (
            insert(UserSkill)
            .values(
                [
                    {
                        "user_id": user_id,
                        "skill_id": skill_id,
                        "source": UserSkillSource.RESUME,
                        "verification_status": VerificationStatus.UNVERIFIED,
                    }
                    for skill_id in skill_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=[UserSkill.user_id, UserSkill.skill_id])
            .returning(UserSkill.skill_id)
        )
        return set(await self.session.scalars(stmt))

    async def user_skills(self, user_id: uuid.UUID) -> list[UserSkill]:
        return list(
            await self.session.scalars(select(UserSkill).where(UserSkill.user_id == user_id))
        )

    async def get(self, skill_id: uuid.UUID) -> Skill | None:
        return await self.session.get(Skill, skill_id)

    async def learning_resources(self, skill_id: uuid.UUID) -> list[LearningResource]:
        """Curated resources only (CLAUDE.md: recommendations never come from anywhere else).

        Order: free first, then beginner -> intermediate -> advanced, then shortest.
        """
        level_rank = case(
            {"beginner": 0, "intermediate": 1, "advanced": 2}, value=LearningResource.level, else_=3
        )
        return list(
            await self.session.scalars(
                select(LearningResource)
                .where(LearningResource.skill_id == skill_id)
                .order_by(
                    LearningResource.is_free.desc(),
                    level_rank,
                    LearningResource.est_hours.asc().nulls_last(),
                    LearningResource.title,
                )
            )
        )

    async def learning_resources_for(
        self, skill_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[LearningResource]]:
        by_skill: dict[uuid.UUID, list[LearningResource]] = {sid: [] for sid in skill_ids}
        if not skill_ids:
            return by_skill
        level_rank = case(
            {"beginner": 0, "intermediate": 1, "advanced": 2}, value=LearningResource.level, else_=3
        )
        rows = await self.session.scalars(
            select(LearningResource)
            .where(LearningResource.skill_id.in_(skill_ids))
            .order_by(
                LearningResource.is_free.desc(),
                level_rank,
                LearningResource.est_hours.asc().nulls_last(),
                LearningResource.title,
            )
        )
        for row in rows:
            by_skill[row.skill_id].append(row)
        return by_skill
