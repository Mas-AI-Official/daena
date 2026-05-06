"""Outreach -> Gmail draft bridge -- Sprint-19 PR-4 (2026-05-06).

Take a ``BizOutreachDraft`` and produce a pending GoaRequest for the
``gmail.create_draft`` controlled tool. Trust ladder may auto-approve
the request if all 6 Sprint-18 walls pass.

This module does NOT:

  * call the Gmail HTTP API itself (the dispatcher does that)
  * send anything (gmail.create_draft is NOT a send tool)
  * advance status to 'sent' (only the send bridge does)

It DOES:

  * verify OAuth readiness for the owner_email (refuses early)
  * stamp the outreach draft with create_draft_approval_id linkage
  * advance the draft status to 'queued_create_draft'
  * NEVER raise -- typed result for every failure mode
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import BizOutreachDraft
from app.models.connections import Connector, ConnectorInstance
from app.models.governance import GoaRequest
from app.services.controlled_execution_dispatch import compute_payload_hash
from app.services.trust_auto_approve import maybe_apply_trust_auto_approval
from app.services.trust_policy import DispatchInitiator

logger = get_logger(__name__)


_TOOL_ID = "gmail.create_draft"
_APPROVAL_TTL_HOURS = 24


@dataclass
class GmailDraftBridgeResult:
    success: bool
    outreach_draft_id: str
    approval_id: str | None
    auto_approved: bool
    payload_hash: str | None
    payload: dict | None
    refusal_code: str | None = None


async def _gmail_oauth_ready(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    owner_email: str,
) -> bool:
    """True iff a Gmail ConnectorInstance with a non-empty
    access_token exists for (tenant, user, owner_email)."""
    target = (owner_email or "").strip().lower()
    if not target:
        return False
    conn = (await db.execute(
        select(Connector).where(Connector.name == "Gmail"),
    )).scalar_one_or_none()
    if conn is None:
        return False
    rows = (await db.execute(
        select(ConnectorInstance)
        .where(ConnectorInstance.tenant_id == tenant_id)
        .where(ConnectorInstance.user_id == user_id)
        .where(ConnectorInstance.connector_id == conn.id),
    )).scalars().all()
    for inst in rows:
        if (inst.owner_email or "").strip().lower() != target:
            continue
        creds = inst.credentials or {}
        if creds.get("access_token"):
            return True
    return False


async def queue_gmail_draft_creation(
    db: AsyncSession,
    *,
    outreach_draft_id: uuid.UUID,
    owner_email: str,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    initiator: DispatchInitiator = DispatchInitiator.OPERATOR,
) -> GmailDraftBridgeResult:
    """Queue a Gmail create_draft approval for the outreach draft.

    NEVER raises. Returns typed result; refusal_code is stable.
    """
    # 1: load outreach draft
    draft = (await db.execute(
        select(BizOutreachDraft).where(
            BizOutreachDraft.id == outreach_draft_id,
            BizOutreachDraft.tenant_id == tenant_id,
        ),
    )).scalar_one_or_none()
    if draft is None:
        return GmailDraftBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            payload=None,
            refusal_code="outreach_draft_not_found",
        )

    # 2: status precondition
    if draft.status != "drafted":
        return GmailDraftBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            payload=None,
            refusal_code=f"draft_status_not_drafted:{draft.status}",
        )

    # 3: OAuth readiness
    if not await _gmail_oauth_ready(
        db, tenant_id=tenant_id, user_id=user_id, owner_email=owner_email,
    ):
        return GmailDraftBridgeResult(
            success=False,
            outreach_draft_id=str(outreach_draft_id),
            approval_id=None,
            auto_approved=False,
            payload_hash=None,
            payload=None,
            refusal_code="gmail_oauth_not_ready",
        )

    # 4: build payload + hash
    payload = {
        "to": draft.recipient_email,
        "subject": draft.subject,
        "body": draft.body,
    }
    payload_hash = compute_payload_hash(payload)

    # 5: create the approval row
    expires_at = datetime.now(UTC) + timedelta(hours=_APPROVAL_TTL_HOURS)
    approval = GoaRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        action_type=_TOOL_ID,
        action_params={
            "to": draft.recipient_email,
            "subject": draft.subject,
            "body": draft.body,
            "outreach_draft_id": str(draft.id),
            "payload_hash": payload_hash,
            "owner_email": owner_email,
        },
        risk_level="LOW",
        governance_tier=2,
        status="PENDING",
        expires_at=expires_at,
    )
    db.add(approval)
    await db.flush()

    # 6: maybe trust-graduate
    decision = await maybe_apply_trust_auto_approval(
        db,
        approval=approval,
        payload=payload,
        initiator=initiator,
        decided_by=user_id,
    )

    # 7: link draft to approval + advance status
    draft.create_draft_approval_id = approval.id
    draft.status = "queued_create_draft"
    await db.flush()

    logger.info(
        "outreach.gmail_bridge.queued",
        outreach_draft_id=str(draft.id),
        approval_id=str(approval.id),
        auto_approved=decision.auto_approve,
        initiator=initiator.value,
    )

    return GmailDraftBridgeResult(
        success=True,
        outreach_draft_id=str(draft.id),
        approval_id=str(approval.id),
        auto_approved=decision.auto_approve,
        payload_hash=payload_hash,
        payload=payload,
    )
