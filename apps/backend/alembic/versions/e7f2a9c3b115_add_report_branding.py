"""Add per-workspace report branding (white label).

Revision ID: e7f2a9c3b115
Revises: c4a1e5b9d201
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f2a9c3b115"
down_revision: str | None = "c4a1e5b9d201"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_branding",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("firm_name", sa.String(length=120), nullable=True),
        sa.Column("primary_color", sa.String(length=7), nullable=True),
        sa.Column("footer_text", sa.String(length=300), nullable=True),
        sa.Column("logo_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("logo_media_type", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_report_branding_workspace_id", "report_branding", ["workspace_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_report_branding_workspace_id", table_name="report_branding")
    op.drop_table("report_branding")
