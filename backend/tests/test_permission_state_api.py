"""Tests for GET /api/v1/governance/permission-state.

The endpoint wraps permission_resolver.explain_permission_ui_state so
the frontend doesn't reimplement the logic. Verify the contract:
* Returns 200 for any governance mode
* Invalid mode falls back to BALANCED
* UNLEASHED response flags per_tool_override_active=true
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unleashed_mode_flags_override_active(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        "/api/v1/governance/permission-state",
        headers=auth_headers,
        params={"governance_mode": "UNLEASHED", "autopilot": "true"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["governance_mode"] == "UNLEASHED"
    assert data["autopilot"] is True
    assert data["per_tool_override_active"] == "true"
    assert "UNLEASHED" in data["banner_headline"]


@pytest.mark.asyncio
async def test_governed_mode_keeps_per_tool_active(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        "/api/v1/governance/permission-state",
        headers=auth_headers,
        params={"governance_mode": "GOVERNED", "autopilot": "false"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["per_tool_override_active"] == "false"
    assert "GOVERNED" in data["banner_headline"]


@pytest.mark.asyncio
async def test_invalid_mode_falls_back_to_balanced(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    response = await client.get(
        "/api/v1/governance/permission-state",
        headers=auth_headers,
        params={"governance_mode": "NOT_A_REAL_MODE", "autopilot": "false"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["governance_mode"] == "BALANCED"


@pytest.mark.asyncio
async def test_requires_auth(client: AsyncClient) -> None:
    """Like every /api/v1 route, unauthenticated returns 401 or 403."""
    response = await client.get("/api/v1/governance/permission-state")
    assert response.status_code in (401, 403)
