import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models._enum import pg_enum
from app.models.enums import ContentSource, SkillImportance

if TYPE_CHECKING:
    from app.models.industry import Industry
    from app.models.skill import Skill


class TargetRole(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "target_roles"
    __table_args__ = (Index("ix_target_roles_source_created_by", "source", "created_by_user_id"),)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # e.g. "junior", "mid", "senior".
    seniority: Mapped[str] = mapped_column(String(32), nullable=False)
    industry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("industries.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    # Curated roles come from the seed files. AI-generated ones are made from a job title a
    # user typed; they're visible only to that user until someone reviews them.
    source: Mapped[ContentSource] = mapped_column(
        pg_enum(ContentSource, "content_source"), nullable=False, default=ContentSource.CURATED
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # Resume sections for this role (SectionKind values). Empty: use the industry's.
    default_sections: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )
    required_sections: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )

    industry: Mapped["Industry"] = relationship(back_populates="roles", lazy="raise")

    role_skills: Mapped[list["RoleSkill"]] = relationship(
        back_populates="role", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )


class RoleSkill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "role_skills"
    __table_args__ = (
        # Also serves lookups by role_id (leftmost column).
        UniqueConstraint("role_id", "skill_id"),
        CheckConstraint("weight BETWEEN 1 AND 10", name="weight_range"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("target_roles.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    importance: Mapped[SkillImportance] = mapped_column(
        pg_enum(SkillImportance, "skill_importance"), nullable=False
    )
    weight: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)

    role: Mapped[TargetRole] = relationship(back_populates="role_skills", lazy="raise")
    skill: Mapped["Skill"] = relationship(lazy="raise")
