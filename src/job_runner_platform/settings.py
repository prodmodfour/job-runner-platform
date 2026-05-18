from __future__ import annotations

from functools import lru_cache
from typing import ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from job_runner_platform import __version__


class Settings(BaseSettings):
    """Environment-backed application settings.

    All runtime configuration is read from environment variables with the
    ``JOB_RUNNER_`` prefix. Defaults are safe for local tests and keep API docs
    disabled unless explicitly enabled.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="JOB_RUNNER_",
        extra="ignore",
    )

    app_name: str = Field(default="job-runner-platform", min_length=1)
    app_version: str = Field(default=__version__, min_length=1)
    environment: str = Field(default="local", min_length=1)
    log_level: str = Field(default="INFO", min_length=1)
    docs_enabled: bool = False

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        """Normalize and validate standard library logging level names."""

        normalized = value.upper()
        allowed_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed_levels:
            message = f"log_level must be one of: {', '.join(sorted(allowed_levels))}"
            raise ValueError(message)
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return cached settings loaded from the process environment."""

    return Settings()
