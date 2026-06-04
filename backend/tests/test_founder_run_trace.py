"""Local run-tracing: founder-safe run-trace timeline endpoint.

Read-side companion to test_run_tracer.py (the writer). Mirrors the DEP-007
error-events test pattern: a freshly-registered user owns their tenant and is
therefore FOUNDER, so they can read; no token is rejected; only safe fields go
on the wire; one request_id's spans never leak into another's timeline.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.run_trace_event import RunTraceEvent


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"runtrace-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email, "password": "SecurePass123!",
            "display_name": "RunTrace", "tenant_name": f"RunTraceOrg-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.mark.asyncio
async def test_run_trace_requires_auth(client: AsyncClient) -> None:
    """No token -> rejected (endpoint is FOUNDER-gated, never public)."""
    resp = await client.get("/api/v1/founder/run-trace/req-anything")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_founder_gets_ordered_safe_run_trace(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A founder gets the chronological span timeline for a request_id; safe fields only."""
    auth = await _register_and_login(client)

    rid = f"req-{uuid.uuid4().hex[:8]}"
    base = datetime(2026, 6, 3, 12, 0, 0, tzinfo=timezone.utc)
    # Seed three spans OUT of chronological order to prove the endpoint sorts.
    db_session.add_all([
        RunTraceEvent(
            event_type="chat.end", stage="9_done", status="ok",
            request_id=rid, run_id="run-1", provider="anthropic", model="claude",
            created_at=base + timedelta(seconds=2),
            metadata_json={"content_len": 42},
        ),
        RunTraceEvent(
            event_type="chat.start", stage="0_start", status="ok",
            request_id=rid, run_id="run-1",
            created_at=base,
        ),
        RunTraceEvent(
            event_type="memory.persisted", stage="9_persist", status="ok",
            request_id=rid, run_id="run-1", provider="anthropic", model="claude",
            created_at=base + timedelta(seconds=1),
            metadata_json={"content_len": 42, "latency_ms": 1200},
        ),
    ])
    # A span from a DIFFERENT request must NOT leak into this trace.
    db_session.add(
        RunTraceEvent(
            event_type="chat.start", stage="0_start", status="ok",
            request_id="req-other", run_id="run-2", created_at=base,
        )
    )
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/founder/run-trace/{rid}", headers=auth["headers"]
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert payload["request_id"] == rid
    assert payload["count"] == 3, "only this request_id's spans, no leakage"

    events = [r["event_type"] for r in payload["data"]]
    assert events == ["chat.start", "memory.persisted", "chat.end"], "chronological order"

    # Safety: the wire shape carries no secret/prompt/body fields at the top level.
    forbidden = {
        "prompt", "response", "content", "body", "secret", "token",
        "credentials", "messages", "system_prompt",
    }
    for row in payload["data"]:
        assert not (forbidden & set(row.keys())), f"unsafe field: {row.keys()}"
    assert "SecurePass123!" not in resp.text


@pytest.mark.asyncio
async def test_run_trace_unknown_request_is_empty(client: AsyncClient) -> None:
    """Unknown request_id -> 200 with an empty timeline (no crash, no info leak)."""
    auth = await _register_and_login(client)
    resp = await client.get(
        "/api/v1/founder/run-trace/req-does-not-exist", headers=auth["headers"]
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert payload["count"] == 0
    assert payload["data"] == []
