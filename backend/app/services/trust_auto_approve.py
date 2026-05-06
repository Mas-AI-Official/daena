"""Trust auto-approval helper -- Sprint-18 PR-3 (2026-05-06).

Glue between ``trust_policy.should_auto_approve`` and the existing
GoaRequest lifecycle. Caller pattern:

  approval = GoaRequest(action_type=tool_id, status="PENDING", ...)
  db.add(approval)
  await db.flush()  # so approval.id exists
  decision = await maybe_apply_trust_auto_approval(
      db, approval=approval, payload=payload,
      initiator=DispatchInitiator.OPERATOR, decided_by=user_id,
  )
  if decision.auto_approve:
      ... approval is now status="APPROVED" with decision_reason
          set to "trust_graduated:<template_class>"

This module:

  * NEVER mutates trust_ladder counters. Auto-approvals are the
    *consequence* of operator review history, not new entries in
    it. The ladder grows only from genuine human decisions
    (record_decision called from the approve / reject endpoints).
  * NEVER calls a tool handler. Auto-approval just flips status;
    the controlled-execution dispatcher still has to be invoked
    by the caller and run all its gates.
  * NEVER raises -- returns the decision struct so the caller can
    audit-log the reason regardless of outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.governance import GoaRequest
from app.services import trust_policy
from app.services.trust_policy import (
    AutoApprovalDecision,
    DispatchInitiator,
)

logger = get_logger(__name__)


async def maybe_apply_trust_auto_approval(
    db: AsyncSession,
    *,
    approval: GoaRequest,
    payload: dict,
    initiator: DispatchInitiator,
    decided_by: UUID,
) -> AutoApprovalDecision:
    """If trust policy says auto-approve, mutate ``approval`` in place
    to status=APPROVED. Otherwise leave it as-is (caller already
    set status=PENDING).

    NEVER raises. NEVER touches trust_ladder. Returns the decision
    struct so callers can write an audit row carrying the reason.
    """
    decision = trust_policy.should_auto_approve(
        tool_id=approval.action_type or "",
        payload=payload or {},
        initiator=initiator,
    )

    if decision.auto_approve:
        approval.status = "APPROVED"
        approval.decided_by = decided_by
        approval.decided_at = datetime.now(UTC)
        approval.decision_reason = (
            f"trust_graduated:{decision.template_class or ''}"
        )
        # Caller still owns commit. We just flush so subsequent
        # selects see the row.
        try:
            await db.flush()
        except Exception as exc:  # noqa: BLE001
            # Flush failure is the caller's problem; we don't undo
            # the in-memory mutation because it's already in the
            # session and a rollback would clear it anyway.
            logger.warning(
                "trust_auto_approve.flush_failed",
                approval_id=str(approval.id),
                error=str(exc),
            )

        logger.info(
            "trust_auto_approve.applied",
            approval_id=str(approval.id),
            tool_id=approval.action_type,
            template_class=decision.template_class,
        )
    else:
        logger.info(
            "trust_auto_approve.skipped",
            approval_id=str(approval.id),
            tool_id=approval.action_type,
            reason=decision.reason,
        )

    return decision
