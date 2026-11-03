import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.models._enum import pg_enum
from app.models.enums import ExperienceLevel, PageSize, ResumeTemplate, ResumeType, Spelling

if TYPE_CHECKING:
    from app.models.proof import Proof
    from app.models.refresh_token import RefreshToken
    from app.models.resume import Resume
    from app.models.skill import UserSkill


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"

    # Stored lowercased by the service layer.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    # Null for accounts created via OAuth.
    hashed_password: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # GitHub's numeric user id is stable; the username can be changed by the user.
    github_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    github_username: Mapped[str | None] = mapped_column(String(39))
    # OpenID Connect subject ids ("sub"): stable per account at Google and LinkedIn.
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    linkedin_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Public LinkedIn profile URL, when known. New resumes start with it in profile_links.
    linkedin_url: Mapped[str | None] = mapped_column(String(200))

    # Access tokens issued before this are refused ("sign out everywhere", password change).
    sessions_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- preferences (Settings page) -----------------------------------------------------
    # What a new resume starts with when the create request doesn't say.
    default_resume_type: Mapped[ResumeType] = mapped_column(
        pg_enum(ResumeType, "resume_type"),
        nullable=False,
        default=ResumeType.RESUME,
        server_default=ResumeType.RESUME.value,
    )
    default_experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        pg_enum(ExperienceLevel, "experience_level")
    )
    # Null: the template recommended for the resume's field.
    default_template: Mapped[ResumeTemplate | None] = mapped_column(
        pg_enum(ResumeTemplate, "resume_template")
    )
    page_size: Mapped[PageSize] = mapped_column(
        pg_enum(PageSize, "page_size"),
        nullable=False,
        default=PageSize.A4,
        server_default=PageSize.A4.value,
    )
    # Null: no preference; the AI follows the spelling already used in the resume.
    spelling: Mapped[Spelling | None] = mapped_column(pg_enum(Spelling, "spelling"))
    # Email me when a proof is verified, needs more, or a referee answers.
    email_proof_updates: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    @property
    def has_password(self) -> bool:
        return self.hashed_password is not None

    @property
    def github_connected(self) -> bool:
        return self.github_id is not None

    @property
    def google_connected(self) -> bool:
        return self.google_id is not None

    @property
    def linkedin_connected(self) -> bool:
        return self.linkedin_id is not None

    @property
    def sign_in_methods(self) -> int:
        """Password plus connected providers. Settings never lets this drop to zero."""
        return sum(
            (
                self.has_password,
                self.github_connected,
                self.google_connected,
                self.linkedin_connected,
            )
        )

    resumes: Mapped[list["Resume"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    skills: Mapped[list["UserSkill"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    proofs: Mapped[list["Proof"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )


class EmailChangeRequest(CreatedAtMixin, Base):
    """A pending change of sign-in email: a 6-digit code was sent to the new address.
    One per user; a new request replaces the old one."""

    __tablename__ = "email_change_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    new_email: Mapped[str] = mapped_column(String(320), nullable=False)
    # HMAC of the code, like employment checks (a bare hash of 6 digits is easily reversed).
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
