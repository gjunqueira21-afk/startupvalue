"""Report branding (white label) storage and API.

Reuses the SQLite + CSRF fixture pattern established in
test_entitlements.py / test_entitlement_enforcement.py, and the
two-TestClient tenancy pattern from test_api_tenancy.py.
"""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import hash_password
from app.core.entitlements import PlanTier, set_workspace_plan
from app.db.base import Base, get_db
from app.db.models import Role, User, WorkspaceMembership
from app.main import app

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
GIF_MAGIC = b"GIF89a"
PASSWORD = "correct-horse-battery-staple"


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
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def two_clients() -> Iterator[tuple[TestClient, TestClient, sessionmaker[Session]]]:
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
    with TestClient(app) as first, TestClient(app) as second:
        yield first, second, factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _csrf_headers(client: TestClient) -> dict[str, str]:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _signup(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/signup",
        json={"name": "Founder", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_member(
    factory: sessionmaker[Session], *, workspace_id: str, email: str, role: Role
) -> None:
    with factory() as db:
        user = User(name="Member", email=email, password_hash=hash_password(PASSWORD))
        db.add(user)
        db.flush()
        db.add(WorkspaceMembership(workspace_id=workspace_id, user_id=user.id, role=role))
        db.commit()


def _set_plan(factory: sessionmaker[Session], workspace_id: str, plan: PlanTier) -> None:
    with factory() as db:
        set_workspace_plan(db, workspace_id=workspace_id, plan=plan, actor_id=None)
        db.commit()


def _get_branding(client: TestClient) -> httpx.Response:
    return client.get("/api/v1/workspace/branding")


def _put_branding(client: TestClient, payload: dict[str, object]) -> httpx.Response:
    return client.put(
        "/api/v1/workspace/branding", json=payload, headers=_csrf_headers(client)
    )


def _upload_logo(
    client: TestClient, body: bytes, content_type: str = "image/png"
) -> httpx.Response:
    headers = _csrf_headers(client)
    headers["Content-Type"] = content_type
    return client.post("/api/v1/workspace/branding/logo", content=body, headers=headers)


def _delete_logo(client: TestClient) -> httpx.Response:
    return client.delete("/api/v1/workspace/branding/logo", headers=_csrf_headers(client))


# --- round trip ---------------------------------------------------------


def test_entitled_workspace_put_then_get_round_trip(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "consultor-owner@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)

    put = _put_branding(
        client,
        {
            "firm_name": "  Acme Valuations  ",
            "primary_color": "#1A2B3C",
            "footer_text": "  Confidential draft  ",
        },
    )
    assert put.status_code == 200, put.text
    assert put.json() == {
        "firm_name": "Acme Valuations",
        "primary_color": "#1A2B3C",
        "footer_text": "Confidential draft",
        "has_logo": False,
    }

    get = _get_branding(client)
    assert get.status_code == 200, get.text
    assert get.json() == put.json()


# --- entitlement gating --------------------------------------------------


def test_free_plan_put_is_forbidden(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-owner@example.com")

    response = _put_branding(client, {"firm_name": "Should not persist"})
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "white_label_not_in_plan"


def test_free_plan_get_is_forbidden(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _ = api
    _signup(client, "free-owner-get@example.com")

    response = _get_branding(client)
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "white_label_not_in_plan"


# --- role gating -----------------------------------------------------------


def test_analyst_role_is_forbidden(
    two_clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    owner_client, analyst_client, factory = two_clients
    owner_session = _signup(owner_client, "analyst-owner@example.com")
    workspace_id = str(owner_session["workspace_id"])
    _set_plan(factory, workspace_id, PlanTier.consultor)
    _add_member(
        factory, workspace_id=workspace_id, email="analyst-member@example.com", role=Role.analyst
    )
    _login(analyst_client, "analyst-member@example.com")

    response = _put_branding(analyst_client, {"firm_name": "Should not persist"})
    assert response.status_code == 403, response.text


# --- cross-tenant isolation --------------------------------------------------


def test_cross_tenant_isolation(
    two_clients: tuple[TestClient, TestClient, sessionmaker[Session]],
) -> None:
    workspace_a, workspace_b, factory = two_clients
    session_a = _signup(workspace_a, "tenant-a@example.com")
    session_b = _signup(workspace_b, "tenant-b@example.com")
    _set_plan(factory, str(session_a["workspace_id"]), PlanTier.consultor)
    _set_plan(factory, str(session_b["workspace_id"]), PlanTier.consultor)

    put_a = _put_branding(
        workspace_a,
        {"firm_name": "Tenant A Firm", "primary_color": "#112233", "footer_text": "A only"},
    )
    assert put_a.status_code == 200, put_a.text

    get_b = _get_branding(workspace_b)
    assert get_b.status_code == 200, get_b.text
    assert get_b.json() == {
        "firm_name": None,
        "primary_color": None,
        "footer_text": None,
        "has_logo": False,
    }

    get_a = _get_branding(workspace_a)
    assert get_a.status_code == 200, get_a.text
    assert get_a.json()["firm_name"] == "Tenant A Firm"


# --- logo upload validation --------------------------------------------------


def test_png_upload_sets_has_logo_true(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "logo-owner@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)

    upload = _upload_logo(client, PNG_MAGIC + b"\x00" * 128, content_type="image/png")
    assert upload.status_code == 200, upload.text
    assert upload.json()["has_logo"] is True

    get = _get_branding(client)
    assert get.status_code == 200, get.text
    assert get.json()["has_logo"] is True


def test_oversized_upload_is_rejected(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "logo-oversize@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)

    oversized = PNG_MAGIC + b"\x00" * (1_048_576 + 1)
    upload = _upload_logo(client, oversized, content_type="image/png")
    assert upload.status_code == 413, upload.text
    assert upload.json()["detail"] == "logo_too_large"


def test_mismatched_magic_bytes_rejected_despite_claimed_content_type(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "logo-spoofed@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)

    spoofed = GIF_MAGIC + b"\x00" * 64
    upload = _upload_logo(client, spoofed, content_type="image/png")
    assert upload.status_code == 422, upload.text
    assert upload.json()["detail"] == "logo_format_unsupported"


def test_delete_logo_clears_fields(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "logo-delete@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)

    upload = _upload_logo(client, PNG_MAGIC + b"\x00" * 32)
    assert upload.status_code == 200, upload.text

    delete = _delete_logo(client)
    assert delete.status_code == 200, delete.text
    assert delete.json()["has_logo"] is False

    get = _get_branding(client)
    assert get.json()["has_logo"] is False


# --- field validation --------------------------------------------------------


def test_invalid_hex_color_is_rejected(
    api: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, factory = api
    session = _signup(client, "bad-color@example.com")
    _set_plan(factory, str(session["workspace_id"]), PlanTier.consultor)

    response = _put_branding(client, {"primary_color": "verde"})
    assert response.status_code == 422, response.text
