import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, SmallInteger, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import PydanticJSONB
from app.models._enum import pg_enum
from app.models.enums import ProofStatus, ProofType
from app.schemas.proof_report import ProofReport

if TYPE_CHECKING:
    from app.models.skill import Skill
    from app.models.user import User

# Join table rather than an array so every skill reference is FK-checked.
proof_skills = Table(
    "proof_skills",
    Base.metadata,
    Column("proof_id", ForeignKey("proofs.id", ondelete="CASCADE"), primary_key=True),
    Column("skill_id", ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Proof(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "proofs"
    __table_args__ = (
        # Referee confirmations have neither: the referee's answer is the evidence.
        CheckConstraint(
            "url IS NOT NULL OR file_path IS NOT NULL OR type::text = 'referee_confirmation'",
            name="url_or_file",
        ),
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        Index("ix_proofs_user_id_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[ProofType] = mapped_column(pg_enum(ProofType, "proof_type"), nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048))
    file_path: Mapped[str | None] = mapped_column(String(1024))
    status: Mapped[ProofStatus] = mapped_column(
        pg_enum(ProofStatus, "proof_status"), nullable=False, default=ProofStatus.PENDING
    )
    # Null until the AI review has run.
    # Live links can point at the GitHub proof for the same project.
    linked_proof_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("proofs.id", ondelete="SET NULL")
    )
    ai_report: Mapped[ProofReport | None] = mapped_column(PydanticJSONB(ProofReport))
    score: Mapped[int | None] = mapped_column(SmallInteger)
    # Which step a running analysis is on (see services/proofs/service.py STAGES); null otherwise.
    progress: Mapped[str | None] = mapped_column(String(20))

    user: Mapped["User"] = relationship(back_populates="proofs", lazy="raise")
    skills: Mapped[list["Skill"]] = relationship(secondary=proof_skills, lazy="raise")
