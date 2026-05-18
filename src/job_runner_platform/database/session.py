from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from job_runner_platform.settings import Settings


def build_async_engine(settings: Settings) -> AsyncEngine:
    """Create the async SQLAlchemy engine for PostgreSQL access."""

    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


def build_async_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a repository-friendly async session factory."""

    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a transactional session boundary for service/repository calls."""

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
