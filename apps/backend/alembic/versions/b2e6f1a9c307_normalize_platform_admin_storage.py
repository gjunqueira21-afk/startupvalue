"""Normalize platform admin flag storage on sqlite.

Revision ID: b2e6f1a9c307
Revises: a9c4d2e8f106

On SQLite, the previous migration's ``server_default="false"`` backfilled
the literal TEXT string ``'false'`` into ``users.is_platform_admin`` for
every pre-existing row (SQLite has no real BOOLEAN type; a bare Python
string default is stored as-is). SQLAlchemy's ``Boolean`` type reads any
non-empty string -- including the text ``'false'`` -- as ``True``, so
every user created before that migration ran on a SQLite database silently
became a platform admin.

PostgreSQL is unaffected: its server evaluates ``DEFAULT 'false'`` against
the column's native ``boolean`` type, casting the text to a real boolean.

This migration repairs already-corrupted SQLite databases by rewriting the
column's stored values to real integers (0/1), which is how SQLite's
``Boolean`` type is correctly represented. It is a no-op on every other
dialect, since they were never affected.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2e6f1a9c307"
down_revision: str | None = "a9c4d2e8f106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        # Only SQLite ever stored the literal string 'false' for this
        # column's server default; other dialects cast it to a real
        # boolean at write time and were never corrupted.
        return

    op.execute(
        "UPDATE users SET is_platform_admin = "
        "CASE WHEN is_platform_admin IN (1, '1', 'true', 'TRUE') "
        "THEN 1 ELSE 0 END"
    )


def downgrade() -> None:
    # Pure data normalization; there is nothing meaningful to revert.
    pass
