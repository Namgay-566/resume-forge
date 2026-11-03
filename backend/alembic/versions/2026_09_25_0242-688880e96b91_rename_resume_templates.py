"""rename resume templates

Revision ID: 688880e96b91
Revises: 231ec12fb65c
Create Date: 2026-09-25 02:42:28.637261

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "688880e96b91"
down_revision: str | None = "231ec12fb65c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RENAMES = [("modern", "modern_minimal"), ("minimal", "compact")]


def upgrade() -> None:
    # Renaming keeps existing rows valid; autogenerate cannot detect enum value changes.
    for old, new in RENAMES:
        op.execute(f"ALTER TYPE resume_template RENAME VALUE '{old}' TO '{new}'")


def downgrade() -> None:
    for old, new in RENAMES:
        op.execute(f"ALTER TYPE resume_template RENAME VALUE '{new}' TO '{old}'")
