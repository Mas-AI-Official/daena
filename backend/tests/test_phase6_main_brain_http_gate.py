"""Phase 6 tests: HTTP-level Main Brain V2 gate + audit hook.

This replaces the unit-level coverage in
test_phase5_main_brain_callable_gate.py with real HTTP requests
that exercise the route end-to-end through the test client. Made
possible by the Phase 6 refactor of set_primary_runtime to take
``db: AsyncSession = Depends(get_db)`` so the test SQLite session
is reachable.

Founder-mandated coverage:
  1. Cannot select non-callable CLI runtime when V2 flag on
  2. Can select callable CLI runtime when V2 flag on
  3. Cannot select non-callable provider when V2 flag on (Phase 6)
  4. Can select callable provider when V2 flag on (Phase 6)
  5. Flag off preserves legacy behavior (no V2 check)
  6. experimental_override pins non-callable AND writes formal audit event
  7. Selection persists in User.settings.primary_runtime
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.models.governance import GoaAuditEvent
from app.models.identity import Tenant, User
from app.services.connection_v2 import legacy_bridge


@pytest.fixture
async def seeded(db_session):
    tid = uuid.uuid4()
    tenant = Tenant(
        id=tid, name="P6", slug=f"p6-{uuid.uuid4().hex[:8]}", settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(),
        tenant_id=tid,
        email=f"p6-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="FOUNDER",
        settings={},
    )
    db_session.add(user)
    await db_session.flush()
    return {"tenant": tenant, "user": user}


async def _make_v2(
    db_session, *, tenant_id, kind: ConnectionKind, slug: str, callable_: bool,
    auth_method: V2AuthMethod = V2AuthMethod.SUBSCRIPTION,
):
    now = datetime.now(timezone.utc)
    row = ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        kind=kind.value,
        slug=slug,
        display_name=slug.replace("_", " ").title(),
        canonical_key=f"k-{uuid.uuid4().hex[:16]}",
        auth_method=auth_method.value,
        trust_tier="official",
        config={},
        detected=True, detected_at=now,
        configured=True, configured_at=now,
        imported=True, imported_at=now,
        reachable=callable_, reachable_at=now if callable_ else None,
        authenticated=callable_, authenticated_at=now if callable_ else None,
        callable=callable_, callable_at=now if callable_ else None,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _headers(user: User) -> dict[str, str]:
    from app.services.auth import create_access_token
    token = create_access_token(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        role=user.role,
    )
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────
# CLI runtime path
# ──────────────────────────────────────────────────────────────────


class TestCliRuntimeGateHttp:
    @pytest.mark.asyncio
    async def test_cannot_select_non_callable_cli_runtime(
        self, db_session, client, seeded, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.CLI_RUNTIME, slug="claude_code",
            callable_=False,
        )
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "claude_code"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "runtime_not_callable"
        assert body["error"]["v2_kind"] == "cli_runtime"

    @pytest.mark.asyncio
    async def test_can_select_callable_cli_runtime(
        self, db_session, client, seeded, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.CLI_RUNTIME, slug="claude_code",
            callable_=True,
        )
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "claude_code"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["v2_gate_applied"] is True
        assert body["data"]["primary_runtime"] == "claude_code"


# ──────────────────────────────────────────────────────────────────
# Provider path (Phase 6 extension)
# ──────────────────────────────────────────────────────────────────


class TestProviderGateHttp:
    @pytest.mark.asyncio
    async def test_cannot_select_non_callable_provider(
        self, db_session, client, seeded, monkeypatch,
    ):
        # ANTHROPIC API key required for legacy validation; populate it.
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "anthropic_api_key", "sk-test", raising=False)
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.PROVIDER, slug="anthropic",
            callable_=False,
            auth_method=V2AuthMethod.API_TOKEN,
        )
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "ANTHROPIC"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "runtime_not_callable"
        assert body["error"]["v2_kind"] == "provider"

    @pytest.mark.asyncio
    async def test_can_select_callable_provider(
        self, db_session, client, seeded, monkeypatch,
    ):
        from app.core.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "openai_api_key", "sk-test", raising=False)
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.PROVIDER, slug="openai",
            callable_=True,
            auth_method=V2AuthMethod.API_TOKEN,
        )
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "OPENAI"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["primary_runtime"] == "OPENAI"
        assert body["data"]["v2_gate_applied"] is True


# ──────────────────────────────────────────────────────────────────
# Flag-off + override + audit
# ──────────────────────────────────────────────────────────────────


class TestFlagOffAndOverride:
    @pytest.mark.asyncio
    async def test_flag_off_skips_v2_gate_entirely(
        self, db_session, client, seeded, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: False)
        # No V2 row -- legacy behavior accepts.
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "claude_code"},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["v2_gate_applied"] is False

    @pytest.mark.asyncio
    async def test_experimental_override_writes_audit_event(
        self, db_session, client, seeded, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.CLI_RUNTIME, slug="claude_code",
            callable_=False,
        )
        headers = await _headers(seeded["user"])

        # Snapshot audit count before.
        before = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == seeded["tenant"].id,
                GoaAuditEvent.action_type == "audit.runtime.primary_override",
            )
        )).scalars().all()
        assert len(before) == 0

        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "claude_code", "experimental_override": True},
            headers=headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["experimental_override_used"] is True

        # Audit row was written.
        after = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == seeded["tenant"].id,
                GoaAuditEvent.action_type == "audit.runtime.primary_override",
            )
        )).scalars().all()
        assert len(after) == 1
        ev = after[0]
        assert ev.actor_id == seeded["user"].id
        assert ev.actor_type == "FOUNDER"
        assert ev.result == "OVERRIDE_GRANTED"
        assert ev.risk_level == "HIGH"
        assert ev.governance_tier == 3
        # Action params include the runtime_id but no plaintext secret.
        assert ev.action_params["runtime_id"] == "claude_code"
        assert ev.action_params["v2_kind"] == "cli_runtime"
        assert ev.action_params["v2_truth"]["callable"] is False

    @pytest.mark.asyncio
    async def test_normal_select_does_not_write_audit_event(
        self, db_session, client, seeded, monkeypatch,
    ):
        """Audit hook only fires on override path. Sanity check."""
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.CLI_RUNTIME, slug="claude_code",
            callable_=True,
        )
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "claude_code"},
            headers=headers,
        )
        assert resp.json()["success"] is True

        rows = (await db_session.execute(
            select(GoaAuditEvent).where(
                GoaAuditEvent.tenant_id == seeded["tenant"].id,
                GoaAuditEvent.action_type == "audit.runtime.primary_override",
            )
        )).scalars().all()
        assert len(rows) == 0


# ──────────────────────────────────────────────────────────────────
# Persistence
# ──────────────────────────────────────────────────────────────────


class TestPersistence:
    @pytest.mark.asyncio
    async def test_selection_persists_to_user_settings(
        self, db_session, client, seeded, monkeypatch,
    ):
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)
        await _make_v2(
            db_session, tenant_id=seeded["tenant"].id,
            kind=ConnectionKind.CLI_RUNTIME, slug="ollama",
            callable_=True,
        )
        headers = await _headers(seeded["user"])
        resp = await client.put(
            "/api/v1/runtimes/primary",
            json={"runtime_id": "ollama"},
            headers=headers,
        )
        assert resp.json()["success"] is True

        # Refresh the user row -- the route committed via Depends(get_db)
        # which is the same session as our fixture, so the change is
        # already visible.
        await db_session.refresh(seeded["user"])
        assert seeded["user"].settings.get("primary_runtime") == "ollama"
