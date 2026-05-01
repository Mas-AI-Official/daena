"""Async SQLAlchemy database engine and session management.

Provides the async engine, session factory, and dependency injection
for FastAPI route handlers. All sessions are scoped to request lifecycle.

Supports both PostgreSQL (production) and SQLite (development).

SQLite pool strategy (2026-04-18):
    * ``:memory:`` URIs keep StaticPool so the one in-process connection
      preserves the schema across async sessions (each new connection to a
      memory URI creates a FRESH empty DB, so pooling is mandatory).
    * File-based URIs use ``NullPool`` so every request opens its own
      physical connection, releases it on request end, and cannot collide
      with a concurrent request's open cursor. This fixes the
      ``sqlite3.OperationalError: cannot commit transaction - SQL
      statements in progress`` that appeared when an SSE streaming
      request held a cursor while a PATCH tried to commit on the SAME
      shared StaticPool connection. WAL mode (enabled below) handles
      multi-reader / single-writer concurrency at the file level.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool

from app.core.config import get_settings

settings = get_settings()

# Build engine kwargs conditionally based on database driver
_engine_kwargs: dict[str, Any] = {
    "echo": settings.database_echo,
}

if settings.database_url.startswith("sqlite"):
    # :memory: SQLite still needs StaticPool (each fresh connection
    # would be a brand-new empty DB). File-based SQLite uses NullPool
    # so concurrent requests never share the same physical connection
    # and one request's open cursor can't block another's commit.
    if ":memory:" in settings.database_url:
        _engine_kwargs["poolclass"] = StaticPool
    else:
        _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / other: full connection pooling
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 3600

engine = create_async_engine(settings.database_url, **_engine_kwargs)

# File-based SQLite: try to enable WAL + busy_timeout on every new
# connection so concurrent requests don't trip "database is locked"
# under NullPool. WAL is a best-effort optimization -- NEVER raise
# from this hook, because an exception here aborts the whole request
# with "unable to open database file" and the user sees the backend
# appear completely dead.
#
# Why best-effort? WSL2 mounts the Windows filesystem via ``drvfs``,
# which doesn't implement all the POSIX locking primitives WAL needs
# to create its ``.db-wal`` + ``.db-shm`` sidecar files. When the DB
# lives on ``/mnt/d/...`` the PRAGMA fails with exactly the error we
# saw in production on 2026-04-18. Falling back to the SQLite default
# (rollback journaling) is correct -- slower under contention but
# still safe. The NullPool switch alone prevents the cursor-collision
# bug we set out to fix.
if (
    settings.database_url.startswith("sqlite")
    and ":memory:" not in settings.database_url
):

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_on_connect(dbapi_conn: Any, _conn_record: Any) -> None:
        # Journal mode policy (revised 2026-04-18 after a real drvfs-
        # corruption incident):
        #
        #   * We used to try ``journal_mode=WAL`` best-effort. On pure
        #     Linux that's correct. On WSL2 drvfs (the /mnt/<drv>/...
        #     mount of the Windows filesystem), WAL sometimes succeeds
        #     on the first connection then trips on a later checkpoint
        #     because drvfs doesn't properly support the shared-memory
        #     mapping WAL needs. Result: btree corruption (``Rowid out
        #     of order``, ``2nd reference to page``), unrecoverable
        #     except via ``.recover``.
        #
        #   * ``journal_mode=DELETE`` is the classic rollback journal.
        #     It's slower under heavy write concurrency but works on
        #     every filesystem SQLite supports, including drvfs. Given
        #     Daena is SQLite-only in dev and Postgres-only in prod,
        #     the drvfs path is the only consumer of this code, so
        #     trading some dev-time concurrency for "never corrupt the
        #     DB again" is an unambiguous win.
        #
        # busy_timeout still helps even without WAL: if a long writer
        # holds the DB, readers wait up to 5s before giving up instead
        # of getting immediate "database is locked" errors.
        cur = dbapi_conn.cursor()
        try:
            for pragma in (
                "PRAGMA journal_mode=DELETE",  # rollback journal (safe everywhere)
                "PRAGMA synchronous=NORMAL",
                "PRAGMA busy_timeout=5000",
                "PRAGMA foreign_keys=ON",
            ):
                try:
                    cur.execute(pragma)
                except Exception:  # noqa: BLE001 -- best-effort pragma
                    pass
        finally:
            try:
                cur.close()
            except Exception:  # noqa: BLE001
                pass


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

    Cancellation guard (Phase 2 efficiency, 2026-04-24): a long-running
    SSE chat stream that the user aborts (Stop button or browser close)
    propagates ``CancelledError`` UP through this generator. The original
    code then tried ``session.commit()`` -- which crashed with
    ``sqlite3.OperationalError: no active connection`` because aiosqlite
    had already torn down the connection during cancellation. The crash
    surfaces as ``unhandled_exception`` 500s in the logs and erases any
    helpful chat error from the audit trail. We now treat cancellation
    as a clean exit: rollback if possible, swallow connection-gone
    errors, and let the cancellation propagate so FastAPI completes the
    response cycle properly. Other exceptions still re-raise.
    """
    import asyncio
    from sqlalchemy.exc import OperationalError

    async with async_session_factory() as session:
        try:
            yield session
            try:
                await session.commit()
            except (asyncio.CancelledError, OperationalError) as exc:
                # Cancellation race: connection may already be gone.
                logger.debug(
                    "get_db.commit_skipped_cancelled",
                    error=str(exc)[:200],
                )
                # Re-raise CancelledError so the task tree unwinds correctly.
                if isinstance(exc, asyncio.CancelledError):
                    raise
        except asyncio.CancelledError:
            # Best-effort rollback; never block cancellation propagation
            # on a hung connection.
            with contextlib.suppress(Exception):
                await session.rollback()
            raise
        except Exception:
            with contextlib.suppress(Exception):
                await session.rollback()
            raise
        finally:
            with contextlib.suppress(Exception):
                await session.close()
