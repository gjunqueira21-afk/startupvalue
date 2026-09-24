from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import IssuedToken, hash_password, hash_token, issue_token, verify_password
from app.core.config import get_settings
from app.db.models import Role, User, UserSession, Workspace, WorkspaceMembership

SESSION_COOKIE = get_settings().session_cookie_name


def session_lifetime() -> timedelta:
    return timedelta(hours=get_settings().session_lifetime_hours)


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class CurrentActor:
    user_id: str
    workspace_id: str
    role: Role
    name: str
    email: str
    session_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CreatedSession:
    actor: CurrentActor
    token: IssuedToken


def _new_session(
    db: Session, *, user: User, workspace_id: str, role: Role
) -> CreatedSession:
    token = issue_token()
    expires_at = datetime.now(UTC) + session_lifetime()
    session = UserSession(
        user_id=user.id,
        workspace_id=workspace_id,
        token_digest=token.digest,
        expires_at=expires_at,
    )
    db.add(session)
    db.flush()
    return CreatedSession(
        CurrentActor(
            user_id=user.id,
            workspace_id=workspace_id,
            role=role,
            name=user.name,
            email=user.email,
            session_id=session.id,
            expires_at=expires_at,
        ),
        token,
    )


def signup(
    db: Session, *, name: str, email: str, password: str, workspace_name: str | None
) -> CreatedSession:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AuthenticationError("email_already_registered")
    user = User(name=name.strip(), email=email, password_hash=hash_password(password))
    workspace = Workspace(name=(workspace_name or f"{name.strip()} Workspace").strip())
    db.add_all((user, workspace))
    db.flush()
    membership = WorkspaceMembership(
        workspace_id=workspace.id, user_id=user.id, role=Role.owner
    )
    db.add(membership)
    db.flush()
    return _new_session(db, user=user, workspace_id=workspace.id, role=membership.role)


def login(db: Session, *, email: str, password: str) -> CreatedSession:
    user = db.scalar(select(User).where(User.email == email))
    if (
        user is None
        or user.disabled_at is not None
        or not verify_password(user.password_hash, password)
    ):
        raise AuthenticationError("invalid_credentials")
    membership = db.scalar(
        select(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == user.id)
        .order_by(WorkspaceMembership.created_at, WorkspaceMembership.id)
    )
    if membership is None:
        raise AuthenticationError("workspace_membership_missing")
    return _new_session(
        db, user=user, workspace_id=membership.workspace_id, role=membership.role
    )


def authenticate(db: Session, plain_token: str) -> CurrentActor | None:
    row = db.execute(
        select(UserSession, User, WorkspaceMembership)
        .join(User, User.id == UserSession.user_id)
        .join(
            WorkspaceMembership,
            (WorkspaceMembership.user_id == UserSession.user_id)
            & (WorkspaceMembership.workspace_id == UserSession.workspace_id),
        )
        .where(
            UserSession.token_digest == hash_token(plain_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
            User.disabled_at.is_(None),
        )
    ).one_or_none()
    if row is None:
        return None
    session, user, membership = row._tuple()
    return CurrentActor(
        user_id=user.id,
        workspace_id=session.workspace_id,
        role=membership.role,
        name=user.name,
        email=user.email,
        session_id=session.id,
        expires_at=session.expires_at,
    )


def revoke(db: Session, session_id: str) -> None:
    session = db.get(UserSession, session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
