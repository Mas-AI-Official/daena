"""Tests for cross-department expense review.

Pin the operator's core scenario:

* Finance has $2k, Engineering requests $4k -- Finance reviews + denies
* Under-threshold + within-budget expenses auto-approve without review
* Over-budget small expenses auto-deny
* Approved proposals deduct from the requesting department's budget
* Reviewer denial leaves budget untouched
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.department_budget import DepartmentBudget, ExpenseProposal
from app.services.department_budget_service import DepartmentBudgetService


@pytest.fixture
def cycle_key() -> str:
    return "2026-Q2"


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """FK from department_budgets.tenant_id -> tenants.id requires a row."""
    from app.models.identity import Tenant
    tenant = Tenant(
        id=test_tenant_id,
        name="Test Tenant",
        slug="test-tenant",
        settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant


@pytest.fixture
async def service(db_session, seeded_tenant):
    return DepartmentBudgetService(db_session)


@pytest.fixture
async def eng_budget(service, test_tenant_id, cycle_key):
    """Engineering has $10k total, $500 auto-approve threshold, Finance approves above."""
    b = await service.get_or_create_budget(
        tenant_id=test_tenant_id,
        department="Engineering",
        cycle_key=cycle_key,
        default_amount=Decimal("10000"),
        default_threshold=Decimal("500"),
        approving_department="Finance",
    )
    return b


@pytest.fixture
async def fin_budget(service, test_tenant_id, cycle_key):
    """Finance has $2k budget as in the operator's scenario."""
    b = await service.get_or_create_budget(
        tenant_id=test_tenant_id,
        department="Finance",
        cycle_key=cycle_key,
        default_amount=Decimal("2000"),
        default_threshold=Decimal("500"),
        approving_department="Finance",  # Finance reviews itself
    )
    return b


# ── The core operator scenario ─────────────────────────────────


@pytest.mark.asyncio
async def test_engineering_4k_request_routes_to_finance_review(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
) -> None:
    """Engineering wants 4k, threshold is 500 => PENDING, to Finance."""
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id,
        from_department="Engineering",
        amount=Decimal("4000"),
        justification="Upgrade CI/CD minutes for Q2 release cadence",
        cycle_key=cycle_key,
    )
    assert proposal.status == "PENDING"
    assert proposal.from_department == "Engineering"
    assert proposal.to_department == "Finance"
    assert proposal.amount == Decimal("4000")


@pytest.mark.asyncio
async def test_finance_can_deny_engineerings_4k_over_its_2k_budget(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
) -> None:
    """The classic 'finance only has 2k, engineering wants 4k' case."""
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id,
        from_department="Engineering",
        amount=Decimal("4000"),
        justification="Need CI/CD upgrade",
        cycle_key=cycle_key,
    )
    assert proposal.status == "PENDING"

    # Finance MIND reviews. It has visibility into Finance's own 2k
    # budget and sees 4k > 2k. Denies with an actionable note.
    decided = await service.review_proposal(
        proposal_id=proposal.id,
        decision="DENIED",
        resolution_note=(
            "Finance Q2 budget is $2,000 total; cannot approve $4,000. "
            "Propose reducing to $2,000 or splitting across Q2 and Q3."
        ),
    )
    assert decided.status == "DENIED"
    assert "2,000" in decided.resolution_note

    # Engineering budget should NOT have been debited.
    assert eng_budget.spent_amount == Decimal("0")


@pytest.mark.asyncio
async def test_finance_can_escalate_with_alternative(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
) -> None:
    """Escalation path: reviewer proposes an alternative, originating
    department must replan. Budget stays untouched."""
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id,
        from_department="Engineering",
        amount=Decimal("4000"),
        justification="Need CI/CD upgrade",
        cycle_key=cycle_key,
    )
    decided = await service.review_proposal(
        proposal_id=proposal.id,
        decision="ESCALATED",
        resolution_note="Reduce scope to $2,000 or split across cycles.",
    )
    assert decided.status == "ESCALATED"
    assert eng_budget.spent_amount == Decimal("0")


# ── Auto-approval paths ────────────────────────────────────────


@pytest.mark.asyncio
async def test_under_threshold_within_budget_auto_approves(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
) -> None:
    """$200 request is under the $500 threshold and within budget -> approved."""
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id,
        from_department="Engineering",
        amount=Decimal("200"),
        justification="Small tool license",
        cycle_key=cycle_key,
    )
    assert proposal.status == "APPROVED"
    assert proposal.resolution_note == "Auto-approved (under threshold, within budget)"


@pytest.mark.asyncio
async def test_approved_expense_deducts_from_budget(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    db_session,
) -> None:
    """Auto-approved expenses debit the requesting department's spent_amount."""
    await service.propose_expense(
        tenant_id=test_tenant_id,
        from_department="Engineering",
        amount=Decimal("300"),
        justification="License",
        cycle_key=cycle_key,
    )
    stmt = select(DepartmentBudget).where(DepartmentBudget.id == eng_budget.id)
    refreshed = (await db_session.execute(stmt)).scalar_one()
    assert refreshed.spent_amount == Decimal("300")
    assert refreshed.remaining() == Decimal("9700")


@pytest.mark.asyncio
async def test_reviewer_approval_debits_budget(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
    db_session,
) -> None:
    """When a reviewer manually approves a PENDING expense, the budget
    is debited at review time, not proposal time."""
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id,
        from_department="Engineering",
        amount=Decimal("1500"),
        justification="Q2 contractor",
        cycle_key=cycle_key,
    )
    assert proposal.status == "PENDING"

    # Pre-review: budget untouched
    stmt = select(DepartmentBudget).where(DepartmentBudget.id == eng_budget.id)
    before = (await db_session.execute(stmt)).scalar_one()
    assert before.spent_amount == Decimal("0")

    await service.review_proposal(
        proposal_id=proposal.id,
        decision="APPROVED",
        resolution_note="Finance agrees, within $2k cap",
    )

    after = (await db_session.execute(stmt)).scalar_one()
    assert after.spent_amount == Decimal("1500")


@pytest.mark.asyncio
async def test_finance_inbox_lists_only_pending(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
) -> None:
    """list_pending_reviews is the Finance MIND's inbox."""
    p1 = await service.propose_expense(
        tenant_id=test_tenant_id, from_department="Engineering",
        amount=Decimal("4000"), justification="A", cycle_key=cycle_key,
    )
    p2 = await service.propose_expense(
        tenant_id=test_tenant_id, from_department="Engineering",
        amount=Decimal("5000"), justification="B", cycle_key=cycle_key,
    )
    # Resolve one; the other remains pending.
    await service.review_proposal(
        proposal_id=p1.id, decision="DENIED", resolution_note="No",
    )

    inbox = await service.list_pending_reviews(
        tenant_id=test_tenant_id, to_department="Finance",
    )
    ids = {p.id for p in inbox}
    assert p2.id in ids
    assert p1.id not in ids


# ── Validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_review_invalid_decision_raises(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
) -> None:
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id, from_department="Engineering",
        amount=Decimal("4000"), justification="", cycle_key=cycle_key,
    )
    with pytest.raises(ValueError, match="must be APPROVED"):
        await service.review_proposal(
            proposal_id=proposal.id, decision="MAYBE", resolution_note="",
        )


@pytest.mark.asyncio
async def test_cannot_rereview_resolved_proposal(
    service,
    test_tenant_id,
    cycle_key,
    eng_budget,
    fin_budget,
) -> None:
    """Resolved proposals are immutable -- prevents double-debit."""
    proposal = await service.propose_expense(
        tenant_id=test_tenant_id, from_department="Engineering",
        amount=Decimal("4000"), justification="", cycle_key=cycle_key,
    )
    await service.review_proposal(
        proposal_id=proposal.id, decision="APPROVED", resolution_note="",
    )
    with pytest.raises(ValueError, match="already resolved"):
        await service.review_proposal(
            proposal_id=proposal.id, decision="DENIED", resolution_note="",
        )
