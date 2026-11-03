import uuid

from sqlalchemy import ForeignKey, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class SkillGroup(UUIDPrimaryKeyMixin, Base):
    """How a field groups its skills on the Skill Gap page ("Clinical skills", "Prospecting &
    pipeline"...). Industry groups belong to an industry; shared ones (soft skills,
    credentials) have none."""

    __tablename__ = "skill_groups"

    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    industry_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("industries.id", ondelete="CASCADE"), index=True
    )
    # Generic skill categories this group takes by default, e.g. ["clinical"]: how skills
    # the seed doesn't place explicitly (and AI-generated ones) find a group.
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )
