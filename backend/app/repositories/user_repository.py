import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email.lower()))

    async def get_by_github_id(self, github_id: int) -> User | None:
        return await self.session.scalar(select(User).where(User.github_id == github_id))

    async def get_by_google_id(self, subject: str) -> User | None:
        return await self.session.scalar(select(User).where(User.google_id == subject))

    async def get_by_linkedin_id(self, subject: str) -> User | None:
        return await self.session.scalar(select(User).where(User.linkedin_id == subject))

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
