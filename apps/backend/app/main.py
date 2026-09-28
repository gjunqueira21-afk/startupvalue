from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router
from app.api.routes.resources import router as resources_router
from app.api.routes.simulations import router as simulations_router
from app.auth.csrf import csrf_guard
from app.core.config import get_settings

settings = get_settings()
if settings.app_env.lower() in {"production", "staging"} and (
    settings.csrf_secret is None or len(settings.csrf_secret) < 32
):
    raise RuntimeError("CSRF_SECRET must contain at least 32 characters")
app = FastAPI(title="QuantoVale API", version="0.1.0", docs_url="/api/docs")
app.middleware("http")(csrf_guard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(resources_router)
app.include_router(dashboard_router)
app.include_router(simulations_router)
app.include_router(reports_router)


@app.get("/api/v1/meta", tags=["meta"])
def metadata() -> dict[str, str]:
    return {
        "service": "startupvalue-backend",
        "model_version": settings.model_version,
        "tax_version": settings.tax_version,
    }
