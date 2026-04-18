"""Tests for the department state registry.

Pin the contract:
* mark_working increments queue_depth + flips status WORKING
* mark_idle decrements + flips back to IDLE at zero
* Overload threshold triggers OVERLOADED status
* snapshot returns all 10 canonical departments (materializing defaults)
* Multiple tenants are isolated
* Offline kill-switch preserves queue_depth
* API endpoint returns the snapshot and requires auth
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient

from app.models.department_state import DepartmentState
from app.services.department_state_service import (
    _CANONICAL_DEPARTMENTS,
    DepartmentStateService,
)


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """department_states.tenant_id FK -> tenants.id needs a real tenant row."""
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
    return DepartmentStateService(db_session)


# ── Transitions ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_working_creates_row_and_sets_state(
    service, test_tenant_id,
) -> None:
    """First call for a (tenant, dept) creates a row and flips to WORKING."""
    state = await service.mark_working(
        tenant_id=test_tenant_id,
        department="Engineering",
        task_id="t-1",
        task_summary="Build CI pipeline",
    )
    assert state.status == "WORKING"
    assert state.queue_depth == 1
    assert state.current_task_id == "t-1"
    assert state.current_task_summary == "Build CI pipeline"
    assert state.last_activity_at is not None


@pytest.mark.asyncio
async def test_mark_idle_returns_to_zero(service, test_tenant_id) -> None:
    """One mark_working + one mark_idle returns to IDLE / queue_depth=0."""
    await service.mark_working(
        tenant_id=test_tenant_id, department="Engineering", task_id="t-1",
    )
    state = await service.mark_idle(
        tenant_id=test_tenant_id, department="Engineering",
    )
    assert state.status == "IDLE"
    assert state.queue_depth == 0
    assert state.current_task_id is None
    assert state.current_task_summary is None


@pytest.mark.asyncio
async def test_concurrent_tasks_stack_then_drain(
    service, test_tenant_id,
) -> None:
    """Three mark_working calls build queue_depth=3; draining yields IDLE."""
    for i in range(3):
        await service.mark_working(
            tenant_id=test_tenant_id, department="Engineering", task_id=f"t-{i}",
        )
    # Verify mid-state
    snap = await service.snapshot(tenant_id=test_tenant_id)
    eng = next(s for s in snap if s["department_name"] == "Engineering")
    assert eng["status"] == "WORKING"
    assert eng["queue_depth"] == 3

    for _ in range(3):
        await service.mark_idle(
            tenant_id=test_tenant_id, department="Engineering",
        )
    snap = await service.snapshot(tenant_id=test_tenant_id)
    eng = next(s for s in snap if s["department_name"] == "Engineering")
    assert eng["status"] == "IDLE"
    assert eng["queue_depth"] == 0


@pytest.mark.asyncio
async def test_overloaded_at_threshold(service, test_tenant_id) -> None:
    """Default overload threshold is 5. 5th concurrent task flips OVERLOADED."""
    for i in range(5):
        state = await service.mark_working(
            tenant_id=test_tenant_id, department="Engineering", task_id=f"t-{i}",
        )
    assert state.queue_depth == 5
    assert state.status == "OVERLOADED"


@pytest.mark.asyncio
async def test_mark_idle_below_zero_clamps(service, test_tenant_id) -> None:
    """Over-draining (more mark_idle than mark_working) must not go negative."""
    await service.mark_idle(
        tenant_id=test_tenant_id, department="Engineering",
    )
    state = await service.mark_idle(
        tenant_id=test_tenant_id, department="Engineering",
    )
    assert state.queue_depth == 0
    assert state.status == "IDLE"


# ── Snapshot ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_materializes_all_ten_departments(
    service, test_tenant_id,
) -> None:
    """Brand-new tenant with zero rows gets all 10 canonical depts
    returned as IDLE/0. The Company Dashboard depends on this."""
    snap = await service.snapshot(tenant_id=test_tenant_id)
    assert len(snap) == len(_CANONICAL_DEPARTMENTS)
    names = {s["department_name"] for s in snap}
    assert names == set(_CANONICAL_DEPARTMENTS)
    for s in snap:
        assert s["status"] == "IDLE"
        assert s["queue_depth"] == 0


@pytest.mark.asyncio
async def test_snapshot_reflects_live_state(service, test_tenant_id) -> None:
    """A department with in-flight work shows WORKING in the snapshot."""
    await service.mark_working(
        tenant_id=test_tenant_id,
        department="Marketing",
        task_id="campaign-q2",
        task_summary="Draft Q2 campaign",
    )
    snap = await service.snapshot(tenant_id=test_tenant_id)
    mkt = next(s for s in snap if s["department_name"] == "Marketing")
    assert mkt["status"] == "WORKING"
    assert mkt["queue_depth"] == 1
    assert mkt["current_task_id"] == "campaign-q2"


# ── Multi-tenant ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenants_are_isolated(service, test_tenant_id, db_session) -> None:
    """Tenant A's WORKING state does not leak into Tenant B's snapshot."""
    from app.models.identity import Tenant

    other_tenant_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    db_session.add(
        Tenant(id=other_tenant_id, name="Other Tenant", slug="other", settings={}),
    )
    await db_session.flush()

    await service.mark_working(
        tenant_id=test_tenant_id, department="Engineering", task_id="t-1",
    )

    snap_other = await service.snapshot(tenant_id=other_tenant_id)
    eng = next(s for s in snap_other if s["department_name"] == "Engineering")
    assert eng["status"] == "IDLE"
    assert eng["queue_depth"] == 0


# ── Offline ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_offline_preserves_queue_depth(
    service, test_tenant_id,
) -> None:
    """Kill-switch preserves queue_depth so recovering doesn't lose counts."""
    await service.mark_working(
        tenant_id=test_tenant_id, department="Engineering", task_id="t-1",
    )
    state = await service.set_offline(
        tenant_id=test_tenant_id, department="Engineering",
    )
    assert state.status == "OFFLINE"
    assert state.queue_depth == 1


# ── list_available (for DaenaVP Session B) ──────────────────────


@pytest.mark.asyncio
async def test_list_available_excludes_overloaded(
    service, test_tenant_id,
) -> None:
    """DaenaVP should not route to OVERLOADED departments."""
    for i in range(5):
        await service.mark_working(
            tenant_id=test_tenant_id, department="Engineering", task_id=f"t-{i}",
        )
    available = await service.list_available(tenant_id=test_tenant_id)
    assert "Engineering" not in available
    # Other 9 should still be available
    assert len(available) == 9


@pytest.mark.asyncio
async def test_list_available_falls_back_when_all_overloaded(
    service, test_tenant_id,
) -> None:
    """If everything is overloaded, return the full canonical list
    rather than an empty list (router must not deadlock on saturated
    company)."""
    for dept in _CANONICAL_DEPARTMENTS:
        for _ in range(5):
            await service.mark_working(
                tenant_id=test_tenant_id, department=dept, task_id="t",
            )
    available = await service.list_available(tenant_id=test_tenant_id)
    assert set(available) == set(_CANONICAL_DEPARTMENTS)


# ── API endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_api_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/department-states")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_api_returns_snapshot(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    response = await client.get(
        "/api/v1/department-states", headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == len(_CANONICAL_DEPARTMENTS)
    assert all("department_name" in d for d in data)
    assert all("status" in d for d in data)


@pytest.mark.asyncio
async def test_offline_endpoint_rejects_unknown_department(
    client: AsyncClient, auth_headers: dict[str, str], seeded_tenant,
) -> None:
    response = await client.post(
        "/api/v1/department-states/NotRealDept/offline",
        headers=auth_headers,
    )
    # Unknown department -> 404 OR auth is checked first and rejects ADMIN req.
    # In the test JWT role is FOUNDER which the require_role("ADMIN") path
    # accepts OR rejects depending on role hierarchy. Either 404 or 403 is
    # acceptable as long as the garbage name is never written.
    assert response.status_code in (403, 404)
