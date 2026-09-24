"""Small fixed-window auth limiter; Redis is mandatory in deployed environments."""

from __future__ import annotations

import hashlib
import threading
import time
from typing import cast

from redis import Redis, RedisError

from app.core.config import get_settings

_lock = threading.Lock()
_local: dict[str, tuple[int, float]] = {}


class RateLimitUnavailable(RuntimeError):
    pass


def _increment(key: str, window_seconds: int) -> int:
    settings = get_settings()
    if settings.redis_url:
        try:
            client = Redis.from_url(
                settings.redis_url, socket_connect_timeout=1, socket_timeout=1
            )
            try:
                if client.set(key, 1, nx=True, ex=window_seconds):
                    return 1
                return cast(int, client.incr(key))
            finally:
                client.close()
        except RedisError as exc:
            raise RateLimitUnavailable("auth_rate_limit_unavailable") from exc
    if settings.app_env.lower() in {"production", "staging"}:
        raise RateLimitUnavailable("auth_rate_limit_unavailable")
    now = time.monotonic()
    with _lock:
        # Bound local memory even under many distinct identifiers.
        if len(_local) > 10_000:
            for stale in [entry for entry, (_, deadline) in _local.items() if deadline <= now]:
                del _local[stale]
        count, deadline = _local.get(key, (0, now + window_seconds))
        if deadline <= now:
            count, deadline = 0, now + window_seconds
        count += 1
        _local[key] = (count, deadline)
        return count


def allow(action: str, identity: str, *, limit: int, window_seconds: int) -> bool:
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return _increment(f"auth:{action}:{digest}", window_seconds) <= limit


def clear_local_for_tests() -> None:
    with _lock:
        _local.clear()
