from fastapi import APIRouter, Response, status
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok", "app": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict[str, str]:
    settings = get_settings()
    database_status = "not_configured"
    if engine is not None:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database_status = "ok"
        except Exception:  # readiness reports state without exposing driver details
            database_status = "unavailable"

    redis_status = "not_configured"
    if settings.redis_url:
        client = Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        try:
            redis_status = "ok" if client.ping() else "unavailable"
        except Exception:  # readiness reports state without exposing credentials/details
            redis_status = "unavailable"
        finally:
            client.close()

    ready_now = database_status == "ok" and redis_status == "ok"
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_now else "degraded",
        "app": "ok",
        "database": database_status,
        "redis": redis_status,
    }
