"""Public waitlist capture endpoint.

Unlike every other mutating route in this API, this one is intentionally
unauthenticated: it is the signup form on the marketing site, consumed before
any account exists (Task 13's form). It therefore takes no ``Actor``
dependency, stores nothing beyond the fields a visitor volunteers, and never
calls ``record_event`` (there is no workspace to attribute the event to).

Rate limiting is a module-level ``dict[str, list[float]]`` keyed by client IP
holding a sliding one-minute window of request timestamps. This is per-process
state: it is *not* shared across uvicorn workers or server instances, so a
determined client could exceed 10/minute/IP in aggregate across a
multi-process deployment. That is an accepted trade-off for a public
waitlist endpoint (low value target, no PII beyond an email address) — it
avoids adding a Redis dependency to the one route in the API that must work
before any infrastructure assumption (session, workspace, Redis-backed auth
limiter) holds.

Two details that keep the limiter correct and bounded:

- It is wired in as a route ``dependencies=[...]`` entry rather than read
  inside the handler body. FastAPI solves all declared dependencies before it
  validates/parses the request body against the pydantic model, so a
  malformed payload still consumes a slot in the limiter and still gets
  throttled on the 11th attempt instead of bypassing it via a 422.
- Every call sweeps the *entire* dict (not just the current IP's entry),
  dropping any IP whose timestamp list is empty after pruning to the trailing
  window. Without this, distinct IPs would accumulate in the dict for the
  life of the process. The sweep is O(distinct IPs seen in-window), which is
  cheap for a low-traffic waitlist form; it only runs on a live request, so a
  single IP that stops sending requests is evicted the next time *any*
  request arrives at least one window later, not instantly.
"""

from __future__ import annotations

import re
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

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


def _evict_stale_ips(now: float) -> None:
    """Drop every IP key whose window has fully expired as of ``now``."""
    cutoff = now - _WINDOW_SECONDS
    for ip in list(_requests_by_ip):
        pruned = [t for t in _requests_by_ip[ip] if t > cutoff]
        if pruned:
            _requests_by_ip[ip] = pruned
        else:
            del _requests_by_ip[ip]


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    _evict_stale_ips(now)
    timestamps = _requests_by_ip.get(ip, [])
    if len(timestamps) >= _RATE_LIMIT:
        return True
    timestamps.append(now)
    _requests_by_ip[ip] = timestamps
    return False


def clear_rate_limiter_for_tests() -> None:
    _requests_by_ip.clear()


def _enforce_rate_limit(request: Request) -> None:
    """Route-level dependency so throttling runs before body validation."""
    if _rate_limited(_client_ip(request)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "waitlist_rate_limited")


@router.post("", dependencies=[Depends(_enforce_rate_limit)])
def join_waitlist(payload: WaitlistRequest, response: Response, db: Database) -> dict[str, str]:
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
    try:
        db.commit()
    except IntegrityError:
        # Lost a TOCTOU race: another request inserted this normalized email
        # between our existence check and our commit. Fall back to the same
        # idempotent-update path a same-process repeat submission takes.
        db.rollback()
        existing = db.scalar(select(WaitlistEntry).where(WaitlistEntry.email == payload.email))
        if existing is None:
            raise
        existing.plan_interest = payload.plan_interest
        db.commit()
        response.status_code = status.HTTP_200_OK
        return {"status": "ok"}

    response.status_code = status.HTTP_201_CREATED
    return {"status": "ok"}
