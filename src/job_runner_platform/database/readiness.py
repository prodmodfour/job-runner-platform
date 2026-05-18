from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DatabaseReadinessCheck:
    """PostgreSQL readiness probe owned by the database layer.

    The probe intentionally performs a minimal ``SELECT 1`` through the
    configured SQLAlchemy session factory. It does not inspect application
    tables or mutate state; it only verifies that the database connection path
    can execute a simple query.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def __call__(self) -> None:
        """Raise ``DatabaseReadinessError`` when PostgreSQL is unavailable."""

        try:
            async with self._session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                if result.scalar_one_or_none() != 1:
                    raise DatabaseReadinessError
        except DatabaseReadinessError:
            raise
        except SQLAlchemyError as exc:
            raise DatabaseReadinessError from exc


class DatabaseReadinessError(RuntimeError):
    """Raised when the database readiness query cannot complete."""
