"""Connection V2 — startup self-heal for stale `probe_unavailable:` rows.

Why this exists
---------------
``install_all_probes()`` is called during deferred startup. Rows imported
or last-probed BEFORE that registration carry a sentinel failure reason

    ``probe_unavailable: no real probe implementation for kind '<k>' yet``

that the registry's normal flow only clears on the operator's next
manual ``Discover installed tools`` click. That makes Connections look
broken (Failed pills with `probe_unavailable`) for callable runtimes
the operator already has working.

This module provides ``heal_stale_probes(db, limit=50)`` — a bounded,
async, idempotent self-heal step that finds rows whose ``*_failure_reason``
starts with the ``probe_unavailable:`` prefix and re-runs ``run_probe``
on each. Real success → callable=true; real failure → fresh reason in
the matching dim. Either way, the stale sentinel is gone.

Hard rules
----------
- Bounded by ``limit`` (default 50) so a populated catalog can't stall
  startup.
- Per-row exceptions are caught + logged; one bad row does not block
  the rest.
- Single ``db.commit()`` at the end — startup is the only writer.
- No locking: at deferred-init time there is no concurrent probe
  traffic; the registry's per-row op-lock is a request-time concern.
- No secrets read; ``run_probe`` is the only caller and it already
  observes Asset Shield rules.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.connection_v2 import ConnectionV2
from app.services.connection_v2.probe import (
    PROBE_UNAVAILABLE_PREFIX,
    run_probe,
)

logger = get_logger(__name__)


async def heal_stale_probes(db: AsyncSession, *, limit: int = 50) -> dict[str, int]:
    """Re-probe rows with a stale ``probe_unavailable:`` failure reason.

    Returns a dict: ``{scanned, healed, restamped, errored}``.
    """
    stmt = (
        select(ConnectionV2)
        .where(
            or_(
                ConnectionV2.callable_failure_reason.ilike(
                    f"{PROBE_UNAVAILABLE_PREFIX}%",
                ),
                ConnectionV2.reachable_failure_reason.ilike(
                    f"{PROBE_UNAVAILABLE_PREFIX}%",
                ),
                ConnectionV2.authenticated_failure_reason.ilike(
                    f"{PROBE_UNAVAILABLE_PREFIX}%",
                ),
            ),
        )
        .order_by(ConnectionV2.created_at.asc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())

    healed = 0
    restamped = 0
    errored = 0
    now = datetime.now(timezone.utc)

    for row in rows:
        try:
            result = await run_probe(row)
        except Exception as exc:  # noqa: BLE001 — never break startup
            logger.warning(
                "probe.heal.row_raised",
                row_id=str(row.id),
                slug=row.slug,
                kind=row.kind,
                error_type=type(exc).__name__,
                error=str(exc)[:200],
            )
            errored += 1
            continue

        if result.success:
            row.reachable = True
            row.reachable_at = now
            row.reachable_failure_at = None
            row.reachable_failure_reason = None
            if (row.auth_method or "none") != "none":
                row.authenticated = True
                row.authenticated_at = now
                row.authenticated_failure_at = None
                row.authenticated_failure_reason = None
            row.callable = True
            row.callable_at = now
            row.callable_failure_at = None
            row.callable_failure_reason = None
            row.healthy_call_ratio = 1.0
            healed += 1
        else:
            dim = result.failure_dim or "callable"
            reason = (result.failure_reason or "probe failed")[:500]
            if dim == "reachable":
                row.reachable = False
                row.reachable_failure_at = now
                row.reachable_failure_reason = reason
                row.callable = False
                row.callable_failure_reason = None
            elif dim == "authenticated":
                row.authenticated = False
                row.authenticated_failure_at = now
                row.authenticated_failure_reason = reason
                row.callable = False
                row.callable_failure_reason = None
            else:
                row.callable = False
                row.callable_failure_at = now
                row.callable_failure_reason = reason
            restamped += 1

    if rows:
        await db.flush()

    return {
        "scanned": len(rows),
        "healed": healed,
        "restamped": restamped,
        "errored": errored,
    }


__all__ = ["heal_stale_probes"]
