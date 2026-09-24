"""Session-bound CSRF tokens for cookie-authenticated API mutations."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.core.config import get_settings
from app.services.auth import SESSION_COOKIE

_development_secret = secrets.token_bytes(32)
_safe_methods = {"GET", "HEAD", "OPTIONS"}
_session_bootstrap = {
    "/api/v1/auth/signup",
    "/api/v1/auth/login",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
}


def _secret() -> bytes:
    settings = get_settings()
    if settings.csrf_secret:
        if settings.app_env.lower() in {"production", "staging"} and len(settings.csrf_secret) < 32:
            raise RuntimeError("CSRF_SECRET must contain at least 32 characters")
        return settings.csrf_secret.encode("utf-8")
    if settings.app_env.lower() in {"production", "staging"}:
        raise RuntimeError("CSRF_SECRET is required in production and staging")
    return _development_secret


def token_for_session(session_token: str) -> str:
    return hmac.new(
        _secret(), session_token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _trusted_origin(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        return True
    settings = get_settings()
    allowed = set(settings.cors_origins)
    if settings.domain:
        allowed.add(f"https://{settings.domain}")
    return origin in allowed


async def csrf_guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method in _safe_methods or not request.url.path.startswith("/api/"):
        return await call_next(request)
    if not _trusted_origin(request):
        return JSONResponse({"detail": "untrusted_origin"}, status_code=403)
    if request.url.path in _session_bootstrap:
        return await call_next(request)
    session_token = request.cookies.get(SESSION_COOKIE)
    if session_token is not None:
        supplied = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(supplied, token_for_session(session_token)):
            return JSONResponse({"detail": "invalid_csrf_token"}, status_code=403)
    return await call_next(request)
