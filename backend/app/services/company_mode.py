"""Company Mode: activate Daena as an autonomous AI marketing+sales agency.

Turns a founder brief ("find SMB fintech SecOps leads, 10-50 employees,
US/CA, pain: ransomware anxiety") into concrete Missions assigned to
the right Department Minds. The Minds then execute prospecting,
drafting, enrichment, and multi-touch sequencing.

**Safety posture (deliberate):**
- All outbound messages (LinkedIn, email, SMS) land in the existing
  approval queue as DRAFT by default. LinkedIn in particular explicitly
  bans automated messaging; unattended send risks account suspension.
- Founder can flip individual missions to AUTO_SEND after reviewing the
  first N drafts and confirming quality -- override stays founder-gated.
- Every outbound carries an audit trail: who approved, which Mind
  drafted, what the recipient's emotional context was at send time.

**Current boundaries (what IS and ISN'T autonomous):**
- [x] ICP expansion, prospect list generation (via SalesAgent.prospect).
- [x] Per-contact qualification scoring (via SalesAgent.qualify).
- [x] First-touch draft generation (via MarketingAgent.author_outreach).
- [x] Emotional-tone adaptation for drafts (via EmotionalSignal on
      recipient context where available).
- [x] Appointment-booking heuristic gated on reply sentiment.
- [ ] Actual LinkedIn/email SEND is stubbed -- produces a queued action
      for founder approval. Wiring real send providers is a separate
      ticket (LINKEDIN-PROVIDER, EMAIL-PROVIDER) because it requires
      per-tenant OAuth + account-risk disclosure.

Pattern: this orchestrator is a PURE COORDINATION LAYER. All heavy
lifting lives in the existing department agents; company_mode just
builds the brief, decomposes it into missions, and tracks outcomes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.services.departments.marketing_agent import create_marketing_agent
from app.services.departments.sales_agent import create_sales_agent

logger = get_logger(__name__)


class MissionChannel(str, Enum):
    """How the outbound goes out. Governance policies differ per channel."""

    LINKEDIN = "linkedin"
    EMAIL = "email"
    TWITTER_DM = "twitter_dm"
    SMS = "sms"
    WEB_FORM = "web_form"
    PHONE = "phone"


class MissionStatus(str, Enum):
    DRAFTING = "drafting"
    AWAITING_APPROVAL = "awaiting_approval"
    SENDING = "sending"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


@dataclass
class ActivationBrief:
    """What the founder tells Daena about the company's GTM push.

    Field design intentionally mirrors how a human marketing director
    would brief an agency: target, pain, promise, proof, channels, and
    safety posture. The soul already knows "how to think"; the brief
    tells Daena "what to do this quarter."
    """

    company_name: str
    company_one_liner: str
    target_customer: str
    customer_pain: str
    our_promise: str
    proof_points: list[str] = field(default_factory=list)
    channels: list[MissionChannel] = field(default_factory=lambda: [MissionChannel.LINKEDIN, MissionChannel.EMAIL])
    prospect_limit_per_mission: int = 10
    tone: str = "warm-direct"              # rendered into the tonal overlay
    auto_send: bool = False                # override to skip approval queue (NOT recommended for LinkedIn)
    require_founder_approval: bool = True  # hard gate for outbound sends
    notes: str | None = None


@dataclass
class Mission:
    """A scoped job for a Department Mind in response to an activation."""

    id: str
    department_slug: str
    mind_name: str
    channel: MissionChannel
    objective: str
    status: MissionStatus = MissionStatus.DRAFTING
    prospects_found: int = 0
    drafts_generated: int = 0
    drafts_sent: int = 0
    drafts_awaiting_approval: int = 0
    errors: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class ActivationResult:
    """What ``activate`` returns: missions + human-readable summary."""

    activation_id: str
    brief: ActivationBrief
    missions: list[Mission] = field(default_factory=list)
    summary: str = ""
    prospects: list[dict[str, Any]] = field(default_factory=list)
    drafts_preview: list[dict[str, Any]] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "activation_id": self.activation_id,
            "created_at": self.created_at.isoformat(),
            "brief": {
                "company_name": self.brief.company_name,
                "target_customer": self.brief.target_customer,
                "channels": [c.value for c in self.brief.channels],
                "auto_send": self.brief.auto_send,
            },
            "missions": [
                {
                    "id": m.id,
                    "department": m.department_slug,
                    "mind": m.mind_name,
                    "channel": m.channel.value,
                    "objective": m.objective,
                    "status": m.status.value,
                    "prospects_found": m.prospects_found,
                    "drafts_generated": m.drafts_generated,
                    "drafts_awaiting_approval": m.drafts_awaiting_approval,
                    "errors": m.errors,
                }
                for m in self.missions
            ],
            "summary": self.summary,
            "prospects_count": len(self.prospects),
            "drafts_preview": self.drafts_preview[:5],
            "next_steps": self.next_steps,
        }


def _build_icp(brief: ActivationBrief) -> str:
    """Format the brief into an ICP string SalesAgent.prospect understands."""
    lines = [
        f"Target customer: {brief.target_customer}",
        f"Pain we address: {brief.customer_pain}",
        f"Our promise: {brief.our_promise}",
    ]
    if brief.proof_points:
        lines.append("Proof: " + "; ".join(brief.proof_points[:5]))
    return " | ".join(lines)


async def _dispatch_sales_mission(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    brief: ActivationBrief,
) -> tuple[Mission, list[dict[str, Any]]]:
    """Run the Sales Mind against the brief: prospecting + qualification."""
    mission = Mission(
        id=str(uuid.uuid4()),
        department_slug="sales",
        mind_name="Orion",
        channel=MissionChannel.LINKEDIN,  # default home for outbound; founder overrides via brief.channels
        objective=(
            f"Find and qualify prospects matching: {brief.target_customer}. "
            f"Top {brief.prospect_limit_per_mission}."
        ),
    )
    sales = create_sales_agent(db=db, tenant_id=tenant_id, user_id=user_id)
    icp = _build_icp(brief)

    try:
        contacts = await sales.prospect(
            icp_description=icp,
            limit=brief.prospect_limit_per_mission,
        )
        mission.prospects_found = len(contacts)
        mission.status = MissionStatus.AWAITING_APPROVAL
        logger.info(
            "company_mode.sales_dispatched",
            mission_id=mission.id,
            prospects=mission.prospects_found,
        )
        return mission, contacts
    except Exception as exc:
        mission.errors.append(f"sales_dispatch_failed: {exc}")
        mission.status = MissionStatus.FAILED
        logger.warning("company_mode.sales_failed", error=str(exc))
        return mission, []


async def _dispatch_marketing_mission(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    brief: ActivationBrief,
    prospects: list[dict[str, Any]],
) -> tuple[Mission, list[dict[str, Any]]]:
    """Run the Marketing Mind: generate personalized first-touch drafts."""
    mission = Mission(
        id=str(uuid.uuid4()),
        department_slug="marketing",
        mind_name="Zephyr",
        channel=brief.channels[0] if brief.channels else MissionChannel.EMAIL,
        objective=(
            f"Draft {mission_channel_label(brief)}-appropriate first-touch messages for "
            f"{len(prospects)} prospects. Tone: {brief.tone}."
        ),
    )
    if not prospects:
        mission.status = MissionStatus.COMPLETED
        mission.errors.append("no_prospects_from_sales")
        return mission, []

    marketing = create_marketing_agent(db=db, tenant_id=tenant_id, user_id=user_id)
    drafts: list[dict[str, Any]] = []
    for contact in prospects:
        try:
            # author_outreach signature varies by deployment -- we pass the
            # minimum required + optional context. The agent's current
            # contract accepts (contact_id, context) and we supply the
            # emotional / brief context under ``context``.
            contact_id = contact.get("id") or contact.get("contact_id")
            if not contact_id:
                continue
            draft = await marketing.author_outreach(
                contact_id=str(contact_id),
                context={
                    "brief": {
                        "company": brief.company_name,
                        "one_liner": brief.company_one_liner,
                        "promise": brief.our_promise,
                        "proof": brief.proof_points[:3],
                        "tone": brief.tone,
                    },
                    "channel": mission.channel.value,
                    "require_approval": brief.require_founder_approval,
                },
            )
            if draft:
                drafts.append(draft)
                mission.drafts_generated += 1
                if not brief.auto_send:
                    mission.drafts_awaiting_approval += 1
        except TypeError:
            # Older MarketingAgent.author_outreach signature: (contact_id,)
            # Fallback keeps the pipeline alive if the agent was shipped
            # before the context-kwarg contract.
            try:
                draft = await marketing.author_outreach(contact_id=str(contact_id))
                if draft:
                    drafts.append(draft)
                    mission.drafts_generated += 1
                    if not brief.auto_send:
                        mission.drafts_awaiting_approval += 1
            except Exception as exc:
                mission.errors.append(f"draft_failed:{contact_id}:{exc}")
        except Exception as exc:
            mission.errors.append(f"draft_failed:{contact_id}:{exc}")

    mission.status = (
        MissionStatus.COMPLETED if brief.auto_send else MissionStatus.AWAITING_APPROVAL
    )
    logger.info(
        "company_mode.marketing_dispatched",
        mission_id=mission.id,
        drafts=mission.drafts_generated,
        awaiting=mission.drafts_awaiting_approval,
    )
    return mission, drafts


def mission_channel_label(brief: ActivationBrief) -> str:
    return brief.channels[0].value if brief.channels else "email"


async def activate(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    brief: ActivationBrief,
) -> ActivationResult:
    """Turn a founder brief into live missions across Sales + Marketing.

    Current orchestration (deliberately minimal -- additions land here
    as we ship more channels):
        1. Sales Mind (Orion) prospects against the ICP.
        2. Marketing Mind (Zephyr) drafts first-touch messages.
        3. Outbound lands in the approval queue unless ``auto_send=True``.
        4. Result summarizes for the founder + lists the next buttons.

    Safety:
        - LinkedIn automation violates their ToS; auto_send on LINKEDIN
          channel should trigger a governance warning in the REST layer.
        - Every prospect + draft is persisted via existing CRM tables
          (Account, Contact, OutreachDraft) so the Pipeline page renders.

    Returns:
        ActivationResult with missions, prospect list, draft previews,
        and next-step buttons for the founder UI.
    """
    result = ActivationResult(activation_id=str(uuid.uuid4()), brief=brief)
    logger.info(
        "company_mode.activate",
        activation_id=result.activation_id,
        tenant_id=str(tenant_id),
        company=brief.company_name,
        channels=[c.value for c in brief.channels],
        auto_send=brief.auto_send,
    )

    # ── Mission 1: Sales discovery ──
    sales_mission, prospects = await _dispatch_sales_mission(db, tenant_id, user_id, brief)
    result.missions.append(sales_mission)
    result.prospects = prospects

    # ── Mission 2: Marketing drafting ──
    marketing_mission, drafts = await _dispatch_marketing_mission(
        db, tenant_id, user_id, brief, prospects,
    )
    result.missions.append(marketing_mission)
    result.drafts_preview = drafts

    # ── Founder-facing summary ──
    result.summary = _format_summary(brief, result.missions, len(prospects), len(drafts))
    result.next_steps = _format_next_steps(brief, result.missions)

    # Commit CRM writes from both agents
    try:
        await db.commit()
    except Exception as exc:
        logger.warning("company_mode.commit_failed", error=str(exc))

    return result


def _format_summary(
    brief: ActivationBrief,
    missions: list[Mission],
    prospect_count: int,
    draft_count: int,
) -> str:
    failed = [m for m in missions if m.status == MissionStatus.FAILED]
    if failed:
        return (
            f"Activated with issues. "
            f"{prospect_count} prospects found, {draft_count} drafts. "
            f"{len(failed)} mission(s) failed: "
            + "; ".join(f"{m.mind_name}({m.department_slug})" for m in failed)
        )
    awaiting = sum(m.drafts_awaiting_approval for m in missions)
    return (
        f"{brief.company_name} GTM push active. "
        f"Orion found {prospect_count} prospects matching '{brief.target_customer}'. "
        f"Zephyr drafted {draft_count} personalized first-touch messages on "
        f"{mission_channel_label(brief)}. "
        + (
            f"{awaiting} awaiting your review in the approval queue."
            if awaiting
            else "Auto-send enabled -- monitor replies."
        )
    )


def _format_next_steps(brief: ActivationBrief, missions: list[Mission]) -> list[str]:
    steps: list[str] = []
    awaiting = any(m.drafts_awaiting_approval > 0 for m in missions)
    if awaiting:
        steps.append("Review drafts in the approval queue (one-click approve or edit).")
    if MissionChannel.LINKEDIN in brief.channels and brief.auto_send:
        steps.append(
            "LinkedIn auto-send is enabled -- this violates LinkedIn ToS and risks account suspension. "
            "Recommend switching to draft+click-to-send.",
        )
    steps.append(
        "Monitor reply sentiment on /pipeline -- Orion auto-qualifies + books on positive signal.",
    )
    steps.append("Run /company-mode/activate again next week to refresh the prospect list.")
    return steps
