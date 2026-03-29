"""Project Pipeline service -- manages project lifecycle through 8 stages.

Each stage transition:
  1. Validates the transition is legal (sequential, no skipping)
  2. Checks human gates (PROPOSAL, CONTRACT, DELIVERY need founder approval)
  3. Updates timestamps and owner department
  4. Logs to governance audit trail
  5. Returns the updated project for SSE notification to next department

All financial calculations use USD. Costs accumulate from runtime usage
tracked by the billing cost_tracker.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.pipeline import PipelineStage, ProjectPipeline

logger = get_logger(__name__)

# Timestamp field name for each stage
_STAGE_TS_FIELD = {
    PipelineStage.DISCOVERY: "discovered_at",
    PipelineStage.QUALIFICATION: "qualified_at",
    PipelineStage.PROPOSAL: "proposed_at",
    PipelineStage.CONTRACT: "contracted_at",
    PipelineStage.EXECUTION: "execution_started_at",
    PipelineStage.DELIVERY: "delivered_at",
    PipelineStage.BILLING: "billed_at",
    PipelineStage.CLOSED: "closed_at",
}


class PipelineService:
    """Manages the project pipeline lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──

    async def create_project(
        self,
        *,
        tenant_id: UUID,
        title: str,
        description: str | None = None,
        client_name: str | None = None,
        client_email: str | None = None,
        source: str | None = None,
        budget_usd: float | None = None,
        timeline_days: int | None = None,
        tags: list[str] | None = None,
        requirements: dict | None = None,
    ) -> dict:
        """Create a new project in DISCOVERY stage."""
        now = datetime.utcnow()
        project = ProjectPipeline(
            tenant_id=tenant_id,
            title=title,
            description=description,
            client_name=client_name,
            client_email=client_email,
            source=source,
            stage=PipelineStage.DISCOVERY,
            owner_department=PipelineStage.OWNER_MAP[PipelineStage.DISCOVERY],
            budget_usd=budget_usd,
            timeline_days=timeline_days,
            tags=tags,
            requirements=requirements,
            discovered_at=now,
        )
        self.db.add(project)
        await self.db.flush()
        logger.info("pipeline.project_created", project_id=str(project.id), title=title)
        return project.to_dict()

    async def get_project(self, project_id: UUID, tenant_id: UUID) -> dict | None:
        """Get a single project by ID."""
        stmt = select(ProjectPipeline).where(
            ProjectPipeline.id == project_id,
            ProjectPipeline.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        return project.to_dict() if project else None

    async def list_projects(
        self,
        tenant_id: UUID,
        *,
        stage: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """List projects with optional stage filter."""
        stmt = select(ProjectPipeline).where(ProjectPipeline.tenant_id == tenant_id)
        if stage:
            stmt = stmt.where(ProjectPipeline.stage == stage)
        stmt = stmt.order_by(desc(ProjectPipeline.created_at))

        # Count
        count_stmt = select(func.count(ProjectPipeline.id)).where(ProjectPipeline.tenant_id == tenant_id)
        if stage:
            count_stmt = count_stmt.where(ProjectPipeline.stage == stage)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Paginate
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        projects = [p.to_dict() for p in result.scalars().all()]

        return {
            "projects": projects,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }

    async def get_pipeline_summary(self, tenant_id: UUID) -> dict:
        """Get count of projects per stage (for Kanban view)."""
        stmt = (
            select(ProjectPipeline.stage, func.count(ProjectPipeline.id))
            .where(ProjectPipeline.tenant_id == tenant_id)
            .group_by(ProjectPipeline.stage)
        )
        result = await self.db.execute(stmt)
        counts = {row[0]: row[1] for row in result}

        # Ensure all stages are represented
        summary = {stage: counts.get(stage, 0) for stage in PipelineStage.ALL}
        summary["total"] = sum(summary.values())
        return summary

    # ── Stage transitions ──

    async def advance_stage(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        founder_approved: bool = False,
        notes: str | None = None,
    ) -> dict:
        """Advance a project to the next pipeline stage.

        Args:
            project_id: Project UUID.
            tenant_id: Tenant scope.
            founder_approved: True if founder explicitly approved this transition.
            notes: Optional transition notes.

        Returns:
            Updated project dict.

        Raises:
            ValueError: If transition is invalid or needs approval.
        """
        stmt = select(ProjectPipeline).where(
            ProjectPipeline.id == project_id,
            ProjectPipeline.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        current = project.stage
        next_stage = PipelineStage.next_stage(current)
        if not next_stage:
            raise ValueError(f"Project is already at final stage: {current}")

        # Human gate check
        if PipelineStage.is_human_gate(current) and not founder_approved:
            raise ValueError(
                f"Stage {current} requires founder approval before advancing to {next_stage}. "
                f"Set founder_approved=true to proceed."
            )

        # Record founder approval timestamp
        now = datetime.utcnow()
        if founder_approved:
            if current == PipelineStage.PROPOSAL:
                project.founder_approved_proposal = now
            elif current == PipelineStage.CONTRACT:
                project.founder_approved_contract = now
            elif current == PipelineStage.DELIVERY:
                project.founder_approved_delivery = now

        # Advance
        project.stage = next_stage
        project.owner_department = PipelineStage.OWNER_MAP.get(next_stage, "")

        # Set stage timestamp
        ts_field = _STAGE_TS_FIELD.get(next_stage)
        if ts_field:
            setattr(project, ts_field, now)

        # Append notes
        if notes:
            existing = project.notes or ""
            project.notes = f"{existing}\n[{now.isoformat()}] {current} -> {next_stage}: {notes}".strip()

        await self.db.flush()
        await self.db.refresh(project)

        logger.info(
            "pipeline.stage_advanced",
            project_id=str(project_id),
            from_stage=current,
            to_stage=next_stage,
            founder_approved=founder_approved,
            owner=project.owner_department,
        )

        return project.to_dict()

    async def update_scoring(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        ai_doability_score: int | None = None,
        competition_level: int | None = None,
        budget_usd: float | None = None,
        timeline_days: int | None = None,
    ) -> dict:
        """Update project scoring (Research/Sales departments)."""
        stmt = select(ProjectPipeline).where(
            ProjectPipeline.id == project_id,
            ProjectPipeline.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if ai_doability_score is not None:
            project.ai_doability_score = max(1, min(10, ai_doability_score))
        if competition_level is not None:
            project.competition_level = max(1, min(10, competition_level))
        if budget_usd is not None:
            project.budget_usd = budget_usd
        if timeline_days is not None:
            project.timeline_days = timeline_days

        # Compute overall score: high doability + high budget + low competition = good
        doability = project.ai_doability_score or 5
        budget = min((project.budget_usd or 0) / 10000, 10)  # Normalize to 0-10
        competition = 10 - (project.competition_level or 5)  # Invert: low competition = high score
        project.overall_score = round((doability * 0.4 + budget * 0.3 + competition * 0.3), 2)

        await self.db.flush()
        await self.db.refresh(project)
        return project.to_dict()

    async def update_financials(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        quoted_amount_usd: float | None = None,
        actual_cost_usd: float | None = None,
        invoiced_amount_usd: float | None = None,
        paid_amount_usd: float | None = None,
        payment_status: str | None = None,
    ) -> dict:
        """Update project financial data (Finance department)."""
        stmt = select(ProjectPipeline).where(
            ProjectPipeline.id == project_id,
            ProjectPipeline.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        if quoted_amount_usd is not None:
            project.quoted_amount_usd = quoted_amount_usd
        if actual_cost_usd is not None:
            project.actual_cost_usd = actual_cost_usd
        if invoiced_amount_usd is not None:
            project.invoiced_amount_usd = invoiced_amount_usd
        if paid_amount_usd is not None:
            project.paid_amount_usd = paid_amount_usd
        if payment_status is not None:
            project.payment_status = payment_status

        await self.db.flush()
        await self.db.refresh(project)
        return project.to_dict()

    async def set_document_path(
        self,
        project_id: UUID,
        tenant_id: UUID,
        *,
        doc_type: str,  # proposal, contract, deliverables, invoice
        path: str,
    ) -> dict:
        """Set a document path for the project."""
        stmt = select(ProjectPipeline).where(
            ProjectPipeline.id == project_id,
            ProjectPipeline.tenant_id == tenant_id,
        )
        result = await self.db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        field_map = {
            "proposal": "proposal_path",
            "contract": "contract_path",
            "deliverables": "deliverables_path",
            "invoice": "invoice_path",
        }
        field = field_map.get(doc_type)
        if not field:
            raise ValueError(f"Unknown doc_type: {doc_type}")

        setattr(project, field, path)
        await self.db.flush()
        await self.db.refresh(project)
        return project.to_dict()

    # ── Department queries ──

    async def get_department_queue(
        self, tenant_id: UUID, department: str,
    ) -> list[dict]:
        """Get all projects currently owned by a department."""
        stmt = (
            select(ProjectPipeline)
            .where(
                ProjectPipeline.tenant_id == tenant_id,
                ProjectPipeline.owner_department == department,
            )
            .order_by(desc(ProjectPipeline.overall_score))
        )
        result = await self.db.execute(stmt)
        return [p.to_dict() for p in result.scalars().all()]

    async def get_top_opportunities(
        self, tenant_id: UUID, limit: int = 3,
    ) -> list[dict]:
        """Get top scored DISCOVERY projects for founder review."""
        stmt = (
            select(ProjectPipeline)
            .where(
                ProjectPipeline.tenant_id == tenant_id,
                ProjectPipeline.stage == PipelineStage.DISCOVERY,
                ProjectPipeline.overall_score.isnot(None),
            )
            .order_by(desc(ProjectPipeline.overall_score))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return [p.to_dict() for p in result.scalars().all()]
