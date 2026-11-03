import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ATSAnalysis, ReadinessSnapshot


class ScoreHistoryRepository:
    """ATS and readiness scores over time, fetched for many resumes in one query each."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def latest_readiness(self, resume_id: uuid.UUID) -> ReadinessSnapshot | None:
        return await self.session.scalar(
            select(ReadinessSnapshot)
            .where(ReadinessSnapshot.resume_id == resume_id)
            .order_by(ReadinessSnapshot.created_at.desc())
            .limit(1)
        )

    async def add_readiness(self, snapshot: ReadinessSnapshot) -> None:
        self.session.add(snapshot)
        await self.session.flush()

    async def ats_history(
        self, resume_ids: Sequence[uuid.UUID], limit: int
    ) -> dict[uuid.UUID, list[tuple[datetime, int]]]:
        """The last `limit` ATS scores per resume, oldest first."""
        if not resume_ids:
            return {}
        rank = (
            func.row_number()
            .over(partition_by=ATSAnalysis.resume_id, order_by=ATSAnalysis.created_at.desc())
            .label("rank")
        )
        inner = (
            select(ATSAnalysis.resume_id, ATSAnalysis.created_at, ATSAnalysis.score, rank)
            .where(ATSAnalysis.resume_id.in_(resume_ids))
            .subquery()
        )
        rows = await self.session.execute(
            select(inner.c.resume_id, inner.c.created_at, inner.c.score)
            .where(inner.c.rank <= limit)
            .order_by(inner.c.created_at)
        )
        return _group(rows.tuples())

    async def readiness_history(
        self, resumes: Sequence[tuple[uuid.UUID, uuid.UUID]], limit: int
    ) -> dict[uuid.UUID, list[tuple[datetime, int]]]:
        """The last `limit` readiness scores per (resume, current target role), oldest first.
        Points from a previous target role are left out: they measured a different job."""
        if not resumes:
            return {}
        role_of = dict(resumes)
        rank = (
            func.row_number()
            .over(
                partition_by=ReadinessSnapshot.resume_id,
                order_by=ReadinessSnapshot.created_at.desc(),
            )
            .label("rank")
        )
        inner = (
            select(
                ReadinessSnapshot.resume_id,
                ReadinessSnapshot.target_role_id,
                ReadinessSnapshot.created_at,
                ReadinessSnapshot.score,
                rank,
            )
            .where(ReadinessSnapshot.resume_id.in_(role_of))
            .subquery()
        )
        rows = await self.session.execute(
            select(inner.c.resume_id, inner.c.target_role_id, inner.c.created_at, inner.c.score)
            .where(inner.c.rank <= limit)
            .order_by(inner.c.created_at)
        )
        return _group(
            (rid, at, score) for rid, role, at, score in rows.tuples() if role_of[rid] == role
        )


def _group(
    rows: Iterable[tuple[uuid.UUID, datetime, int]],
) -> dict[uuid.UUID, list[tuple[datetime, int]]]:
    out: dict[uuid.UUID, list[tuple[datetime, int]]] = defaultdict(list)
    for resume_id, at, score in rows:
        out[resume_id].append((at, score))
    return dict(out)
