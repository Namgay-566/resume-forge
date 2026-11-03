import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )

    async def delete(self, token: RefreshToken) -> None:
        await self.session.delete(token)

    async def delete_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))

    async def delete_expired_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.expires_at < datetime.now(UTC)
            )
        )
