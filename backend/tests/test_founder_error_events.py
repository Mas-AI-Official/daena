"""DEP-007 follow-up: founder-safe recent-error-events endpoint."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.error_event import ErrorEvent


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"errev-{unique}@test.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email, "password": "SecurePass123!",
            "display_name": "ErrEv", "tenant_name": f"ErrEvOrg-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


@pytest.mark.asyncio
async def test_error_events_requires_auth(client: AsyncClient) -> None:
    """No token -> rejected (endpoint is FOUNDER-gated, never public)."""
    resp = await client.get("/api/v1/founder/error-events")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_founder_lists_safe_error_events(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A founder can list recent error events; only safe fields are returned."""
    auth = await _register_and_login(client)

    # Seed one error event (committed so the endpoint's session sees it).
    db_session.add(
        ErrorEvent(
            source="exception_handler",
            severity="error",
            route="/api/v1/test",
            method="POST",
            status_code=500,
            error_code="INTERNAL_ERROR",
            error_type="ValueError",
            safe_message="Something went wrong. Please try again.",
            request_id="req-errev-1",
        )
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/founder/error-events?limit=50", headers=auth["headers"]
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["success"] is True
    assert isinstance(payload["data"], list)

    seeded = [r for r in payload["data"] if r.get("request_id") == "req-errev-1"]
    assert seeded, "seeded error event should be listed"
    row = seeded[0]
    assert row["error_type"] == "ValueError"
    assert row["safe_message"] == "Something went wrong. Please try again."
    # Safety: the wire shape carries no secret/stack/raw-exc fields.
    forbidden = {"traceback", "stack", "exception", "secret", "token", "credentials"}
    assert not (forbidden & set(row.keys())), f"unsafe field in response: {row.keys()}"
    assert "Traceback" not in resp.text
