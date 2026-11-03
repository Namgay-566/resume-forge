import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class ReadinessSnapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Role readiness at a point in time. Readiness is computed on read, so a row is only
    written when the value (or the target role) changes; together they form its history."""

    __tablename__ = "readiness_snapshots"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        Index("ix_readiness_snapshots_resume_id_created_at", "resume_id", "created_at"),
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    target_role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("target_roles.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
