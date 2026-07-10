"""Opportunity-to-Workstream bridge -- Sprint-20 PR-3 (2026-05-06).

Promotes a discovered Opportunity into a tracked Workstream owned by
the department that should pursue it. The workstream is the operator's
unit of autonomy (Council R3 lock); pursuing an opportunity without a
workstream means the work has no owner, no timeline, no audit trail.

What this bridge DOES:
  * Resolves the opportunity by (tenant_id, opportunity_id).
  * Looks up the right Department by deterministic type-to-name map.
  * Refuses duplicate promotion (one workstream per opportunity).
  * Creates the Workstream with source_type=OPPORTUNITY +
    source_ref_id=opportunity.id + context fields snapshotted from
    the opportunity row.
  * Appends a STARTED WorkstreamEvent.
  * Stamps Opportunity.assigned_department + advances status to
    'queued' so the inbox card shows the promotion happened.

What this bridge DOES NOT DO:
  * Send email, post anywhere, submit a form, pay, scrape behind auth.
    None of those are reachable from this code.
  * Create approval rows. The bridge is a LOCAL audit move; outreach
    drafts and Gmail bridges remain separate (Sprint-19).
  * Auto-run on discovery. Promotion is operator-initiated (or
    routine-driven, but always with an explicit invocation).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.business import Opportunity
from app.models.organization import Department
from app.models.workstream import (
    Workstream,
    WorkstreamEvent,
    WorkstreamEventKind,
    WorkstreamSourceType,
    WorkstreamStatus,
)
from app.services.business_pipeline.validator import (
    has_persisted_validation,
)

logger = get_logger(__name__)


# ────────────────────────────────────────────────────────────────────
# Locked routing map
# ────────────────────────────────────────────────────────────────────


# Deterministic mapping. Each opportunity type goes to exactly one
# primary department. The "secondary" departments mentioned in the
# Sprint-20 brief are tracked in workstream context.collaborators
# rather than producing two parallel workstreams (which would split
# ownership and confuse the operator).
OPP_TYPE_TO_PRIMARY_DEPT: dict[str, str] = {
    "grant": "Finance",
    "accelerator": "Finance",
    "hackathon": "Engineering",
    "customer_lead": "Sales",
    "freelance_project": "Sales",
    "partnership": "Sales",
    "bug_bounty_program": "Security Operations",
    "content_opportunity": "Marketing",
    # Phase 4: Research owns idea validation (market research, competitive
    # analysis, tech scouting -- constants.py DEFAULT_DEPARTMENTS sunflower 6).
    "startup_idea": "Research",
}

OPP_TYPE_TO_COLLABORATORS: dict[str, list[str]] = {
    "grant": ["Founder Office"],
    "accelerator": ["Founder Office"],
    "hackathon": ["Product"],
    "customer_lead": ["Product"],
    "freelance_project": ["Product"],
    "partnership": ["Legal & Compliance"],
    "bug_bounty_program": [],
    "content_opportunity": ["Operations"],
    # Phase 4: Product shapes the idea, Finance sizes the market/unit economics.
    "startup_idea": ["Product", "Finance"],
}


# ────────────────────────────────────────────────────────────────────
# Errors
# ────────────────────────────────────────────────────────────────────


class WorkstreamBridgeError(Exception):
    """Stable refusal codes the API surfaces verbatim."""

    code: str = "bridge_error"


class OpportunityNotFound(WorkstreamBridgeError):
    code = "opportunity_not_found"


class UnknownOpportunityType(WorkstreamBridgeError):
    code = "unknown_opportunity_type"


class DepartmentNotFound(WorkstreamBridgeError):
    code = "department_not_found"


class DuplicateWorkstream(WorkstreamBridgeError):
    code = "duplicate_workstream"

    def __init__(self, existing_workstream_id: uuid.UUID):
        super().__init__(str(existing_workstream_id))
        self.existing_workstream_id = existing_workstream_id


class ValidationRequired(WorkstreamBridgeError):
    code = "validation_required"


# ────────────────────────────────────────────────────────────────────
# Bridge entry point
# ────────────────────────────────────────────────────────────────────


@dataclass
class BridgeResult:
    workstream_id: uuid.UUID
    department_name: str
    collaborators: list[str]
    opportunity_id: uuid.UUID


async def create_workstream_for_opportunity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    opportunity_id: uuid.UUID,
) -> BridgeResult:
    """Promote an Opportunity into a Workstream.

    Raises ``WorkstreamBridgeError`` subclasses for stable refusal
    codes the API can surface.
    """
    # 1. Resolve opportunity (tenant-scoped).
    opp_stmt = select(Opportunity).where(
        Opportunity.id == opportunity_id,
        Opportunity.tenant_id == tenant_id,
    )
    opp = (await db.execute(opp_stmt)).scalar_one_or_none()
    if opp is None:
        raise OpportunityNotFound(str(opportunity_id))

    # Phase 4 gate: a startup_idea must carry a persisted
    # validation score before it can consume a department's
    # effort. Human owns GO/NO-GO; this only enforces that
    # validation RAN (has_persisted_validation).
    if opp.type == "startup_idea" and not has_persisted_validation(
        opp.raw_metadata
    ):
        raise ValidationRequired(str(opportunity_id))

    # 2. Resolve target department by type.
    dept_name = OPP_TYPE_TO_PRIMARY_DEPT.get(opp.type)
    if dept_name is None:
        raise UnknownOpportunityType(opp.type)

    dept_stmt = select(Department).where(
        Department.tenant_id == tenant_id,
        Department.name == dept_name,
        Department.is_active.is_(True),
    )
    dept = (await db.execute(dept_stmt)).scalar_one_or_none()
    if dept is None:
        raise DepartmentNotFound(dept_name)

    # 3. Refuse duplicate promotion. A workstream already exists for
    # this opportunity if (source_type=OPPORTUNITY, source_ref_id=opp.id)
    # is present and not soft-deleted.
    existing_stmt = select(Workstream).where(
        Workstream.tenant_id == tenant_id,
        Workstream.source_type == WorkstreamSourceType.OPPORTUNITY,
        Workstream.source_ref_id == opp.id,
        Workstream.archived_at.is_(None),
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing is not None:
        raise DuplicateWorkstream(existing.id)

    # 4. Build the workstream. Snapshot opportunity fields into
    # context so the workstream remains stable if the opportunity row
    # is later mutated.
    collaborators = list(OPP_TYPE_TO_COLLABORATORS.get(opp.type, []))
    goal = f"Pursue {opp.type.replace('_', ' ')}: {opp.title[:80]}"
    next_step = (
        opp.next_action
        or "Decide whether to draft outreach for this opportunity."
    )
    context = {
        "opportunity_type": opp.type,
        "opportunity_title": opp.title,
        "source_name": opp.source_name,
        "source_url": opp.source_url,
        "deadline_at": (
            opp.deadline_at.isoformat() if opp.deadline_at else None
        ),
        "estimated_value_usd": opp.estimated_value_usd,
        "score_at_promotion": opp.score,
        "collaborators": collaborators,
    }

    ws = Workstream(
        tenant_id=tenant_id,
        department_id=dept.id,
        user_id=user_id,
        goal=goal[:500],
        status=WorkstreamStatus.RUNNING,
        next_step_text=next_step[:500],
        context=context,
        source_type=WorkstreamSourceType.OPPORTUNITY,
        source_ref_id=opp.id,
        progress_percent=0,
    )
    db.add(ws)
    await db.flush()  # populate ws.id

    db.add(WorkstreamEvent(
        tenant_id=tenant_id,
        workstream_id=ws.id,
        kind=WorkstreamEventKind.STARTED,
        summary=f"Promoted from opportunity inbox ({opp.type}).",
        payload={
            "opportunity_id": str(opp.id),
            "department": dept_name,
            "collaborators": collaborators,
        },
    ))

    # 5. Stamp the opportunity row so the inbox shows promotion + the
    # operator can see which department now owns it. Status advances
    # 'discovered' -> 'queued' (the next legal status).
    opp.assigned_department = dept_name
    if opp.status == "discovered":
        opp.status = "queued"

    await db.flush()

    logger.info(
        "business.opportunity.promoted_to_workstream",
        opportunity_id=str(opp.id),
        workstream_id=str(ws.id),
        department=dept_name,
    )

    return BridgeResult(
        workstream_id=ws.id,
        department_name=dept_name,
        collaborators=collaborators,
        opportunity_id=opp.id,
    )
