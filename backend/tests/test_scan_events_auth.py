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
