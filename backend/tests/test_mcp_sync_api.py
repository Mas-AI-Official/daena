"""Tests for the MCP sync API endpoints.

Pin the contract:
* ``GET /api/v1/mcp-sync/detected`` requires auth.
* ``POST /api/v1/mcp-sync/import`` runs the install scanner and rejects
  malformed URLs / shell-injection patterns before registering.
* A clean entry is registered in the shared MCP registry.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_mcp_sync_detected_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated callers get 401 on detected listing."""
    response = await client.get("/api/v1/mcp-sync/detected")
    # FastAPI's HTTPBearer returns 403 when no header is present,
    # 401 when a bad token is provided. Either is acceptable here --
    # the contract is "not open to anonymous callers."
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_mcp_sync_import_governs_via_install_scanner(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    """A command-based entry (npx + first arg) survives the scanner and
    is registered with governance_tier=2 for external tools."""
    from app.core import events as events_mod

    # Reset the singleton so assertions do not leak across tests.
    events_mod._mcp_registry = None

    response = await client.post(
        "/api/v1/mcp-sync/import",
        headers=auth_headers,
        json={
            "name": "gmail",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-gmail"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["safe"] is True
    assert body["registered"] is True
    assert body["name"] == "gmail"
    assert body["governance_tier"] == 2

    # The tool should now be discoverable in the shared registry.
    registry = events_mod.get_mcp_registry()
    assert registry.get_tool("gmail") is not None


@pytest.mark.asyncio
async def test_mcp_sync_import_rejects_malformed_url(
    client: AsyncClient, auth_headers: dict[str, str],
) -> None:
    """A URL without http/https/npx/uvx prefix or with shell-injection
    characters comes back as unsafe and is NOT registered."""
    from app.core import events as events_mod

    events_mod._mcp_registry = None

    response = await client.post(
        "/api/v1/mcp-sync/import",
        headers=auth_headers,
        json={
            "name": "malicious",
            "url": "ftp://not-a-real-scheme.example.com",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["safe"] is False
    assert body["registered"] is False
    assert body["blockers"]  # scanner reported something

    registry = events_mod.get_mcp_registry()
    assert registry.get_tool("malicious") is None
