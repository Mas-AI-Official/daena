"""Auth gating for the Klyntar scan-events SSE stream (K-1, 2026-06-01).

GET /api/v1/security/scans/{job_id}/events was previously unauthenticated.
That meant anyone who could guess (or scrape from logs/Referer) a job_id
could stream the live scan reasoning, observations, phase transitions,
queue decisions, and final findings — a direct leak of sensitive security
findings and an information-disclosure surface even when the underlying
target was authorized.

These tests lock in the K-1 hardening:
  * No token  -> 401 (route enforces auth, not just 'job not found').
  * Bad token -> 401 (rejects bogus bearer before reaching the workflow).

A 200-on-valid-token + valid-job test is intentionally NOT here: the scan
workflow is a process-global singleton with no test fixture, so a positive
test would require spinning up a real ScanWorkflow with a real job. The
auth dependency itself is tested in the broader auth test surface; this
file's job is to prove the route is not silently public anymore.

Native browser EventSource cannot send custom headers, which is why the
frontend consumers (ScanWalkthroughPage, ScanProgressCard) were migrated
to the fetch-based useResilientSSE hook that forwards
``Authorization: Bearer <token>`` from localStorage.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_scan_events_requires_auth(client: AsyncClient) -> None:
    """GET /security/scans/{job_id}/events without a token is rejected
    before reaching the workflow lookup."""
    res = await client.get("/api/v1/security/scans/some-fake-job-id/events")
    assert res.status_code == 401
    # Body must NOT leak whether the job exists; a 404 here would be an
    # info-disclosure regression. The auth gate fires first.
    assert "not found" not in res.text.lower()


@pytest.mark.asyncio
async def test_scan_events_rejects_bogus_token(client: AsyncClient) -> None:
    """A malformed/forged bearer token is rejected with 401, never 200."""
    res = await client.get(
        "/api/v1/security/scans/some-fake-job-id/events",
        headers={"Authorization": "Bearer this-is-not-a-real-token"},
    )
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# K-2 (2026-06-01): the rest of /security/scans/* surface
#
# Survey during K-1 verification found every /scans route except
# POST /scans/start and POST /scans/{id}/findings/{id}/create-remediation
# was unauthenticated. Worst-case routes are DELETE /scans (bulk archive
# or hard-delete every scan) and POST /scans/{id}/rerun (cost
# amplification: anyone could trigger expensive LLM-driven re-scans).
# These tests lock in the K-2 hardening route-by-route.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scans_list_requires_auth(client: AsyncClient) -> None:
    """GET /security/scans without a token must not enumerate any scans."""
    res = await client.get("/api/v1/security/scans")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_detail_requires_auth(client: AsyncClient) -> None:
    """GET /security/scans/{id} (trace JSON) requires auth."""
    res = await client.get("/api/v1/security/scans/some-fake-id")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_status_requires_auth(client: AsyncClient) -> None:
    """GET /security/scans/{id}/status requires auth."""
    res = await client.get("/api/v1/security/scans/some-fake-id/status")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_report_requires_auth(client: AsyncClient) -> None:
    """GET /security/scans/{id}/report requires auth."""
    res = await client.get("/api/v1/security/scans/some-fake-id/report")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_report_pdf_requires_auth(client: AsyncClient) -> None:
    """GET /security/scans/{id}/report/pdf requires auth."""
    res = await client.get("/api/v1/security/scans/some-fake-id/report/pdf")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_rerun_requires_auth(client: AsyncClient) -> None:
    """POST /security/scans/{id}/rerun requires auth (cost-amp gate)."""
    res = await client.post("/api/v1/security/scans/some-fake-id/rerun")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_delete_one_requires_auth(client: AsyncClient) -> None:
    """DELETE /security/scans/{id} requires auth (destructive)."""
    res = await client.delete("/api/v1/security/scans/some-fake-id")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_scan_delete_all_requires_auth(client: AsyncClient) -> None:
    """DELETE /security/scans (bulk) requires auth (catastrophic destructive)."""
    res = await client.delete("/api/v1/security/scans")
    assert res.status_code == 401
