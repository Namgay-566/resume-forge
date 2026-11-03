"""Verification that doesn't depend on public code: referee confirmations (one-time links
to a named referee) and employer email checks (a code sent to a work address)."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import PydanticJSONB
from app.schemas.referee import RefereeAnswers, RefereeClaim

if TYPE_CHECKING:
    from app.models.proof import Proof


class RefereeRequest(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "referee_requests"

    proof_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proofs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # sha256 of the one-time token; the token itself only ever exists in the email.
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    referee_name: Mapped[str] = mapped_column(String(120), nullable=False)
    referee_role: Mapped[str] = mapped_column(String(120), nullable=False)
    referee_organization: Mapped[str] = mapped_column(String(200), nullable=False)
    referee_email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    email_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_kind: Mapped[str] = mapped_column(String(16), nullable=False)  # company | free
    domain_matches_organization: Mapped[bool] = mapped_column(Boolean, nullable=False)
    claim: Mapped[RefereeClaim] = mapped_column(PydanticJSONB(RefereeClaim), nullable=False)
    # sent | confirmed | declined | expired | failed (the email couldn't be sent)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="sent")
    sent_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Never returned to the candidate.
    answers: Mapped[RefereeAnswers | None] = mapped_column(PydanticJSONB(RefereeAnswers))
    decline_reason: Mapped[str | None] = mapped_column(String(32))

    proof: Mapped["Proof"] = relationship(lazy="raise")


class EmailSuppression(CreatedAtMixin, Base):
    """Addresses that asked never to be emailed again (stored as a hash)."""

    __tablename__ = "email_suppressions"

    email_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)


class EmploymentEmailCheck(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The user proved they can read mail at a work address at `company`."""

    __tablename__ = "employment_email_checks"
    __table_args__ = (UniqueConstraint("user_id", "email", "company"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    email_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_matches_company: Mapped[bool] = mapped_column(Boolean, nullable=False)
    code_hash: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
