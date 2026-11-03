import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Proof
from app.models.enums import ProofStatus


class ProofRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, proof: Proof) -> Proof:
        self.session.add(proof)
        await self.session.flush()
        return proof

    async def list_for_user(self, user_id: uuid.UUID) -> list[Proof]:
        return list(
            await self.session.scalars(
                select(Proof)
                .where(Proof.user_id == user_id)
                .options(selectinload(Proof.skills))
                .order_by(Proof.created_at.desc())
            )
        )

    async def verified_for_user(self, user_id: uuid.UUID) -> list[Proof]:
        """The user's verified proofs, oldest first."""
        return list(
            await self.session.scalars(
                select(Proof)
                .where(Proof.user_id == user_id, Proof.status == ProofStatus.VERIFIED)
                .options(selectinload(Proof.skills))
                .order_by(Proof.created_at)
            )
        )

    async def get(self, proof_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Proof | None:
        query = (
            select(Proof)
            .where(Proof.id == proof_id)
            .options(selectinload(Proof.skills), selectinload(Proof.user))
            .execution_options(populate_existing=True)
        )
        if user_id is not None:
            query = query.where(Proof.user_id == user_id)
        return await self.session.scalar(query)
