"""Outreach draft factory -- Sprint-19 PR-3 (2026-05-06).

Turn an ``Opportunity`` row into a local ``BizOutreachDraft`` row.

Hard rules:

  * No external action.
  * Recipient safety wall MUST pass before persistence (drafts that
    fail safety land with status='blocked_recipient' for the
    operator to see; they NEVER reach the Gmail bridge).
  * Payload hash is computed over canonical JSON of
    {to, subject, body}.
  * Confidence + needs_review are stamped per draft kind.
  * Templates are deterministic Python f-strings; no LLM in v1.
    Future sprints can layer LLM-suggested body on top, but
    factory output stays auditable.

Mapping opportunity_type -> draft_kind:

  customer_lead       -> customer_cold_email
  grant               -> grant_inquiry_email
  accelerator         -> accelerator_intro_email
  hackathon           -> hackathon_application_inquiry
  freelance_project   -> customer_cold_email
  partnership         -> partnership_email
  bug_bounty_program  -> security_program_inquiry
  content_opportunity -> partnership_email   (closest fit)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import (
    OUTREACH_DRAFT_KINDS,
    BizOutreachDraft,
    Opportunity,
)
from app.services.outreach.recipient_safety import (
    RecipientSafetyResult,
    check_recipient_safety,
)

logger = get_logger(__name__)


_OPPORTUNITY_TO_DRAFT_KIND: dict[str, str] = {
    "customer_lead": "customer_cold_email",
    "grant": "grant_inquiry_email",
    "accelerator": "accelerator_intro_email",
    "hackathon": "hackathon_application_inquiry",
    "freelance_project": "customer_cold_email",
    "partnership": "partnership_email",
    "bug_bounty_program": "security_program_inquiry",
    "content_opportunity": "partnership_email",
}


@dataclass
class DraftFactoryResult:
    draft_id: str | None
    status: str
    safety: RecipientSafetyResult | None
    blocked_reason: str | None = None


def compute_payload_hash(*, to: str, subject: str, body: str) -> str:
    """Canonical hash over outreach payload. Mirrors the dispatcher's
    hash format so downstream Gmail bridge can compose without
    drift."""
    payload = {"to": to, "subject": subject, "body": body}
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ────────────────────────────────────────────────────────────────────
# Templates -- deterministic, no LLM in v1
# ────────────────────────────────────────────────────────────────────


def _render_subject(opportunity: Opportunity, draft_kind: str) -> str:
    title = (opportunity.title or "").strip()
    if draft_kind == "customer_cold_email":
        return f"Quick intro: {title}"
    if draft_kind == "grant_inquiry_email":
        return f"Inquiry: {title}"
    if draft_kind == "accelerator_intro_email":
        return f"Application interest: {title}"
    if draft_kind == "hackathon_application_inquiry":
        return f"Team / participation inquiry: {title}"
    if draft_kind == "partnership_email":
        return f"Partnership exploration: {title}"
    if draft_kind == "security_program_inquiry":
        return f"Program scope inquiry: {title}"
    return title


def _render_body(opportunity: Opportunity, draft_kind: str) -> str:
    title = (opportunity.title or "").strip()
    description = (opportunity.description or "").strip()
    source = opportunity.source_url or opportunity.source_name

    intros = {
        "customer_cold_email": (
            f"Hi,\n\nI'm reaching out regarding {title}. "
            f"Briefly: MAS-AI Technologies builds governed AI "
            f"orchestration; we may be a fit. Would a 15-minute "
            f"call this or next week be useful?\n\n"
        ),
        "grant_inquiry_email": (
            f"Hi,\n\nI'm exploring the {title} program. We are "
            f"MAS-AI Technologies (Ontario) building governed "
            f"multi-agent AI for SMBs. Could you share the next "
            f"intake date and any pre-screening questions?\n\n"
        ),
        "accelerator_intro_email": (
            f"Hi,\n\nWe are MAS-AI Technologies and would like to "
            f"apply to {title}. Brief context: governed AI "
            f"orchestration platform, two USPTO provisionals filed, "
            f"early customer pipeline forming. Could we get any "
            f"prep guidance before submitting?\n\n"
        ),
        "hackathon_application_inquiry": (
            f"Hi,\n\nWe're interested in joining {title}. Two "
            f"questions: (1) is solo participation allowed, "
            f"(2) any pre-event team-matching channel?\n\n"
        ),
        "partnership_email": (
            f"Hi,\n\nI noticed {title} and think there may be a "
            f"partnership angle with MAS-AI's governed AI platform. "
            f"Open to a short exploratory call?\n\n"
        ),
        "security_program_inquiry": (
            f"Hi,\n\nI'd like to confirm the in-scope assets and "
            f"acceptance criteria for {title} before submitting "
            f"any reports.\n\n"
        ),
    }
    intro = intros.get(draft_kind, f"Hi,\n\nRegarding {title}.\n\n")
    body_parts = [intro]
    if description:
        body_parts.append(f"Context I noted: {description}\n\n")
    body_parts.append(
        "Best,\nMasoud Masoori\nFounder, MAS-AI Technologies Inc.\n"
    )
    if source:
        body_parts.append(f"\nReference: {source}\n")
    return "".join(body_parts)


# ────────────────────────────────────────────────────────────────────
# Factory entry point
# ────────────────────────────────────────────────────────────────────


async def create_outreach_draft_for_opportunity(
    db: AsyncSession,
    *,
    opportunity: Opportunity,
    user_id: uuid.UUID,
    recipient_email: str,
    confidence: int = 50,
) -> DraftFactoryResult:
    """Create a BizOutreachDraft for the given Opportunity.

    Recipient safety is enforced -- if it fails, the draft is still
    persisted but with status='blocked_recipient' so the operator
    can see what was attempted.

    NEVER raises.
    """
    draft_kind = _OPPORTUNITY_TO_DRAFT_KIND.get(opportunity.type)
    if draft_kind is None or draft_kind not in OUTREACH_DRAFT_KINDS:
        return DraftFactoryResult(
            draft_id=None,
            status="rejected",
            safety=None,
            blocked_reason="opportunity_type_not_mappable",
        )

    safety = await check_recipient_safety(
        db, recipient=recipient_email, tenant_id=opportunity.tenant_id,
    )

    subject = _render_subject(opportunity, draft_kind)
    body = _render_body(opportunity, draft_kind)
    payload_hash = compute_payload_hash(
        to=safety.recipient, subject=subject, body=body,
    )

    if not safety.safe:
        draft = BizOutreachDraft(
            tenant_id=opportunity.tenant_id,
            user_id=user_id,
            opportunity_id=opportunity.id,
            draft_kind=draft_kind,
            recipient_email=safety.recipient,
            subject=subject,
            body=body,
            payload_hash=payload_hash,
            needs_review=True,
            confidence=0,
            status="blocked_recipient",
            blocked_reason=safety.reason,
        )
        db.add(draft)
        await db.flush()
        logger.info(
            "outreach.draft.blocked_recipient",
            opportunity_id=str(opportunity.id),
            reason=safety.reason,
        )
        return DraftFactoryResult(
            draft_id=str(draft.id),
            status="blocked_recipient",
            safety=safety,
            blocked_reason=safety.reason,
        )

    draft = BizOutreachDraft(
        tenant_id=opportunity.tenant_id,
        user_id=user_id,
        opportunity_id=opportunity.id,
        draft_kind=draft_kind,
        recipient_email=safety.recipient,
        subject=subject,
        body=body,
        payload_hash=payload_hash,
        needs_review=True,
        confidence=max(0, min(100, int(confidence))),
        status="drafted",
    )
    db.add(draft)
    await db.flush()

    # Mark the opportunity as having a draft so the inbox UI shows it.
    opportunity.status = "drafted"
    await db.flush()

    logger.info(
        "outreach.draft.created",
        opportunity_id=str(opportunity.id),
        draft_id=str(draft.id),
        draft_kind=draft_kind,
    )
    return DraftFactoryResult(
        draft_id=str(draft.id),
        status="drafted",
        safety=safety,
    )
