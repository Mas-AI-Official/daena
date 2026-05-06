"""Safe first business outreach drill -- Sprint-20 PR-5 (2026-05-06).

Operator-runnable helper that walks the full outreach pipeline ONCE
for one allowlisted recipient. Stops at the FIRST approval -- the
operator must approve in the UI for the Gmail draft to be created,
and again for the send. The drill never bypasses any wall.

Six walls, each independent:

  1. Env flag     ``DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL=true``
  2. Allowlist    ``DAENA_DRILL_RECIPIENT_ALLOWLIST=a@x.com,b@y.com``
                  the recipient_email MUST appear here
  3. Opportunity  resolves by (tenant, opportunity_id)
  4. Recipient safety (existing 5-check wall)
  5. Rate limit   today's remaining > 0
  6. OAuth ready  Gmail ConnectorInstance present + access_token

If any wall fails, the drill returns a stable refusal code and
NEVER queues anything. If all walls pass, the drill produces:

  * Local BizOutreachDraft (status=drafted)
  * Pending GoaRequest for ``gmail.create_draft`` (NEVER auto-approved)

The operator approves in the UI; the controlled execution dispatcher
then creates the Gmail draft. A second approval is required to send
the draft -- that path is operator-driven through the UI, not from
this module. Nothing in this module bypasses that.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import Opportunity
from app.services.outreach.draft_factory import (
    create_outreach_draft_for_opportunity,
)
from app.services.outreach.gmail_bridge import queue_gmail_draft_creation
from app.services.outreach.send_rate_limit import (
    get_cap_per_day, get_usage,
)
from app.services.trust_policy import DispatchInitiator

logger = get_logger(__name__)


# ────────────────────────────────────────────────────────────────────


_ENABLE_FLAG = "DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL"
_ALLOWLIST_VAR = "DAENA_DRILL_RECIPIENT_ALLOWLIST"


def _is_enabled() -> bool:
    return (os.environ.get(_ENABLE_FLAG, "") or "").strip().lower() == "true"


def _parse_allowlist() -> set[str]:
    raw = os.environ.get(_ALLOWLIST_VAR, "") or ""
    return {
        e.strip().lower()
        for e in raw.split(",")
        if e.strip()
    }


# ────────────────────────────────────────────────────────────────────


@dataclass
class DrillResult:
    success: bool
    refusal_code: str | None = None
    outreach_draft_id: str | None = None
    gmail_create_draft_approval_id: str | None = None
    refusal_detail: str | None = None


REFUSAL_CODES: tuple[str, ...] = (
    "drill_disabled_env_flag_missing",
    "drill_recipient_allowlist_empty",
    "drill_recipient_not_in_allowlist",
    "drill_opportunity_not_found",
    "drill_rate_limit_exhausted",
    "drill_recipient_safety_failed",
    "drill_oauth_not_ready",
    "drill_gmail_bridge_failed",
)


async def run_outreach_drill(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    recipient_email: str,
    owner_email: str,
) -> DrillResult:
    """Walk the pipeline once for one recipient. Stops at first
    approval. NEVER auto-approves. NEVER raises.

    Six walls, each independent. Refusal codes are stable and feed
    the operator-facing summary.
    """

    # Wall 1: env flag
    if not _is_enabled():
        return DrillResult(
            success=False,
            refusal_code="drill_disabled_env_flag_missing",
            refusal_detail=(
                f"Set {_ENABLE_FLAG}=true to enable. "
                "This flag is operator-only -- never set by Daena."
            ),
        )

    # Wall 2: recipient allowlist
    allowlist = _parse_allowlist()
    if not allowlist:
        return DrillResult(
            success=False,
            refusal_code="drill_recipient_allowlist_empty",
            refusal_detail=(
                f"Set {_ALLOWLIST_VAR} to a comma-separated list of "
                "recipient emails the drill is allowed to target."
            ),
        )
    target = (recipient_email or "").strip().lower()
    if not target or target not in allowlist:
        return DrillResult(
            success=False,
            refusal_code="drill_recipient_not_in_allowlist",
            refusal_detail=(
                f"Recipient {recipient_email!r} not in "
                f"{_ALLOWLIST_VAR}. Add it explicitly to run the drill."
            ),
        )

    # Wall 3: opportunity exists
    opp = (await db.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.tenant_id == tenant_id,
        ),
    )).scalar_one_or_none()
    if opp is None:
        return DrillResult(
            success=False,
            refusal_code="drill_opportunity_not_found",
            refusal_detail=(
                f"No opportunity {opportunity_id} for this tenant."
            ),
        )

    # Wall 4: rate limit (read-only check; bridge does its own check
    # at send time, but if cap is already 0 there is no point creating
    # a draft + Gmail approval the operator cannot send).
    cap = get_cap_per_day()
    used = get_usage(tenant_id)
    if used >= cap:
        return DrillResult(
            success=False,
            refusal_code="drill_rate_limit_exhausted",
            refusal_detail=(
                f"Daily send cap reached ({used}/{cap}). "
                "Wait for the UTC day to roll over."
            ),
        )

    # Wall 5: recipient safety + draft creation
    factory_result = await create_outreach_draft_for_opportunity(
        db, opportunity=opp, user_id=user_id,
        recipient_email=recipient_email,
    )
    if factory_result.status != "drafted":
        return DrillResult(
            success=False,
            refusal_code="drill_recipient_safety_failed",
            refusal_detail=(
                f"Draft factory blocked: {factory_result.blocked_reason!r}."
            ),
            outreach_draft_id=factory_result.draft_id,
        )

    # Wall 6: OAuth ready -- queue the gmail.create_draft approval.
    bridge = await queue_gmail_draft_creation(
        db,
        outreach_draft_id=uuid.UUID(factory_result.draft_id),
        owner_email=owner_email,
        tenant_id=tenant_id,
        user_id=user_id,
        # Drill is operator-initiated by definition. Trust auto-approval
        # MAY fire ONLY if the trust ladder has been graduated -- this
        # mirrors the standard operator path.
        initiator=DispatchInitiator.OPERATOR,
    )
    if not bridge.success:
        if bridge.refusal_code == "gmail_oauth_not_ready":
            return DrillResult(
                success=False,
                refusal_code="drill_oauth_not_ready",
                refusal_detail=(
                    f"Gmail OAuth not connected for {owner_email!r}. "
                    "Open the Apps panel and connect this account."
                ),
                outreach_draft_id=factory_result.draft_id,
            )
        return DrillResult(
            success=False,
            refusal_code="drill_gmail_bridge_failed",
            refusal_detail=(
                f"Gmail bridge refused: {bridge.refusal_code!r}."
            ),
            outreach_draft_id=factory_result.draft_id,
        )

    logger.info(
        "outreach.drill.queued",
        tenant=str(tenant_id),
        opportunity=str(opportunity_id),
        outreach_draft=factory_result.draft_id,
        approval=bridge.approval_id,
        auto_approved=bridge.auto_approved,
    )

    return DrillResult(
        success=True,
        outreach_draft_id=factory_result.draft_id,
        gmail_create_draft_approval_id=bridge.approval_id,
    )
