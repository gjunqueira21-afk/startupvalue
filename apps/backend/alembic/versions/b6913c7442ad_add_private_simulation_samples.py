"""Store private scenario vectors for Decision Intelligence.

Revision ID: b6913c7442ad
Revises: 8f4e0f8781c7
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6913c7442ad"
down_revision: str | None = "8f4e0f8781c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_samples",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("simulation_result_id", sa.String(length=36), nullable=False),
        sa.Column("format_version", sa.String(length=32), nullable=False),
        sa.Column("factor_names", sa.JSON(), nullable=False),
        sa.Column("scenario_count", sa.Integer(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["simulation_result_id"], ["simulation_results.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("simulation_result_id"),
    )
    op.create_index("ix_simulation_samples_workspace_id", "simulation_samples", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_simulation_samples_workspace_id", table_name="simulation_samples")
    op.drop_table("simulation_samples")
