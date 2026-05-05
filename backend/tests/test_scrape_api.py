"""Sprint-10 PR-2: API surface for the governed read-only scrape skill.

Pins the contract for ``POST /api/v1/scrape/extract``.
"""

from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.identity import Tenant, User
from app.services.scrape import ExtractResult, ScrapeError


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def seeded_tenant_user(db_session) -> tuple[str, str]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id, name=f"Sc {tenant_id.hex[:6]}",
        slug=f"sc-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@sc.local",
        password_hash="$2b$12$x" * 4,
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    await db_session.commit()
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id),
        role="FOUNDER", email="dev@sc.local", display_name="Sc",
    )
    return token, str(user_id)


async def test_extract_endpoint_requires_auth(client: AsyncClient):
    res = await client.post(
        "/api/v1/scrape/extract",
        json={"url": "https://example.com/", "goal": "x"},
    )
    assert res.status_code in (401, 403)


async def test_extract_endpoint_lower_role_forbidden(
    client: AsyncClient, seeded_tenant_user, db_session,
):
    """ADMIN role lacks FOUNDER privilege; the endpoint must refuse."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id, name=f"Sc2 {tenant_id.hex[:6]}",
        slug=f"sc2-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@sc2.local",
        password_hash="$2b$12$x" * 4,
        role="USER", email_verified=True,
    ))
    await db_session.commit()
    low_token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id),
        role="USER", email="user@sc.local", display_name="U",
    )
    res = await client.post(
        "/api/v1/scrape/extract",
        headers={"Authorization": f"Bearer {low_token}"},
        json={"url": "https://example.com/", "goal": "x"},
    )
    assert res.status_code in (401, 403)


async def test_extract_endpoint_blocks_ssrf_url(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    token, _ = seeded_tenant_user
    # The service raises ScrapeError("url_safety:...") before the
    # subprocess spawns, so we don't need a worker mock here.
    res = await client.post(
        "/api/v1/scrape/extract",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": "http://localhost/admin?secret=hunter2", "goal": "extract"},
    )
    assert res.status_code == 400
    body = res.json()
    detail = body.get("detail", {})
    assert detail.get("code") == "url_safety"
    assert "url_loopback_host" in detail.get("message", "") or \
           "url_localhost_host" in detail.get("message", "")
    # Audit row id is surfaced so the operator can correlate.
    assert detail.get("audit_event_id"), body
    # The raw URL value (with the secret query) must not echo back.
    assert "hunter2" not in res.text


async def test_extract_endpoint_happy_path(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    token, user_id = seeded_tenant_user

    async def fake_extract(url, goal, *, max_chars=8000, **_):
        return ExtractResult(
            success=True,
            result="Page title: Example Domain.",
            truncated=False,
            error=None,
            worker_version="1.0.0",
        )

    monkeypatch.setattr(
        "app.api.v1.scrape.extract_from_url", fake_extract,
    )
    res = await client.post(
        "/api/v1/scrape/extract",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://example.com/",
            "goal": "find the page title",
            "max_chars": 4000,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert "Example Domain" in body["result"]
    assert body["worker_version"] == "1.0.0"
    assert body["audit_event_id"]


async def test_extract_endpoint_audit_row_does_not_leak_url_value_or_goal(
    client: AsyncClient, seeded_tenant_user, db_session, monkeypatch,
):
    """The audit row must carry url_host (scheme+host) but never the
    full URL with query/fragment, and never the goal text itself."""
    token, _ = seeded_tenant_user

    async def fake_extract(url, goal, *, max_chars=8000, **_):
        return ExtractResult(
            success=True, result="ok", truncated=False,
            error=None, worker_version="1.0.0",
        )

    monkeypatch.setattr(
        "app.api.v1.scrape.extract_from_url", fake_extract,
    )

    sensitive_url = "https://example.com/private?ssn=123-45-6789&pw=hunter2"
    sensitive_goal = "find the ssn"
    res = await client.post(
        "/api/v1/scrape/extract",
        headers={"Authorization": f"Bearer {token}"},
        json={"url": sensitive_url, "goal": sensitive_goal},
    )
    assert res.status_code == 200

    # Inspect the latest audit row for this skill_id.
    from sqlalchemy import select, desc
    from app.models.governance import GoaAuditEvent
    rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.action_type == "plugin.skill_invocation")
        .order_by(desc(GoaAuditEvent.created_at))
        .limit(1)
    )).scalars().all()
    assert rows, "audit row missing"
    row = rows[0]
    params_text = json.dumps(row.action_params or {})
    # url_host present, full URL value absent, query string absent.
    assert "https://example.com" in params_text
    assert "ssn=" not in params_text
    assert "hunter2" not in params_text
    assert sensitive_goal not in params_text
    # goal_length was stored, not the goal text.
    assert (row.action_params or {}).get("goal_length") == len(sensitive_goal)
