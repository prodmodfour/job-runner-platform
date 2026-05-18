from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Request, Response
from fastapi import status as http_status

from job_runner_platform.api.dependencies import ReadinessServiceDependency
from job_runner_platform.api.schemas import (
    HealthResponse,
    ReadinessCheckResponse,
    ReadinessResponse,
)
from job_runner_platform.services import ReadinessResult
from job_runner_platform.settings import Settings

router = APIRouter(tags=["system"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz(request: Request) -> HealthResponse:
    """Return liveness for the API process without dependency checks."""

    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/readyz", response_model=ReadinessResponse)
async def readyz(
    response: Response,
    service: ReadinessServiceDependency,
) -> ReadinessResponse:
    """Return dependency readiness for PostgreSQL and Redis."""

    result = await service.check()
    if not result.is_ready:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
    return _readiness_response(result)


def _readiness_response(result: ReadinessResult) -> ReadinessResponse:
    return ReadinessResponse(
        status="ready" if result.is_ready else "not_ready",
        checks={
            check.name: ReadinessCheckResponse(
                status="ok" if check.ready else "unavailable",
                message=check.message,
            )
            for check in result.checks
        },
    )
