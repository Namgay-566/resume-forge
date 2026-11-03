import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models._enum import pg_enum
from app.models.enums import ContentSource, UserSkillSource, VerificationStatus

if TYPE_CHECKING:
    from app.models.learning_resource import LearningResource
    from app.models.skill_group import SkillGroup
    from app.models.user import User


class Skill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        # Supports `aliases @> ARRAY['github']` / `&&` matching during gap analysis.
        Index("ix_skills_aliases", "aliases", postgresql_using="gin"),
    )

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # e.g. "soft_skill", "license", "certification", "tool", "clinical", "language".
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # AI-generated skills come from custom role profiles and await review.
    source: Mapped[ContentSource] = mapped_column(
        pg_enum(ContentSource, "content_source"), nullable=False, default=ContentSource.CURATED
    )
    # Lowercase alternative spellings, e.g. ["git", "github", "version control"].
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(String(120)), nullable=False, default=list, server_default=text("'{}'")
    )
    # Proof types that suit this skill, best first (ProofType values), from the proof rules.
    proof_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, default=list, server_default=text("'{}'")
    )
    # The field-specific category it's shown under ("Clinical skills", "Credentials"...).
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skill_groups.id", ondelete="SET NULL"), index=True
    )
    group: Mapped["SkillGroup | None"] = relationship(lazy="raise")

    learning_resources: Mapped[list["LearningResource"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )


class UserSkill(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[UserSkillSource] = mapped_column(
        pg_enum(UserSkillSource, "user_skill_source"), nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        pg_enum(VerificationStatus, "verification_status"),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="skills", lazy="raise")
    skill: Mapped[Skill] = relationship(lazy="raise")
