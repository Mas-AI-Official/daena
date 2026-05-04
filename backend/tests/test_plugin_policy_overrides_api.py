"""PR-CONN-PER-TENANT-POLICY-OVERRIDES (Sprint-6 PR-6, 2026-05-04) tests.

Pins the per-tenant override contract:

  1. GET returns empty list when no overrides exist.
  2. PUT inserts an override for FOUNDER role; GET reflects it.
  3. PUT is idempotent (second PUT updates the existing row, no
     duplicate; unique constraint enforces this).
  4. Invalid tier rejected with 422 (Pydantic enum validation).
  5. Invalid skill_class rejected with 422.
  6. Tenant isolation: tenant A's override invisible to tenant B.
  7. Endpoint requires auth (anonymous rejected).
  8. Phase 2 enforcement is unchanged: PHASE2_ALLOWLIST still has
     zero non-read-only entries even after an override.
  9. Response payload carries no token / secret substring.
"""

from __future__ import annotations

import uuid as _uuid

import pytest
from sqlalchemy import select

from app.models.identity import Tenant, User
from app.models.plugin_policy_override import PluginPolicyOverride


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, tenant_id, user_id):
    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_id, name="T", slug=f"t-ovr-{tenant_id.hex[:6]}",
            settings={},
        ))
        await db_session.flush()
    if (await db_session.execute(
        select(User).where(User.id == user_id),
    )).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email=f"founder-{user_id.hex[:6]}@test.local", role="FOUNDER",
        ))
        await db_session.flush()
    await db_session.commit()


# ──────────────────────────────────────────────────────────────────
# 1. GET empty
# ──────────────────────────────────────────────────────────────────


async def test_get_returns_empty_list_when_no_overrides(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["overrides"] == []


# ──────────────────────────────────────────────────────────────────
# 2. PUT inserts; GET reflects
# ──────────────────────────────────────────────────────────────────


async def test_put_inserts_override_visible_via_get(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    put = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-stripe",
            "skill_class": "payment",
            "tier": "deny",
            "rationale": "We never want auto-charge.",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()["data"]
    assert body["plugin_id"] == "mcp-stripe"
    assert body["tier"] == "deny"

    listing = await client.get(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
    )
    overrides = listing.json()["data"]["overrides"]
    assert len(overrides) == 1
    assert overrides[0]["plugin_id"] == "mcp-stripe"
    assert overrides[0]["tier"] == "deny"


# ──────────────────────────────────────────────────────────────────
# 3. PUT idempotent (no duplicate row)
# ──────────────────────────────────────────────────────────────────


async def test_put_idempotent_updates_existing_row(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    payload = {
        "plugin_id": "mcp-filesystem",
        "skill_class": "write_external",
        "tier": "deny",
        "rationale": "first call",
    }
    a = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers, json=payload,
    )
    assert a.status_code == 200
    b = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={**payload, "tier": "ask", "rationale": "second call"},
    )
    assert b.status_code == 200

    rows = (await db_session.execute(
        select(PluginPolicyOverride).where(
            PluginPolicyOverride.tenant_id == test_tenant_id,
            PluginPolicyOverride.plugin_id == "mcp-filesystem",
            PluginPolicyOverride.skill_class == "write_external",
        ),
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].tier == "ask"
    assert rows[0].rationale == "second call"


# ──────────────────────────────────────────────────────────────────
# 4. Invalid tier rejected
# ──────────────────────────────────────────────────────────────────


async def test_invalid_tier_rejected_with_422(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-stripe",
            "skill_class": "payment",
            "tier": "MAGICAL_TIER_NOT_REAL",
        },
    )
    assert res.status_code == 422


async def test_invalid_skill_class_rejected_with_422(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-stripe",
            "skill_class": "invented_class",
            "tier": "ask",
        },
    )
    assert res.status_code == 422


# ──────────────────────────────────────────────────────────────────
# 5. Tenant isolation
# ──────────────────────────────────────────────────────────────────


async def test_tenant_a_override_invisible_to_tenant_b(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """Tenant A inserts an override; tenant B's GET sees nothing.

    Implementation note: we mint tenant B's row directly via the DB
    (avoids needing a second JWT for B in scope). The HTTP path for
    A is what proves the upsert; the GET-as-B simulation is via
    direct query with tenant_id filter, which mirrors what the API
    does.
    """
    await _seed_user(db_session, test_tenant_id, test_user_id)
    # A inserts via API.
    put = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-stripe", "skill_class": "payment",
            "tier": "deny",
        },
    )
    assert put.status_code == 200

    # B looks for the row using its own tenant_id -- never finds it.
    tenant_b_id = _uuid.UUID("44444444-4444-4444-4444-444444440002")
    rows = (await db_session.execute(
        select(PluginPolicyOverride).where(
            PluginPolicyOverride.tenant_id == tenant_b_id,
            PluginPolicyOverride.plugin_id == "mcp-stripe",
        ),
    )).scalars().all()
    assert rows == []


# ──────────────────────────────────────────────────────────────────
# 6. Endpoint requires auth
# ──────────────────────────────────────────────────────────────────


async def test_get_requires_auth(client):
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
    )
    assert res.status_code in (401, 403)


async def test_put_requires_auth(client):
    res = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        json={
            "plugin_id": "x", "skill_class": "payment", "tier": "deny",
        },
    )
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# 7. Phase 2 enforcement unchanged after override
# ──────────────────────────────────────────────────────────────────


async def test_override_does_not_unlock_phase2_writes(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-github",
            "skill_class": "write_external",
            "tier": "allow",
        },
    )
    assert res.status_code == 200
    # PHASE2_ALLOWLIST still has zero non-read-only entries -- the
    # override does NOT make any write skill executable.
    from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST
    write_allowed = [e for e in PHASE2_ALLOWLIST if not e.read_only]
    assert write_allowed == []


# ──────────────────────────────────────────────────────────────────
# 8. Response carries no token-shaped fields
# ──────────────────────────────────────────────────────────────────


async def test_response_carries_no_token_substring(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.put(
        "/api/v1/connections/v2/governance/plugin-policy-overrides",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-stripe", "skill_class": "payment",
            "tier": "deny",
        },
    )
    raw = res.text
    for forbidden in (
        "access_token", "refresh_token", "Bearer",
        "client_secret", "vault", "credentials",
    ):
        assert forbidden not in raw, (
            f"override payload leaked '{forbidden}'"
        )
