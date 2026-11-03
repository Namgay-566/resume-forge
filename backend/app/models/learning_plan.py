import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import PydanticJSONB
from app.models._enum import pg_enum
from app.models.enums import PlanStatus
from app.schemas.project_idea import ProjectIdea


class LearningPlanItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's progress on closing one skill gap. Per user + skill, so it carries across
    resumes and roles."""

    __tablename__ = "learning_plan_items"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)
    __mapper_args__ = {"eager_defaults": True}

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[PlanStatus] = mapped_column(
        pg_enum(PlanStatus, "plan_status"), nullable=False, default=PlanStatus.NOT_STARTED
    )
    # Cached AI project idea (null until the user asks for one).
    project: Mapped[ProjectIdea | None] = mapped_column(PydanticJSONB(ProjectIdea))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
