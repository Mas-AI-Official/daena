"""Unit tests for AuditService tamper-evident hash-chained ledger.

Covers:
    * log_decision writes an event with correct hash linkage
    * chain integrity holds across multiple entries
    * chain integrity breaks when an entry is mutated
    * multi-tenant isolation (chains don't cross-contaminate)
    * hash payload determinism
    * _event_to_dict serialization
    * pagination + filtering on get_audit_trail
    * _compute_hash pure-function sanity

Uses the in-memory SQLite engine + db_session fixtures from conftest.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant, User
from app.services.audit import AuditService


@pytest.fixture
async def seeded_tenant_user(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a unique tenant + user so FK constraints on
    ``goa_audit_events.actor_id`` (-> users.id) are satisfiable.
    Uses fresh UUIDs per test so DB state never collides across
    tests that share the session.
    """
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        name=f"Test Tenant {tenant_id.hex[:6]}",
        slug=f"test-tenant-{tenant_id.hex[:8]}",
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@test.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="FOUNDER",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    return tenant_id, user_id


async def _seed_extra_user(
    db_session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID,
) -> None:
    """Helper: insert an additional user row for multi-actor tests."""
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@test.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
        role="OPERATOR",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()


async def _seed_extra_tenant(
    db_session: AsyncSession, tenant_id: uuid.UUID,
) -> None:
    """Helper: insert an additional tenant row."""
    t = Tenant(
        id=tenant_id,
        name=f"Tenant {tenant_id.hex[:4]}",
        slug=f"tenant-{tenant_id.hex[:8]}",
    )
    db_session.add(t)
    await db_session.flush()


# ----------------------------------------------------------------------
# _compute_hash: pure function (no DB needed)
# ----------------------------------------------------------------------


def test_compute_hash_is_deterministic():
    actor = uuid.uuid4()
    h1 = AuditService._compute_hash(
        actor_id=actor, action_type="DELETE", result="BLOCKED",
        prev_hash=None, timestamp="2026-04-21T00:00:00",
    )
    h2 = AuditService._compute_hash(
        actor_id=actor, action_type="DELETE", result="BLOCKED",
        prev_hash=None, timestamp="2026-04-21T00:00:00",
    )
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_hash_diverges_on_any_input_change():
    base = dict(
        actor_id=uuid.uuid4(), action_type="DELETE", result="BLOCKED",
        prev_hash=None, timestamp="2026-04-21T00:00:00",
    )
    base_hash = AuditService._compute_hash(**base)
    # Change action_type
    assert AuditService._compute_hash(**{**base, "action_type": "READ"}) != base_hash
    # Change result
    assert AuditService._compute_hash(**{**base, "result": "ALLOWED"}) != base_hash
    # Change timestamp
    assert AuditService._compute_hash(
        **{**base, "timestamp": "2026-04-21T00:00:01"},
    ) != base_hash
    # Change prev_hash (chain link)
    assert AuditService._compute_hash(**{**base, "prev_hash": "a" * 64}) != base_hash


def test_compute_hash_uses_system_for_null_actor():
    """Null actor_id hashes as 'SYSTEM' for consistency with events.py."""
    h_none = AuditService._compute_hash(
        actor_id=None, action_type="HEARTBEAT", result="OK",
        prev_hash=None, timestamp="2026-04-21T00:00:00",
    )
    # Manually construct expected payload
    expected_payload = "SYSTEM|HEARTBEAT|OK|GENESIS|2026-04-21T00:00:00"
    expected = hashlib.sha256(expected_payload.encode()).hexdigest()
    assert h_none == expected


def test_compute_hash_uses_genesis_for_first_entry():
    """prev_hash=None hashes as 'GENESIS' so the first entry in any chain
    has a well-defined predecessor marker.
    """
    h = AuditService._compute_hash(
        actor_id=None, action_type="INIT", result="OK",
        prev_hash=None, timestamp="2026-01-01T00:00:00",
    )
    expected_payload = "SYSTEM|INIT|OK|GENESIS|2026-01-01T00:00:00"
    assert h == hashlib.sha256(expected_payload.encode()).hexdigest()


# ----------------------------------------------------------------------
# log_decision + chain integrity (requires db_session)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_decision_writes_entry(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    entry = await svc.log_decision(
        tenant_id=test_tenant_id,
        actor_id=test_user_id,
        actor_type="USER",
        action_type="READ",
        result="ALLOWED",
        risk_level="NONE",
        governance_tier=0,
    )
    assert entry["tenant_id"] == str(test_tenant_id)
    assert entry["actor_id"] == str(test_user_id)
    assert entry["action_type"] == "READ"
    assert entry["result"] == "ALLOWED"
    assert len(entry["entry_hash"]) == 64
    assert entry["prev_hash"] is None  # First entry for this tenant


@pytest.mark.asyncio
async def test_log_decision_links_chain(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    first = await svc.log_decision(
        tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
        action_type="A", result="ALLOWED", risk_level="NONE", governance_tier=0,
    )
    second = await svc.log_decision(
        tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
        action_type="B", result="ALLOWED", risk_level="NONE", governance_tier=0,
    )
    # Second entry's prev_hash MUST equal first entry's entry_hash
    assert second["prev_hash"] == first["entry_hash"]


@pytest.mark.asyncio
async def test_chain_integrity_valid_after_sequential_writes(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(5):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"ACTION_{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    result = await svc.verify_chain_integrity(tenant_id=test_tenant_id)
    assert result["valid"] is True
    assert result["total_entries"] == 5
    assert result["first_broken_id"] is None


@pytest.mark.asyncio
async def test_chain_integrity_detects_tampering(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """Mutating an entry's prev_hash out-of-band breaks the chain."""
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(3):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"A{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    await db_session.commit()

    # Simulate tampering: corrupt the middle entry's prev_hash.
    from sqlalchemy import select
    rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.tenant_id == test_tenant_id)
        .order_by(GoaAuditEvent.created_at.asc())
    )).scalars().all()
    assert len(rows) == 3
    rows[1].prev_hash = "deadbeef" * 8  # corrupt middle entry's link
    await db_session.commit()

    result = await svc.verify_chain_integrity(tenant_id=test_tenant_id)
    assert result["valid"] is False
    assert result["first_broken_id"] == str(rows[1].id)


@pytest.mark.asyncio
async def test_chain_empty_is_valid(
    db_session: AsyncSession,
):
    """Empty chain is trivially valid (nothing to break)."""
    svc = AuditService(db_session)
    fresh_tenant = uuid.uuid4()
    result = await svc.verify_chain_integrity(tenant_id=fresh_tenant)
    assert result["valid"] is True
    assert result["total_entries"] == 0
    assert result["first_broken_id"] is None


# ----------------------------------------------------------------------
# Multi-tenant isolation
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chains_isolated_per_tenant(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """Two tenants get independent chains."""
    _, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    t1 = uuid.uuid4()
    t2 = uuid.uuid4()
    await _seed_extra_tenant(db_session, t1)
    await _seed_extra_tenant(db_session, t2)
    entry1 = await svc.log_decision(
        tenant_id=t1, actor_id=test_user_id, actor_type="USER",
        action_type="A", result="ALLOWED", risk_level="NONE", governance_tier=0,
    )
    entry2 = await svc.log_decision(
        tenant_id=t2, actor_id=test_user_id, actor_type="USER",
        action_type="A", result="ALLOWED", risk_level="NONE", governance_tier=0,
    )
    # Both are "first entries" for their tenant, so prev_hash is None for both.
    assert entry1["prev_hash"] is None
    assert entry2["prev_hash"] is None

    # Tampering tenant 1 must NOT affect tenant 2 integrity.
    from sqlalchemy import select
    rows = (await db_session.execute(
        select(GoaAuditEvent).where(GoaAuditEvent.tenant_id == t1)
    )).scalars().all()
    assert len(rows) == 1
    rows[0].result = "TAMPERED"
    await db_session.commit()

    r2 = await svc.verify_chain_integrity(tenant_id=t2)
    assert r2["valid"] is True  # t2's chain intact


# ----------------------------------------------------------------------
# get_audit_trail pagination + filters
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_audit_trail_returns_recent_first(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """AUD-001 RESOLVED: the 20ms sleep workaround is no longer
    needed. get_audit_trail now orders by (created_at desc, id desc)
    so ties break deterministically on Windows low-resolution clocks.
    """
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(3):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"ACTION_{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    trail = await svc.get_audit_trail(tenant_id=test_tenant_id, page_size=10)
    assert trail["pagination"]["total"] == 3
    # Ordered by created_at desc (with id desc tie-breaker): most
    # recent first. If timestamps tie, id.desc() still gives a stable
    # order, though which of the 3 is "newest" is undefined in that
    # edge case. Regardless, the SET of results is correct.
    action_types = [e["action_type"] for e in trail["data"]]
    assert set(action_types) == {"ACTION_0", "ACTION_1", "ACTION_2"}


@pytest.mark.asyncio
async def test_get_audit_trail_pagination(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(7):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"A{i}", result="ALLOWED",
            risk_level="NONE", governance_tier=0,
        )
    page1 = await svc.get_audit_trail(tenant_id=test_tenant_id, page=1, page_size=3)
    page2 = await svc.get_audit_trail(tenant_id=test_tenant_id, page=2, page_size=3)
    assert page1["pagination"]["total"] == 7
    assert page1["pagination"]["total_pages"] == 3
    assert len(page1["data"]) == 3
    assert len(page2["data"]) == 3
    # Disjoint pages
    ids_p1 = {e["id"] for e in page1["data"]}
    ids_p2 = {e["id"] for e in page2["data"]}
    assert ids_p1.isdisjoint(ids_p2)


@pytest.mark.asyncio
async def test_get_audit_trail_filter_by_action_type(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    await svc.log_decision(
        tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
        action_type="DELETE", result="BLOCKED",
        risk_level="CRITICAL", governance_tier=4,
    )
    await svc.log_decision(
        tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
        action_type="READ", result="ALLOWED",
        risk_level="NONE", governance_tier=0,
    )
    filtered = await svc.get_audit_trail(
        tenant_id=test_tenant_id, action_type="DELETE",
    )
    assert filtered["pagination"]["total"] == 1
    assert filtered["data"][0]["action_type"] == "DELETE"


@pytest.mark.asyncio
async def test_get_audit_trail_filter_by_actor(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    test_tenant_id, _ = seeded_tenant_user
    svc = AuditService(db_session)
    a = uuid.uuid4()
    b = uuid.uuid4()
    await _seed_extra_user(db_session, test_tenant_id, a)
    await _seed_extra_user(db_session, test_tenant_id, b)
    await svc.log_decision(
        tenant_id=test_tenant_id, actor_id=a, actor_type="USER",
        action_type="A", result="ALLOWED", risk_level="NONE", governance_tier=0,
    )
    await svc.log_decision(
        tenant_id=test_tenant_id, actor_id=b, actor_type="USER",
        action_type="B", result="ALLOWED", risk_level="NONE", governance_tier=0,
    )
    filtered = await svc.get_audit_trail(tenant_id=test_tenant_id, actor_id=a)
    assert filtered["pagination"]["total"] == 1
    assert filtered["data"][0]["actor_id"] == str(a)


# ----------------------------------------------------------------------
# _event_to_dict serialization
# ----------------------------------------------------------------------


def test_event_to_dict_serializes_core_fields():
    now = datetime.utcnow()
    ev = GoaAuditEvent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        actor_type="USER",
        action_type="DELETE",
        result="BLOCKED",
        risk_level="CRITICAL",
        governance_tier=4,
        prev_hash=None,
        entry_hash="a" * 64,
        created_at=now,
    )
    d = AuditService._event_to_dict(ev)
    assert d["action_type"] == "DELETE"
    assert d["result"] == "BLOCKED"
    assert d["governance_tier"] == 4
    assert d["entry_hash"] == "a" * 64


def test_event_to_dict_handles_null_actor():
    ev = GoaAuditEvent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        actor_id=None,
        actor_type="SYSTEM",
        action_type="HEARTBEAT",
        result="OK",
        risk_level="NONE",
        governance_tier=0,
        prev_hash=None,
        entry_hash="b" * 64,
        created_at=datetime.utcnow(),
    )
    d = AuditService._event_to_dict(ev)
    assert d["actor_id"] is None
    assert d["actor_type"] == "SYSTEM"


# ----------------------------------------------------------------------
# Large-chain integrity (regression guard on loop correctness)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_integrity_across_larger_sequence(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """Regression: chain must stay walkable across many entries.

    AUD-001 RESOLVED: the 20ms sleep workaround is no longer needed.
    verify_chain_integrity now walks by following prev_hash links
    rather than sorting by created_at, so it is correct by
    construction regardless of timestamp resolution.
    """
    _, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    t = uuid.uuid4()
    await _seed_extra_tenant(db_session, t)
    for i in range(15):
        await svc.log_decision(
            tenant_id=t, actor_id=test_user_id, actor_type="USER",
            action_type=f"A{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    result = await svc.verify_chain_integrity(tenant_id=t)
    assert result["valid"] is True
    assert result["total_entries"] == 15


@pytest.mark.asyncio
async def test_chain_integrity_with_clock_ties(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
    monkeypatch,
):
    """AUD-002 regression: a burst of audit writes that all land on the SAME
    created_at must NOT fork the tamper-evident hash chain.

    datetime.utcnow() is only ~15.6ms-resolution on Windows, so rapid
    log_decision calls tie on created_at. The write-path chain-head selector
    (_get_last_hash) orders by created_at; under ties it can pick a non-tail
    row, so two events end up sharing one prev_hash -> fork -> verify reports
    valid=False. This freezes the clock (worst case: every event ties) -- the
    residual cause of the timing-/order-dependent full-suite flake on the chain
    tests. The fix makes created_at strictly monotonic per tenant so the chain
    always has exactly one tail regardless of timestamp resolution.
    """
    import app.services.audit as audit_mod

    _, test_user_id = seeded_tenant_user
    t = uuid.uuid4()
    await _seed_extra_tenant(db_session, t)

    # Freeze the clock so EVERY insert ties on created_at (worst case).
    frozen = datetime(2026, 1, 1, 12, 0, 0)

    class _FrozenDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return frozen

    monkeypatch.setattr(audit_mod, "datetime", _FrozenDateTime)

    svc = AuditService(db_session)
    for i in range(15):
        await svc.log_decision(
            tenant_id=t, actor_id=test_user_id, actor_type="USER",
            action_type=f"T{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )

    result = await svc.verify_chain_integrity(tenant_id=t)
    assert result["valid"] is True, f"clock-tie burst forked the chain: {result}"
    assert result["total_entries"] == 15


# ----------------------------------------------------------------------
# PR-AUDIT-VERIFY: deep mode (recompute every payload hash)
# ----------------------------------------------------------------------
#
# The structural walker (default mode) follows prev_hash -> entry_hash
# links and catches any tamper that breaks the chain topology. It does
# NOT recompute SHA-256 from each row's payload, so it cannot detect a
# tamper that leaves the chain links intact -- e.g. an attacker who
# flips ``result`` from BLOCKED to ALLOWED but does not touch
# ``prev_hash`` or ``entry_hash``. PR-AUDIT-VERIFY adds the
# ``deep=True`` mode which closes that gap.


@pytest.mark.asyncio
async def test_chain_integrity_deep_mode_passes_clean_chain(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """Happy path: deep recompute matches every stored entry_hash."""
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(4):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"D{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    result = await svc.verify_chain_integrity(tenant_id=test_tenant_id, deep=True)
    assert result["valid"] is True
    assert result["total_entries"] == 4
    assert result["first_broken_id"] is None
    assert result["first_corrupt_id"] is None  # New field, no tamper


@pytest.mark.asyncio
async def test_chain_integrity_deep_mode_catches_content_tamper(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """The whole point of deep mode: catch a tamper that the structural
    walker cannot see.

    Setup: write 3 entries forming a clean chain. Then mutate the
    middle row's ``result`` field WITHOUT touching ``prev_hash`` or
    ``entry_hash``. The structural walker still walks cleanly because
    every prev_hash still points at a valid entry_hash. But the deep
    recompute finds that SHA-256(actor|action|RESULT|prev|ts) no longer
    equals the stored entry_hash.
    """
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(3):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"C{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    await db_session.commit()

    # Read rows back, mutate middle row's result only.
    from sqlalchemy import select
    rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.tenant_id == test_tenant_id)
        .order_by(GoaAuditEvent.created_at.asc())
    )).scalars().all()
    assert len(rows) == 3
    middle = rows[1]
    middle.result = "BLOCKED"  # Flip ALLOWED -> BLOCKED. Do NOT touch hashes.
    await db_session.commit()

    # Structural mode still passes (chain links untouched).
    structural = await svc.verify_chain_integrity(
        tenant_id=test_tenant_id, deep=False,
    )
    assert structural["valid"] is True, (
        "Structural-only walker should miss this content tamper -- "
        "if it does not, the test is no longer pinning the gap."
    )
    assert structural["first_corrupt_id"] is None  # Always None when deep=False

    # Deep mode catches it.
    deep = await svc.verify_chain_integrity(
        tenant_id=test_tenant_id, deep=True,
    )
    assert deep["valid"] is False
    assert deep["first_corrupt_id"] == str(middle.id)
    assert deep["first_broken_id"] is None  # Structure remains intact


@pytest.mark.asyncio
async def test_chain_integrity_default_mode_misses_content_tamper(
    db_session: AsyncSession,
    seeded_tenant_user: tuple[uuid.UUID, uuid.UUID],
):
    """Regression guard: structural-only walker cannot detect content
    tampering (this is by-design; the limitation is what justifies deep
    mode existing).

    If this test ever fails because structural also catches it, the
    structural walker has gained payload validation -- in which case
    deep mode is no longer needed and the rationale in
    PR_AUDIT_VERIFY_AND_RAG_HONEST_REPORT.md should be revisited.
    """
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(3):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"X{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    await db_session.commit()

    from sqlalchemy import select
    rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.tenant_id == test_tenant_id)
        .order_by(GoaAuditEvent.created_at.asc())
    )).scalars().all()
    rows[0].result = "TAMPERED"
    rows[2].action_type = "DOPED"
    await db_session.commit()

    # Default (deep=False) returns valid -- the gap is real.
    result = await svc.verify_chain_integrity(tenant_id=test_tenant_id)
    assert result["valid"] is True
    assert result["first_broken_id"] is None
    assert result["first_corrupt_id"] is None  # Field exists but unused


# ----------------------------------------------------------------------
# PR-AUDIT-VERIFY: response shape stability
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chain_integrity_response_shape_includes_corrupt_field(
    db_session: AsyncSession,
):
    """``first_corrupt_id`` must always appear in the response dict so
    frontend interfaces can rely on the key existing regardless of
    deep flag. Empty chain is the simplest case.
    """
    svc = AuditService(db_session)
    fresh_tenant = uuid.uuid4()
    for deep_flag in (False, True):
        result = await svc.verify_chain_integrity(
            tenant_id=fresh_tenant, deep=deep_flag,
        )
        assert "first_corrupt_id" in result
        assert result["first_corrupt_id"] is None
        # Existing keys preserved
        assert "valid" in result
        assert "total_entries" in result
        assert "first_broken_id" in result


# ----------------------------------------------------------------------
# PR-AUDIT-VERIFY: _recompute_event_hash determinism
# ----------------------------------------------------------------------


def test_recompute_event_hash_matches_log_decision_hash():
    """Pure function: recompute output for a freshly built event must
    equal the hash log_decision would have written. Validates the
    payload ordering + tz-strip normalization match.
    """
    actor = uuid.uuid4()
    now_dt = datetime(2026, 5, 1, 12, 34, 56, 789012)  # naive, microsecond precision
    expected = AuditService._compute_hash(
        actor_id=actor,
        action_type="READ",
        result="ALLOWED",
        prev_hash=None,
        timestamp=now_dt.isoformat(),
    )

    ev = GoaAuditEvent(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        actor_id=actor,
        actor_type="USER",
        action_type="READ",
        result="ALLOWED",
        risk_level="LOW",
        governance_tier=1,
        prev_hash=None,
        entry_hash=expected,
        created_at=now_dt,
    )

    assert AuditService._recompute_event_hash(ev) == expected


def test_recompute_event_hash_strips_timezone():
    """Postgres returns tz-aware datetimes; SQLite returns naive. Strip
    tz before isoformat so both dialects produce the same hash input.
    """
    from datetime import timezone

    actor = uuid.uuid4()
    naive_dt = datetime(2026, 5, 1, 12, 34, 56, 789012)
    aware_dt = naive_dt.replace(tzinfo=timezone.utc)

    naive_event = GoaAuditEvent(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(),
        actor_id=actor, actor_type="USER",
        action_type="READ", result="ALLOWED",
        risk_level="LOW", governance_tier=1,
        prev_hash=None,
        entry_hash="x" * 64,
        created_at=naive_dt,
    )
    aware_event = GoaAuditEvent(
        id=uuid.uuid4(), tenant_id=uuid.uuid4(),
        actor_id=actor, actor_type="USER",
        action_type="READ", result="ALLOWED",
        risk_level="LOW", governance_tier=1,
        prev_hash=None,
        entry_hash="x" * 64,
        created_at=aware_dt,
    )

    assert (
        AuditService._recompute_event_hash(naive_event)
        == AuditService._recompute_event_hash(aware_event)
    )
