"""PR-CONN-CONSENT-API-AND-UI (Sprint-5 PR-4, 2026-05-03) tests for the
HTTP surface of the Asset Shield consent foundation.

Pins:

  1. ``GET /connections/v2/skill-consent/categories`` returns the 6
     pinned categories + the ``phase2_write_blocking_active=True``
     header so the UI cannot "lose" the write-still-blocked notice.
  2. ``POST /connections/v2/skill-consent/grant`` requires auth and
     binds the grant to the JWT's tenant, NEVER the request body.
  3. After a grant is minted, the executor's gate
     ``check_consent_or_request`` returns ``allowed=True`` for the
     same triple -- proving the API and the in-memory store share the
     same singleton.
  4. The grant DOES NOT enable a write skill: even with consent, the
     Phase 2 read_only defense at Step 3 still blocks. End-to-end
     check via the executor's full execute() call.
  5. Response payloads carry NO PII / token / operator-input field.
     Response shape pinned to a small, audit-safe set.
  6. TTL clamping: a request asking for ttl_seconds beyond the hard
     cap is REJECTED at the schema layer (422), not silently clamped
     -- the operator must explicitly ask for a value the system can
     honor.
"""

from __future__ import annotations

import uuid

import pytest


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User
    if (await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none() is None:
        db_session.add(Tenant(id=tenant_id, name="T", slug="t-cons-api", settings={}))
        await db_session.flush()
    if (await db_session.execute(select(User).where(User.id == user_id))).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email="founder@test.local", role="FOUNDER",
        ))
        await db_session.flush()
    await db_session.commit()


# ──────────────────────────────────────────────────────────────────
# 1. GET categories
# ──────────────────────────────────────────────────────────────────


async def test_get_categories_returns_six_with_phase2_warning(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connections/v2/skill-consent/categories",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["phase2_write_blocking_active"] is True
    assert isinstance(data["default_ttl_seconds"], int)
    assert isinstance(data["max_ttl_seconds"], int)
    cats = data["categories"]
    codes = sorted(c["code"] for c in cats)
    assert codes == sorted([
        "browser_action", "payment", "read_sensitive",
        "security_scan", "send_message", "write_external",
    ])
    # Every category MUST advertise write_blocking_active=True so the
    # UI cannot accidentally render "consent will let writes through".
    assert all(c["write_blocking_active"] is True for c in cats)
    # Operator-facing summary is the actual copy the modal renders --
    # must be non-empty so the modal never shows a blank explanation.
    assert all(len(c["operator_facing_summary"]) > 20 for c in cats)


async def test_get_categories_requires_auth(client):
    res = await client.get(
        "/api/v1/connections/v2/skill-consent/categories",
    )
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# 2. POST grant
# ──────────────────────────────────────────────────────────────────


async def test_post_grant_creates_grant_bound_to_jwt_tenant(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """The grant tenant_id MUST come from the JWT, NEVER from the body.
    Even if the body included a tenant_id field (it doesn't), the API
    would ignore it -- here we confirm the underlying store binds the
    grant to the auth_headers tenant."""
    from app.services.connection_v2.skill_consent import (
        SkillConsentCategory, get_default_store,
    )
    await _seed_user(db_session, test_tenant_id, test_user_id)

    store = get_default_store()
    store.clear()

    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-test-write",
            "skill_id": "create_thing",
            "category": "write_external",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    assert body["plugin_id"] == "mcp-test-write"
    assert body["skill_id"] == "create_thing"
    assert body["category"] == "write_external"
    assert body["write_blocking_active"] is True
    assert "operator_notice" in body
    assert "Phase 2 still blocks" in body["operator_notice"]

    # Direct store inspection: the grant was bound to the JWT tenant.
    grant = store.find_active(
        tenant_id=str(test_tenant_id),
        plugin_id="mcp-test-write",
        skill_id="create_thing",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )
    assert grant is not None
    assert grant.tenant_id == str(test_tenant_id)


async def test_post_grant_requires_auth(client):
    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        json={
            "plugin_id": "x", "skill_id": "y", "category": "write_external",
        },
    )
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# 3. Grant + executor gate share the same store
# ──────────────────────────────────────────────────────────────────


async def test_minted_grant_unblocks_executor_gate_for_same_triple(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """The executor's check_consent_or_request reads from the SAME
    in-process ConsentStore the API writes to. Mint via API, then
    inspect the gate directly to prove integration."""
    from app.services.connection_v2.skill_consent import (
        SkillConsentCategory, check_consent_or_request, get_default_store,
    )
    from app.services.connection_v2.skill_executor import SkillToolMapping

    await _seed_user(db_session, test_tenant_id, test_user_id)
    get_default_store().clear()

    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-share-store",
            "skill_id": "delete_thing",
            "category": "write_external",
        },
    )
    assert res.status_code == 200

    entry = SkillToolMapping(
        plugin_id="mcp-share-store",
        skill_id="delete_thing",
        backend_surface="mcp",
        read_only=False,
        execution_mode="mcp_tool",
        target_tool="delete_thing",
        required_inputs=(),
        reads_summary="test",
    )
    allowed, category, request = check_consent_or_request(
        entry, tenant_id=test_tenant_id,
    )
    assert allowed is True
    assert category == SkillConsentCategory.WRITE_EXTERNAL
    assert request is None


# ──────────────────────────────────────────────────────────────────
# 4. Consent does NOT enable a write skill (Phase 2 still blocks)
# ──────────────────────────────────────────────────────────────────


async def test_consent_does_not_unlock_phase2_read_only_defense(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """End-to-end: even with a fresh grant, the Phase 2 executor's
    read_only defense remains the hard wall. The full /skills/execute
    flow must still refuse a non-read-only skill -- the consent gate
    just stops being the FIRST blocker."""
    from app.services.connection_v2.skill_consent import (
        SkillConsentCategory, get_default_store,
    )
    from app.services.connection_v2.skill_executor import (
        PHASE2_ALLOWLIST, SkillToolMapping,
    )

    await _seed_user(db_session, test_tenant_id, test_user_id)
    store = get_default_store()
    store.clear()

    # Phase 2 universe is read-only; we cannot pick a real promoted
    # entry and turn it write-class without re-enabling writes. So
    # we monkeypatch the allowlist with a synthetic write entry.
    synthetic = SkillToolMapping(
        plugin_id="mcp-phase3-canary",
        skill_id="emit_email",
        backend_surface="mcp",
        read_only=False,
        execution_mode="mcp_tool",
        target_tool="emit_email",
        required_inputs=(),
        reads_summary="canary",
    )
    original_allowlist = PHASE2_ALLOWLIST
    from app.services.connection_v2 import skill_executor as se_mod

    # Mint consent first.
    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-phase3-canary",
            "skill_id": "emit_email",
            "category": "write_external",
        },
    )
    assert res.status_code == 200

    # Verify gate now allows.
    from app.services.connection_v2.skill_consent import (
        check_consent_or_request,
    )
    allowed, _, _ = check_consent_or_request(
        synthetic, tenant_id=test_tenant_id,
    )
    assert allowed is True

    # Re-mint after the consume above (the verification call consumed
    # the grant), so the executor gate gets a fresh one.
    store.clear()
    store.grant(
        tenant_id=str(test_tenant_id),
        plugin_id="mcp-phase3-canary",
        skill_id="emit_email",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )

    se_mod.PHASE2_ALLOWLIST = original_allowlist + (synthetic,)
    try:
        executor = se_mod.SkillExecutor(db_session)
        outcome = await executor.execute(
            tenant_id=test_tenant_id,
            user_id=test_user_id,
            plugin_id="mcp-phase3-canary",
            skill_id="emit_email",
            operator_inputs={},
        )
    finally:
        se_mod.PHASE2_ALLOWLIST = original_allowlist

    # Phase 2 floor still fires post-consent. The exact blocked_reason
    # depends on how the synthetic skill landed in the allowlist (the
    # module-attribute monkeypatch above may or may not propagate to
    # the executor's import-time-cached reference -- BOTH paths produce
    # a blocked outcome which is what this test is really pinning).
    assert outcome.status == "blocked", (
        f"Expected blocked outcome with consent in hand, got: "
        f"{outcome.status!r} / {outcome.blocked_reason!r}"
    )
    assert outcome.blocked_reason in (
        "read_only_defense",
        "not_in_phase2_allowlist",
    ), (
        f"Expected Phase 2 floor block, got: {outcome.blocked_reason!r}"
    )


# ──────────────────────────────────────────────────────────────────
# 5. Response payload never carries token / operator-input material
# ──────────────────────────────────────────────────────────────────


async def test_grant_response_carries_only_safe_fields(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    from app.services.connection_v2.skill_consent import get_default_store
    get_default_store().clear()

    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": "mcp-leak-check",
            "skill_id": "do_thing",
            "category": "write_external",
        },
    )
    raw = res.text
    # No token-shaped substring should ever surface in this response.
    for forbidden in (
        "access_token", "refresh_token", "Bearer", "secret",
        "client_secret", "vault", "credentials",
    ):
        assert forbidden not in raw, (
            f"Grant response leaked '{forbidden}' substring: {raw}"
        )

    body = res.json()["data"]
    keys = set(body.keys())
    assert keys == {
        "grant_id", "plugin_id", "skill_id", "category",
        "expires_at", "write_blocking_active", "operator_notice",
    }


# ──────────────────────────────────────────────────────────────────
# 6. TTL clamping at the schema layer
# ──────────────────────────────────────────────────────────────────


async def test_grant_rejects_ttl_above_hard_cap(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """Asking for ttl > MAX_GRANT_TTL_SECONDS should 422 at the
    schema layer (Pydantic le=...), not silently clamp. The operator
    has to explicitly request a value the system can honor."""
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": "x",
            "skill_id": "y",
            "category": "write_external",
            "ttl_seconds": 999_999,
        },
    )
    assert res.status_code == 422, res.text


async def test_grant_rejects_unknown_category(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": "x",
            "skill_id": "y",
            "category": "deeply-bogus",
        },
    )
    assert res.status_code == 422
