"""Concurrent DB session helpers.

SQLAlchemy 2.0's ``AsyncSession`` is NOT concurrency-safe. Two awaits
that both touch the same session can race on the underlying connection
provisioning step, raising::

    sqlalchemy.exc.InvalidRequestError: This session is provisioning a
    new connection; concurrent operations are not permitted on this
    session.

The fix in 2026-04-29 stabilization: when an endpoint or service needs
to fan out work, give each coroutine its OWN fresh session via
``async_session_factory()``. This module ships the canonical helper +
two patterns endpoints should use.

Pattern A -- gather four queries with separate sessions::

    from app.core.db_concurrent import gather_with_sessions

    async def _query_a(session: AsyncSession, tenant_id: UUID) -> ...
    async def _query_b(session: AsyncSession, tenant_id: UUID) -> ...
    async def _query_c(session: AsyncSession, tenant_id: UUID) -> ...

    a, b, c = await gather_with_sessions(
        lambda s: _query_a(s, tenant_id),
        lambda s: _query_b(s, tenant_id),
        lambda s: _query_c(s, tenant_id),
    )

Pattern B -- spawn a fire-and-forget task that needs DB access::

    from app.core.db_concurrent import session_scope

    async def _post_request_work(tenant_id: UUID) -> None:
        async with session_scope() as session:
            ...your queries here...

    asyncio.create_task(_post_request_work(tenant_id))

NEVER do this::

    # WRONG -- races on the request-scoped `db`.
    a, b, c = await asyncio.gather(
        _query_a(db, tenant_id),
        _query_b(db, tenant_id),
        _query_c(db, tenant_id),
    )

The AST guard test at ``tests/test_no_shared_session_gather.py`` blocks
this antipattern at CI time.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory

T = TypeVar("T")

# Type alias for "callable that takes a session and returns an awaitable".
QueryFn = Callable[[AsyncSession], Awaitable[T]]


@contextlib.asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Open a fresh session, commit on success, rollback on failure.

    Use this for background tasks, post-request work, or anywhere you
    need DB access OUTSIDE a FastAPI request lifecycle. Inside a
    request, prefer ``Depends(get_db)`` for the request-scoped session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def gather_with_sessions(
    *query_fns: QueryFn[T],
    return_exceptions: bool = False,
) -> list[T]:
    """Run query callables in parallel, each with its own fresh session.

    Each ``query_fn`` is called with a brand-new ``AsyncSession``. The
    sessions are committed (and closed) before this function returns.
    If a callable raises, that session is rolled back and either
    re-raised or returned (when ``return_exceptions=True``).

    Args:
        *query_fns: One or more ``async def fn(session) -> T`` callables.
        return_exceptions: If True, exceptions are returned in-band like
            ``asyncio.gather(return_exceptions=True)``. Default False.

    Returns:
        List of results in the same order as ``query_fns``.

    Example::

        usage, gov, depts = await gather_with_sessions(
            lambda s: _query_usage(s, tenant_id),
            lambda s: _query_gov(s, tenant_id),
            lambda s: _query_depts(s, tenant_id),
        )
    """
    async def _run_with_session(fn: QueryFn[T]) -> T:
        async with session_scope() as session:
            return await fn(session)

    return await asyncio.gather(
        *[_run_with_session(fn) for fn in query_fns],
        return_exceptions=return_exceptions,
    )
