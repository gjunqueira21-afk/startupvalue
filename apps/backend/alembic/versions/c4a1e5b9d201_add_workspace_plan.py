"""Add commercial plan tier to workspaces."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4a1e5b9d201"
down_revision: str | None = "d9673a8e2b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "plan")
