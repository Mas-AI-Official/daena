"""Tests for PipelineService stage transitions and loss tracking.

Covers:
- mark_lost() records lost_at + lost_reason and emits Sales.lost_deal
- advance_stage() emits Legal.contract_signed on CONTRACT transition
- advance_stage() emits Sales.closed_deal on CLOSED transition
- mark_lost() raises on CLOSED or already-lost projects

These tests protect the cross-department notification contract: if a
pipeline transition ever stops emitting, the Marketing / Research /
Legal / Finance rooms go silent and the company loses situational
awareness. The BorderAgent emit is what keeps departments aware of
each other in real time without meetings.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.identity import Tenant
from app.models.pipeline import PipelineStage, ProjectPipeline
from app.services.departments.border_agent import (
    DepartmentEvent,
    get_border_agent,
    reset_registry,
)
from app.services.pipeline_service import PipelineService


# ── Fixtures ──


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """Ensure the FK target row exists before any ProjectPipeline insert."""
    tenant = Tenant(
        id=test_tenant_id,
        name="PipelineTestOrg",
        slug=f"pipe-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(tenant)
    await db_session.flush()
    return test_tenant_id


# ── Helpers ──


async def _seed_tenant(db_session, tenant_id: uuid.UUID) -> None:
    """Insert the tenant row referenced by the FK on ProjectPipeline."""
    tenant = Tenant(
        id=tenant_id,
        name="PipelineTestOrg",
        slug=f"pipe-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(tenant)
    await db_session.flush()


async def _seed_project(
    db_session,
    tenant_id: uuid.UUID,
    *,
    stage: str = PipelineStage.DISCOVERY,
    title: str = "Test Project",
    client_name: str = "Acme Corp",
    budget_usd: float | None = 50_000.0,
) -> ProjectPipeline:
    """Insert a pipeline project row directly at the desired stage."""
    project = ProjectPipeline(
        tenant_id=tenant_id,
        title=title,
        client_name=client_name,
        budget_usd=budget_usd,
        stage=stage,
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


# ── mark_lost ──


class TestMarkLost:
    @pytest.mark.asyncio
    async def test_records_lost_at_and_reason(
        self, db_session, seeded_tenant
    ) -> None:
        await reset_registry()
        project = await _seed_project(
            db_session, seeded_tenant, stage=PipelineStage.QUALIFICATION
        )
        service = PipelineService(db_session)

        result = await service.mark_lost(
            project.id, seeded_tenant, reason="budget mismatch"
        )

        assert result["lost_at"] is not None
        assert result["lost_reason"] == "budget mismatch"
        # Stage stays where it was -- lost is orthogonal to the flow
        assert result["stage"] == PipelineStage.QUALIFICATION

    @pytest.mark.asyncio
    async def test_emits_sales_lost_deal_signal(
        self, db_session, seeded_tenant
    ) -> None:
        await reset_registry()
        # Pre-create a peer listener so the emit is captured
        marketing = await get_border_agent(
            tenant_id=seeded_tenant, department="Marketing"
        )
        marketing.clear()

        project = await _seed_project(
            db_session, seeded_tenant, stage=PipelineStage.PROPOSAL
        )
        service = PipelineService(db_session)
        await service.mark_lost(
            project.id, seeded_tenant, reason="went with competitor"
        )

        signals = marketing.recent_signals(limit=5)
        types = [s.get("event_type") for s in signals]
        assert DepartmentEvent.LOST_DEAL in types, (
            f"Marketing should receive Sales.lost_deal, got: {types}"
        )
        # Payload smoke check -- Marketing consumes stage_at_loss for
        # retention pattern detection.
        lost_signal = next(
            s for s in signals
            if s.get("event_type") == DepartmentEvent.LOST_DEAL
        )
        payload = lost_signal.get("payload") or {}
        assert payload.get("stage_at_loss") == PipelineStage.PROPOSAL
        assert payload.get("reason") == "went with competitor"

    @pytest.mark.asyncio
    async def test_cannot_mark_closed_project_lost(
        self, db_session, seeded_tenant
    ) -> None:
        await reset_registry()
        project = await _seed_project(
            db_session, seeded_tenant, stage=PipelineStage.CLOSED
        )
        service = PipelineService(db_session)

        with pytest.raises(ValueError, match="already CLOSED"):
            await service.mark_lost(
                project.id, seeded_tenant, reason="too late"
            )

    @pytest.mark.asyncio
    async def test_cannot_mark_lost_twice(
        self, db_session, seeded_tenant
    ) -> None:
        await reset_registry()
        project = await _seed_project(
            db_session, seeded_tenant, stage=PipelineStage.CONTRACT
        )
        service = PipelineService(db_session)
        await service.mark_lost(project.id, seeded_tenant, reason="first")

        with pytest.raises(ValueError, match="already marked as lost"):
            await service.mark_lost(project.id, seeded_tenant, reason="again")


# ── advance_stage emit coverage ──


class TestAdvanceStageEmits:
    @pytest.mark.asyncio
    async def test_advance_to_contract_emits_contract_signed(
        self, db_session, seeded_tenant
    ) -> None:
        await reset_registry()
        # Daena's wildcard lens sees all department emits for the tenant
        daena = await get_border_agent(
            tenant_id=seeded_tenant, department="Daena"
        )
        daena.clear()

        # Seed at PROPOSAL so a single advance crosses into CONTRACT.
        # PROPOSAL is a human gate, so founder_approved must be True.
        project = await _seed_project(
            db_session, seeded_tenant, stage=PipelineStage.PROPOSAL
        )
        service = PipelineService(db_session)
        await service.advance_stage(
            project.id, seeded_tenant, founder_approved=True
        )

        types = [
            s.get("event_type") for s in daena.recent_signals(limit=5)
        ]
        assert DepartmentEvent.CONTRACT_SIGNED in types, (
            f"Daena VP should see Legal.contract_signed, got: {types}"
        )

    @pytest.mark.asyncio
    async def test_advance_to_closed_emits_closed_deal(
        self, db_session, seeded_tenant
    ) -> None:
        await reset_registry()
        daena = await get_border_agent(
            tenant_id=seeded_tenant, department="Daena"
        )
        daena.clear()

        # Seed at BILLING so a single advance crosses into CLOSED.
        project = await _seed_project(
            db_session, seeded_tenant, stage=PipelineStage.BILLING
        )
        service = PipelineService(db_session)
        await service.advance_stage(project.id, seeded_tenant)

        types = [
            s.get("event_type") for s in daena.recent_signals(limit=5)
        ]
        assert DepartmentEvent.CLOSED_DEAL in types, (
            f"Daena VP should see Sales.closed_deal, got: {types}"
        )
