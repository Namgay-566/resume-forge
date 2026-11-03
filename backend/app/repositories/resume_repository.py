import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Resume


class ResumeRepository:
    """Every read is scoped to an owner, so callers cannot fetch another user's resume."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[Resume]:
        result = await self.session.scalars(
            select(Resume)
            .where(Resume.user_id == user_id)
            .options(joinedload(Resume.target_role))
            .order_by(Resume.updated_at.desc())
        )
        return list(result)

    async def get_for_user(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume | None:
        return await self.session.scalar(
            select(Resume)
            .where(Resume.id == resume_id, Resume.user_id == user_id)
            .options(joinedload(Resume.target_role))
            # Reload after writes so updated_at and target_role reflect the database.
            .execution_options(populate_existing=True)
        )

    async def add(self, resume: Resume) -> Resume:
        self.session.add(resume)
        await self.session.flush()
        return resume

    async def delete(self, resume: Resume) -> None:
        await self.session.delete(resume)
