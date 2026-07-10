"""Business routine handler -- Sprint-19 PR-6 (2026-05-06)
extended Sprint-20 PR-6 (2026-05-06).

Wires THREE business routines into the routine_autonomy scheduler:

  * ``opportunity_discovery``        -- run discovery loop
  * ``business_workstream_proposal`` -- promote top-K to workstreams
  * ``local_draft_action_creation``  -- create local outreach drafts
                                        for promoted opportunities

ALL three handlers run as scheduler-initiated work so trust
auto-approval can NEVER fire for routine-produced output
(Sprint-18 wall #2). The Sprint-20 PR-6 BRIGHT LINE:

  Scheduler-initiated routines never invoke the Gmail-bridge or
  send-bridge surfaces. The only path from a discovered opportunity
  to a Gmail draft is operator-initiated.

This is what makes routine work safe: the scheduler can prepare the
morning queue (discover, route, draft) so the founder wakes up to a
ready-to-review batch -- but the operator still hits Approve before
anything reaches Gmail. The bright line is enforced by:

  1. This file does NOT import any send-bridge / Gmail-bridge symbol
     (test pins this via source grep).
  2. The local_draft handler calls ONLY the local draft factory,
     which produces a BizOutreachDraft row but NO GoaRequest.

Forbidden FOREVER for routines:

  * send / submit / post / pay
  * file apply / git commit
  * security scan
  * Gmail bridge invocation (PR-6 bright line)
"""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.business import Opportunity
from app.services.business_pipeline.orchestrator import (
    DEFAULT_TOP_N,
    run_discovery_loop,
)
from app.services.business_pipeline.workstream_bridge import (
    DuplicateWorkstream,
    UnknownOpportunityType,
    DepartmentNotFound,
    ValidationRequired,
    create_workstream_for_opportunity,
)
from app.services.outreach.draft_factory import (
    create_outreach_draft_for_opportunity,
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


async def business_workstream_proposal_handler(
    *, db=None, tenant_id=None, user_id=None, top_k: int = 3, **_extra,
):
    """Promote top-K discovered opportunities to workstreams. NEVER
    calls Gmail / send / submit / file / git / scan paths.

    Returns the (artifacts, detail) tuple shape that
    ``routine_autonomy.run_once`` expects.
    """
    if db is None or tenant_id is None or user_id is None:
        return ([], "missing db / tenant_id / user_id")

    # Top-K discovered (status='discovered' only -- already-promoted
    # opportunities are skipped at the bridge layer too, but filter
    # here so we don't waste calls).
    stmt = (
        select(Opportunity)
        .where(Opportunity.tenant_id == tenant_id)
        .where(Opportunity.status == "discovered")
        .order_by(Opportunity.score.desc())
        .limit(max(1, min(int(top_k), 20)))
    )
    candidates = list((await db.execute(stmt)).scalars().all())

    artifacts: list[str] = []
    promoted = 0
    skipped = 0
    failed = 0
    for opp in candidates:
        try:
            r = await create_workstream_for_opportunity(
                db, tenant_id=tenant_id, user_id=user_id,
                opportunity_id=opp.id,
            )
            artifacts.append(f"workstream:{r.workstream_id}")
            promoted += 1
        except DuplicateWorkstream:
            skipped += 1
        except (UnknownOpportunityType, DepartmentNotFound) as exc:
            logger.warning(
                "business.routine.workstream_skipped",
                opportunity_id=str(opp.id), reason=type(exc).__name__,
            )
            failed += 1
        except ValidationRequired:
            logger.info(
                "business.routine.workstream_pending_validation",
                opportunity_id=str(opp.id),
            )
            skipped += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "business.routine.workstream_failed",
                opportunity_id=str(opp.id), error=str(exc),
            )
            failed += 1

    detail = (
        f"candidates={len(candidates)} promoted={promoted} "
        f"skipped={skipped} failed={failed}"
    )
    return (artifacts, detail)


async def local_draft_action_creation_handler(
    *, db=None, tenant_id=None, user_id=None,
    top_k: int = 3, **_extra,
):
    """Create local outreach drafts for opportunities that ALREADY
    have a recipient email captured in raw_metadata['recipient_email'].

    BRIGHT LINE: this handler does NOT call the Gmail bridge. It
    produces only ``BizOutreachDraft`` rows (status='drafted' or
    'blocked_recipient'). Operator must approve the create_draft
    GoaRequest manually via the UI.

    Returns the (artifacts, detail) tuple.
    """
    if db is None or tenant_id is None or user_id is None:
        return ([], "missing db / tenant_id / user_id")

    # Eligibility: status='discovered' OR 'queued', has raw_metadata
    # with recipient_email, no existing draft yet (status not 'drafted'
    # / 'queued_create_draft' / etc).
    stmt = (
        select(Opportunity)
        .where(Opportunity.tenant_id == tenant_id)
        .where(Opportunity.status.in_(["discovered", "queued"]))
        .order_by(Opportunity.score.desc())
        .limit(max(1, min(int(top_k), 20)))
    )
    candidates = list((await db.execute(stmt)).scalars().all())

    artifacts: list[str] = []
    drafted = 0
    skipped_no_recipient = 0
    blocked = 0
    for opp in candidates:
        recipient = (opp.raw_metadata or {}).get("recipient_email")
        if not recipient or not isinstance(recipient, str):
            skipped_no_recipient += 1
            continue
        try:
            r = await create_outreach_draft_for_opportunity(
                db, opportunity=opp, user_id=user_id,
                recipient_email=recipient,
            )
            if r.status == "drafted":
                artifacts.append(f"draft:{r.draft_id}")
                drafted += 1
            else:
                blocked += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "business.routine.local_draft_failed",
                opportunity_id=str(opp.id), error=str(exc),
            )

    detail = (
        f"candidates={len(candidates)} drafted={drafted} "
        f"blocked={blocked} skipped_no_recipient={skipped_no_recipient}"
    )
    return (artifacts, detail)


def register() -> None:
    """Register all business handlers with routine_autonomy.
    Idempotent -- re-registration replaces existing handlers."""
    # routine_autonomy.register_handler refuses unknown kind.
    for kind, fn in (
        ("opportunity_discovery", opportunity_discovery_handler),
        ("business_workstream_proposal",
         business_workstream_proposal_handler),
        ("local_draft_action_creation",
         local_draft_action_creation_handler),
    ):
        routine_autonomy._HANDLERS.pop(kind, None)
        register_handler(kind, fn)
        logger.info("business.routine.registered", kind=kind)


# Auto-register on import. Tests using isolated_state can call
# `routine_autonomy._HANDLERS.clear()` and then re-register
# explicitly.
register()
