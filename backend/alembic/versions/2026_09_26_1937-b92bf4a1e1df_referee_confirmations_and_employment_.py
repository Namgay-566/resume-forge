"""Referee confirmations and employment email checks.

Adds the referee_confirmation proof type and the awaiting_response status, and lets a
referee proof have neither a URL nor a file.

Revision ID: b92bf4a1e1df
Revises: 9dd3cfb85735
Create Date: 2026-09-26 19:37:05.835967

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b92bf4a1e1df"
down_revision: str | None = "9dd3cfb85735"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


URL_OR_FILE = "url IS NOT NULL OR file_path IS NOT NULL"


def upgrade() -> None:
    # PostgreSQL allows ADD VALUE in a transaction as long as the value isn't used in it
    # (the constraint below compares text, not the new enum value).
    op.execute("ALTER TYPE proof_type ADD VALUE IF NOT EXISTS 'referee_confirmation'")
    op.execute("ALTER TYPE proof_status ADD VALUE IF NOT EXISTS 'awaiting_response'")
    op.drop_constraint(op.f("ck_proofs_url_or_file"), "proofs", type_="check")
    op.create_check_constraint(
        op.f("ck_proofs_url_or_file"),
        "proofs",
        f"{URL_OR_FILE} OR type::text = 'referee_confirmation'",
    )
    op.create_table(
        "email_suppressions",
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("email_hash", name=op.f("pk_email_suppressions")),
    )
    op.create_table(
        "employment_email_checks",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_domain", sa.String(length=255), nullable=False),
        sa.Column("domain_matches_company", sa.Boolean(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("sent_count", sa.SmallInteger(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_employment_email_checks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employment_email_checks")),
        sa.UniqueConstraint(
            "user_id",
            "email",
            "company",
            name=op.f("uq_employment_email_checks_user_id_email_company"),
        ),
    )
    op.create_index(
        op.f("ix_employment_email_checks_user_id"),
        "employment_email_checks",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "referee_requests",
        sa.Column("proof_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("referee_name", sa.String(length=120), nullable=False),
        sa.Column("referee_role", sa.String(length=120), nullable=False),
        sa.Column("referee_organization", sa.String(length=200), nullable=False),
        sa.Column("referee_email", sa.String(length=320), nullable=False),
        sa.Column("email_domain", sa.String(length=255), nullable=False),
        sa.Column("domain_kind", sa.String(length=16), nullable=False),
        sa.Column("domain_matches_organization", sa.Boolean(), nullable=False),
        sa.Column("claim", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("sent_count", sa.SmallInteger(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decline_reason", sa.String(length=32), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["proof_id"],
            ["proofs.id"],
            name=op.f("fk_referee_requests_proof_id_proofs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_referee_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_referee_requests")),
        sa.UniqueConstraint("proof_id", name=op.f("uq_referee_requests_proof_id")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_referee_requests_token_hash")),
    )
    op.create_index(
        op.f("ix_referee_requests_referee_email"),
        "referee_requests",
        ["referee_email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_referee_requests_user_id"), "referee_requests", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_referee_requests_user_id"), table_name="referee_requests")
    op.drop_index(op.f("ix_referee_requests_referee_email"), table_name="referee_requests")
    op.drop_table("referee_requests")
    op.drop_index(op.f("ix_employment_email_checks_user_id"), table_name="employment_email_checks")
    op.drop_table("employment_email_checks")
    op.drop_table("email_suppressions")
    # Enum values can't be dropped in PostgreSQL; they stay unused. Referee proofs go.
    op.execute("DELETE FROM proofs WHERE type::text = 'referee_confirmation'")
    op.execute("UPDATE proofs SET status = 'needs_more' WHERE status::text = 'awaiting_response'")
    op.drop_constraint(op.f("ck_proofs_url_or_file"), "proofs", type_="check")
    op.create_check_constraint(op.f("ck_proofs_url_or_file"), "proofs", URL_OR_FILE)
