"""Outreach -> Gmail send bridge -- Sprint-19 PR-5 (2026-05-06).

Take a ``BizOutreachDraft`` whose Gmail draft has already been
created (status='gmail_draft_created') and queue a SECOND approval
for the ``gmail.send_existing_draft`` controlled tool.

This bridge:

  * checks the rate limit BEFORE creating the approval row
    (independent gate -- even auto-approved sends count toward
    the daily cap)
  * NEVER auto-approves -- `gmail.send_existing_draft` is in
    ``TRUST_FORBIDDEN_TOOLS`` (Sprint-18) and `should_auto_approve`
    refuses by wall #1
  * NEVER raises
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import BizOutreachDraft
from app.models.governance import GoaRequest
from app.services.controlled_execution_dispatch import compute_payload_hash
from app.services.outreach.send_rate_limit import (
    RateLimitDecision,
    check_and_increment,
)
from app.services.trust_auto_approve import maybe_apply_trust_auto_approval
from app.services.trust_policy import DispatchInitiator

logger = get_logger(__name__)


_TOOL_ID = "gmail.send_existing_draft"
_APPROVAL_TTL_HOURS = 24


@dataclass
class SendBridgeResult:
    success: bool
    outreach_draft_id: str
    approval_id: str | None
    auto_approved: bool
    payload_hash: str | None
    rate_limit_used: int
    rate_limit_cap: int
    refusal_code: str | None = None


async def queue_gmail_send(
    db: AsyncSession,
    *,
    outreach_draft_id: uuid.UUID,
    owner_email: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    initiator: DispatchInitiator = DispatchInitiator.OPERATOR,
) -> SendBridgeResult:
    """Queue a send approval for the outreach draft. NEVER raises."""

    # 1: load outreach draft
    draft = (await db.execute(
        select(BizOutreachDraft).where(
            BizOutreachDraft.id == outreach_draft_id,
            BizOutreachDraft.tenant_id == tenant_id,
        ),
    )).scalar_one_or_none()
    if draft is None:
        return SendBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            rate_limit_used=0,
            rate_limit_cap=0,
            refusal_code="outreach_draft_not_found",
        )

    # 2: status precondition -- Gmail draft must already exist.
    if draft.status != "gmail_draft_created":
        return SendBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            rate_limit_used=0,
            rate_limit_cap=0,
            refusal_code=f"draft_status_not_gmail_draft_created:{draft.status}",
        )

    # 3: linkage check
    if not draft.gmail_draft_id:
        return SendBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            rate_limit_used=0,
            rate_limit_cap=0,
            refusal_code="gmail_draft_id_missing",
        )

    # 4: RATE LIMIT (independent gate, fires BEFORE approval row).
    rl = check_and_increment(tenant_id)
    if not rl.allowed:
        # Stamp the draft to reflect the refusal.
        draft.status = "rate_limited"
        draft.blocked_reason = rl.reason
        await db.flush()
        logger.warning(
            "outreach.send_bridge.rate_limited",
            outreach_draft_id=str(draft.id),
            used=rl.used, cap=rl.cap,
        )
        return SendBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            rate_limit_used=rl.used,
            rate_limit_cap=rl.cap,
            refusal_code=rl.reason or "rate_limit_exceeded",
        )

    # 5: build payload + hash. Payload for send_existing_draft is
    # just the draft_id; the snapshot integrity check inside the
    # send handler verifies recipient/subject/body match what was
    # stored.
    payload = {"draft_id": draft.gmail_draft_id}
    payload_hash = compute_payload_hash(payload)

    # 6: create approval row
    expires_at = datetime.now(UTC) + timedelta(hours=_APPROVAL_TTL_HOURS)
    approval = GoaRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=_TOOL_ID,
        action_params={
            "draft_id": draft.gmail_draft_id,
            "outreach_draft_id": str(draft.id),
            "payload_hash": payload_hash,
            "owner_email": owner_email,
        },
        risk_level="MEDIUM",  # send is medium even for low-effort drafts
        governance_tier=2,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(approval)
    await db.flush()

    # 7: trust-graduate? send_existing_draft is FORBIDDEN from
    # graduation by Sprint-18 wall #1, so this should ALWAYS return
    # auto_approve=False. We still call it so the audit trail
    # records the decision reason explicitly.
    decision = await maybe_apply_trust_auto_approval(
        db,
        approval=approval,
        payload=payload,
        initiator=initiator,
        decided_by=user_id,
    )
    # Defensive sanity: send must NEVER auto-approve.
    if decision.auto_approve:
        logger.error(
            "outreach.send_bridge.unexpected_auto_approve",
            tool_id=_TOOL_ID, approval_id=str(approval.id),
        )

    draft.send_approval_id = approval.id
    draft.status = "queued_send"
    await db.flush()

    logger.info(
        "outreach.send_bridge.queued",
        outreach_draft_id=str(draft.id),
        approval_id=str(approval.id),
        rate_limit_used=rl.used,
        rate_limit_cap=rl.cap,
    )

    return SendBridgeResult(
        success=True,
        outreach_draft_id=str(draft.id),
        approval_id=str(approval.id),
        auto_approved=False,  # send NEVER auto-approves
        payload_hash=payload_hash,
        rate_limit_used=rl.used,
        rate_limit_cap=rl.cap,
    )
