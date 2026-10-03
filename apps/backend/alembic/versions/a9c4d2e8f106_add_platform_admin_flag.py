"""Add platform admin flag to users.

Revision ID: a9c4d2e8f106
Revises: f3d8b6a1c922
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9c4d2e8f106"
down_revision: str | None = "f3d8b6a1c922"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_platform_admin")
