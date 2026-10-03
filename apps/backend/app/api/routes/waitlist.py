"""Public waitlist capture endpoint.

Unlike every other mutating route in this API, this one is intentionally
unauthenticated: it is the signup form on the marketing site, consumed before
any account exists (Task 13's form). It therefore takes no ``Actor``
dependency, stores nothing beyond the fields a visitor volunteers, and never
calls ``record_event`` (there is no workspace to attribute the event to).

Rate limiting is a module-level ``dict[str, list[float]]`` keyed by client IP
holding a sliding one-minute window of request timestamps, pruned on every
call. This is per-process state: it is *not* shared across uvicorn workers or
server instances, so a determined client could exceed 10/minute/IP in
aggregate across a multi-process deployment. That is an accepted trade-off
for a public waitlist endpoint (low value target, no PII beyond an email
address) — it avoids adding a Redis dependency to the one route in the API
that must work before any infrastructure assumption (session, workspace,
Redis-backed auth limiter) holds.
"""

from __future__ import annotations

import re
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import Field, field_validator
from sqlalchemy import select

from app.api.dependencies import Database
from app.api.schemas import ApiModel
from app.db.models import WaitlistEntry

router = APIRouter(prefix="/api/v1/waitlist", tags=["waitlist"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_EMAIL_LENGTH = 320

PlanInterest = Literal["free", "empresario", "consultor", "escritorio"]

_RATE_LIMIT = 10
_WINDOW_SECONDS = 60.0
_requests_by_ip: dict[str, list[float]] = {}


class WaitlistRequest(ApiModel):
    email: str
    plan_interest: PlanInterest
    source: str = Field(min_length=1, max_length=40)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) > _MAX_EMAIL_LENGTH or not _EMAIL_RE.match(normalized):
            raise ValueError("invalid_email")
        return normalized


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str) -> bool:
    """Prune ``ip``'s timestamp list to the trailing window, then test/record."""
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS
    timestamps = [t for t in _requests_by_ip.get(ip, []) if t > cutoff]
    if len(timestamps) >= _RATE_LIMIT:
        _requests_by_ip[ip] = timestamps
        return True
    timestamps.append(now)
    _requests_by_ip[ip] = timestamps
    return False


def clear_rate_limiter_for_tests() -> None:
    _requests_by_ip.clear()


@router.post("")
def join_waitlist(
    payload: WaitlistRequest, request: Request, response: Response, db: Database
) -> dict[str, str]:
    if _rate_limited(_client_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "waitlist_rate_limited")

    existing = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == payload.email))
    if existing is not None:
        existing.plan_interest = payload.plan_interest
        db.commit()
        response.status_code = status.HTTP_200_OK
        return {"status": "ok"}

    entry = WaitlistEntry(
        email=payload.email, plan_interest=payload.plan_interest, source=payload.source
    )
    db.add(entry)
    db.commit()
    response.status_code = status.HTTP_201_CREATED
    return {"status": "ok"}
