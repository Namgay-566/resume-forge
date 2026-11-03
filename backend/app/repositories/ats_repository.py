import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ATSAnalysis


class AtsAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, analysis: ATSAnalysis) -> ATSAnalysis:
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def latest_two(self, resume_id: uuid.UUID) -> list[ATSAnalysis]:
        return list(
            await self.session.scalars(
                select(ATSAnalysis)
                .where(ATSAnalysis.resume_id == resume_id)
                .order_by(ATSAnalysis.created_at.desc())
                .limit(2)
            )
        )

    async def latest_for_resume(self, resume_id: uuid.UUID) -> ATSAnalysis | None:
        return await self.session.scalar(
            select(ATSAnalysis)
            .where(ATSAnalysis.resume_id == resume_id)
            .order_by(ATSAnalysis.created_at.desc())
            .limit(1)
        )
