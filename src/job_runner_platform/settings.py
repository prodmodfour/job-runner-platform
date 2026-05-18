from __future__ import annotations

from functools import lru_cache
from typing import Annotated, ClassVar

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    auth_enabled: bool = False
    auth_api_keys: Annotated[tuple[str, ...], NoDecode] = Field(
        default_factory=tuple,
        repr=False,
    )
    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/job_runner",
        min_length=1,
    )
    redis_url: str = Field(default="redis://localhost:6379/0", min_length=1)
    worker_id: str = Field(default="local-worker-1", min_length=1, max_length=128)
    job_lease_seconds: float = Field(default=60.0, gt=0.0)
    job_poll_seconds: float = Field(default=1.0, gt=0.0)

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

    @field_validator("auth_api_keys", mode="before")
    @classmethod
    def parse_auth_api_keys(cls, value: object) -> tuple[str, ...]:
        """Parse comma-separated API keys from environment configuration."""

        if value is None or value == "":
            return ()
        if isinstance(value, str):
            candidates = value.split(",")
        elif isinstance(value, (list, tuple, set, frozenset)):
            candidates = [str(item) for item in value]
        else:
            raise ValueError("auth_api_keys must be a comma-separated string")
        return tuple(candidate.strip() for candidate in candidates if candidate.strip())


@lru_cache
def get_settings() -> Settings:
    """Return cached settings loaded from the process environment."""

    return Settings()
