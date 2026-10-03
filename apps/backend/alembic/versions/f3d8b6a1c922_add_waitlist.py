"""Add public waitlist entries.

Revision ID: f3d8b6a1c922
Revises: e7f2a9c3b115
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3d8b6a1c922"
down_revision: str | None = "e7f2a9c3b115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("plan_interest", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_waitlist_entries_email", "waitlist_entries", ["email"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_waitlist_entries_email", table_name="waitlist_entries")
    op.drop_table("waitlist_entries")
