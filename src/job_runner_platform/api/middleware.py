from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from job_runner_platform.logging import (
    REQUEST_ID_HEADER,
    reset_request_id,
    set_request_id,
)
from job_runner_platform.observability import get_metrics_recorder


def _get_or_create_request_id(header_value: str | None) -> str:
    if header_value is not None and header_value.strip():
        return header_value
    return str(uuid4())


def _route_path(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    return "unmatched"


async def request_id_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Propagate ``X-Request-ID`` and bind it to structured logs."""

    request_id = _get_or_create_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = set_request_id(request_id)
    started_at = perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        get_metrics_recorder().record_api_request(
            method=request.method,
            path=_route_path(request),
            status_code=status_code,
            duration_seconds=perf_counter() - started_at,
        )
        reset_request_id(token)
