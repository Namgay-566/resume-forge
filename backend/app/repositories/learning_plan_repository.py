import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LearningPlanItem


class LearningPlanRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def for_user(self, user_id: uuid.UUID) -> dict[uuid.UUID, LearningPlanItem]:
        rows = await self.session.scalars(
            select(LearningPlanItem).where(LearningPlanItem.user_id == user_id)
        )
        return {row.skill_id: row for row in rows}

    async def get_or_create(self, user_id: uuid.UUID, skill_id: uuid.UUID) -> LearningPlanItem:
        item = await self.session.scalar(
            select(LearningPlanItem).where(
                LearningPlanItem.user_id == user_id, LearningPlanItem.skill_id == skill_id
            )
        )
        if item is None:
            item = LearningPlanItem(user_id=user_id, skill_id=skill_id)
            self.session.add(item)
            await self.session.flush()
        return item
