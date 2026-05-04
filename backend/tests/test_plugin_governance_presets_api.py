"""PR-CONN-GOV-PRESETS-API-UI (Sprint-5 PR-5, 2026-05-03) tests for the
HTTP surface of the per-plugin governance preset table.

Pins:

  1. Endpoint requires auth.
  2. Returns the full preset table including the DEFAULT fallback marker.
  3. Founder's 8 plugins (Filesystem / GitHub / Gmail / Drive / Slack /
     Stripe / Playwright / ChromeDevTools) are all present.
  4. Response carries the conservative defaults the founder pinned:
     Stripe PAYMENT=DENY, Filesystem WRITE_EXTERNAL=DENY,
     Gmail SEND_MESSAGE=DENY.
  5. Response is JSON-safe + carries no token/credentials substring
     (defense-in-depth -- the table is purely strings, but the test
     pins this so a future code change can't accidentally leak).
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User
    if (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none() is None:
        db_session.add(Tenant(id=tenant_id, name="T", slug="t-gp", settings={}))
        await db_session.flush()
    if (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email="founder@test.local", role="FOUNDER",
        ))
        await db_session.flush()
    await db_session.commit()


# ──────────────────────────────────────────────────────────────────
# 1. Auth required
# ──────────────────────────────────────────────────────────────────


async def test_endpoint_requires_auth(client):
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-presets",
    )
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# 2. Returns full table + DEFAULT marker
# ──────────────────────────────────────────────────────────────────


async def test_returns_full_table_with_fallback_marker(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-presets",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    presets = body["data"]["presets"]
    # Founder list is 8 plugins + DEFAULT fallback = 9 entries.
    assert len(presets) == 9
    fallbacks = [p for p in presets if p.get("_is_fallback")]
    assert len(fallbacks) == 1
    assert fallbacks[0]["plugin_id"] == "__default__"


# ──────────────────────────────────────────────────────────────────
# 3. Founder coverage
# ──────────────────────────────────────────────────────────────────


async def test_founder_plugins_all_present(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-presets",
        headers=auth_headers,
    )
    presets = res.json()["data"]["presets"]
    plugin_ids = {p["plugin_id"] for p in presets if not p.get("_is_fallback")}
    expected = {
        "mcp-filesystem", "mcp-github", "app-gmail",
        "app-google-drive", "mcp-slack", "mcp-stripe",
        "mcp-playwright", "mcp-chrome-devtools",
    }
    missing = expected - plugin_ids
    assert not missing, f"Missing founder plugins: {missing}"


# ──────────────────────────────────────────────────────────────────
# 4. Conservative defaults preserved through serialization
# ──────────────────────────────────────────────────────────────────


async def test_conservative_defaults_preserved(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-presets",
        headers=auth_headers,
    )
    by_id = {p["plugin_id"]: p for p in res.json()["data"]["presets"]}
    assert by_id["mcp-stripe"]["tiers"]["payment"] == "deny"
    assert by_id["mcp-filesystem"]["tiers"]["write_external"] == "deny"
    assert by_id["app-gmail"]["tiers"]["send_message"] == "deny"
    # And the permissive-read defaults stay permissive:
    assert by_id["mcp-github"]["tiers"]["read"] == "allow"


# ──────────────────────────────────────────────────────────────────
# 5. Token-leak defense
# ──────────────────────────────────────────────────────────────────


async def test_response_payload_carries_no_token_substring(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connections/v2/governance/plugin-presets",
        headers=auth_headers,
    )
    raw = res.text
    for forbidden in (
        "access_token", "refresh_token", "Bearer",
        "client_secret", "vault", "credentials",
    ):
        assert forbidden not in raw, (
            f"Plugin presets payload leaked '{forbidden}'"
        )
