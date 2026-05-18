from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response body for the liveness endpoint."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    app_name: str
    app_version: str
    environment: str
