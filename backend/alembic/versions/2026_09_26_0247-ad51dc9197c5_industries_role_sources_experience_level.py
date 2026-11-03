"""industries, role sources, experience level

Revision ID: ad51dc9197c5
Revises: 4004b149e76d
Create Date: 2026-09-26 02:47:00.940622

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ad51dc9197c5"
down_revision: str | None = "4004b149e76d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


content_source = postgresql.ENUM(
    "curated", "ai_generated", name="content_source", create_type=False
)
experience_level = postgresql.ENUM(
    "student",
    "entry",
    "mid",
    "senior",
    "career_changer",
    name="experience_level",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    content_source.create(bind, checkfirst=True)
    experience_level.create(bind, checkfirst=True)

    op.create_table(
        "industries",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_industries")),
        sa.UniqueConstraint("name", name=op.f("uq_industries_name")),
        sa.UniqueConstraint("slug", name=op.f("uq_industries_slug")),
    )
    # Every role existing so far is a tech role; the seed refines names and descriptions.
    op.execute(
        "INSERT INTO industries (slug, name, description, sort_order) "
        "VALUES ('technology', 'Technology', '', 0)"
    )

    op.add_column("resumes", sa.Column("experience_level", experience_level, nullable=True))
    op.add_column(
        "skills",
        sa.Column("source", content_source, nullable=False, server_default="curated"),
    )
    op.add_column("target_roles", sa.Column("industry_id", sa.UUID(), nullable=True))
    op.execute(
        "UPDATE target_roles "
        "SET industry_id = (SELECT id FROM industries WHERE slug = 'technology')"
    )
    op.alter_column("target_roles", "industry_id", nullable=False)
    op.add_column(
        "target_roles",
        sa.Column("source", content_source, nullable=False, server_default="curated"),
    )
    op.add_column("target_roles", sa.Column("created_by_user_id", sa.UUID(), nullable=True))
    op.add_column(
        "target_roles",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_target_roles_industry_id"), "target_roles", ["industry_id"], unique=False
    )
    op.create_index(
        "ix_target_roles_source_created_by",
        "target_roles",
        ["source", "created_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_target_roles_created_by_user_id_users"),
        "target_roles",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_target_roles_industry_id_industries"),
        "target_roles",
        "industries",
        ["industry_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_target_roles_industry_id_industries"), "target_roles", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_target_roles_created_by_user_id_users"), "target_roles", type_="foreignkey"
    )
    op.drop_index("ix_target_roles_source_created_by", table_name="target_roles")
    op.drop_index(op.f("ix_target_roles_industry_id"), table_name="target_roles")
    op.execute("DELETE FROM target_roles WHERE source = 'ai_generated'")
    op.drop_column("target_roles", "created_at")
    op.drop_column("target_roles", "created_by_user_id")
    op.drop_column("target_roles", "source")
    op.drop_column("target_roles", "industry_id")
    op.execute("DELETE FROM skills WHERE source = 'ai_generated'")
    op.drop_column("skills", "source")
    op.drop_column("resumes", "experience_level")
    op.drop_table("industries")
    experience_level.drop(op.get_bind(), checkfirst=True)
    content_source.drop(op.get_bind(), checkfirst=True)
