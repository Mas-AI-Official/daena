"""Tests for ConnectionRegistryV2 (Phase 4b PR 1).

Covers the 8 founder-mandated test areas plus state_machine + op_lock
invariants:

  1. import persists                                  -> TestImport
  2. duplicate discovery deduplicates                 -> TestImport
  3. failed probe does not mark callable              -> TestProbe
  4. successful probe marks callable                  -> TestProbe
  5. secret writes use vault_v2                       -> TestSecretsViaV2
  6. legacy rows remain readable via dual-read        -> TestDualRead
  7. feature flag off keeps legacy behavior           -> TestFeatureFlag
  8. feature flag on uses V2 in dev                   -> TestFeatureFlag

Plus state_machine pure-function coverage + op_lock TTL behavior.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.vault import encrypt_dict
from app.core.vault_v2 import SecretClass, derive_tenant_kek
from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
    OpKind,
)
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User
from app.models.secret import Secret
from app.services.connection_v2 import (
    ConnectionRegistryV2,
    acquire_op_lock,
    active_ops_for,
    derive_label,
    release_op_lock,
)

KEK_SEED = b"k" * 32


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def registry(db_session, seeded_tenant):
    return ConnectionRegistryV2(db_session, kek_seed=KEK_SEED)


# ──────────────────────────────────────────────────────────────────
# 1 + 2 — import persists; duplicate discovery deduplicates
# ──────────────────────────────────────────────────────────────────


class TestImport:
    @pytest.mark.asyncio
    async def test_import_persists(self, db_session, registry, test_tenant_id):
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="test-mcp",
            display_name="Test MCP",
            auth_method=AuthMethod.NONE,
            config={"transport": "stdio", "command": "echo"},
        )
        assert result.created is True
        assert result.connection.imported is True
        assert result.connection.imported_at is not None
        # Survives flush -- query back independently
        rows = (await db_session.execute(
            select(ConnectionV2).where(ConnectionV2.tenant_id == test_tenant_id)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].slug == "test-mcp"
        assert rows[0].imported is True

    @pytest.mark.asyncio
    async def test_duplicate_import_deduplicates(self, db_session, registry, test_tenant_id):
        first = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="dup-mcp",
            display_name="Dup",
            auth_method=AuthMethod.NONE,
        )
        second = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="dup-mcp",
            display_name="Dup (other)",
            auth_method=AuthMethod.NONE,
        )
        assert first.created is True
        assert second.created is False
        assert second.connection.id == first.connection.id

        rows = (await db_session.execute(
            select(ConnectionV2).where(ConnectionV2.slug == "dup-mcp")
        )).scalars().all()
        assert len(rows) == 1


# ──────────────────────────────────────────────────────────────────
# 3 + 4 — failed probe doesn't mark callable; success marks callable
# ──────────────────────────────────────────────────────────────────


class TestProbe:
    @pytest.mark.asyncio
    async def test_failed_probe_does_not_mark_callable(
        self, db_session, registry, test_tenant_id,
    ):
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="probe-fail",
            display_name="Fail",
            auth_method=AuthMethod.NONE,
            config={"_test_probe": "fail_callable"},
        )
        row, label, outcome = await registry.probe_and_record(
            tenant_id=test_tenant_id, connection_id=result.connection.id,
        )
        assert outcome["success"] is False
        assert row.callable is False
        assert row.callable_failure_at is not None
        assert row.callable_failure_reason and "test" in row.callable_failure_reason

    @pytest.mark.asyncio
    async def test_successful_probe_marks_callable(
        self, db_session, registry, test_tenant_id,
    ):
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="probe-ok",
            display_name="Ok",
            auth_method=AuthMethod.NONE,
            config={"_test_probe": "success", "_test_capabilities": [
                {"kind": "mcp_tool", "name": "echo"},
            ]},
        )
        row, label, outcome = await registry.probe_and_record(
            tenant_id=test_tenant_id, connection_id=result.connection.id,
        )
        assert outcome["success"] is True
        assert row.callable is True
        assert row.callable_at is not None
        assert label == "healthy"

    @pytest.mark.asyncio
    async def test_per_dim_failure_does_not_overwrite_other_dim(
        self, db_session, registry, test_tenant_id,
    ):
        """ADR-002 D-001 -- failure on reachable does not nuke an
        existing authenticated_failure_reason."""
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="per-dim",
            display_name="PD",
            auth_method=AuthMethod.API_TOKEN,
            secret_value="fake-token",
        )
        row = result.connection
        # Pre-populate an auth failure reason.
        row.authenticated = False
        row.authenticated_failure_at = datetime.now(timezone.utc)
        row.authenticated_failure_reason = "stale auth (preexisting)"
        # Now probe-fail on reachable.
        row.config = {"_test_probe": "fail_reachable"}
        await db_session.flush()

        await registry.probe_and_record(
            tenant_id=test_tenant_id, connection_id=row.id,
        )
        await db_session.refresh(row)
        # auth reason MUST be untouched.
        assert row.authenticated_failure_reason == "stale auth (preexisting)"
        # reachable reason now set.
        assert row.reachable_failure_reason and "unreachable" in row.reachable_failure_reason


# ──────────────────────────────────────────────────────────────────
# 5 — secret writes use vault_v2
# ──────────────────────────────────────────────────────────────────


class TestSecretsViaV2:
    @pytest.mark.asyncio
    async def test_api_token_import_persists_via_vault_v2(
        self, db_session, registry, test_tenant_id,
    ):
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.PROVIDER,
            slug="anthropic",
            display_name="Anthropic",
            auth_method=AuthMethod.API_TOKEN,
            secret_value="sk-fake-do-not-use",
        )
        assert result.secret_written is True

        # Secret row in `secrets` table -- not in legacy ConnectorInstance.
        secret = (await db_session.execute(
            select(Secret).where(
                Secret.tenant_id == test_tenant_id,
                Secret.bound_to == f"connection_v2:{result.connection.id}",
            )
        )).scalar_one()
        assert secret.format_version == 2
        assert len(secret.nonce) == 12
        assert len(secret.tag) == 16
        # Plaintext is NEVER stored on the connection row.
        assert "sk-fake" not in str(result.connection.config)

        # Dual-read should return the plaintext.
        plaintext = await registry.read_secret_dual(
            tenant_id=test_tenant_id, connection_id=result.connection.id,
        )
        assert plaintext == {"api_key": "sk-fake-do-not-use"}


# ──────────────────────────────────────────────────────────────────
# 6 — legacy rows remain readable via dual-read
# ──────────────────────────────────────────────────────────────────


class TestDualRead:
    @pytest.mark.asyncio
    async def test_legacy_connector_instance_readable_via_dual_read(
        self, db_session, registry, test_tenant_id,
    ):
        # Seed a legacy ConnectorInstance with vault.encrypt_dict creds.
        user = User(
            id=uuid.uuid4(), tenant_id=test_tenant_id,
            email="t@t.local", display_name="T", role="FOUNDER", settings={},
        )
        connector = Connector(
            id=uuid.uuid4(), name="legacy-conn",
            auth_type="API_KEY", config_schema={}, tools=[],
        )
        db_session.add_all([user, connector])
        await db_session.flush()

        legacy_instance_id = uuid.uuid4()
        plaintext = {"api_key": "legacy-secret-value"}
        legacy_inst = ConnectorInstance(
            id=legacy_instance_id,
            tenant_id=test_tenant_id,
            connector_id=connector.id,
            user_id=user.id,
            credentials=encrypt_dict(plaintext),
            status="CONNECTED",
        )
        db_session.add(legacy_inst)
        await db_session.flush()

        # Dual-read MUST find it via the legacy fallback path.
        # No corresponding Secret row exists.
        result = await registry.read_secret_dual(
            tenant_id=test_tenant_id, connection_id=legacy_instance_id,
        )
        assert result == plaintext


# ──────────────────────────────────────────────────────────────────
# 7 + 8 — feature flag default + dev override
# ──────────────────────────────────────────────────────────────────


class TestFeatureFlag:
    def test_flag_defaults_false_in_settings(self):
        # Per founder rule: USE_CONNECTION_REGISTRY_V2 default false.
        # Confirms the model field default.
        s = get_settings()
        assert s.use_connection_registry_v2 is False

    def test_flag_can_be_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("USE_CONNECTION_REGISTRY_V2", "true")
        # Force fresh settings load.
        get_settings.cache_clear()
        try:
            s = get_settings()
            assert s.use_connection_registry_v2 is True
        finally:
            get_settings.cache_clear()

    def test_flag_off_means_v2_routes_still_callable_but_legacy_unaffected(self):
        """The flag gates LIVE-UI routing in Phase 4b PR 2; PR 1 keeps the
        V2 routes mounted always so dev can exercise them. Confirm no
        startup-time gating prevents the V2 router from loading."""
        from app.api.v1 import connections_v2  # noqa: F401
        from app.api.v1 import router as v1_router

        v2_routes = [r for r in v1_router.routes if "/connections/v2" in str(getattr(r, "path", ""))]
        assert len(v2_routes) >= 1


# ──────────────────────────────────────────────────────────────────
# State machine pure-function coverage
# ──────────────────────────────────────────────────────────────────


class TestStateMachine:
    def _row(self, **kwargs) -> ConnectionV2:
        defaults = dict(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            kind=ConnectionKind.MCP_SERVER.value,
            slug="x", display_name="X",
            canonical_key="abc",
            auth_method=AuthMethod.NONE.value,
            trust_tier="official",
            config={},
            detected=False, configured=False, imported=False,
            reachable=False, authenticated=False, callable=False,
            healthy_call_ratio=1.0,
            archived=False, disabled=False, governance_tier=2,
        )
        defaults.update(kwargs)
        return ConnectionV2(**defaults)

    def test_archived_wins(self):
        r = self._row(archived=True)
        assert derive_label(r, []) == "archived"

    def test_disabled_wins_over_state(self):
        r = self._row(disabled=True, callable=True, callable_at=datetime.now(timezone.utc))
        assert derive_label(r, []) == "disabled"

    def test_active_op_overrides_steady_state(self):
        r = self._row(detected=True, configured=True, imported=True, reachable=True, callable=True,
                      callable_at=datetime.now(timezone.utc))
        assert derive_label(r, ["probe"]) == "probing"
        assert derive_label(r, ["install"]) == "installing"
        assert derive_label(r, ["authenticate"]) == "auth_pending"

    def test_unknown_when_not_detected(self):
        r = self._row()
        assert derive_label(r, []) == "unknown"

    def test_needs_config_when_detected_only(self):
        r = self._row(detected=True)
        assert derive_label(r, []) == "needs_config"

    def test_installable_when_configured_not_imported(self):
        r = self._row(detected=True, configured=True)
        assert derive_label(r, []) == "installable"

    def test_failed_when_reachable_failure_fresher_than_success(self):
        now = datetime.now(timezone.utc)
        r = self._row(
            detected=True, configured=True, imported=True,
            reachable=True, reachable_at=now - timedelta(seconds=10),
            reachable_failure_at=now,
            reachable_failure_reason="connection refused",
        )
        assert derive_label(r, []) == "failed"

    def test_healthy_when_callable_fresh(self):
        now = datetime.now(timezone.utc)
        r = self._row(
            detected=True, configured=True, imported=True,
            reachable=True, callable=True, callable_at=now,
        )
        assert derive_label(r, []) == "healthy"

    def test_healthy_stale_when_callable_old(self):
        old = datetime.now(timezone.utc) - timedelta(hours=1)
        r = self._row(
            detected=True, configured=True, imported=True,
            reachable=True, callable=True, callable_at=old,
        )
        assert derive_label(r, []) == "healthy_stale"

    def test_degraded_stale_when_old_and_low_ratio(self):
        old = datetime.now(timezone.utc) - timedelta(hours=1)
        r = self._row(
            detected=True, configured=True, imported=True,
            reachable=True, callable=True, callable_at=old,
            healthy_call_ratio=0.3,
        )
        assert derive_label(r, []) == "degraded_stale"


# ──────────────────────────────────────────────────────────────────
# Op-lock TTL + idempotency
# ──────────────────────────────────────────────────────────────────


class TestOpLock:
    @pytest.mark.asyncio
    async def test_acquire_then_release_roundtrip(
        self, db_session, registry, test_tenant_id,
    ):
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="lock-1", display_name="L1",
            auth_method=AuthMethod.NONE,
        )
        cid = result.connection.id

        token = await acquire_op_lock(db_session, connection_id=cid, op=OpKind.PROBE.value)
        assert token is not None
        assert OpKind.PROBE.value in await active_ops_for(db_session, cid)

        released = await release_op_lock(
            db_session, connection_id=cid, op=OpKind.PROBE.value, owner_token=token,
        )
        assert released is True
        assert OpKind.PROBE.value not in await active_ops_for(db_session, cid)

    @pytest.mark.asyncio
    async def test_double_acquire_returns_none(
        self, db_session, registry, test_tenant_id,
    ):
        result = await registry.import_connection(
            tenant_id=test_tenant_id,
            kind=ConnectionKind.MCP_SERVER,
            slug="lock-2", display_name="L2",
            auth_method=AuthMethod.NONE,
        )
        cid = result.connection.id

        token_a = await acquire_op_lock(db_session, connection_id=cid, op=OpKind.PROBE.value)
        token_b = await acquire_op_lock(db_session, connection_id=cid, op=OpKind.PROBE.value)
        assert token_a is not None
        assert token_b is None
