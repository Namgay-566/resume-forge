import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models._enum import pg_enum
from app.models.enums import ResourceType

if TYPE_CHECKING:
    from app.models.skill import Skill


class LearningResource(UUIDPrimaryKeyMixin, Base):
    """Curated resources. Recommendations may only ever come from this table."""

    __tablename__ = "learning_resources"
    __table_args__ = (
        # Also serves lookups by skill_id (leftmost column).
        UniqueConstraint("skill_id", "url"),
        CheckConstraint("est_hours > 0", name="est_hours_positive"),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    type: Mapped[ResourceType] = mapped_column(
        pg_enum(ResourceType, "resource_type"), nullable=False
    )
    # e.g. "beginner", "intermediate", "advanced".
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    est_hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))

    skill: Mapped["Skill"] = relationship(back_populates="learning_resources", lazy="raise")
