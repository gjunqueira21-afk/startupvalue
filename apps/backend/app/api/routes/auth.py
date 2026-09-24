from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import Actor, Database
from app.api.schemas import LoginRequest, MessageResponse, SessionResponse, SignupRequest
from app.auth.csrf import token_for_session
from app.auth.rate_limit import RateLimitUnavailable, allow
from app.auth.reset import (
    consume_reset,
    delivery_configured,
    invalidate_reset,
    issue_reset,
    send_reset_email,
)
from app.core.config import get_settings
from app.db.models import User
from app.services import auth as auth_service
from app.services.audit import record_event

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=256)
    password: str = Field(min_length=12, max_length=256)


def _limit(action: str, identity: str, count: int, seconds: int) -> None:
    try:
        accepted = allow(action, identity, limit=count, window_seconds=seconds)
    except RateLimitUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if not accepted:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limit_exceeded")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/csrf")
def csrf(request: Request, actor: Actor) -> dict[str, str]:
    del actor
    session_token = request.cookies.get(auth_service.SESSION_COOKIE)
    if session_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication_required")
    return {"csrf_token": token_for_session(session_token)}


def _session_response(created: auth_service.CreatedSession) -> SessionResponse:
    actor = created.actor
    return SessionResponse(
        user_id=actor.user_id,
        workspace_id=actor.workspace_id,
        name=actor.name,
        email=actor.email,
        role=actor.role.value,
        expires_at=actor.expires_at,
    )


def _set_cookie(response: Response, created: auth_service.CreatedSession) -> None:
    settings = get_settings()
    secure = settings.session_cookie_secure
    if secure is None:
        secure = settings.app_env.lower() in {"production", "staging"}
    response.set_cookie(
        key=auth_service.SESSION_COOKIE,
        value=created.token.plain,
        max_age=int(auth_service.session_lifetime().total_seconds()),
        expires=created.actor.expires_at,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/signup", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: SignupRequest, response: Response, db: Database, request: Request
) -> SessionResponse:
    _limit("signup:ip", _client_ip(request), 5, 3600)
    try:
        created = auth_service.signup(
            db,
            name=payload.name,
            email=payload.email,
            password=payload.password,
            workspace_name=payload.workspace_name,
        )
        record_event(
            db,
            action="auth.signup",
            resource_type="user",
            workspace_id=created.actor.workspace_id,
            actor_id=created.actor.user_id,
            resource_id=created.actor.user_id,
        )
        db.commit()
    except auth_service.AuthenticationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email_already_registered") from exc
    _set_cookie(response, created)
    return _session_response(created)


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest, response: Response, db: Database, request: Request
) -> SessionResponse:
    _limit("login:ip", _client_ip(request), 30, 900)
    _limit("login:account", payload.email, 10, 900)
    try:
        created = auth_service.login(db, email=payload.email, password=payload.password)
        record_event(
            db,
            action="auth.login",
            resource_type="session",
            workspace_id=created.actor.workspace_id,
            actor_id=created.actor.user_id,
            resource_id=created.actor.session_id,
        )
        db.commit()
    except auth_service.AuthenticationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    _set_cookie(response, created)
    return _session_response(created)


@router.post(
    "/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def forgot_password(
    payload: ForgotPasswordRequest, db: Database, request: Request
) -> MessageResponse:
    _limit("forgot:ip", _client_ip(request), 10, 3600)
    # Account throttling is deliberately silent to keep the response identical.
    try:
        account_allowed = allow("forgot:account", payload.email, limit=3, window_seconds=3600)
    except RateLimitUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    if not account_allowed:
        return MessageResponse(message="if_account_exists_email_sent")
    user = db.scalar(select(User).where(User.email == payload.email, User.disabled_at.is_(None)))
    if user is None:
        return MessageResponse(message="if_account_exists_email_sent")
    if not delivery_configured():
        logger.warning("password_reset_delivery_not_configured")
        return MessageResponse(message="if_account_exists_email_sent")
    token = issue_reset(db, user)
    record_event(
        db,
        action="auth.password_reset_requested",
        resource_type="user",
        workspace_id=None,
        actor_id=user.id,
        resource_id=user.id,
    )
    db.commit()
    if not send_reset_email(user.email, token):
        invalidate_reset(db, token)
        db.commit()
    return MessageResponse(message="if_account_exists_email_sent")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest, response: Response, db: Database, request: Request
) -> MessageResponse:
    _limit("reset:ip", _client_ip(request), 20, 3600)
    user = consume_reset(db, payload.token, payload.password)
    if user is None:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_or_expired_reset_link")
    record_event(
        db,
        action="auth.password_reset_completed",
        resource_type="user",
        workspace_id=None,
        actor_id=user.id,
        resource_id=user.id,
    )
    db.commit()
    response.delete_cookie(auth_service.SESSION_COOKIE, path="/")
    return MessageResponse(message="password_reset_complete")


@router.get("/me", response_model=SessionResponse)
def me(actor: Actor) -> SessionResponse:
    return SessionResponse(
        user_id=actor.user_id,
        workspace_id=actor.workspace_id,
        name=actor.name,
        email=actor.email,
        role=actor.role.value,
        expires_at=actor.expires_at,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response, db: Database, actor: Actor) -> MessageResponse:
    auth_service.revoke(db, actor.session_id)
    record_event(
        db,
        action="auth.logout",
        resource_type="session",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=actor.session_id,
    )
    db.commit()
    response.delete_cookie(auth_service.SESSION_COOKIE, path="/")
    return MessageResponse(message="logged_out")
