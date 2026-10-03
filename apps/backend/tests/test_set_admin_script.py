"""``scripts/set_admin.py`` normalizes the email the same way signup stores it."""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import User

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "set_admin.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("set_admin_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_grant_and_revoke_match_a_mixed_case_padded_email(
    factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    with factory() as db:
        db.add(User(email="owner@example.com", name="Owner", password_hash="x"))
        db.commit()
    script = _load_script()
    monkeypatch.setattr(script, "SessionLocal", factory)

    assert script.main(["--email", "  Owner@Example.COM ", "--grant"]) == 0
    with factory() as db:
        user = db.query(User).filter_by(email="owner@example.com").one()
        assert user.is_platform_admin is True

    assert script.main(["--email", "OWNER@example.com", "--revoke"]) == 0
    with factory() as db:
        user = db.query(User).filter_by(email="owner@example.com").one()
        assert user.is_platform_admin is False


def test_unknown_email_returns_error(
    factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _load_script()
    monkeypatch.setattr(script, "SessionLocal", factory)

    assert script.main(["--email", "nobody@example.com", "--grant"]) == 1
