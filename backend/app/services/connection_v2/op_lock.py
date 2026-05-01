"""ConnectionV2 op-lock helpers (Phase 4b PR 1).

Per ADR-002 D-002: in-progress state lives in
``connection_v2_op_lock`` rows with TTL, NOT booleans on the parent
row. ``derive_label()`` reads the active set via ``active_ops_for``.

DB row is the durable source-of-truth (Phase 4b PR 1). A future Redis
mirror is an optimization for hot-path reads, not required here.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connection_v2 import ConnectionV2OpLock, OpKind

# Default TTLs per op (V2 §4 + ADR-002 D-002).
DEFAULT_TTLS: dict[str, int] = {
    OpKind.AUTHENTICATE.value: 600,
    OpKind.PROBE.value: 30,
    OpKind.INSTALL.value: 120,
    OpKind.OAUTH_CALLBACK.value: 60,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def acquire_op_lock(
    db: AsyncSession,
    *,
    connection_id: UUID,
    op: str,
    ttl_seconds: int | None = None,
    owner_token: str | None = None,
) -> str | None:
    """Acquire an exclusive lock for (connection_id, op).

    Returns the owner_token on success, or None if already locked.
    Caller must call ``release_op_lock(token)`` to free it. Locks
    auto-expire via ``expires_at``; a sweeper / passive cleanup deletes
    expired rows on next acquire of the same key.
    """
    if op not in DEFAULT_TTLS:
        raise ValueError(f"unknown op {op!r}; allowed: {sorted(DEFAULT_TTLS)}")
    if ttl_seconds is None:
        ttl_seconds = DEFAULT_TTLS[op]
    if owner_token is None:
        owner_token = secrets.token_urlsafe(24)

    now = _now()
    expires = now + timedelta(seconds=ttl_seconds)

    # Passive cleanup: delete any expired lock for this (connection_id, op)
    # so a fresh acquire can succeed.
    await db.execute(
        delete(ConnectionV2OpLock).where(
            ConnectionV2OpLock.connection_id == connection_id,
            ConnectionV2OpLock.op == op,
            ConnectionV2OpLock.expires_at <= now,
        )
    )
    await db.flush()

    lock = ConnectionV2OpLock(
        id=uuid4(),
        connection_id=connection_id,
        op=op,
        acquired_at=now,
        expires_at=expires,
        owner_token=owner_token,
    )
    db.add(lock)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return None
    return owner_token


async def release_op_lock(
    db: AsyncSession,
    *,
    connection_id: UUID,
    op: str,
    owner_token: str,
) -> bool:
    """Release a lock you acquired. No-op if you don't own it."""
    result = await db.execute(
        delete(ConnectionV2OpLock).where(
            ConnectionV2OpLock.connection_id == connection_id,
            ConnectionV2OpLock.op == op,
            ConnectionV2OpLock.owner_token == owner_token,
        )
    )
    await db.flush()
    return (result.rowcount or 0) > 0


async def active_ops_for(
    db: AsyncSession,
    connection_id: UUID,
) -> set[str]:
    """Return the set of op strings currently held (and not expired)."""
    now = _now()
    rows = await db.execute(
        select(ConnectionV2OpLock.op).where(
            ConnectionV2OpLock.connection_id == connection_id,
            ConnectionV2OpLock.expires_at > now,
        )
    )
    return {r[0] for r in rows.all()}
