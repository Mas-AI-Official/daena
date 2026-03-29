"""Project Pipeline model -- tracks AI company projects through stages.

Pipeline stages:
  DISCOVERY -> QUALIFICATION -> PROPOSAL -> CONTRACT ->
  EXECUTION -> DELIVERY -> BILLING -> CLOSED

Human gates: PROPOSAL, CONTRACT, DELIVERY (requires founder review).
Everything else runs autonomously through department heartbeats.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TenantMixin, TimestampMixin


class PipelineStage:
    """Pipeline stage constants."""

    DISCOVERY = "DISCOVERY"
    QUALIFICATION = "QUALIFICATION"
    PROPOSAL = "PROPOSAL"
    CONTRACT = "CONTRACT"
    EXECUTION = "EXECUTION"
    DELIVERY = "DELIVERY"
    BILLING = "BILLING"
    CLOSED = "CLOSED"

    ALL = [DISCOVERY, QUALIFICATION, PROPOSAL, CONTRACT, EXECUTION, DELIVERY, BILLING, CLOSED]

    # Stages that require human (founder) approval before advancing
    HUMAN_GATES = {PROPOSAL, CONTRACT, DELIVERY}

    # Department responsible for each stage
    OWNER_MAP = {
        DISCOVERY: "Research",
        QUALIFICATION: "Sales",
        PROPOSAL: "Sales",
        CONTRACT: "Legal & Compliance",
        EXECUTION: "Engineering",
        DELIVERY: "Operations",
        BILLING: "Finance",
        CLOSED: "Operations",
    }

    @classmethod
    def next_stage(cls, current: str) -> str | None:
        """Get the next stage in the pipeline, or None if already CLOSED."""
        try:
            idx = cls.ALL.index(current)
            return cls.ALL[idx + 1] if idx + 1 < len(cls.ALL) else None
        except ValueError:
            return None

    @classmethod
    def is_human_gate(cls, stage: str) -> bool:
        """Check if a stage requires human approval to advance."""
        return stage in cls.HUMAN_GATES


class ProjectPipeline(Base, TenantMixin, TimestampMixin):
    """A project flowing through the MAS-AI pipeline."""

    __tablename__ = "project_pipeline"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )

    # Basic info
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    client_name = Column(String(200), nullable=True)
    client_email = Column(String(200), nullable=True)
    source = Column(String(100), nullable=True)  # upwork, fiverr, linkedin, referral, direct

    # Pipeline state
    stage = Column(String(50), nullable=False, default=PipelineStage.DISCOVERY, index=True)
    owner_department = Column(String(100), nullable=True)
    assigned_to = Column(String(200), nullable=True)  # user_id or "auto"

    # Scoring (set during DISCOVERY/QUALIFICATION)
    budget_usd = Column(Float, nullable=True)
    timeline_days = Column(Integer, nullable=True)
    ai_doability_score = Column(Integer, nullable=True)  # 1-10
    competition_level = Column(Integer, nullable=True)  # 1-10 (10 = high competition)
    overall_score = Column(Float, nullable=True)  # Composite score

    # Stage timestamps
    discovered_at = Column(DateTime, nullable=True)
    qualified_at = Column(DateTime, nullable=True)
    proposed_at = Column(DateTime, nullable=True)
    contracted_at = Column(DateTime, nullable=True)
    execution_started_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    billed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Financial
    quoted_amount_usd = Column(Float, nullable=True)
    actual_cost_usd = Column(Float, default=0.0)
    invoiced_amount_usd = Column(Float, nullable=True)
    paid_amount_usd = Column(Float, default=0.0)
    payment_status = Column(String(50), nullable=True)  # pending, partial, paid, overdue

    # Documents (paths to Daena-Mind vault)
    proposal_path = Column(String(500), nullable=True)
    contract_path = Column(String(500), nullable=True)
    deliverables_path = Column(String(500), nullable=True)
    invoice_path = Column(String(500), nullable=True)

    # Metadata
    tags = Column(SQLiteJSON, nullable=True)  # ["python", "web-scraping", "automation"]
    requirements = Column(SQLiteJSON, nullable=True)  # Structured requirements
    milestones = Column(SQLiteJSON, nullable=True)  # [{name, due_date, status, deliverable}]
    notes = Column(Text, nullable=True)  # Free-form notes

    # Approval tracking
    founder_approved_proposal = Column(DateTime, nullable=True)
    founder_approved_contract = Column(DateTime, nullable=True)
    founder_approved_delivery = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "title": self.title,
            "description": self.description,
            "client_name": self.client_name,
            "client_email": self.client_email,
            "source": self.source,
            "stage": self.stage,
            "owner_department": self.owner_department or PipelineStage.OWNER_MAP.get(self.stage, ""),
            "assigned_to": self.assigned_to,
            "budget_usd": self.budget_usd,
            "timeline_days": self.timeline_days,
            "ai_doability_score": self.ai_doability_score,
            "competition_level": self.competition_level,
            "overall_score": self.overall_score,
            "quoted_amount_usd": self.quoted_amount_usd,
            "actual_cost_usd": self.actual_cost_usd,
            "invoiced_amount_usd": self.invoiced_amount_usd,
            "paid_amount_usd": self.paid_amount_usd,
            "payment_status": self.payment_status,
            "proposal_path": self.proposal_path,
            "contract_path": self.contract_path,
            "deliverables_path": self.deliverables_path,
            "invoice_path": self.invoice_path,
            "tags": self.tags or [],
            "requirements": self.requirements,
            "milestones": self.milestones or [],
            "notes": self.notes,
            "discovered_at": str(self.discovered_at) if self.discovered_at else None,
            "qualified_at": str(self.qualified_at) if self.qualified_at else None,
            "proposed_at": str(self.proposed_at) if self.proposed_at else None,
            "contracted_at": str(self.contracted_at) if self.contracted_at else None,
            "execution_started_at": str(self.execution_started_at) if self.execution_started_at else None,
            "delivered_at": str(self.delivered_at) if self.delivered_at else None,
            "billed_at": str(self.billed_at) if self.billed_at else None,
            "closed_at": str(self.closed_at) if self.closed_at else None,
            "founder_approved_proposal": str(self.founder_approved_proposal) if self.founder_approved_proposal else None,
            "founder_approved_contract": str(self.founder_approved_contract) if self.founder_approved_contract else None,
            "founder_approved_delivery": str(self.founder_approved_delivery) if self.founder_approved_delivery else None,
            "created_at": str(self.created_at) if self.created_at else None,
            "updated_at": str(self.updated_at) if self.updated_at else None,
        }
