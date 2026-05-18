from __future__ import annotations

from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from job_runner_platform.logging import (
    REQUEST_ID_HEADER,
    reset_request_id,
    set_request_id,
)


def _get_or_create_request_id(header_value: str | None) -> str:
    if header_value is not None and header_value.strip():
        return header_value
    return str(uuid4())


async def request_id_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Propagate ``X-Request-ID`` and bind it to structured logs."""

    request_id = _get_or_create_request_id(request.headers.get(REQUEST_ID_HEADER))
    token = set_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
    finally:
        reset_request_id(token)
