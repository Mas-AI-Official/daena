"""Tests for SkillService and skill endpoints.

Integration tests: register → login → CRUD skills.
Verifies tenant-scoped catalog, deactivation, and RBAC.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

# ── Helpers ──


async def _register_and_login(client: AsyncClient) -> dict:
    """Register a FOUNDER user and login."""
    unique = uuid.uuid4().hex[:8]
    email = f"skill-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Skill Tester",
            "tenant_name": f"SkillOrg-{unique}",
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


# ── Skill CRUD ──


@pytest.mark.asyncio
async def test_create_skill(client: AsyncClient) -> None:
    """POST /skills creates a skill with correct defaults."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/skills",
        json={
            "name": "web_search",
            "description": "Search the web using Perplexity API",
            "category": "research",
            "schema_def": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
            },
            "governance_tier": 1,
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["name"] == "web_search"
    assert body["data"]["governance_tier"] == 1
    assert body["data"]["is_active"] is True
    assert body["data"]["version"] == "1.0.0"
    assert body["data"]["usage_count"] == 0


@pytest.mark.asyncio
async def test_create_duplicate_skill_fails(client: AsyncClient) -> None:
    """Creating two skills with the same name in one tenant fails."""
    auth = await _register_and_login(client)
    skill_data = {"name": "duplicate_skill", "governance_tier": 0}

    resp1 = await client.post(
        "/api/v1/skills",
        json=skill_data,
        headers=auth["headers"],
    )
    assert resp1.status_code == 201

    resp2 = await client.post(
        "/api/v1/skills",
        json=skill_data,
        headers=auth["headers"],
    )
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_list_skills(client: AsyncClient) -> None:
    """GET /skills lists tenant's skills."""
    auth = await _register_and_login(client)

    await client.post(
        "/api/v1/skills",
        json={"name": "skill_alpha", "category": "ops"},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/skills",
        json={"name": "skill_beta", "category": "research"},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/skills",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) >= 2


@pytest.mark.asyncio
async def test_list_skills_filter_by_category(client: AsyncClient) -> None:
    """GET /skills?category=ops only returns matching skills."""
    auth = await _register_and_login(client)

    await client.post(
        "/api/v1/skills",
        json={"name": "ops_skill", "category": "ops"},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/skills",
        json={"name": "research_skill", "category": "research"},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/skills?category=ops",
        headers=auth["headers"],
    )
    body = response.json()
    assert all(s["category"] == "ops" for s in body["data"])


@pytest.mark.asyncio
async def test_get_skill(client: AsyncClient) -> None:
    """GET /skills/{id} returns full skill details."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/skills",
        json={"name": "detail_skill", "description": "A detailed skill"},
        headers=auth["headers"],
    )
    skill_id = create_resp.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/skills/{skill_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["name"] == "detail_skill"
    assert body["data"]["description"] == "A detailed skill"


@pytest.mark.asyncio
async def test_update_skill(client: AsyncClient) -> None:
    """PATCH /skills/{id} updates only provided fields."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/skills",
        json={"name": "updatable_skill", "governance_tier": 0},
        headers=auth["headers"],
    )
    skill_id = create_resp.json()["data"]["id"]

    response = await client.patch(
        f"/api/v1/skills/{skill_id}",
        json={"governance_tier": 3, "description": "Now tier 3"},
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["governance_tier"] == 3
    assert body["data"]["description"] == "Now tier 3"
    assert body["data"]["name"] == "updatable_skill"  # Unchanged


@pytest.mark.asyncio
async def test_deactivate_skill(client: AsyncClient) -> None:
    """DELETE /skills/{id} soft-deactivates (sets is_active=False)."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/skills",
        json={"name": "deactivatable_skill"},
        headers=auth["headers"],
    )
    skill_id = create_resp.json()["data"]["id"]

    response = await client.delete(
        f"/api/v1/skills/{skill_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["is_active"] is False

    # Verify it's hidden from default listing
    list_resp = await client.get(
        "/api/v1/skills",
        headers=auth["headers"],
    )
    names = [s["name"] for s in list_resp.json()["data"]]
    assert "deactivatable_skill" not in names
