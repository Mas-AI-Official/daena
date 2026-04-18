"""Department budgets + expense proposals.

Session 11: first piece of the "unified company" architecture. Gives
each DepartmentAgent a real budget constraint so cross-department
approval can happen. Solves the operator's Finance-2k-vs-Engineering-4k
scenario.

Design
------
Two tables:

1. ``department_budgets`` -- one row per (tenant, department, cycle).
   Holds the allocated amount, amount spent so far, and the
   ``approval_threshold`` above which expenses must be reviewed by
   another department (typically Finance).

2. ``expense_proposals`` -- an expense request from one department.
   If its amount is under the proposing department's threshold AND
   within remaining budget, auto-approved. Otherwise enters the
   review state and waits for the approving department's decision.

Why a dedicated table rather than JSONB on User.settings?
---------------------------------------------------------
- Multi-user per tenant: department budgets belong to the TENANT
  not to one user. JSONB on User wouldn't share between users.
- Auditability: every spend decision needs a queryable audit record.
- Approval workflow: expense proposals drive a queue UI, need FK +
  indexes for fast listing.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TenantMixin, TimestampMixin


class DepartmentBudget(Base, TenantMixin, TimestampMixin):
    """Per-cycle budget for a department.

    ``approval_threshold`` and ``approving_department_id`` together
    answer: "when a spend exceeds this, which department reviews it?"
    Finance as the standard approver; any department can be set.
    """

    __tablename__ = "department_budgets"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "department_name", "cycle_key",
            name="uq_department_budgets_tenant_dept_cycle",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    department_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    cycle_key: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2026-Q2", "2026-04"
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    spent_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0",
    )
    approval_threshold: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="500",
    )
    # Which department must approve spends > threshold. Default = Finance.
    approving_department: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="Finance",
    )

    def remaining(self) -> Decimal:
        """Budget left to spend this cycle."""
        return self.budget_amount - self.spent_amount

    def requires_review(self, amount: Decimal) -> bool:
        """True if this spend must be reviewed by another department."""
        return amount > self.approval_threshold


class ExpenseProposal(Base, TenantMixin, TimestampMixin):
    """A proposed expense from one department. Drives the review queue.

    Status lifecycle::

        PENDING   -- just submitted, awaiting auto-resolve or review
        APPROVED  -- either auto-approved (under threshold + within budget)
                     or human/agent reviewer said yes
        DENIED    -- reviewer said no
        ESCALATED -- reviewer proposed alternative; originating dept must replan

    The operator's Finance-2k-vs-Engineering-4k scenario lives here:
      1. Engineering creates ExpenseProposal(amount=4000, dept=Engineering)
      2. Engineering's budget has approval_threshold=1000 => requires_review
      3. Status = PENDING, approving_department = Finance
      4. Finance's DepartmentAgent reviews, checks its budget + rules
      5. Sets status to DENIED with a reason, or ESCALATED with alt suggestion
      6. Engineering replans based on status
    """

    __tablename__ = "expense_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    from_department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    to_department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("department_budgets.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    justification: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="PENDING")
    # Reviewer's notes when they APPROVED/DENIED/ESCALATED.
    resolution_note: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    budget: Mapped[DepartmentBudget] = relationship()
