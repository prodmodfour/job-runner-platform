from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request

from job_runner_platform.api.schemas import HealthResponse
from job_runner_platform.settings import Settings

router = APIRouter(tags=["system"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    """Return liveness for the API process.

    This endpoint intentionally performs no dependency checks. PostgreSQL and
    Redis readiness checks will be added to ``/readyz`` in a later ticket.
    """

    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
    )
