"""Cross-department expense review service.

Turns the 10 isolated DepartmentAgents into a unified company by
giving them shared budget constraints. Answers the operator's
Finance-2k-vs-Engineering-4k question.

Usage by DepartmentAgent::

    svc = DepartmentBudgetService(db)

    # Engineering wants to spend:
    proposal = await svc.propose_expense(
        tenant_id=tenant_id,
        from_department="Engineering",
        amount=Decimal("4000"),
        justification="Upgrade CI/CD minutes for Q2 release cadence",
        cycle_key="2026-Q2",
    )

    if proposal.status == "APPROVED":
        # under threshold + within budget -> just do it
        ...
    elif proposal.status == "PENDING":
        # over threshold -> waiting for Finance review
        # Finance.MIND will pick it up from its inbox via
        # list_pending_reviews(to_department="Finance")
        ...
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.department_budget import DepartmentBudget, ExpenseProposal

logger = get_logger(__name__)


class DepartmentBudgetService:
    """Encapsulates expense proposal + approval workflow."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Budget CRUD ──────────────────────────────────────────────

    async def get_or_create_budget(
        self,
        *,
        tenant_id: UUID,
        department: str,
        cycle_key: str,
        default_amount: Decimal = Decimal("0"),
        default_threshold: Decimal = Decimal("500"),
        approving_department: str = "Finance",
    ) -> DepartmentBudget:
        """Fetch the department's budget for this cycle, creating with
        defaults if missing. Useful for first-run / test setup."""
        stmt = select(DepartmentBudget).where(
            DepartmentBudget.tenant_id == tenant_id,
            DepartmentBudget.department_name == department,
            DepartmentBudget.cycle_key == cycle_key,
        )
        result = await self._db.execute(stmt)
        budget = result.scalar_one_or_none()
        if budget is not None:
            return budget

        budget = DepartmentBudget(
            tenant_id=tenant_id,
            department_name=department,
            cycle_key=cycle_key,
            budget_amount=default_amount,
            spent_amount=Decimal("0"),
            approval_threshold=default_threshold,
            approving_department=approving_department,
        )
        self._db.add(budget)
        await self._db.flush()
        return budget

    # ── Propose ──────────────────────────────────────────────────

    async def propose_expense(
        self,
        *,
        tenant_id: UUID,
        from_department: str,
        amount: Decimal,
        justification: str,
        cycle_key: str,
    ) -> ExpenseProposal:
        """Submit an expense for review.

        Three outcomes:
        * Auto-approved: under threshold AND within remaining budget
        * Denied immediately: exceeds remaining budget (no point asking)
        * Pending: over threshold, waits for reviewing department
        """
        budget = await self.get_or_create_budget(
            tenant_id=tenant_id,
            department=from_department,
            cycle_key=cycle_key,
        )

        remaining = budget.remaining()
        if amount > remaining and not budget.requires_review(amount):
            # Exceeds budget AND not eligible for escalation review (edge
            # case: small amount over what's left). Auto-denied.
            proposal = ExpenseProposal(
                tenant_id=tenant_id,
                from_department=from_department,
                to_department=from_department,  # self-rejected
                budget_id=budget.id,
                amount=amount,
                justification=justification,
                status="DENIED",
                resolution_note=f"Exceeds remaining budget (remaining={remaining})",
                resolved_at=datetime.now(UTC),
            )
            self._db.add(proposal)
            await self._db.flush()
            logger.info(
                "department_budget.auto_denied_over_budget",
                from_department=from_department, amount=str(amount),
                remaining=str(remaining),
            )
            return proposal

        if not budget.requires_review(amount) and amount <= remaining:
            # Auto-approved: under threshold and within budget.
            budget.spent_amount = budget.spent_amount + amount
            proposal = ExpenseProposal(
                tenant_id=tenant_id,
                from_department=from_department,
                to_department=from_department,  # self-approved
                budget_id=budget.id,
                amount=amount,
                justification=justification,
                status="APPROVED",
                resolution_note="Auto-approved (under threshold, within budget)",
                resolved_at=datetime.now(UTC),
            )
            self._db.add(proposal)
            await self._db.flush()
            logger.info(
                "department_budget.auto_approved",
                from_department=from_department, amount=str(amount),
                remaining=str(budget.remaining()),
            )
            return proposal

        # Pending review: over threshold (regardless of budget headroom).
        # The approving department's DepartmentAgent MUST see this.
        proposal = ExpenseProposal(
            tenant_id=tenant_id,
            from_department=from_department,
            to_department=budget.approving_department,
            budget_id=budget.id,
            amount=amount,
            justification=justification,
            status="PENDING",
        )
        self._db.add(proposal)
        await self._db.flush()
        logger.info(
            "department_budget.pending_review",
            from_department=from_department,
            to_department=budget.approving_department,
            amount=str(amount),
        )
        return proposal

    # ── Review (called by approving department's agent) ─────────

    async def list_pending_reviews(
        self,
        *,
        tenant_id: UUID,
        to_department: str,
    ) -> list[ExpenseProposal]:
        """The approving department's inbox of expense requests."""
        stmt = select(ExpenseProposal).where(
            ExpenseProposal.tenant_id == tenant_id,
            ExpenseProposal.to_department == to_department,
            ExpenseProposal.status == "PENDING",
        ).order_by(ExpenseProposal.created_at.asc())
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def review_proposal(
        self,
        *,
        proposal_id: UUID,
        decision: str,  # APPROVED | DENIED | ESCALATED
        resolution_note: str,
    ) -> ExpenseProposal:
        """Reviewer writes a decision on a PENDING proposal.

        Called by the approving department's DepartmentAgent.MIND after
        it evaluated the justification against its own constraints.
        """
        if decision not in {"APPROVED", "DENIED", "ESCALATED"}:
            raise ValueError(
                f"decision must be APPROVED | DENIED | ESCALATED, got {decision}"
            )
        stmt = select(ExpenseProposal).where(ExpenseProposal.id == proposal_id)
        result = await self._db.execute(stmt)
        proposal = result.scalar_one()
        if proposal.status != "PENDING":
            raise ValueError(
                f"Proposal already resolved: {proposal.status}"
            )
        proposal.status = decision
        proposal.resolution_note = resolution_note
        proposal.resolved_at = datetime.now(UTC)

        # If approved, deduct from budget now
        if decision == "APPROVED":
            stmt_b = select(DepartmentBudget).where(DepartmentBudget.id == proposal.budget_id)
            result_b = await self._db.execute(stmt_b)
            budget = result_b.scalar_one()
            budget.spent_amount = budget.spent_amount + proposal.amount

        await self._db.flush()
        logger.info(
            "department_budget.reviewed",
            proposal_id=str(proposal_id), decision=decision,
        )
        return proposal
