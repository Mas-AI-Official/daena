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


@pytest.mark.asyncio
async def test_readiness_does_not_gate_on_optional_redis(client: AsyncClient) -> None:
    """RT-02: /health/ready is ready when DB is up even if Redis is absent.

    Redis is an optional/graceful-fallback dependency; gating readiness on
    it made Cloud Run startup probes fail on any deploy without a Redis
    sidecar. The test env has no Redis, so this asserts the new contract:
    status=ready, redis reported as a non-gating optional status.
    """
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready", f"DB up should be ready; got {data}"
    assert data["checks"]["database"] == "connected"
    # Redis is non-gating: either connected, or the optional-unavailable marker.
    assert data["checks"]["redis"] in {"connected", "optional_unavailable"}


@pytest.mark.asyncio
async def test_request_id_correlation_header(client: AsyncClient) -> None:
    """EH-02: every response carries X-Request-ID; an inbound id is echoed."""
    # Generated when absent.
    r1 = await client.get("/health")
    assert r1.headers.get("X-Request-ID"), "X-Request-ID must be present"

    # Propagated when the caller supplies one (gateway/support correlation).
    supplied = "test-correlation-id-123"
    r2 = await client.get("/health", headers={"X-Request-ID": supplied})
    assert r2.headers.get("X-Request-ID") == supplied
