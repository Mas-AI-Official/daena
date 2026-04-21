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
    """See AUD-001: tiny sleep between writes forces strictly
    distinct created_at values on Windows low-resolution utcnow.
    """
    import asyncio as _asyncio
    test_tenant_id, test_user_id = seeded_tenant_user
    svc = AuditService(db_session)
    for i in range(3):
        await svc.log_decision(
            tenant_id=test_tenant_id, actor_id=test_user_id, actor_type="USER",
            action_type=f"ACTION_{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
        await _asyncio.sleep(0.02)
    trail = await svc.get_audit_trail(tenant_id=test_tenant_id, page_size=10)
    assert trail["pagination"]["total"] == 3
    # Ordered by created_at desc: most recent first.
    assert trail["data"][0]["action_type"] == "ACTION_2"
    assert trail["data"][-1]["action_type"] == "ACTION_0"


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

    Known issue AUD-001: Windows datetime.utcnow() has ~15.6ms
    resolution, so rapid successive log_decision() calls can land on
    identical created_at values. The verify_chain_integrity walk
    orders by created_at asc and can then yield a non-deterministic
    order when timestamps tie. A tiny explicit sleep between writes
    forces distinct timestamps until AUD-001 is fixed (add a
    tie-breaker sort by id or entry_hash in verify_chain_integrity).
    """
    import asyncio as _asyncio
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
        # See AUD-001 docstring above.
        await _asyncio.sleep(0.02)
    result = await svc.verify_chain_integrity(tenant_id=t)
    assert result["valid"] is True
    assert result["total_entries"] == 15
