"""Tests for AgentService and agent/department endpoints.

Integration tests: register -> login -> seed -> departments -> agents CRUD.
Validates the Sunflower-Honeycomb organizational structure:
10 departments x 6 sub-capabilities = 60 agents.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

# ── Helpers ──


async def _register_and_login(client: AsyncClient) -> dict:
    """Register a user and login, returning access token + user data."""
    unique = uuid.uuid4().hex[:8]
    email = f"agent-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Agent Tester",
            "tenant_name": f"AgentOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


# ── Seed ──


@pytest.mark.asyncio
async def test_seed_defaults(client: AsyncClient) -> None:
    """POST /agents/seed ensures 10 departments + 60 agents exist.

    Auto-seeding in main.py lifespan may have already created them,
    so we assert on totals, not on created counts.
    """
    auth = await _register_and_login(client)
    resp = await client.post("/api/v1/agents/seed", headers=auth["headers"])

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["total_departments"] >= 10
    assert body["data"]["total_agents"] >= 60

    # Verify departments actually exist via list endpoint
    dept_resp = await client.get(
        "/api/v1/agents/departments", headers=auth["headers"],
    )
    assert len(dept_resp.json()["data"]) >= 10


@pytest.mark.asyncio
async def test_seed_idempotent(client: AsyncClient) -> None:
    """Seeding twice does not duplicate departments or agents."""
    auth = await _register_and_login(client)

    # First seed (may be a no-op if auto-seed already ran)
    resp1 = await client.post("/api/v1/agents/seed", headers=auth["headers"])
    assert resp1.status_code == 201

    # Second seed — should create 0 new
    resp2 = await client.post("/api/v1/agents/seed", headers=auth["headers"])
    assert resp2.status_code == 201
    assert resp2.json()["data"]["departments_created"] == 0
    assert resp2.json()["data"]["agents_created"] == 0


# ── Departments ──


@pytest.mark.asyncio
async def test_list_departments_after_register(client: AsyncClient) -> None:
    """GET /agents/departments returns auto-seeded departments for new tenant."""
    auth = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/agents/departments", headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Registration auto-seeds 10 default departments
    assert len(resp.json()["data"]) >= 10


@pytest.mark.asyncio
async def test_list_departments_after_seed(client: AsyncClient) -> None:
    """GET /agents/departments returns 10 departments after seed."""
    auth = await _register_and_login(client)
    await client.post("/api/v1/agents/seed", headers=auth["headers"])

    resp = await client.get(
        "/api/v1/agents/departments", headers=auth["headers"],
    )
    assert resp.status_code == 200
    departments = resp.json()["data"]
    assert len(departments) == 10

    # Check order by sunflower_index
    names = [d["name"] for d in departments]
    assert names[0] == "Engineering"
    assert names[7] == "Legal & Compliance"
    assert names[8] == "Skill Governance"
    assert names[9] == "Security Operations"

    # Each should have 6 agents
    for dept in departments:
        assert dept["agent_count"] == 6


@pytest.mark.asyncio
async def test_get_department_by_id(client: AsyncClient) -> None:
    """GET /agents/departments/{id} returns single department."""
    auth = await _register_and_login(client)
    await client.post("/api/v1/agents/seed", headers=auth["headers"])

    # List to get an ID
    list_resp = await client.get(
        "/api/v1/agents/departments", headers=auth["headers"],
    )
    dept_id = list_resp.json()["data"][0]["id"]

    resp = await client.get(
        f"/api/v1/agents/departments/{dept_id}", headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Engineering"
    assert resp.json()["data"]["agent_count"] == 6


@pytest.mark.asyncio
async def test_get_department_not_found(client: AsyncClient) -> None:
    """GET /agents/departments/{bad_id} returns 404."""
    auth = await _register_and_login(client)
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/api/v1/agents/departments/{fake_id}", headers=auth["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_department(client: AsyncClient) -> None:
    """POST /agents/departments creates a custom department."""
    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/agents/departments",
        headers=auth["headers"],
        json={
            "name": "Legal",
            "description": "Legal analysis and compliance",
            "sunflower_index": 8,
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Legal"
    assert data["sunflower_index"] == 8
    assert data["is_active"] is True
    assert data["agent_count"] == 0


@pytest.mark.asyncio
async def test_create_department_duplicate_name(client: AsyncClient) -> None:
    """POST /agents/departments rejects duplicate name for same tenant."""
    auth = await _register_and_login(client)

    payload = {"name": "Legal", "sunflower_index": 8}
    resp1 = await client.post(
        "/api/v1/agents/departments", headers=auth["headers"], json=payload,
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/agents/departments", headers=auth["headers"], json=payload,
    )
    assert resp2.status_code == 409


# ── Agents ──


@pytest.mark.asyncio
async def test_list_agents_after_seed(client: AsyncClient) -> None:
    """GET /agents/agents returns 60 agents after seed."""
    auth = await _register_and_login(client)
    await client.post("/api/v1/agents/seed", headers=auth["headers"])

    resp = await client.get(
        "/api/v1/agents/agents", headers=auth["headers"],
    )
    assert resp.status_code == 200
    agents = resp.json()["data"]
    assert len(agents) == 60


@pytest.mark.asyncio
async def test_list_agents_filter_by_department(client: AsyncClient) -> None:
    """GET /agents/agents?department_id=X returns 6 agents for that dept."""
    auth = await _register_and_login(client)
    await client.post("/api/v1/agents/seed", headers=auth["headers"])

    # Get department ID
    dept_resp = await client.get(
        "/api/v1/agents/departments", headers=auth["headers"],
    )
    dept_id = dept_resp.json()["data"][0]["id"]

    resp = await client.get(
        f"/api/v1/agents/agents?department_id={dept_id}",
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    agents = resp.json()["data"]
    assert len(agents) == 6

    # All 6 sub-capabilities present
    caps = sorted([a["sub_capability"] for a in agents])
    assert caps == ["EYES", "HANDS", "MEMORY", "MIND", "SHIELD", "VOICE"]


@pytest.mark.asyncio
async def test_get_agent_by_id(client: AsyncClient) -> None:
    """GET /agents/agents/{id} returns single agent."""
    auth = await _register_and_login(client)
    await client.post("/api/v1/agents/seed", headers=auth["headers"])

    # List to get an ID
    list_resp = await client.get(
        "/api/v1/agents/agents", headers=auth["headers"],
    )
    agent_id = list_resp.json()["data"][0]["id"]

    resp = await client.get(
        f"/api/v1/agents/agents/{agent_id}", headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == agent_id


@pytest.mark.asyncio
async def test_get_agent_not_found(client: AsyncClient) -> None:
    """GET /agents/agents/{bad_id} returns 404."""
    auth = await _register_and_login(client)
    fake_id = str(uuid.uuid4())

    resp = await client.get(
        f"/api/v1/agents/agents/{fake_id}", headers=auth["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient) -> None:
    """POST /agents/agents creates a new agent in a department."""
    auth = await _register_and_login(client)

    # Create a department first
    dept_resp = await client.post(
        "/api/v1/agents/departments",
        headers=auth["headers"],
        json={"name": "Legal", "sunflower_index": 8},
    )
    dept_id = dept_resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/agents/agents",
        headers=auth["headers"],
        json={
            "department_id": dept_id,
            "name": "Legal-MIND",
            "sub_capability": "MIND",
            "description": "Reasoning for legal department",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Legal-MIND"
    assert data["sub_capability"] == "MIND"
    assert data["department_id"] == dept_id
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_agent_invalid_sub_capability(client: AsyncClient) -> None:
    """POST /agents/agents rejects invalid sub_capability."""
    auth = await _register_and_login(client)

    dept_resp = await client.post(
        "/api/v1/agents/departments",
        headers=auth["headers"],
        json={"name": "Legal", "sunflower_index": 8},
    )
    dept_id = dept_resp.json()["data"]["id"]

    resp = await client.post(
        "/api/v1/agents/agents",
        headers=auth["headers"],
        json={
            "department_id": dept_id,
            "name": "Legal-INVALID",
            "sub_capability": "INVALID",
        },
    )
    # Schema regex validation rejects at 422
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_agent_duplicate_sub_capability(client: AsyncClient) -> None:
    """POST /agents/agents rejects duplicate sub_capability in same dept."""
    auth = await _register_and_login(client)

    dept_resp = await client.post(
        "/api/v1/agents/departments",
        headers=auth["headers"],
        json={"name": "Legal", "sunflower_index": 8},
    )
    dept_id = dept_resp.json()["data"]["id"]

    payload = {
        "department_id": dept_id,
        "name": "Legal-MIND",
        "sub_capability": "MIND",
    }
    resp1 = await client.post(
        "/api/v1/agents/agents", headers=auth["headers"], json=payload,
    )
    assert resp1.status_code == 201

    # Same sub_capability in same department → 409
    payload["name"] = "Legal-MIND-2"
    resp2 = await client.post(
        "/api/v1/agents/agents", headers=auth["headers"], json=payload,
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_create_agent_bad_department(client: AsyncClient) -> None:
    """POST /agents/agents rejects nonexistent department_id."""
    auth = await _register_and_login(client)
    fake_id = str(uuid.uuid4())

    resp = await client.post(
        "/api/v1/agents/agents",
        headers=auth["headers"],
        json={
            "department_id": fake_id,
            "name": "Ghost-MIND",
            "sub_capability": "MIND",
        },
    )
    assert resp.status_code == 404


# ── Tenant isolation ──


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient) -> None:
    """Departments created by tenant A are invisible to tenant B.

    Both tenants get auto-seeded defaults on registration, but custom
    departments created by A must not leak to B.
    """
    auth_a = await _register_and_login(client)
    auth_b = await _register_and_login(client)

    # Tenant A creates a custom department
    custom_resp = await client.post(
        "/api/v1/agents/departments",
        headers=auth_a["headers"],
        json={"name": "CustomDeptA", "sunflower_index": 99},
    )
    assert custom_resp.status_code == 201

    # Tenant B should NOT see tenant A's custom department
    resp = await client.get(
        "/api/v1/agents/departments", headers=auth_b["headers"],
    )
    assert resp.status_code == 200
    dept_names = [d["name"] for d in resp.json()["data"]]
    assert "CustomDeptA" not in dept_names

    # Tenant B has its own auto-seeded departments
    assert len(resp.json()["data"]) >= 8
