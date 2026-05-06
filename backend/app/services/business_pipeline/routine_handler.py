"""Business routine handler -- Sprint-19 PR-6 (2026-05-06).

Wires ``run_discovery_loop`` to the routine_autonomy scheduler as
the handler for the ``opportunity_discovery`` kind. Initiator is
ALWAYS ``DispatchInitiator.SCHEDULER`` so trust auto-approval can
NEVER fire for routine-produced work (Sprint-18 wall #2).

The brief's allowed scheduler actions:

  * find opportunities       (run_discovery_loop -- this PR)
  * score opportunities      (same; scoring inside the loop)
  * create workstreams       (Sprint-19+ wiring)
  * create local drafts      (Sprint-19+ wiring; PR-3 factory exists)
  * queue approvals          (PR-4/5 bridges -- always SCHEDULER initiator)

Forbidden FOREVER for routines:

  * send / submit / post / pay
  * file apply / git commit
  * security scan
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.services.business_pipeline.orchestrator import (
    DEFAULT_TOP_N,
    run_discovery_loop,
)
from app.services import routine_autonomy
from app.services.routine_autonomy import register_handler

logger = get_logger(__name__)


async def opportunity_discovery_handler(
    *, db=None, tenant_id=None, user_id=None, top_n: int = DEFAULT_TOP_N,
    **_extra,
):
    """Routine_autonomy.run_once handler for ``opportunity_discovery``.

    Returns the (artifacts, detail) tuple shape that
    ``routine_autonomy.run_once`` expects. NEVER raises -- the
    routine layer also has its own catch, but we layer defensively.
    """
    if db is None or tenant_id is None:
        logger.warning(
            "business.routine.missing_context",
            db_present=db is not None, tenant=str(tenant_id),
        )
        return ([], "missing db or tenant_id")

    try:
        result = await run_discovery_loop(
            db, tenant_id=tenant_id, top_n=top_n,
            initiator="scheduler",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("business.routine.run_failed", error=str(exc))
        return ([], f"run_failed:{exc}")

    artifacts = []
    if result.persisted_count > 0:
        artifacts.append(
            f"persisted:{result.persisted_count}",
        )
    if result.updated_count > 0:
        artifacts.append(
            f"updated:{result.updated_count}",
        )

    detail = (
        f"discovered={result.discovered_count} "
        f"deduped={result.deduped_count} "
        f"persisted={result.persisted_count} "
        f"updated={result.updated_count} "
        f"capped={result.capped_count}"
    )
    return (artifacts, detail)


def register() -> None:
    """Register the handler with routine_autonomy. Idempotent --
    re-registration replaces the existing handler entry."""
    # routine_autonomy.register_handler refuses unknown kind; valid here.
    routine_autonomy._HANDLERS.pop("opportunity_discovery", None)
    register_handler("opportunity_discovery", opportunity_discovery_handler)
    logger.info("business.routine.registered", kind="opportunity_discovery")


# Auto-register on import. Tests using isolated_state can call
# `routine_autonomy._HANDLERS.clear()` and then re-register
# explicitly.
register()
