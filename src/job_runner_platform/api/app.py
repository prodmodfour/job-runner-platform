from __future__ import annotations

from fastapi import Depends, FastAPI

from job_runner_platform.api.auth import require_api_key
from job_runner_platform.api.middleware import request_id_middleware
from job_runner_platform.api.routes.health import router as health_router
from job_runner_platform.api.routes.jobs import router as jobs_router
from job_runner_platform.api.routes.metrics import router as metrics_router
from job_runner_platform.logging import configure_logging
from job_runner_platform.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings if settings is not None else get_settings()
    configure_logging(resolved_settings.log_level)

    docs_url = "/docs" if resolved_settings.docs_enabled else None
    redoc_url = "/redoc" if resolved_settings.docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.docs_enabled else None

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.settings = resolved_settings
    app.middleware("http")(request_id_middleware)
    app.include_router(health_router)
    app.include_router(jobs_router, dependencies=[Depends(require_api_key)])
    app.include_router(metrics_router)
    return app


app = create_app()
