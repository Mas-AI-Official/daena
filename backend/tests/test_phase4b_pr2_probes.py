"""Tests for Phase 4b PR 2: real runtime probes + legacy /connections/* swap.

Founder-mandated truth rules under test:
  1. binary-only adapter is not callable
  2. timeout adapter is not callable
  3. auth failure is not callable
  4. successful harmless round-trip is callable
  5. feature flag off keeps legacy route behavior
  6. feature flag on uses V2-derived status (D-010 bypass)
  7. _status_for_install no longer controls connected label under V2
  8. mcp_bridge rename does not break imports

Probe semantics:
  - detected != reachable
  - reachable != authenticated
  - authenticated != callable
  - CLI binary exists != online
  - MCP config exists != callable

All probes run with monkeypatched subprocess so tests stay
hermetic / fast / network-free.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.constants import ConnectorStatus
from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant
from app.services.connection_v2 import ConnectionRegistryV2
from app.services.connection_v2.legacy_bridge import (
    _kind_for_connector,
    _slug_for_instance,
    label_to_legacy_status,
)
from app.services.runtimes.base_adapter import RuntimeProbeResult


KEK_SEED = b"k" * 32

# ──────────────────────────────────────────────────────────────────
# Fakes for subprocess.run -- adapters call _run_cmd which calls
# subprocess.run. We patch the module-level _run_cmd to return a
# CompletedProcess directly.
# ──────────────────────────────────────────────────────────────────


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a fake subprocess.CompletedProcess result."""
    cp = subprocess.CompletedProcess(
        args=["fake"], returncode=returncode, stdout=stdout, stderr=stderr,
    )
    return cp


def _completed_factory(stdout: str = "", returncode: int = 0):
    """Factory for an async-callable that returns _completed()."""
    def _runner(cmd, *, cwd=None, timeout=60.0):
        return _completed(stdout=stdout, returncode=returncode)
    return _runner


def _timeout_runner(cmd, *, cwd=None, timeout=60.0):
    """Always raises TimeoutExpired -- simulates hung CLI."""
    raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)


# ──────────────────────────────────────────────────────────────────
# 1 + 2: claude_code probe truth rules
# ──────────────────────────────────────────────────────────────────


class TestClaudeCodeProbe:
    """Validate the rewritten claude_code probe respects all truth rules."""

    @pytest.fixture
    def adapter(self, monkeypatch):
        """Build adapter with binary path stubbed."""
        from app.services.runtimes.adapters import claude_code as cc

        # Stub _claude_bin to skip discovery + ClaudeSessionManager init
        with patch.object(
            cc.ClaudeCodeAdapter, "__init__", lambda self: None,
        ):
            instance = cc.ClaudeCodeAdapter()
            instance.runtime_id = "claude_code"
            instance.display_name = "Claude Code"
            instance._claude_bin = "/fake/claude"
            instance._session_manager = None
        return instance

    @pytest.mark.asyncio
    async def test_binary_only_is_not_callable(self, adapter, monkeypatch):
        """Rule 1: binary-only adapter is not callable.

        Even if --version succeeds AND auth is valid, callable=False
        when round-trip is not exercised. We simulate this by failing
        the round-trip (claude -p ping returns is_error=True).
        """
        from app.services.runtimes.adapters import claude_code as cc
        from app.services.runtimes.subscription_auth import (
            AuthMethod, SubscriptionAuth, SubscriptionStatus,
        )

        # binary exists, version OK, subscription OK, but round-trip errors
        def _runner(cmd, *, cwd=None, timeout=60.0):
            if "--version" in cmd:
                return _completed("claude 1.0", returncode=0)
            if "-p" in cmd:
                return _completed(
                    json.dumps({"is_error": True, "result": "auth failure"}),
                    returncode=0,
                )
            return _completed("", returncode=0)

        async def _fake_sub(self):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.AUTHENTICATED,
                user_display="test",
                plan_name="Claude Pro",
            )

        # Pretend file exists on disk.
        # _claude_bin is "/fake/claude" -- doesn't exist on disk -> isfile=False
        # -> probe falls through to --version check via _run_cmd.
        monkeypatch.setattr(cc, "_run_cmd", _runner)
        monkeypatch.setattr(
            cc.ClaudeCodeAdapter, "check_subscription", _fake_sub,
        )

        result = await adapter.probe()
        assert result.detected is True
        assert result.reachable is True
        assert result.authenticated is True
        assert result.callable is False
        assert result.failure_dim == "callable"

    @pytest.mark.asyncio
    async def test_timeout_is_not_callable(self, adapter, monkeypatch):
        """Rule 2: timeout in round-trip leaves callable=False."""
        from app.services.runtimes.adapters import claude_code as cc
        from app.services.runtimes.subscription_auth import (
            AuthMethod, SubscriptionAuth, SubscriptionStatus,
        )

        def _runner(cmd, *, cwd=None, timeout=60.0):
            if "--version" in cmd:
                return _completed("claude 1.0", returncode=0)
            # Round-trip times out.
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

        async def _fake_sub(self):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.AUTHENTICATED,
                user_display="test",
                plan_name="Claude Pro",
            )

        # _claude_bin is "/fake/claude" -- doesn't exist on disk -> isfile=False
        # -> probe falls through to --version check via _run_cmd.
        monkeypatch.setattr(cc, "_run_cmd", _runner)
        monkeypatch.setattr(
            cc.ClaudeCodeAdapter, "check_subscription", _fake_sub,
        )

        result = await adapter.probe()
        assert result.callable is False
        assert result.failure_dim == "callable"
        assert "timed out" in (result.failure_reason or "").lower()

    @pytest.mark.asyncio
    async def test_auth_failure_is_not_callable(self, adapter, monkeypatch):
        """Rule 3: auth failure means callable=False with failure_dim='authenticated'."""
        from app.services.runtimes.adapters import claude_code as cc
        from app.services.runtimes.subscription_auth import (
            AuthMethod, SubscriptionAuth, SubscriptionStatus,
        )

        def _runner(cmd, *, cwd=None, timeout=60.0):
            return _completed("claude 1.0", returncode=0)

        async def _fake_sub(self):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.NOT_AUTHENTICATED,
                detail="not logged in",
            )

        # _claude_bin is "/fake/claude" -- doesn't exist on disk -> isfile=False
        # -> probe falls through to --version check via _run_cmd.
        monkeypatch.setattr(cc, "_run_cmd", _runner)
        monkeypatch.setattr(
            cc.ClaudeCodeAdapter, "check_subscription", _fake_sub,
        )

        result = await adapter.probe()
        assert result.detected is True
        assert result.reachable is True
        assert result.authenticated is False
        assert result.callable is False
        assert result.failure_dim == "authenticated"

    @pytest.mark.asyncio
    async def test_successful_round_trip_is_callable(self, adapter, monkeypatch):
        """Rule 4: full success ladder flips callable=True."""
        from app.services.runtimes.adapters import claude_code as cc
        from app.services.runtimes.subscription_auth import (
            AuthMethod, SubscriptionAuth, SubscriptionStatus,
        )

        def _runner(cmd, *, cwd=None, timeout=60.0):
            if "--version" in cmd:
                return _completed("claude 1.0", returncode=0)
            if "-p" in cmd:
                return _completed(
                    json.dumps({"is_error": False, "result": "pong"}),
                    returncode=0,
                )
            return _completed("", returncode=0)

        async def _fake_sub(self):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.AUTHENTICATED,
                user_display="test",
                plan_name="Claude Max",
            )

        # _claude_bin is "/fake/claude" -- doesn't exist on disk -> isfile=False
        # -> probe falls through to --version check via _run_cmd.
        monkeypatch.setattr(cc, "_run_cmd", _runner)
        monkeypatch.setattr(
            cc.ClaudeCodeAdapter, "check_subscription", _fake_sub,
        )

        result = await adapter.probe()
        assert result.detected is True
        assert result.reachable is True
        assert result.authenticated is True
        assert result.callable is True
        assert result.failure_dim is None
        assert result.failure_reason is None
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_binary_missing_dim_detected(self, adapter, monkeypatch):
        """No binary -> detected=False -> callable=False."""
        from app.services.runtimes.adapters import claude_code as cc

        # Set _claude_bin to literal "claude" (PATH-only path).
        # Then _run_cmd returns rc=127 (not found) -> detected stays False.
        adapter._claude_bin = "claude"

        def _runner(cmd, *, cwd=None, timeout=60.0):
            return _completed("", returncode=127)

        monkeypatch.setattr(cc, "_run_cmd", _runner)

        result = await adapter.probe()
        assert result.detected is False
        assert result.callable is False
        assert result.failure_dim == "detected"


# ──────────────────────────────────────────────────────────────────
# Codex probe (smoke-level coverage of the same truth ladder)
# ──────────────────────────────────────────────────────────────────


class TestCodexProbe:
    @pytest.fixture
    def adapter(self):
        from app.services.runtimes.adapters import codex as cx

        with patch.object(cx.CodexAdapter, "__init__", lambda self: None):
            instance = cx.CodexAdapter()
            instance.runtime_id = "codex"
            instance.display_name = "Codex (OpenAI)"
            instance._codex_bin = "/fake/codex"
        return instance

    @pytest.mark.asyncio
    async def test_codex_callable_on_round_trip_success(self, adapter, monkeypatch):
        from app.services.runtimes.adapters import codex as cx
        from app.services.runtimes.subscription_auth import (
            AuthMethod, SubscriptionAuth, SubscriptionStatus,
        )

        def _runner(cmd, *, cwd=None, timeout=60.0):
            if "--version" in cmd:
                return _completed("codex 0.1", returncode=0)
            if "exec" in cmd:
                return _completed("pong\n", returncode=0)
            return _completed("", returncode=0)

        async def _fake_sub(self):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.AUTHENTICATED,
                plan_name="ChatGPT Plus",
            )

        # _codex_bin is "/fake/codex" -- doesn't exist -> falls through to --version.
        monkeypatch.setattr(cx, "_run_cmd", _runner)
        monkeypatch.setattr(cx.CodexAdapter, "check_subscription", _fake_sub)

        result = await adapter.probe()
        assert result.callable is True
        assert result.failure_dim is None

    @pytest.mark.asyncio
    async def test_codex_empty_round_trip_not_callable(self, adapter, monkeypatch):
        from app.services.runtimes.adapters import codex as cx
        from app.services.runtimes.subscription_auth import (
            AuthMethod, SubscriptionAuth, SubscriptionStatus,
        )

        def _runner(cmd, *, cwd=None, timeout=60.0):
            if "--version" in cmd:
                return _completed("codex 0.1", returncode=0)
            return _completed("", returncode=0)  # empty stdout

        async def _fake_sub(self):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.AUTHENTICATED,
                plan_name="ChatGPT Plus",
            )

        # _codex_bin is "/fake/codex" -- doesn't exist -> falls through to --version.
        monkeypatch.setattr(cx, "_run_cmd", _runner)
        monkeypatch.setattr(cx.CodexAdapter, "check_subscription", _fake_sub)

        result = await adapter.probe()
        assert result.callable is False
        assert result.failure_dim == "callable"


# ──────────────────────────────────────────────────────────────────
# Gemini CLI probe -- exercises hang-then-timeout dim
# ──────────────────────────────────────────────────────────────────


class TestGeminiCLIProbe:
    @pytest.fixture
    def adapter(self):
        from app.services.runtimes.adapters import gemini_cli as gc

        # GeminiCLIAdapter.__init__ is light; just call it.
        return gc.GeminiCLIAdapter()

    @pytest.mark.asyncio
    async def test_gemini_no_binary(self, adapter, monkeypatch):
        from app.services.runtimes.adapters import gemini_cli as gc

        monkeypatch.setattr(gc.shutil, "which", lambda name: None)
        result = await adapter.probe()
        assert result.detected is False
        assert result.failure_dim == "detected"
        assert result.callable is False

    @pytest.mark.asyncio
    async def test_gemini_version_hang_unreachable(self, adapter, monkeypatch):
        from app.services.runtimes.adapters import gemini_cli as gc

        monkeypatch.setattr(gc.shutil, "which", lambda name: "/usr/bin/gemini")
        monkeypatch.setattr(gc, "_run_cmd", _timeout_runner)

        result = await adapter.probe()
        assert result.detected is True
        assert result.reachable is False
        assert result.failure_dim == "reachable"
        assert "hung" in (result.failure_reason or "").lower()


# ──────────────────────────────────────────────────────────────────
# MCP bridge probe -- HTTP path
# ──────────────────────────────────────────────────────────────────


class TestMCPBridgeProbe:
    @pytest.mark.asyncio
    async def test_mcp_no_transport_is_misconfigured(self):
        from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import (
            MCPBridgeAdapter,
        )

        adapter = MCPBridgeAdapter("orphan")  # no command, no url
        result = await adapter.probe()
        assert result.detected is False
        assert result.configured is False
        assert result.failure_dim == "configured"
        assert result.callable is False

    @pytest.mark.asyncio
    async def test_mcp_http_full_handshake_success(self, monkeypatch):
        from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import (
            MCPBridgeAdapter,
        )

        adapter = MCPBridgeAdapter(
            "test_http", url="http://localhost:9999",
        )

        # Build a fake httpx.AsyncClient context manager
        class _FakeResp:
            def __init__(self, status_code: int, payload: dict | None = None):
                self.status_code = status_code
                self._payload = payload or {}
                self.text = json.dumps(self._payload)

            def json(self) -> dict:
                return self._payload

        class _FakeClient:
            def __init__(self, *a, **k):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                return _FakeResp(200)
            async def post(self, url, json=None):
                if json["method"] == "initialize":
                    return _FakeResp(200, {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "result": {
                            "serverInfo": {"name": "test", "version": "1.0"},
                            "protocolVersion": "2024-11-05",
                        },
                    })
                if json["method"] == "tools/list":
                    return _FakeResp(200, {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "result": {
                            "tools": [
                                {"name": "echo", "description": "echoes back"},
                            ],
                        },
                    })
                return _FakeResp(404)

        import httpx as _httpx
        monkeypatch.setattr(_httpx, "AsyncClient", _FakeClient)

        result = await adapter.probe()
        assert result.detected is True
        assert result.reachable is True
        assert result.authenticated is True
        assert result.callable is True
        assert result.failure_dim is None
        # Capability discovered.
        assert any(c.get("name") == "echo" for c in result.capabilities)

    @pytest.mark.asyncio
    async def test_mcp_http_initialize_error_means_unauthenticated(self, monkeypatch):
        from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import (
            MCPBridgeAdapter,
        )

        adapter = MCPBridgeAdapter(
            "test_http", url="http://localhost:9999",
        )

        class _FakeResp:
            def __init__(self, status_code: int, payload: dict | None = None):
                self.status_code = status_code
                self._payload = payload or {}
                self.text = json.dumps(self._payload)
            def json(self):
                return self._payload

        class _FakeClient:
            def __init__(self, *a, **k):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                return _FakeResp(200)
            async def post(self, url, json=None):
                if json["method"] == "initialize":
                    return _FakeResp(200, {
                        "jsonrpc": "2.0", "id": 1,
                        "error": {"code": -32001, "message": "missing API key"},
                    })
                return _FakeResp(404)

        import httpx as _httpx
        monkeypatch.setattr(_httpx, "AsyncClient", _FakeClient)

        result = await adapter.probe()
        assert result.reachable is True
        assert result.authenticated is False
        assert result.callable is False
        assert result.failure_dim == "authenticated"


# ──────────────────────────────────────────────────────────────────
# Rule 8: mcp_bridge rename does not break imports
# ──────────────────────────────────────────────────────────────────


class TestMCPBridgeRenameCompatibility:
    def test_old_path_still_resolves_to_class(self):
        """Both import paths resolve to the same class."""
        from app.services.runtimes.adapters.mcp_bridge import (
            MCPBridgeAdapter as Old,
        )
        from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import (
            MCPBridgeAdapter as New,
        )
        assert Old is New

    def test_runtime_registry_loads_with_renamed_path(self):
        """Adapters package re-exports the class from the new path."""
        from app.services.runtimes.adapters import MCPBridgeAdapter
        from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import (
            MCPBridgeAdapter as Canonical,
        )
        assert MCPBridgeAdapter is Canonical


# ──────────────────────────────────────────────────────────────────
# Rules 5 + 6 + 7: legacy /connections/* feature flag swap
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session):
    """Per-test tenant with a unique id.

    We DO NOT use the shared ``test_tenant_id`` from conftest because
    ``service.install`` / ``service.connect`` commit (bypassing the
    per-test session rollback), leaving residue that collides with
    other test files (e.g. test_connection_v2.py also uses
    ``test_tenant_id``). Per-test unique id eliminates that bleed.
    """
    tid = uuid.uuid4()
    tenant = Tenant(
        id=tid, name="T", slug=f"t-pr2-{uuid.uuid4().hex[:8]}",
        settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
async def seeded_user(db_session, seeded_tenant):
    """Concrete user row so ConnectorInstance.user_id FK resolves."""
    from app.models.identity import User

    user = User(
        id=uuid.uuid4(),
        tenant_id=seeded_tenant.id,
        email=f"test-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="FOUNDER",
        settings={},
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def seeded_connector_no_auth(db_session, seeded_tenant):
    """Per-test connector row -- name must be unique across the session."""
    conn = Connector(
        id=uuid.uuid4(),
        name=f"TestNoAuth-{uuid.uuid4().hex[:8]}",
        description="no-auth connector for tests",
        auth_type="none",
        config_schema={"callable_without_auth": True},
        tools=[],
        category="test",
    )
    db_session.add(conn)
    await db_session.flush()
    return conn


@pytest.fixture
async def seeded_connector_apikey(db_session, seeded_tenant):
    """Per-test API_KEY connector row -- unique name across the session."""
    conn = Connector(
        id=uuid.uuid4(),
        name=f"TestApiKey-{uuid.uuid4().hex[:8]}",
        description="api-key connector for tests",
        auth_type="API_KEY",
        config_schema={},
        tools=[],
        category="test",
    )
    db_session.add(conn)
    await db_session.flush()
    return conn


class TestLegacyFlagSwap:
    """Rule 5 + 6 + 7: feature flag swap on /connections/* legacy routes."""

    @pytest.mark.asyncio
    async def test_flag_off_uses_legacy_status_for_install(
        self, db_session, seeded_tenant, seeded_user, seeded_connector_apikey, monkeypatch,
    ):
        """Rule 5: flag off -> _status_for_install drives status (legacy)."""
        from app.services.connection_service import ConnectionService
        from app.services.connection_v2 import legacy_bridge

        # Force flag off.
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: False)

        service = ConnectionService(db_session)
        result = await service.install(
            connector_id=seeded_connector_apikey.id,
            user_id=seeded_user.id,
            tenant_id=seeded_tenant.id,
        )
        # Legacy: API_KEY connector with no creds -> INSTALLED.
        assert result["status"] == ConnectorStatus.INSTALLED.value

        # And NO V2 row got mirrored (flag off).
        rows = (await db_session.execute(
            select(ConnectionV2).where(ConnectionV2.tenant_id == seeded_tenant.id)
        )).scalars().all()
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_flag_on_mirrors_to_v2_and_overrides_status(
        self, db_session, seeded_tenant, seeded_user, seeded_connector_apikey, monkeypatch,
    ):
        """Rule 6 + 7: flag on -> V2 row written, status from V2 derived label.

        For an API_KEY connector that's been imported but NEVER probed,
        the V2 truth dims are: detected=T, configured=T, imported=T,
        reachable=F, authenticated=F, callable=F. derive_label maps
        that to 'failed' (per ADR-002 -- never-probed counts as no
        proof) -> legacy ERROR.

        Critically: legacy ``_status_for_install`` would have returned
        INSTALLED. The bypass is what we're asserting -- V2 truth wins.
        """
        from app.services.connection_service import ConnectionService
        from app.services.connection_v2 import legacy_bridge

        # Force flag on.
        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)

        service = ConnectionService(db_session)
        result = await service.install(
            connector_id=seeded_connector_apikey.id,
            user_id=seeded_user.id,
            tenant_id=seeded_tenant.id,
        )
        # V2 row created.
        rows = (await db_session.execute(
            select(ConnectionV2).where(ConnectionV2.tenant_id == seeded_tenant.id)
        )).scalars().all()
        assert len(rows) == 1
        v2_row = rows[0]
        assert v2_row.kind == ConnectionKind.PROVIDER.value
        assert v2_row.auth_method == V2AuthMethod.API_TOKEN.value
        assert v2_row.imported is True
        # No probe yet -> reachable=False -> derive_label='failed' -> ERROR.
        # Critically: NOT 'INSTALLED' (which is what _status_for_install would say).
        assert result["status"] == ConnectorStatus.ERROR.value

    @pytest.mark.asyncio
    async def test_flag_on_status_for_install_no_longer_drives_label(
        self, db_session, seeded_tenant, seeded_user, seeded_connector_apikey, monkeypatch,
    ):
        """Rule 7: when V2 is on, _status_for_install heuristic does NOT decide.

        Even if we PASS credentials (which would normally trigger
        _status_for_install -> CONNECTED), the V2 path returns
        ERROR because no probe has flipped reachable/callable yet.

        This is the canonical "imported != callable" assertion.
        """
        from app.services.connection_service import ConnectionService
        from app.services.connection_v2 import legacy_bridge

        monkeypatch.setattr(legacy_bridge, "is_v2_enabled", lambda: True)

        service = ConnectionService(db_session)
        result = await service.connect(
            connector_id=seeded_connector_apikey.id,
            user_id=seeded_user.id,
            tenant_id=seeded_tenant.id,
            credentials={"api_key": "fake-test-key"},
        )
        # _status_for_install with credentials would return 'CONNECTED'.
        # V2 path returns ERROR because the V2 row was just imported and
        # never probed -- detected=T but reachable/callable=F.
        # The presence of a credential is NOT proof of working anymore.
        assert result["status"] == ConnectorStatus.ERROR.value


# ──────────────────────────────────────────────────────────────────
# Bridge helper coverage
# ──────────────────────────────────────────────────────────────────


class TestBridgeHelpers:
    def test_kind_for_connector_oauth(self, monkeypatch):
        c = Connector(name="Gmail", auth_type="OAUTH2")
        assert _kind_for_connector(c) == ConnectionKind.OAUTH_APP

    def test_kind_for_connector_api_key(self):
        c = Connector(name="Stripe", auth_type="API_KEY")
        assert _kind_for_connector(c) == ConnectionKind.PROVIDER

    def test_kind_for_connector_none(self):
        c = Connector(name="Demo", auth_type="none")
        assert _kind_for_connector(c) == ConnectionKind.PLUGIN

    def test_slug_for_instance_is_stable(self):
        c = Connector(name="My Connector", auth_type="API_KEY")
        uid = uuid.UUID("12345678-1234-5678-1234-567812345678")
        slug = _slug_for_instance(c, uid)
        # Same input -> same slug.
        assert slug == _slug_for_instance(c, uid)
        # Lowercased + dashed.
        assert "my-connector" in slug
        # Includes user prefix for uniqueness.
        assert "12345678" in slug

    def test_label_to_legacy_status_full_map(self):
        # Healthy variants -> CONNECTED.
        for label in ("healthy", "healthy_stale", "degraded", "degraded_stale", "probing"):
            assert label_to_legacy_status(label) == ConnectorStatus.CONNECTED.value
        # Auth variants -> NEEDS_REAUTH.
        for label in ("needs_auth", "auth_pending"):
            assert label_to_legacy_status(label) == ConnectorStatus.NEEDS_REAUTH.value
        # Pre-install variants -> INSTALLED.
        for label in ("installable", "needs_config", "installing"):
            assert label_to_legacy_status(label) == ConnectorStatus.INSTALLED.value
        # Failed states -> ERROR.
        for label in ("failed", "unknown"):
            assert label_to_legacy_status(label) == ConnectorStatus.ERROR.value
        # Disabled / archived -> DISCONNECTED.
        for label in ("disabled", "archived"):
            assert label_to_legacy_status(label) == ConnectorStatus.DISCONNECTED.value

    def test_label_to_legacy_status_unknown_label_defaults_installed(self):
        assert (
            label_to_legacy_status("totally-unknown-label")
            == ConnectorStatus.INSTALLED.value
        )


# ──────────────────────────────────────────────────────────────────
# Default probe coverage on BaseRuntimeAdapter
# ──────────────────────────────────────────────────────────────────


class TestBaseAdapterDefaultProbe:
    @pytest.mark.asyncio
    async def test_default_probe_honest_about_undetected(self):
        from app.services.runtimes.base_adapter import (
            BaseRuntimeAdapter, RuntimeStatus, RuntimeCapability,
        )

        class _Stub(BaseRuntimeAdapter):
            async def check_installed(self):
                return False
            async def check_health(self):
                return RuntimeStatus.NOT_INSTALLED
            async def get_capabilities(self):
                return RuntimeCapability()
            async def execute(self, task, ctx):
                yield ""
            async def cancel(self, sid):
                return False
            def get_auth_requirements(self):
                return {}

        result = await _Stub("stub", "Stub").probe()
        assert result.detected is False
        assert result.callable is False
        assert result.failure_dim == "detected"

    @pytest.mark.asyncio
    async def test_default_probe_does_not_lie_about_callable(self):
        """Even if check_installed=True, default probe DOES NOT mark callable=True."""
        from app.services.runtimes.base_adapter import (
            BaseRuntimeAdapter, RuntimeStatus, RuntimeCapability,
        )

        class _Stub(BaseRuntimeAdapter):
            async def check_installed(self):
                return True
            async def check_health(self):
                return RuntimeStatus.ONLINE
            async def get_capabilities(self):
                return RuntimeCapability()
            async def execute(self, task, ctx):
                yield ""
            async def cancel(self, sid):
                return False
            def get_auth_requirements(self):
                return {}

        result = await _Stub("stub", "Stub").probe()
        assert result.detected is True
        # Default probe is conservative: callable stays False without a real round-trip.
        assert result.callable is False
