"""Pins the April 2026 fix: gated engagements persist a PendingApproval row.

Before the fix, POST /api/v1/engagements returned
``approval_required=True`` but never wrote a row. The Sidebar badge
never incremented until the user re-tried via the chat path. This
test proves the row now lands the moment the banner shows.

The T5 tier wire value is resolved from the pre-existing ReportTier
enum so this file does not contain the legacy identifier as a string
literal in its narrative.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.governance import GoaRequest, PendingApproval
from app.services.security.report_tiers import ReportTier

_T5 = ReportTier.EVILBOB.value


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"engage-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Engage Tester",
            "tenant_name": f"EngageOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
        "tenant_id": uuid.UUID(data["user"]["tenant_id"]),
    }


@pytest.mark.asyncio
async def test_t5_tier_persists_approval_row(
    client: AsyncClient, db_session,
) -> None:
    """T5 tier engagement blocks AND creates a PendingApproval.

    The agent defaults to GOVERNED mode when governance_mode is not on
    the user record, so T5 always hits the gate.
    """
    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/engagements",
        json={"target": "https://target.example", "tier": _T5},
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is False
    assert body["approval_required"] is True
    assert body["tier"] == _T5
    assert body["approval_request_id"]  # must be populated post-fix

    # The row itself must exist in the test DB, tenant-scoped.
    rows = (
        await db_session.execute(
            select(PendingApproval).where(
                PendingApproval.tenant_id == auth["tenant_id"]
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    goa_rows = (
        await db_session.execute(
            select(GoaRequest).where(GoaRequest.tenant_id == auth["tenant_id"])
        )
    ).scalars().all()
    assert len(goa_rows) == 1
    assert goa_rows[0].action_type == "SECURITY_ENGAGEMENT"
    # T5 routes to CRITICAL risk + tier 4.
    assert goa_rows[0].risk_level == "CRITICAL"
    assert goa_rows[0].governance_tier == 4


@pytest.mark.asyncio
async def test_scout_tier_does_not_create_approval(
    client: AsyncClient, db_session,
) -> None:
    """Low-risk tiers proceed without approval. No spurious rows."""
    auth = await _register_and_login(client)

    resp = await client.post(
        "/api/v1/engagements",
        json={"target": "https://target.example", "tier": "SCOUT"},
        headers=auth["headers"],
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert "approval_required" not in body.get("data", {}) or not body["data"].get("approval_required")

    rows = (
        await db_session.execute(
            select(PendingApproval).where(
                PendingApproval.tenant_id == auth["tenant_id"]
            )
        )
    ).scalars().all()
    assert len(rows) == 0
