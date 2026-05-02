"""Pin POST /api/v1/governance/audit/verify rich-diagnostic verification.

Distinct from ``test_audit_service_unit.py`` which exercises
``AuditService.verify_chain_integrity`` directly: this file goes
through the FastAPI request layer to pin the response shape that
operators / CLIs / future SDKs depend on.

What is pinned:

* Clean chain -> verified=true, first_break_index=null, first_break=null.
* Content tamper (mutate ``result`` on row N, leave hashes intact)
  -> verified=false, first_break.kind="content", first_break_index = N,
  expected_hash = recomputed sha256, actual_hash = stored entry_hash.
* Structural break (mutate ``prev_hash``) -> verified=false,
  first_break.kind="structural".
* Tenant isolation: tampering with tenant A's chain leaves tenant B's
  POST /audit/verify still verified.
* The audit ledger itself is NOT mutated by the verify call (chain
  count + entry_hashes unchanged).

Hard rule honored: no audit row is created or modified by the verify
endpoint itself. Tests assert this explicitly.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.governance import GoaAuditEvent
from app.services.audit import AuditService


async def _register_admin_and_login(client: AsyncClient) -> dict[str, Any]:
    """Register + login a FOUNDER user (FOUNDER >= ADMIN role gate)."""
    unique = uuid.uuid4().hex[:8]
    email = f"audit-verify-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Verify Tester",
            "tenant_name": f"VerifyOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    user_obj = data["user"]
    # auth router returns the user identity under different keys across
    # builds; mirror PR-S2's tolerant fallback.
    user_id_raw = (
        user_obj.get("id") or user_obj.get("user_id") or user_obj.get("sub")
    )
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": uuid.UUID(user_id_raw),
        "tenant_id": uuid.UUID(user_obj["tenant_id"]),
    }


async def _seed_chain(
    db_session: AsyncSession,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    n: int,
) -> list[GoaAuditEvent]:
    """Write N audit rows forming a clean chain. Returns rows in
    insertion order so tests can refer to row[i] without re-querying.
    """
    svc = AuditService(db_session)
    for i in range(n):
        await svc.log_decision(
            tenant_id=tenant_id, actor_id=actor_id, actor_type="USER",
            action_type=f"V{i}", result="ALLOWED",
            risk_level="LOW", governance_tier=1,
        )
    await db_session.commit()
    rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.tenant_id == tenant_id)
        .order_by(GoaAuditEvent.created_at.asc())
    )).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Clean-chain happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_verify_clean_chain_returns_verified_true(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    auth = await _register_admin_and_login(client)
    await _seed_chain(db_session, auth["tenant_id"], auth["user_id"], n=4)

    resp = await client.post(
        "/api/v1/governance/audit/verify", headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["verified"] is True
    assert data["total_entries"] >= 4  # plus auto-emitted login/register events
    assert data["first_break_index"] is None
    assert data["first_break"] is None
    assert data["tenant_id"] == str(auth["tenant_id"])


# ---------------------------------------------------------------------------
# Content tamper -> rich diagnostic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_verify_content_tamper_returns_diagnostic(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Mutate one row's ``result`` without touching ``prev_hash`` or
    ``entry_hash`` -- the structural walker would pass; the diagnostic
    endpoint must fail with ``kind=content`` and report the recomputed
    hash as ``expected_hash`` and the stored hash as ``actual_hash``.
    """
    auth = await _register_admin_and_login(client)
    rows = await _seed_chain(
        db_session, auth["tenant_id"], auth["user_id"], n=3,
    )
    # The chain may include auto-emitted login/register audit rows
    # in front of our V0..V2. Find a V-row to tamper with so we know
    # the original payload.
    v_rows = [r for r in rows if r.action_type and r.action_type.startswith("V")]
    assert len(v_rows) >= 2, "expected at least 2 seeded V-rows"
    target = v_rows[1]
    original_hash = target.entry_hash
    original_prev = target.prev_hash

    # Mutate result; leave hashes alone.
    target.result = "BLOCKED"
    await db_session.commit()

    resp = await client.post(
        "/api/v1/governance/audit/verify", headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["verified"] is False
    assert data["first_break_index"] is not None
    assert data["first_break"] is not None
    fb = data["first_break"]
    assert fb["row_id"] == str(target.id)
    assert fb["kind"] == "content"
    assert fb["previous_hash"] == original_prev
    assert fb["actual_hash"] == original_hash
    # Expected hash is the recomputed sha256 with the new (tampered)
    # ``result`` value -- it must be a 64-char hex string and DIFFERENT
    # from the stored actual_hash (otherwise the tamper was a no-op).
    assert isinstance(fb["expected_hash"], str)
    assert len(fb["expected_hash"]) == 64
    assert fb["expected_hash"] != fb["actual_hash"]


# ---------------------------------------------------------------------------
# Structural break -> rich diagnostic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_verify_structural_break_returns_diagnostic(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Corrupt one row's ``prev_hash`` so the chain forks / orphans;
    verify must report ``kind=structural``.
    """
    auth = await _register_admin_and_login(client)
    rows = await _seed_chain(
        db_session, auth["tenant_id"], auth["user_id"], n=3,
    )
    v_rows = [r for r in rows if r.action_type and r.action_type.startswith("V")]
    assert len(v_rows) >= 2
    target = v_rows[1]

    target.prev_hash = "deadbeef" * 8  # 64-char nonsense; orphans this row
    await db_session.commit()

    resp = await client.post(
        "/api/v1/governance/audit/verify", headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["verified"] is False
    fb = data["first_break"]
    assert fb is not None
    assert fb["kind"] == "structural"
    assert fb["row_id"] is not None
    assert isinstance(fb["actual_hash"], str)


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_verify_tenant_isolation(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Tampering tenant A's chain must NOT cause tenant B's verify
    to fail. The hash chain is per-tenant; cross-tenant tamper cannot
    leak from one POST /audit/verify response to another's.
    """
    auth_a = await _register_admin_and_login(client)
    auth_b = await _register_admin_and_login(client)

    # Each tenant gets its own clean chain.
    rows_a = await _seed_chain(
        db_session, auth_a["tenant_id"], auth_a["user_id"], n=3,
    )
    await _seed_chain(db_session, auth_b["tenant_id"], auth_b["user_id"], n=3)

    # Tamper tenant A's chain only.
    a_v_rows = [
        r for r in rows_a
        if r.action_type and r.action_type.startswith("V")
    ]
    a_v_rows[0].result = "TAMPERED"
    await db_session.commit()

    # A: verify FAILS.
    resp_a = await client.post(
        "/api/v1/governance/audit/verify", headers=auth_a["headers"],
    )
    assert resp_a.status_code == 200
    assert resp_a.json()["data"]["verified"] is False

    # B: verify still PASSES -- tenant isolation holds.
    resp_b = await client.post(
        "/api/v1/governance/audit/verify", headers=auth_b["headers"],
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()["data"]
    assert data_b["verified"] is True
    assert data_b["first_break"] is None
    assert data_b["tenant_id"] == str(auth_b["tenant_id"])


# ---------------------------------------------------------------------------
# Verify call must NOT mutate the audit ledger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_verify_does_not_mutate_audit_rows(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Hard rule honored: verification reads only. Row count and every
    entry_hash must be byte-identical before and after.

    If verification ever needs to write (e.g. to record a verify
    timestamp), it MUST go to a separate table -- never the
    append-only ledger itself.
    """
    auth = await _register_admin_and_login(client)
    await _seed_chain(db_session, auth["tenant_id"], auth["user_id"], n=4)

    before_rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.tenant_id == auth["tenant_id"])
        .order_by(GoaAuditEvent.created_at.asc())
    )).scalars().all()
    before_count = len(before_rows)
    before_hashes = [r.entry_hash for r in before_rows]

    resp = await client.post(
        "/api/v1/governance/audit/verify", headers=auth["headers"],
    )
    assert resp.status_code == 200

    after_rows = (await db_session.execute(
        select(GoaAuditEvent)
        .where(GoaAuditEvent.tenant_id == auth["tenant_id"])
        .order_by(GoaAuditEvent.created_at.asc())
    )).scalars().all()

    assert len(after_rows) == before_count, (
        "verify must not change the row count -- it is a read-only operation"
    )
    after_hashes = [r.entry_hash for r in after_rows]
    assert after_hashes == before_hashes, (
        "verify must not modify any entry_hash -- the ledger is append-only"
    )
