"""PR-CONN-CONSENT-DB-PERSISTENCE (Sprint-6 PR-5, 2026-05-04) tests.

Pins the DBConsentStore contract:

  1. ``grant`` writes a row to ``consent_grants`` with
     consumed_at=NULL.
  2. ``find_active`` returns the same grant (by content match).
  3. ``acknowledge`` flips consumed_at to a timestamp; subsequent
     ``acknowledge`` returns None (single-use).
  4. ``find_active`` filters out expired grants.
  5. Tenant isolation: a grant minted by tenant A is never returned
     to tenant B.
  6. Schema-level: the row carries no token-shaped fields.
  7. End-to-end via API: mint via /skill-consent/grant, then look up
     in the DB store directly.
  8. Synthetic write skill still blocked even after consent (the
     existing read_only defense + Phase 2 floor are unchanged).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.consent_grant import ConsentGrant
from app.models.identity import Tenant, User
from app.services.connection_v2.skill_consent import (
    DBConsentStore,
    SkillConsentCategory,
    SkillConsentExpired,
)


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, tenant_id, user_id):
    """Idempotent seed of (tenant, user). Commits to make the row
    visible to the FastAPI app's session (override_get_db yields
    THIS session, but commit + isolation level on SQLite means the
    HTTP path sees only committed state). Keep the slug stable so
    repeated runs don't violate uniqueness."""
    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_id, name="T", slug=f"t-cdb-{tenant_id.hex[:6]}",
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
# 1. Grant + find round-trip
# ──────────────────────────────────────────────────────────────────


async def test_grant_then_find_returns_same_grant(
    db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    store = DBConsentStore(db_session)

    g = await store.grant(
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        category=SkillConsentCategory.READ_SENSITIVE,
    )
    assert g.grant_id
    assert not g.consumed

    found = await store.find_active(
        tenant_id=test_tenant_id,
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        category=SkillConsentCategory.READ_SENSITIVE,
    )
    assert found is not None
    assert found.grant_id == g.grant_id


# ──────────────────────────────────────────────────────────────────
# 2. Acknowledge is single-use
# ──────────────────────────────────────────────────────────────────


async def test_acknowledge_single_use(
    db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    store = DBConsentStore(db_session)
    g = await store.grant(
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        plugin_id="mcp-github",
        skill_id="create_issue",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )
    first = await store.acknowledge(g.grant_id, tenant_id=test_tenant_id)
    assert first is not None
    assert first.consumed is True

    # A second acknowledge on the same id returns None.
    second = await store.acknowledge(g.grant_id, tenant_id=test_tenant_id)
    assert second is None


# ──────────────────────────────────────────────────────────────────
# 3. Expired grants filtered out
# ──────────────────────────────────────────────────────────────────


async def test_expired_grant_filtered_from_find(
    db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    # Insert a row with expires_at in the past.
    past = datetime.now(UTC) - timedelta(seconds=60)
    row = ConsentGrant(
        tenant_id=test_tenant_id,
        plugin_id="mcp-slack",
        skill_id="send_message",
        category=SkillConsentCategory.SEND_MESSAGE.value,
        expires_at=past,
    )
    db_session.add(row)
    await db_session.flush()
    await db_session.commit()

    store = DBConsentStore(db_session)
    found = await store.find_active(
        tenant_id=test_tenant_id,
        plugin_id="mcp-slack",
        skill_id="send_message",
        category=SkillConsentCategory.SEND_MESSAGE,
    )
    assert found is None


async def test_acknowledge_expired_raises(
    db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    past = datetime.now(UTC) - timedelta(seconds=10)
    row = ConsentGrant(
        tenant_id=test_tenant_id,
        plugin_id="mcp-slack",
        skill_id="send_message",
        category=SkillConsentCategory.SEND_MESSAGE.value,
        expires_at=past,
    )
    db_session.add(row)
    await db_session.flush()
    await db_session.commit()

    store = DBConsentStore(db_session)
    with pytest.raises(SkillConsentExpired):
        await store.acknowledge(str(row.id), tenant_id=test_tenant_id)


# ──────────────────────────────────────────────────────────────────
# 4. Tenant isolation
# ──────────────────────────────────────────────────────────────────


async def test_grant_in_tenant_a_invisible_to_tenant_b(
    db_session, test_tenant_id, test_user_id,
):
    """Tenant A mints a grant; tenant B's find_active never returns it."""
    import uuid as _uuid
    # Use a tenant id distinct from any other test's "other tenant"
    # convention to avoid cross-test fixture collision (test_engine is
    # session-scoped, so committed rows persist across tests).
    tenant_b_id = _uuid.UUID("44444444-4444-4444-4444-cdb000000001")
    await _seed_user(db_session, test_tenant_id, test_user_id)
    # Seed tenant B + a user.
    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_b_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_b_id, name="B", slug="b-cdb", settings={},
        ))
        await db_session.flush()
        await db_session.commit()

    store = DBConsentStore(db_session)
    g = await store.grant(
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        category=SkillConsentCategory.READ_SENSITIVE,
    )
    assert g.grant_id

    # Tenant B query for the same content -> None.
    found = await store.find_active(
        tenant_id=tenant_b_id,
        plugin_id="app-gmail",
        skill_id="summarize_unread",
        category=SkillConsentCategory.READ_SENSITIVE,
    )
    assert found is None

    # Tenant B acknowledge by guessed grant_id -> None (tenant filter).
    ack = await store.acknowledge(g.grant_id, tenant_id=tenant_b_id)
    assert ack is None


# ──────────────────────────────────────────────────────────────────
# 5. Row schema carries no token-shaped fields
# ──────────────────────────────────────────────────────────────────


async def test_consent_grant_row_has_no_token_shaped_columns(
    db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    store = DBConsentStore(db_session)
    g = await store.grant(
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        plugin_id="mcp-stripe",
        skill_id="create_charge",
        category=SkillConsentCategory.PAYMENT,
    )
    row = (await db_session.execute(
        select(ConsentGrant).where(ConsentGrant.id == g.grant_id),
    )).scalar_one()
    columns = set(row.__table__.columns.keys())
    forbidden = {
        "access_token", "refresh_token", "bearer", "secret",
        "client_secret", "credentials", "token", "password",
    }
    leaked = columns & forbidden
    assert not leaked, f"consent_grants leaked sensitive cols: {leaked}"


# ──────────────────────────────────────────────────────────────────
# 6. End-to-end via API
# ──────────────────────────────────────────────────────────────────


async def test_api_mint_persists_to_db(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """POST /skill-consent/grant writes a row visible in the DB.

    Use unique-per-test plugin_id + skill_id so cross-test grants
    (test_engine is session-scoped, committed grants survive) never
    interfere with this assertion.
    """
    await _seed_user(db_session, test_tenant_id, test_user_id)
    plugin_id = "app-gmail-cdb-test-api-mint"
    skill_id = "summarize_unread_cdb_test_api_mint"

    res = await client.post(
        "/api/v1/connections/v2/skill-consent/grant",
        headers=auth_headers,
        json={
            "plugin_id": plugin_id,
            "skill_id": skill_id,
            "category": "read_sensitive",
        },
    )
    assert res.status_code == 200, res.text
    grant_id = res.json()["data"]["grant_id"]
    assert grant_id

    # Direct DB lookup by grant_id (sidesteps find_active's ordering
    # heuristics when multiple grants share a created_at second).
    import uuid as _uuid
    row = (await db_session.execute(
        select(ConsentGrant).where(
            ConsentGrant.id == _uuid.UUID(grant_id),
            ConsentGrant.tenant_id == test_tenant_id,
        ),
    )).scalar_one()
    assert row.plugin_id == plugin_id
    assert row.skill_id == skill_id
    assert row.category == "read_sensitive"

    # And find_active returns this grant (only one for this unique
    # plugin/skill pair, so ordering is not a concern).
    store = DBConsentStore(db_session)
    found = await store.find_active(
        tenant_id=test_tenant_id,
        plugin_id=plugin_id,
        skill_id=skill_id,
        category=SkillConsentCategory.READ_SENSITIVE,
    )
    assert found is not None
    assert found.grant_id == grant_id


# ──────────────────────────────────────────────────────────────────
# 7. Even a real DB grant doesn't unlock Phase 2 writes
# ──────────────────────────────────────────────────────────────────


async def test_db_grant_does_not_unlock_phase2_read_only_defense(
    db_session, test_tenant_id, test_user_id,
):
    """Sprint-5 PR-4 already pinned this for the in-memory store. Repeat
    the invariant against the DB store: a fresh grant for a write-class
    category still leaves the read_only defense intact, so no Phase 3
    write actually fires."""
    await _seed_user(db_session, test_tenant_id, test_user_id)
    store = DBConsentStore(db_session)
    g = await store.grant(
        tenant_id=test_tenant_id,
        user_id=test_user_id,
        plugin_id="mcp-github",
        skill_id="create_issue",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )
    # The grant exists -- but the Phase 2 PHASE2_ALLOWLIST has no
    # read_only=False entries, so the executor's read_only defense
    # blocks before it even reaches the consent gate. We assert the
    # contract by inspecting the live allowlist module.
    from app.services.connection_v2.skill_executor import PHASE2_ALLOWLIST
    write_allowed = [
        e for e in PHASE2_ALLOWLIST if not e.read_only
    ]
    assert write_allowed == [], (
        "Sprint-6 PR-5 invariant violated: a non-read-only skill leaked "
        "into PHASE2_ALLOWLIST. The read_only defense is no longer the "
        "Phase 2 floor."
    )
    # And the grant we created is still find-able (the DB store works);
    # it just doesn't bypass the floor.
    found = await store.find_active(
        tenant_id=test_tenant_id,
        plugin_id="mcp-github",
        skill_id="create_issue",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )
    assert found is not None
    assert found.grant_id == g.grant_id
