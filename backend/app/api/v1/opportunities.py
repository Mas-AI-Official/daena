"""Opportunities API -- Sprint-19 PR-2 (2026-05-06).

Read + minor-mutation surface over the ``opportunities`` table.

Endpoints:

  * GET  /opportunities                       -- list (filterable)
  * GET  /opportunities/{id}                  -- one row
  * POST /opportunities/run-discovery         -- run orchestrator now
  * POST /opportunities/{id}/archive          -- mark archived
  * POST /opportunities/{id}/reject           -- mark rejected

NO send / submit / post / pay endpoints. The status mutations
above are local-only audit moves; the controlled execution
dispatcher is the only path to external action.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.business import (
    OPPORTUNITY_STATUSES,
    OPPORTUNITY_TYPES,
    Opportunity,
)
from app.services.business_pipeline.orchestrator import run_discovery_loop
from app.services.business_pipeline.workstream_bridge import (
    DepartmentNotFound,
    DuplicateWorkstream,
    OpportunityNotFound,
    UnknownOpportunityType,
    WorkstreamBridgeError,
    create_workstream_for_opportunity,
)

logger = get_logger(__name__)
router = APIRouter()


class OpportunityRow(BaseModel):
    id: str
    type: str
    title: str
    description: str | None
    source_name: str
    source_url: str | None
    score: int
    deadline_at: str | None
    estimated_value_usd: int | None
    effort_hours: int | None
    risk_label: str | None
    next_action: str | None
    assigned_department: str | None
    status: str
    created_at: str
    updated_at: str | None


def _row_to_response(o: Opportunity) -> OpportunityRow:
    return OpportunityRow(
        id=str(o.id),
        type=o.type,
        title=o.title,
        description=o.description,
        source_name=o.source_name,
        source_url=o.source_url,
        score=o.score,
        deadline_at=o.deadline_at.isoformat() if o.deadline_at else None,
        estimated_value_usd=o.estimated_value_usd,
        effort_hours=o.effort_hours,
        risk_label=o.risk_label,
        next_action=o.next_action,
        assigned_department=o.assigned_department,
        status=o.status,
        created_at=o.created_at.isoformat() if o.created_at else "",
        updated_at=o.updated_at.isoformat() if o.updated_at else None,
    )


# ── Sprint-20 PR-4: Send rate limit visibility ───────────────────────
# Mounted BEFORE /{opportunity_id} so FastAPI's route matcher does not
# treat 'send-rate-limit' as a UUID-shaped path parameter.


class SendRateLimitResponse(BaseModel):
    today_utc: str
    used: int
    cap: int
    remaining: int


@router.get("/send-rate-limit", response_model=SendRateLimitResponse)
async def send_rate_limit(
    user: CurrentUser = Depends(get_current_user),
) -> SendRateLimitResponse:
    """How many outreach sends remain today for this tenant.

    Pure read of the persistent counter. NEVER mutates. Surfaced on
    the OpportunityInboxPage so the operator never has to guess
    whether a send will be rate-limited before they queue it.
    """
    from datetime import UTC, datetime

    from app.services.outreach.send_rate_limit import (
        get_cap_per_day, get_usage,
    )
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    used = get_usage(user.tenant_id, day=today)
    cap = get_cap_per_day()
    return SendRateLimitResponse(
        today_utc=today, used=used, cap=cap,
        remaining=max(cap - used, 0),
    )


@router.get("/", response_model=list[OpportunityRow])
async def list_opportunities(
    status: str | None = Query(None),
    type: str | None = Query(None),  # noqa: A002
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OpportunityRow]:
    stmt = select(Opportunity).where(Opportunity.tenant_id == user.tenant_id)
    if status is not None:
        if status not in OPPORTUNITY_STATUSES:
            raise HTTPException(status_code=400, detail="invalid_status")
        stmt = stmt.where(Opportunity.status == status)
    if type is not None:
        if type not in OPPORTUNITY_TYPES:
            raise HTTPException(status_code=400, detail="invalid_type")
        stmt = stmt.where(Opportunity.type == type)
    stmt = stmt.order_by(Opportunity.score.desc(), Opportunity.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_row_to_response(r) for r in rows]


@router.get("/{opportunity_id}", response_model=OpportunityRow)
async def get_opportunity(
    opportunity_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRow:
    try:
        oid = uuid.UUID(opportunity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_uuid")
    stmt = select(Opportunity).where(
        Opportunity.id == oid, Opportunity.tenant_id == user.tenant_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    return _row_to_response(row)


class RunDiscoveryRequest(BaseModel):
    top_n: int = Field(default=10, ge=1, le=100)


class RunDiscoveryResponse(BaseModel):
    discovered_count: int
    deduped_count: int
    persisted_count: int
    updated_count: int
    capped_count: int
    sources_queried: list[str]
    sources_failed: list[str]
    started_at: str | None
    finished_at: str | None


@router.post("/run-discovery", response_model=RunDiscoveryResponse)
async def run_discovery(
    body: RunDiscoveryRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunDiscoveryResponse:
    """Run the discovery loop on demand. Initiator='operator'."""
    result = await run_discovery_loop(
        db, tenant_id=user.tenant_id, top_n=body.top_n,
        initiator="operator",
    )
    await db.commit()
    return RunDiscoveryResponse(
        discovered_count=result.discovered_count,
        deduped_count=result.deduped_count,
        persisted_count=result.persisted_count,
        updated_count=result.updated_count,
        capped_count=result.capped_count,
        sources_queried=result.sources_queried,
        sources_failed=result.sources_failed,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )


async def _set_status(db, *, tenant_id, opportunity_id, status):
    try:
        oid = uuid.UUID(opportunity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_uuid")
    stmt = select(Opportunity).where(
        Opportunity.id == oid, Opportunity.tenant_id == tenant_id,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    row.status = status
    await db.flush()
    # Eagerly load all attrs so the greenlet wrapper finishes any
    # deferred IO before we build the Pydantic response (which is
    # plain attribute access from outside the async context).
    await db.refresh(row)
    return row


@router.post("/{opportunity_id}/archive", response_model=OpportunityRow)
async def archive(
    opportunity_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRow:
    row = await _set_status(
        db, tenant_id=user.tenant_id,
        opportunity_id=opportunity_id, status="archived",
    )
    response = _row_to_response(row)
    await db.commit()
    return response


@router.post("/{opportunity_id}/reject", response_model=OpportunityRow)
async def reject(
    opportunity_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OpportunityRow:
    row = await _set_status(
        db, tenant_id=user.tenant_id,
        opportunity_id=opportunity_id, status="rejected",
    )
    response = _row_to_response(row)
    await db.commit()
    return response


# ── Sprint-20 PR-3: Promote opportunity to workstream ───────────────


class CreateWorkstreamResponse(BaseModel):
    workstream_id: str
    opportunity_id: str
    department_name: str
    collaborators: list[str]


@router.post(
    "/{opportunity_id}/create-workstream",
    response_model=CreateWorkstreamResponse,
)
async def create_workstream(
    opportunity_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateWorkstreamResponse:
    """Promote a discovered opportunity into a tracked workstream owned
    by the right department. Local-only -- no external action."""
    try:
        oid = uuid.UUID(opportunity_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_uuid")

    try:
        result = await create_workstream_for_opportunity(
            db, tenant_id=user.tenant_id, user_id=user.id,
            opportunity_id=oid,
        )
    except OpportunityNotFound:
        raise HTTPException(status_code=404, detail="opportunity_not_found")
    except UnknownOpportunityType as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "unknown_opportunity_type", "type": str(exc)},
        )
    except DepartmentNotFound as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "department_not_found", "department": str(exc)},
        )
    except DuplicateWorkstream as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_workstream",
                "existing_workstream_id": str(exc.existing_workstream_id),
            },
        )
    except WorkstreamBridgeError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": exc.code, "message": str(exc)},
        )

    response = CreateWorkstreamResponse(
        workstream_id=str(result.workstream_id),
        opportunity_id=str(result.opportunity_id),
        department_name=result.department_name,
        collaborators=result.collaborators,
    )
    await db.commit()
    return response
