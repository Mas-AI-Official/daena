"""Integration tests for Session B.

Verify the pieces fit together end-to-end:

* DaenaVP.plan + route uses a LIVE DepartmentStateService against the
  test DB (not a mock), so an OVERLOADED department ACTUALLY reroutes
  via the same rule + state machinery the orchestrator will use.
* The Stage 3.5 chat_orchestrator feature flag defaults OFF.
* With the flag ON, an operator query produces a VP plan whose
  departments reflect the rule table.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.services.daena_vp import DaenaVP, VPPlan, VPSubtask
from app.services.department_state_service import DepartmentStateService


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    from app.models.identity import Tenant
    tenant = Tenant(
        id=test_tenant_id, name="Test Tenant",
        slug="test-tenant", settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    yield tenant


# ── VP + real State Registry ────────────────────────────────────


@pytest.mark.asyncio
async def test_vp_reroutes_when_marketing_is_actually_overloaded(
    db_session, test_tenant_id, seeded_tenant,
) -> None:
    """Full wiring: saturate Marketing via the REAL service, then have
    the VP route a Marketing-matched request. It should reroute to the
    first available alternate."""
    state_svc = DepartmentStateService(db_session)

    # Saturate Marketing above the overload threshold (default 5).
    for i in range(5):
        await state_svc.mark_working(
            tenant_id=test_tenant_id,
            department="Marketing",
            task_id=f"t-{i}",
        )

    vp = DaenaVP(state_service=state_svc)
    plan = await vp.plan("Draft a Q2 brand campaign")
    assert plan.subtasks[0].department == "Marketing"  # initial rule hit
    routed = await vp.route(plan, tenant_id=test_tenant_id)
    # Alternate for Marketing in the rule table is ["Product", "Sales"].
    # Product is IDLE in test DB -> should win.
    assert routed.subtasks[0].department == "Product"


@pytest.mark.asyncio
async def test_vp_keeps_original_when_all_alternates_saturated(
    db_session, test_tenant_id, seeded_tenant,
) -> None:
    """When primary + all alternates are overloaded, the subtask stays
    on the original department and queues."""
    state_svc = DepartmentStateService(db_session)

    # Saturate Marketing + Product + Sales (alternates for Marketing)
    for dept in ("Marketing", "Product", "Sales"):
        for i in range(5):
            await state_svc.mark_working(
                tenant_id=test_tenant_id,
                department=dept,
                task_id=f"{dept}-{i}",
            )

    vp = DaenaVP(state_service=state_svc)
    plan = await vp.plan("Draft a Q2 brand campaign")
    routed = await vp.route(plan, tenant_id=test_tenant_id)
    assert routed.subtasks[0].department == "Marketing"


@pytest.mark.asyncio
async def test_vp_multi_intent_plan_involves_multiple_depts(
    db_session, test_tenant_id, seeded_tenant,
) -> None:
    """Request that spans Marketing + Finance + Legal produces all 3
    departments in the plan (rule path)."""
    state_svc = DepartmentStateService(db_session)
    vp = DaenaVP(state_service=state_svc)

    plan = await vp.plan(
        "Launch a Q2 marketing campaign with a $5k budget and run the claims by legal",
    )
    depts = plan.involved_departments
    assert "Marketing" in depts
    assert "Finance" in depts
    assert "Legal & Compliance" in depts


# ── Feature flag off by default ─────────────────────────────────


def test_daena_vp_feature_flag_exists_and_enabled() -> None:
    """Session B shipped the VP behind a flag. As of 2026-04-17 the
    default is ON -- multi-department chat requests now emit
    daena_vp_plan SSE events so the Company Dashboard and chat view
    can render routing. Set DAENA_VP_ENABLED=false in .env to roll back.
    The Stage 2.8 plan call in chat_orchestrator is fail-safe: the VP
    never blocks chat."""
    from app.core.config import get_settings

    settings = get_settings()
    assert hasattr(settings, "daena_vp_enabled")
    assert settings.daena_vp_enabled is True


# ── Scenario: the operator's living-company end-to-end path ────


@pytest.mark.asyncio
async def test_operator_scenario_campaign_routes_to_multiple_depts(
    db_session, test_tenant_id, seeded_tenant,
) -> None:
    """The approved-plan verification scenario: user asks to launch a
    Q2 campaign; VP decomposes into Marketing + Finance + Legal; State
    Registry reflects the departments that would get tasks."""
    state_svc = DepartmentStateService(db_session)
    vp = DaenaVP(state_service=state_svc)

    plan = await vp.plan(
        "Launch a Q2 marketing campaign for product X within our $5k budget, "
        "and make sure legal reviews the claims before shipping.",
    )
    routed = await vp.route(plan, tenant_id=test_tenant_id)

    # Expected departments per the rule table's coverage of this text:
    expected = {"Marketing", "Finance", "Legal & Compliance"}
    assert expected.issubset(set(routed.involved_departments))
    # Each subtask has a human-readable reason for audit trail.
    for st in routed.subtasks:
        assert st.reason  # non-empty
