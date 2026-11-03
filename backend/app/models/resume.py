import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import PydanticJSONB
from app.models._enum import pg_enum
from app.models.enums import ExperienceLevel, ResumeTemplate, ResumeType
from app.schemas.resume_data import ResumeData

if TYPE_CHECKING:
    from app.models.ats_analysis import ATSAnalysis
    from app.models.target_role import TargetRole
    from app.models.user import User


class Resume(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint("ats_score BETWEEN 0 AND 100", name="ats_score_range"),
        Index("ix_resumes_user_id_updated_at", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[ResumeType] = mapped_column(
        pg_enum(ResumeType, "resume_type"), nullable=False, default=ResumeType.RESUME
    )
    target_role_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("target_roles.id", ondelete="SET NULL"), index=True
    )
    # Null until the user says; scoring then falls back to what the resume shows.
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        pg_enum(ExperienceLevel, "experience_level")
    )
    template: Mapped[ResumeTemplate] = mapped_column(
        pg_enum(ResumeTemplate, "resume_template"),
        nullable=False,
        default=ResumeTemplate.CLASSIC,
    )
    data: Mapped[ResumeData] = mapped_column(
        PydanticJSONB(ResumeData), nullable=False, default=ResumeData
    )
    ats_score: Mapped[int | None] = mapped_column(SmallInteger)
    # Proof suggestions the user dismissed for this resume (ids like "skill:<uuid>").
    dismissed_suggestions: Mapped[list[str]] = mapped_column(
        ARRAY(String(80)), nullable=False, default=list, server_default=text("'{}'")
    )

    user: Mapped["User"] = relationship(back_populates="resumes", lazy="raise")
    target_role: Mapped["TargetRole | None"] = relationship(lazy="raise")
    ats_analyses: Mapped[list["ATSAnalysis"]] = relationship(
        back_populates="resume", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
