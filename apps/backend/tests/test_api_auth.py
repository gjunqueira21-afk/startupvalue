from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.rate_limit import clear_local_for_tests
from app.auth.security import hash_token
from app.db.base import Base, get_db
from app.db.models import PasswordResetToken, UserSession
from app.main import app
from app.services.auth import SESSION_COOKIE


@pytest.fixture
def api() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    clear_local_for_tests()
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
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
    clear_local_for_tests()


def signup(client: TestClient, suffix: str = "one") -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "name": f"Founder {suffix}",
            "email": f"founder-{suffix}@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code == 201, response.text
    csrf = client.get("/api/v1/auth/csrf")
    assert csrf.status_code == 200
    client.headers.update({"X-CSRF-Token": csrf.json()["csrf_token"]})
    return response.json()


def test_signup_stores_only_digest_and_logout_revokes_session(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    body = signup(client)
    set_cookie = client.post(
        "/api/v1/auth/login",
        json={
            "email": "founder-one@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert set_cookie.status_code == 200
    header = set_cookie.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    plain_token = client.cookies[SESSION_COOKIE]
    with factory() as db:
        stored = db.scalar(
            select(UserSession).where(UserSession.token_digest == hash_token(plain_token))
        )
        assert stored is not None
        assert stored.token_digest != plain_token
    assert client.get("/api/v1/auth/me").json()["workspace_id"] == body["workspace_id"]
    client.headers.update({"X-CSRF-Token": client.get("/api/v1/auth/csrf").json()["csrf_token"]})
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_uses_generic_failure_and_duplicate_signup_conflicts(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    signup(client)
    duplicate = client.post(
        "/api/v1/auth/signup",
        json={
            "name": "Someone",
            "email": "FOUNDER-ONE@example.com",
            "password": "another-strong-password",
        },
    )
    assert duplicate.status_code == 409
    failed = client.post(
        "/api/v1/auth/login",
        json={"email": "founder-one@example.com", "password": "wrong"},
    )
    assert failed.status_code == 401
    assert failed.json()["detail"] == "invalid_credentials"


def test_password_policy_is_validated_before_persistence(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Founder", "email": "founder@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_cookie_mutations_require_session_bound_csrf(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    signup(client)
    client.headers.pop("X-CSRF-Token")
    denied = client.post("/api/v1/startups", json={"name": "Denied", "currency": "BRL"})
    assert denied.status_code == 403
    assert denied.json()["detail"] == "invalid_csrf_token"
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    forged = client.post(
        "/api/v1/startups",
        json={"name": "Denied", "currency": "BRL"},
        headers={"X-CSRF-Token": token, "Origin": "https://attacker.example"},
    )
    assert forged.status_code == 403
    assert forged.json()["detail"] == "untrusted_origin"
    accepted = client.post(
        "/api/v1/startups",
        json={"name": "Allowed", "currency": "BRL"},
        headers={"X-CSRF-Token": token, "Origin": "http://localhost:3000"},
    )
    assert accepted.status_code == 201


def test_password_reset_is_single_use_and_revokes_all_sessions(
    api: tuple[TestClient, sessionmaker[Session]], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory = api
    signup(client, "reset")
    session_before = client.cookies[SESSION_COOKIE]
    sent: list[str] = []
    monkeypatch.setattr("app.api.routes.auth.delivery_configured", lambda: True)
    monkeypatch.setattr(
        "app.api.routes.auth.send_reset_email",
        lambda _email, token: sent.append(token) or True,
    )
    known = client.post(
        "/api/v1/auth/forgot-password", json={"email": "founder-reset@example.com"}
    )
    unknown = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(sent) == 1
    with factory() as db:
        stored = db.scalar(select(PasswordResetToken))
        assert stored is not None
        assert stored.token_digest == hash_token(sent[0])
        assert sent[0] not in stored.token_digest

    changed = client.post(
        "/api/v1/auth/reset-password",
        json={"token": sent[0], "password": "brand-new-correct-horse-password"},
    )
    assert changed.status_code == 200, changed.text
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": sent[0], "password": "yet-another-correct-password"},
    ).status_code == 400
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "founder-reset@example.com", "password": "correct-horse-battery-staple"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "founder-reset@example.com", "password": "brand-new-correct-horse-password"},
    ).status_code == 200
    with factory() as db:
        old = db.scalar(
            select(UserSession).where(UserSession.token_digest == hash_token(session_before))
        )
        assert old is not None and old.revoked_at is not None


def test_reset_expiry_and_failed_delivery(
    api: tuple[TestClient, sessionmaker[Session]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta

    client, factory = api
    signup(client, "expiry")
    sent: list[str] = []
    monkeypatch.setattr("app.api.routes.auth.delivery_configured", lambda: True)
    monkeypatch.setattr(
        "app.api.routes.auth.send_reset_email",
        lambda _email, token: sent.append(token) or True,
    )
    assert client.post(
        "/api/v1/auth/forgot-password", json={"email": "founder-expiry@example.com"}
    ).status_code == 202
    with factory() as db:
        stored = db.scalar(select(PasswordResetToken))
        assert stored is not None
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": sent[0], "password": "brand-new-correct-horse-password"},
    ).status_code == 400
    assert client.get("/api/v1/auth/me").status_code == 200

    monkeypatch.setattr("app.api.routes.auth.send_reset_email", lambda _email, _token: False)
    assert client.post(
        "/api/v1/auth/forgot-password", json={"email": "founder-expiry@example.com"}
    ).status_code == 202
    with factory() as db:
        unused = db.scalars(
            select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))
        ).all()
        assert unused == []
