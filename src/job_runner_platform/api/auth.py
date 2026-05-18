from __future__ import annotations

from hmac import compare_digest
from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, Security
from fastapi import status as http_status
from fastapi.security import APIKeyHeader

from job_runner_platform.api.dependencies import get_request_settings
from job_runner_platform.settings import Settings

API_KEY_HEADER_NAME = "X-API-Key"

_api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def require_api_key(
    settings: Annotated[Settings, Depends(get_request_settings)],
    api_key: Annotated[str | None, Security(_api_key_header)] = None,
) -> None:
    """Require a configured API key when business endpoint auth is enabled."""

    if not settings.auth_enabled:
        return

    provided_key = api_key.strip() if api_key is not None else ""
    if not provided_key:
        _raise_unauthorized("API key is required")

    if not _is_allowed_api_key(provided_key, settings.auth_api_keys):
        _raise_unauthorized("Invalid API key")


def _is_allowed_api_key(provided_key: str, allowed_keys: tuple[str, ...]) -> bool:
    return any(
        compare_digest(provided_key, allowed_key) for allowed_key in allowed_keys
    )


def _raise_unauthorized(detail: str) -> NoReturn:
    raise HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail=detail,
    )
