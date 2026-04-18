"""API for cross-department expense proposals + review.

Session 11: wires the DepartmentBudget service to HTTP so:
  * Any department agent can POST a proposal
  * Finance (or the approver) can GET the pending queue
  * Reviewer can POST a decision
  * UI can show the full audit trail
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.services.department_budget_service import DepartmentBudgetService

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────


class BudgetCreateRequest(BaseModel):
    department: str
    cycle_key: str
    budget_amount: Decimal = Field(..., ge=0)
    approval_threshold: Decimal = Field(Decimal("500"), ge=0)
    approving_department: str = "Finance"


class BudgetResponse(BaseModel):
    id: str
    department_name: str
    cycle_key: str
    budget_amount: str
    spent_amount: str
    remaining: str
    approval_threshold: str
    approving_department: str


class ProposalCreateRequest(BaseModel):
    from_department: str
    amount: Decimal = Field(..., gt=0)
    justification: str = Field(..., min_length=1, max_length=2000)
    cycle_key: str


class ProposalReviewRequest(BaseModel):
    decision: str = Field(..., description="APPROVED | DENIED | ESCALATED")
    resolution_note: str = Field(..., min_length=1, max_length=2000)


class ProposalResponse(BaseModel):
    id: str
    from_department: str
    to_department: str
    amount: str
    justification: str
    status: str
    resolution_note: str | None
    resolved_at: str | None


def _budget_to_response(b) -> BudgetResponse:
    return BudgetResponse(
        id=str(b.id),
        department_name=b.department_name,
        cycle_key=b.cycle_key,
        budget_amount=str(b.budget_amount),
        spent_amount=str(b.spent_amount),
        remaining=str(b.remaining()),
        approval_threshold=str(b.approval_threshold),
        approving_department=b.approving_department,
    )


def _proposal_to_response(p) -> ProposalResponse:
    return ProposalResponse(
        id=str(p.id),
        from_department=p.from_department,
        to_department=p.to_department,
        amount=str(p.amount),
        justification=p.justification,
        status=p.status,
        resolution_note=p.resolution_note,
        resolved_at=p.resolved_at.isoformat() if p.resolved_at else None,
    )


# ── Endpoints ───────────────────────────────────────────────────


@router.post("/budgets", response_model=BudgetResponse)
async def create_or_update_budget(
    body: BudgetCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BudgetResponse:
    """Set a department's budget for a cycle. Idempotent: re-POST to
    update the amount or threshold."""
    svc = DepartmentBudgetService(db)
    budget = await svc.get_or_create_budget(
        tenant_id=user.tenant_id,
        department=body.department,
        cycle_key=body.cycle_key,
        default_amount=body.budget_amount,
        default_threshold=body.approval_threshold,
        approving_department=body.approving_department,
    )
    # Update if already existed
    budget.budget_amount = body.budget_amount
    budget.approval_threshold = body.approval_threshold
    budget.approving_department = body.approving_department
    await db.flush()
    return _budget_to_response(budget)


@router.post("/proposals", response_model=ProposalResponse)
async def propose(
    body: ProposalCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """Any agent / user submits an expense proposal. Auto-resolves
    if under threshold + within budget; otherwise enters PENDING."""
    svc = DepartmentBudgetService(db)
    proposal = await svc.propose_expense(
        tenant_id=user.tenant_id,
        from_department=body.from_department,
        amount=body.amount,
        justification=body.justification,
        cycle_key=body.cycle_key,
    )
    return _proposal_to_response(proposal)


@router.get("/proposals/pending", response_model=list[ProposalResponse])
async def list_pending(
    to_department: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProposalResponse]:
    """Inbox: proposals awaiting review by ``to_department``."""
    svc = DepartmentBudgetService(db)
    items = await svc.list_pending_reviews(
        tenant_id=user.tenant_id, to_department=to_department,
    )
    return [_proposal_to_response(p) for p in items]


@router.post("/proposals/{proposal_id}/review", response_model=ProposalResponse)
async def review(
    proposal_id: UUID,
    body: ProposalReviewRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProposalResponse:
    """Reviewing department writes a decision."""
    svc = DepartmentBudgetService(db)
    try:
        proposal = await svc.review_proposal(
            proposal_id=proposal_id,
            decision=body.decision,
            resolution_note=body.resolution_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _proposal_to_response(proposal)
