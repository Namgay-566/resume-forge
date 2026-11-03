"""Account settings: preferences, sign-out-everywhere and email change requests.

Revision ID: 4522f1263b84
Revises: b92bf4a1e1df
Create Date: 2026-09-30 01:15:16.200761

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4522f1263b84"
down_revision: str | None = "b92bf4a1e1df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Types that already exist (resumes use them) and two new ones.
RESUME_TYPE = postgresql.ENUM(name="resume_type", create_type=False)
EXPERIENCE_LEVEL = postgresql.ENUM(name="experience_level", create_type=False)
RESUME_TEMPLATE = postgresql.ENUM(name="resume_template", create_type=False)
PAGE_SIZE = postgresql.ENUM("a4", "letter", name="page_size")
SPELLING = postgresql.ENUM("en_us", "en_gb", name="spelling")


def upgrade() -> None:
    PAGE_SIZE.create(op.get_bind())
    SPELLING.create(op.get_bind())
    op.create_table(
        "email_change_requests",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("new_email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("sent_count", sa.SmallInteger(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_change_requests_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_email_change_requests")),
    )
    op.add_column(
        "users", sa.Column("sessions_revoked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("default_resume_type", RESUME_TYPE, server_default="resume", nullable=False),
    )
    op.add_column("users", sa.Column("default_experience_level", EXPERIENCE_LEVEL, nullable=True))
    op.add_column("users", sa.Column("default_template", RESUME_TEMPLATE, nullable=True))
    op.add_column(
        "users", sa.Column("page_size", PAGE_SIZE, server_default="a4", nullable=False)
    )
    op.add_column("users", sa.Column("spelling", SPELLING, nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "email_proof_updates", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "email_proof_updates")
    op.drop_column("users", "spelling")
    op.drop_column("users", "page_size")
    op.drop_column("users", "default_template")
    op.drop_column("users", "default_experience_level")
    op.drop_column("users", "default_resume_type")
    op.drop_column("users", "sessions_revoked_at")
    op.drop_table("email_change_requests")
    SPELLING.drop(op.get_bind())
    PAGE_SIZE.drop(op.get_bind())
