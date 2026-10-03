"""Regression test for the SQLite platform-admin storage corruption bug.

On a SQLite database upgraded via the original
``a9c4d2e8f106_add_platform_admin_flag`` migration (before it was fixed),
``ALTER TABLE users ADD COLUMN is_platform_admin ... server_default='false'``
backfilled the literal TEXT string ``'false'`` into every pre-existing row.
SQLAlchemy's ``Boolean`` type reads any non-empty string -- including the
text ``'false'`` -- as ``True``, so every pre-existing user silently became
a platform admin. PostgreSQL is unaffected because its server casts the
default to a real boolean.

This test simulates that corruption directly against a SQLite session,
then applies the same normalization SQL as the
``b2e6f1a9c307_normalize_platform_admin_storage`` migration and asserts
the ORM reads the flag correctly afterward, and that the raw stored value
is a real integer (0/1), not a string.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import User

NORMALIZE_SQL = (
    "UPDATE users SET is_platform_admin = "
    "CASE WHEN is_platform_admin IN (1, '1', 'true', 'TRUE') "
    "THEN 1 ELSE 0 END"
)


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield maker
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _raw_typeof(db: Session, user_id: str) -> str:
    row = db.execute(
        sa.text("SELECT typeof(is_platform_admin) FROM users WHERE id = :id"),
        {"id": user_id},
    ).first()
    assert row is not None
    return row[0]


def test_sqlite_text_false_is_misread_as_true_by_the_orm(
    factory: sessionmaker[Session],
) -> None:
    """Confirms the corruption this migration fixes actually occurs."""
    with factory() as db:
        user = User(name="Pre-existing", email="pre@example.com", password_hash="x")
        db.add(user)
        db.commit()
        user_id = user.id

        # Simulate the pre-fix migration's TEXT backfill: SQLite stores the
        # literal string 'false', not a boolean.
        db.execute(
            sa.text("UPDATE users SET is_platform_admin = 'false' WHERE id = :id"),
            {"id": user_id},
        )
        db.commit()

    with factory() as db:
        assert _raw_typeof(db, user_id) == "text"
        reloaded = db.get(User, user_id)
        assert reloaded is not None
        # This is the bug: a non-empty string is truthy to SQLAlchemy's
        # Boolean type, so the corrupted row misreads as an admin.
        assert reloaded.is_platform_admin is True


def test_normalization_sql_repairs_corrupted_rows(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        user = User(name="Pre-existing", email="pre2@example.com", password_hash="x")
        db.add(user)
        db.commit()
        user_id = user.id

        db.execute(
            sa.text("UPDATE users SET is_platform_admin = 'false' WHERE id = :id"),
            {"id": user_id},
        )
        db.commit()

        # Apply the same normalization the migration runs.
        db.execute(sa.text(NORMALIZE_SQL))
        db.commit()

    with factory() as db:
        assert _raw_typeof(db, user_id) == "integer"
        reloaded = db.get(User, user_id)
        assert reloaded is not None
        assert reloaded.is_platform_admin is False


def test_normalization_sql_preserves_true_admin_rows(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        user = User(name="Real admin", email="admin@example.com", password_hash="x")
        db.add(user)
        db.commit()
        user_id = user.id

        db.execute(
            sa.text("UPDATE users SET is_platform_admin = 'true' WHERE id = :id"),
            {"id": user_id},
        )
        db.commit()

        db.execute(sa.text(NORMALIZE_SQL))
        db.commit()

    with factory() as db:
        assert _raw_typeof(db, user_id) == "integer"
        reloaded = db.get(User, user_id)
        assert reloaded is not None
        assert reloaded.is_platform_admin is True


def test_fresh_orm_created_user_reads_false_and_stores_integer(
    factory: sessionmaker[Session],
) -> None:
    with factory() as db:
        user = User(name="New user", email="new@example.com", password_hash="x")
        db.add(user)
        db.commit()
        user_id = user.id

    with factory() as db:
        assert _raw_typeof(db, user_id) == "integer"
        reloaded = db.get(User, user_id)
        assert reloaded is not None
        assert reloaded.is_platform_admin is False
