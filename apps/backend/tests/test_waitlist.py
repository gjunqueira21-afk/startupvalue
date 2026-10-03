"""Public waitlist capture endpoint.

Reuses the SQLite TestClient fixture pattern from test_branding_api.py. The
waitlist route has no ``Actor`` dependency (no auth cookie required) and the
in-process IP rate limiter is module state in ``app.api.routes.waitlist``,
so it is cleared around every test for isolation.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import waitlist as waitlist_routes
from app.db.base import Base, get_db
from app.db.models import WaitlistEntry
from app.main import app


@pytest.fixture
def api() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    waitlist_routes.clear_rate_limiter_for_tests()
    with TestClient(app) as client:
        yield client, factory
    waitlist_routes.clear_rate_limiter_for_tests()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _join(
    client: TestClient, email: str, plan_interest: str = "free", source: str = "landing"
) -> object:
    return client.post(
        "/api/v1/waitlist",
        json={"email": email, "plan_interest": plan_interest, "source": source},
    )


def test_join_waitlist_creates_entry(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    response = _join(client, "founder@example.com")
    assert response.status_code == 201, response.text
    assert response.json() == {"status": "ok"}

    with factory() as db:
        rows = db.scalars(select(WaitlistEntry)).all()
        assert len(rows) == 1
        assert rows[0].email == "founder@example.com"
        assert rows[0].plan_interest == "free"
        assert rows[0].source == "landing"


def test_repeat_email_is_idempotent_case_and_whitespace_insensitive(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    first = _join(client, " User@X.com ", plan_interest="free")
    assert first.status_code == 201, first.text

    second = _join(client, "user@x.com", plan_interest="empresario")
    assert second.status_code == 200, second.text
    assert second.json() == {"status": "ok"}

    with factory() as db:
        rows = db.scalars(select(WaitlistEntry)).all()
        assert len(rows) == 1
        assert rows[0].email == "user@x.com"
        assert rows[0].plan_interest == "empresario"


def test_invalid_email_is_rejected(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    response = _join(client, "not-an-email")
    assert response.status_code == 422, response.text


def test_unknown_plan_interest_is_rejected(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    response = _join(client, "someone@example.com", plan_interest="enterprise")
    assert response.status_code == 422, response.text


def test_eleventh_rapid_request_is_rate_limited(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    for index in range(10):
        response = _join(client, f"rate-{index}@example.com")
        assert response.status_code == 201, response.text

    eleventh = _join(client, "rate-11@example.com")
    assert eleventh.status_code == 429, eleventh.text
    assert eleventh.json()["detail"] == "waitlist_rate_limited"


def test_endpoint_works_without_auth_cookie(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    assert not client.cookies
    response = _join(client, "no-cookie@example.com")
    assert response.status_code == 201, response.text


# --- fix-report regression coverage -----------------------------------------


def test_concurrent_duplicate_insert_falls_back_to_idempotent_update(
    api: tuple[TestClient, sessionmaker[Session]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TOCTOU: another request's row lands between our existence check and
    our own insert's commit. The handler must catch the resulting
    IntegrityError and fall back to the idempotent update path (200, one
    row) instead of letting it bubble up as a 500.

    Simulated deterministically: the conflicting row is seeded directly, and
    ``Session.scalar`` is patched to miss it on exactly the handler's first
    lookup (its pre-insert existence check), so the handler proceeds to
    INSERT and collides with the unique index on ``email``.
    """
    client, factory = api
    email = "race@example.com"

    with factory() as seed_db:
        seed_db.add(WaitlistEntry(email=email, plan_interest="free", source="seed"))
        seed_db.commit()

    original_scalar = Session.scalar
    calls = {"n": 0}

    def fake_scalar(self: Session, statement: object, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return original_scalar(self, statement, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Session, "scalar", fake_scalar)

    response = _join(client, email, plan_interest="empresario")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert calls["n"] == 2  # the missed pre-check, then the post-IntegrityError re-fetch

    with factory() as db:
        rows = db.scalars(select(WaitlistEntry)).all()
        assert len(rows) == 1
        assert rows[0].email == email
        assert rows[0].plan_interest == "empresario"


def test_rate_limiter_evicts_stale_ip_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    waitlist_routes.clear_rate_limiter_for_tests()
    try:
        fake_now = [1_000.0]
        monkeypatch.setattr(waitlist_routes.time, "monotonic", lambda: fake_now[0])

        assert waitlist_routes._rate_limited("1.1.1.1") is False
        assert "1.1.1.1" in waitlist_routes._requests_by_ip

        fake_now[0] += waitlist_routes._WINDOW_SECONDS + 1
        assert waitlist_routes._rate_limited("2.2.2.2") is False

        assert "1.1.1.1" not in waitlist_routes._requests_by_ip
        assert "2.2.2.2" in waitlist_routes._requests_by_ip
    finally:
        waitlist_routes.clear_rate_limiter_for_tests()


def test_malformed_payload_flood_is_rate_limited(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    """A 422-triggering body must still be throttled: rate limiting is wired
    as a route dependency so it runs before pydantic validates the body.
    """
    client, _ = api
    for _ in range(10):
        response = client.post(
            "/api/v1/waitlist",
            json={"email": "not-an-email", "plan_interest": "free", "source": "x"},
        )
        assert response.status_code == 422, response.text

    eleventh = client.post(
        "/api/v1/waitlist",
        json={"email": "not-an-email", "plan_interest": "free", "source": "x"},
    )
    assert eleventh.status_code == 429, eleventh.text
    assert eleventh.json()["detail"] == "waitlist_rate_limited"
