import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import PydanticJSONB
from app.schemas.ats import AtsReport

if TYPE_CHECKING:
    from app.models.resume import Resume


class ATSAnalysis(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ats_analyses"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        Index("ix_ats_analyses_resume_id_created_at", "resume_id", "created_at"),
    )

    resume_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    job_description: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    report: Mapped[AtsReport] = mapped_column(PydanticJSONB(AtsReport), nullable=False)

    resume: Mapped["Resume"] = relationship(back_populates="ats_analyses", lazy="raise")
