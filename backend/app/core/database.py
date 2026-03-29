"""Async SQLAlchemy database engine and session management.

Provides the async engine, session factory, and dependency injection
for FastAPI route handlers. All sessions are scoped to request lifecycle.

Supports both PostgreSQL (production) and SQLite (development).
Pool settings are only applied for PostgreSQL — SQLite uses StaticPool.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

# Build engine kwargs conditionally based on database driver
_engine_kwargs: dict[str, Any] = {
    "echo": settings.database_echo,
}

if settings.database_url.startswith("sqlite"):
    # SQLite: use StaticPool for async compatibility, enable WAL mode
    _engine_kwargs["poolclass"] = StaticPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / other: full connection pooling
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 3600

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an async database session.

    Session is automatically closed after the request completes.
    Usage in routes:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
