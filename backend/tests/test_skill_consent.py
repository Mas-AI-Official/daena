"""PR-CONN-ASSET-SHIELD-CONSENT-DESIGN (Sprint-4 PR-4, 2026-05-03) tests.

Pins the foundation:

  1. Categorization is correct + complete:
     - read_only=True -> None (no consent needed)
     - Stripe / Slack / Gmail / Playwright plugins map to their
       category regardless of skill name
     - skill-name substring (send/draft/delete/...) routes to the
       right category
     - Any non-read-only skill that escapes both tables defaults to
       WRITE_EXTERNAL (conservative)
  2. ConsentStore: TTL + single-use + per-(tenant,plugin,skill,category)
     scope.
  3. Executor gate is DORMANT for current Phase 2 entries (every
     allowlist entry is read_only=True so consent is never asked).
  4. Synthetic write skill without consent -> needs_consent outcome.
  5. Synthetic write skill with matching consent -> consent consumed,
     execution proceeds past the consent gate (then hits the read_only
     defense -- proves the consent layer is foundation-only AND
     Phase 2 is still safe).
  6. No PII: SkillConsentRequest + SkillConsentGrant carry only the
     (plugin, skill, category) tuple + UUID + timestamps.

ZERO real network anywhere -- all tests are pure-Python or use
in-memory ConsentStore + DB-only executor calls.
"""

from __future__ import annotations

import time
import uuid
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Tenant, User
from app.services.connection_v2.skill_consent import (
    DEFAULT_GRANT_TTL_SECONDS,
    MAX_GRANT_TTL_SECONDS,
    ConsentStore,
    SkillConsentCategory,
    SkillConsentExpired,
    SkillConsentGrant,
    SkillConsentRequest,
    categorize_skill,
    check_consent_or_request,
)
from app.services.connection_v2.skill_executor import (
    PHASE2_ALLOWLIST,
    SkillExecutor,
    SkillToolMapping,
)


# ──────────────────────────────────────────────────────────────────
# 1. Categorization
# ──────────────────────────────────────────────────────────────────


def _entry(plugin_id: str, skill_id: str, *, read_only: bool) -> SkillToolMapping:
    """Synthetic entry helper for categorization tests."""
    return SkillToolMapping(
        plugin_id=plugin_id,
        skill_id=skill_id,
        backend_surface="oauth",
        read_only=read_only,
        execution_mode="planned_only",
        target_tool=skill_id,
        required_inputs=(),
        reads_summary="test",
    )


def test_categorize_read_only_returns_none():
    e = _entry("app-gmail", "summarize_unread", read_only=True)
    assert categorize_skill(e) is None


def test_categorize_stripe_write_is_payment():
    e = _entry("mcp-stripe", "process_payment", read_only=False)
    assert categorize_skill(e) == SkillConsentCategory.PAYMENT


def test_categorize_slack_write_is_send_message():
    e = _entry("mcp-slack", "draft_reply", read_only=False)
    assert categorize_skill(e) == SkillConsentCategory.SEND_MESSAGE


def test_categorize_gmail_write_is_send_message():
    e = _entry("app-gmail", "send_email", read_only=False)
    assert categorize_skill(e) == SkillConsentCategory.SEND_MESSAGE


def test_categorize_playwright_is_browser_action():
    e = _entry("mcp-playwright", "open_page", read_only=False)
    assert categorize_skill(e) == SkillConsentCategory.BROWSER_ACTION


def test_categorize_skill_name_substring_send():
    e = _entry("mcp-unknown", "send_thing", read_only=False)
    assert categorize_skill(e) == SkillConsentCategory.SEND_MESSAGE


def test_categorize_skill_name_substring_delete():
    e = _entry("mcp-unknown", "delete_record", read_only=False)
    assert categorize_skill(e) == SkillConsentCategory.WRITE_EXTERNAL


def test_categorize_unknown_write_defaults_to_write_external():
    e = _entry("mcp-mysterious", "do_thing_xyz", read_only=False)
    # No plugin hint, no name substring -> conservative WRITE_EXTERNAL.
    assert categorize_skill(e) == SkillConsentCategory.WRITE_EXTERNAL


# ──────────────────────────────────────────────────────────────────
# 2. ConsentStore semantics
# ──────────────────────────────────────────────────────────────────


def test_store_grant_then_find_then_acknowledge():
    s = ConsentStore()
    g = s.grant(
        tenant_id=str(uuid.uuid4()),
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        category=SkillConsentCategory.PAYMENT,
    )
    found = s.find_active(
        tenant_id=g.tenant_id,
        plugin_id=g.plugin_id,
        skill_id=g.skill_id,
        category=g.category,
    )
    assert found is g
    consumed = s.acknowledge(g.grant_id)
    assert consumed is g
    assert g.consumed is True
    # Second find returns None (consumed).
    assert s.find_active(
        tenant_id=g.tenant_id, plugin_id=g.plugin_id,
        skill_id=g.skill_id, category=g.category,
    ) is None


def test_store_scope_mismatch_returns_none():
    s = ConsentStore()
    s.grant(
        tenant_id=str(uuid.uuid4()),
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        category=SkillConsentCategory.PAYMENT,
    )
    # Different skill -> no match.
    assert s.find_active(
        tenant_id=str(uuid.uuid4()),  # also different tenant
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        category=SkillConsentCategory.PAYMENT,
    ) is None


def test_store_ttl_clamped_to_max():
    s = ConsentStore()
    g = s.grant(
        tenant_id="t", plugin_id="p", skill_id="sk",
        category=SkillConsentCategory.WRITE_EXTERNAL,
        ttl_seconds=10**9,  # absurd
    )
    assert g.expires_at - g.granted_at <= MAX_GRANT_TTL_SECONDS + 1


def test_store_expired_grant_raises_on_acknowledge():
    s = ConsentStore()
    g = s.grant(
        tenant_id="t", plugin_id="p", skill_id="sk",
        category=SkillConsentCategory.WRITE_EXTERNAL,
        ttl_seconds=1,
    )
    # Force expiry by manipulating expires_at backward.
    g.expires_at = time.time() - 1
    with pytest.raises(SkillConsentExpired):
        s.acknowledge(g.grant_id)


def test_store_expired_grant_lazy_gc_via_find():
    s = ConsentStore()
    g = s.grant(
        tenant_id="t", plugin_id="p", skill_id="sk",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )
    g.expires_at = time.time() - 1
    found = s.find_active(
        tenant_id="t", plugin_id="p", skill_id="sk",
        category=SkillConsentCategory.WRITE_EXTERNAL,
    )
    assert found is None  # expired -> GC'd


# ──────────────────────────────────────────────────────────────────
# 3. check_consent_or_request flow
# ──────────────────────────────────────────────────────────────────


def test_check_returns_allowed_for_read_only():
    s = ConsentStore()
    e = _entry("app-gmail", "summarize_unread", read_only=True)
    allowed, category, request = check_consent_or_request(
        e, tenant_id=uuid.uuid4(), store=s,
    )
    assert allowed is True
    assert category is None
    assert request is None


def test_check_returns_request_when_consent_missing():
    s = ConsentStore()
    e = _entry("mcp-stripe", "process_payment", read_only=False)
    tenant_id = uuid.uuid4()
    allowed, category, request = check_consent_or_request(
        e, tenant_id=tenant_id, store=s,
    )
    assert allowed is False
    assert category == SkillConsentCategory.PAYMENT
    assert request is not None
    assert request.tenant_id == str(tenant_id)
    assert request.plugin_id == "mcp-stripe"
    assert request.skill_id == "process_payment"
    assert request.category == SkillConsentCategory.PAYMENT
    # Operator-facing summary mentions the category.
    assert "payment" in request.operator_facing_summary.lower()


def test_check_consumes_grant_when_present():
    s = ConsentStore()
    tenant_id = uuid.uuid4()
    e = _entry("mcp-stripe", "process_payment", read_only=False)
    s.grant(
        tenant_id=str(tenant_id),
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        category=SkillConsentCategory.PAYMENT,
    )

    allowed, category, request = check_consent_or_request(
        e, tenant_id=tenant_id, store=s,
    )
    assert allowed is True
    assert category == SkillConsentCategory.PAYMENT
    assert request is None
    # Single-use semantics: a second call needs fresh consent.
    allowed2, _, request2 = check_consent_or_request(
        e, tenant_id=tenant_id, store=s,
    )
    assert allowed2 is False
    assert request2 is not None


# ──────────────────────────────────────────────────────────────────
# 4. PII / leak defense
# ──────────────────────────────────────────────────────────────────


def test_request_carries_no_operator_input_or_token():
    """Defense in depth: SkillConsentRequest fields are pinned to
    the (plugin, skill, category) tuple + UUID + timestamp. No
    operator-input value should ever leak in."""
    fields = set(SkillConsentRequest.__dataclass_fields__.keys())
    forbidden = {"access_token", "refresh_token", "operator_inputs", "secret"}
    assert fields & forbidden == set()


def test_grant_carries_no_token_field():
    fields = set(SkillConsentGrant.__dataclass_fields__.keys())
    forbidden = {"access_token", "refresh_token", "secret", "bearer"}
    assert fields & forbidden == set()


# ──────────────────────────────────────────────────────────────────
# 5. Foundation invariant: no Phase 2 skill currently triggers consent
# ──────────────────────────────────────────────────────────────────


def test_no_phase2_skill_currently_requires_consent():
    """Founder rule: today every Phase 2 allowlist entry is read_only=
    True so the consent gate is dormant. If a future PR adds a
    write skill it MUST also wire the consent flow OR explicitly
    document the opt-out (audit-logged). This invariant fails on
    the silent-write-skill scenario."""
    triggered = [
        e for e in PHASE2_ALLOWLIST
        if categorize_skill(e) is not None
    ]
    assert triggered == [], (
        f"These Phase 2 entries trigger the consent gate; either "
        f"they should stay read_only=True or wire the consent flow "
        f"explicitly: {[(e.plugin_id, e.skill_id) for e in triggered]}"
    )


# ──────────────────────────────────────────────────────────────────
# 6. End-to-end: SkillExecutor + synthetic write entry
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant_user(db_session: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id, name=f"Cons {tenant_id.hex[:6]}",
        slug=f"cons-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@cons.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    return tenant_id, user_id


@pytest.mark.asyncio
async def test_executor_blocks_synthetic_write_without_consent(
    db_session, seeded_tenant_user, monkeypatch,
):
    """Inject a synthetic write entry via get_allowlist_entry monkeypatch
    so the executor reaches the consent gate. With no grant the
    outcome is needs_consent / consent_required."""
    tenant_id, user_id = seeded_tenant_user
    synth = _entry("mcp-stripe", "process_payment", read_only=False)
    monkeypatch.setattr(
        "app.services.connection_v2.skill_executor.get_allowlist_entry",
        lambda p, s: synth,
    )
    store = ConsentStore()
    executor = SkillExecutor(db_session, consent_store=store)

    result = await executor.execute(
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={},
    )
    assert result.status == "needs_consent"
    assert result.blocked_reason == "consent_required"


@pytest.mark.asyncio
async def test_executor_consumes_consent_then_hits_phase2_defense(
    db_session, seeded_tenant_user, monkeypatch,
):
    """Synthetic write entry + matching grant -> consent gate consumes
    the grant (proves the layer is wired) -> then the Phase 2
    read_only defense blocks (proves the layer is FOUNDATION ONLY
    and Phase 2 is still safe). This is the invariant that lets us
    ship the consent gate without enabling any write today."""
    tenant_id, user_id = seeded_tenant_user
    synth = _entry("mcp-stripe", "process_payment", read_only=False)
    monkeypatch.setattr(
        "app.services.connection_v2.skill_executor.get_allowlist_entry",
        lambda p, s: synth,
    )
    store = ConsentStore()
    g = store.grant(
        tenant_id=str(tenant_id),
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        category=SkillConsentCategory.PAYMENT,
    )
    executor = SkillExecutor(db_session, consent_store=store)

    result = await executor.execute(
        plugin_id="mcp-stripe",
        skill_id="process_payment",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={},
    )
    # The consent gate consumed the grant...
    assert g.consumed is True
    # ...but the Phase 2 read_only defense blocks anyway.
    assert result.status == "blocked"
    assert result.blocked_reason == "not_read_only"


@pytest.mark.asyncio
async def test_executor_read_only_skill_does_not_consult_consent_store(
    db_session, seeded_tenant_user, monkeypatch,
):
    """Defense: a read_only=True skill MUST NOT consult the consent
    store. Categorization returns None and the gate is skipped.
    Verify by injecting a store whose .find_active raises -- the
    real entry runs cleanly through to its planned outcome."""
    tenant_id, user_id = seeded_tenant_user

    class ExplodingStore(ConsentStore):
        def find_active(self, **_):
            raise AssertionError(
                "find_active should NOT be called for a read_only=True skill"
            )

    executor = SkillExecutor(db_session, consent_store=ExplodingStore())

    # mcp-postgres:describe_schema is read_only=True, planned_only,
    # AND has a callable V2 row check. We bypass the V2 check by
    # monkeypatching _is_plugin_callable to True.
    async def fake_callable(**_):
        return True

    monkeypatch.setattr(executor, "_is_plugin_callable", fake_callable)

    result = await executor.execute(
        plugin_id="mcp-postgres",
        skill_id="describe_schema",
        tenant_id=tenant_id,
        user_id=user_id,
        operator_inputs={"database": "test"},
    )
    # Reaches the planned-only path; consent store NEVER consulted.
    assert result.status == "planned"


@pytest.mark.asyncio
async def test_executor_passes_consent_store_through_init(db_session):
    """The executor accepts a consent_store kwarg for test isolation."""
    custom = ConsentStore()
    executor = SkillExecutor(db_session, consent_store=custom)
    assert executor._consent_store is custom


@pytest.mark.asyncio
async def test_executor_uses_default_store_when_none_passed(db_session):
    from app.services.connection_v2.skill_consent import get_default_store
    executor = SkillExecutor(db_session)
    assert executor._consent_store is get_default_store()
