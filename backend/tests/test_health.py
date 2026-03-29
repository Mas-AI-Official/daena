"""Smoke tests for health check endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_health_check(client: AsyncClient) -> None:
    """Root /health endpoint returns 200 with status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "daena-backend"
    assert "version" in data


@pytest.mark.asyncio
async def test_api_health_check(client: AsyncClient) -> None:
    """API /api/v1/health endpoint returns dependency status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data


@pytest.mark.asyncio
async def test_runtime_health_check(client: AsyncClient) -> None:
    """Runtime health exposes redacted config truth and guardrail state."""
    response = await client.get("/api/v1/health/runtime")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in {"healthy", "warning"}
    assert "runtime" in data
    assert "guardrail_issues" in data["runtime"]
    assert "provider_keys" in data["runtime"]
