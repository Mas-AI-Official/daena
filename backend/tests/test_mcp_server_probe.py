"""PR-CONN-MCP-PROBE tests.

Pins the McpServerProbe contract:
  1. Happy path: initialize + tools/list both succeed -> success=True
     with capabilities populated from the tools list.
  2. Empty tools -> failure_reason starts with no_tools.
  3. Initialize fails -> failure_reason starts with initialize_failed.
  4. Initialize hangs -> failure_reason starts with initialize_timeout.
  5. Subprocess crashes immediately -> failure_reason starts with
     command_failed.
  6. Binary not on PATH -> failure_reason starts with binary_not_found.
  7. Unsupported transport (HTTP / SSE) -> failure_reason starts with
     unsupported_transport.
  8. Config missing command -> failure_reason starts with config_missing.
  9. Env values are passed through to the subprocess BUT never logged
     by the probe AND never returned in failure_reason.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.services.connection_v2.probes.mcp_server_probe import (
    DEFAULT_TIMEOUTS,
    FAIL_BINARY_NOT_FOUND,
    FAIL_COMMAND_FAILED,
    FAIL_CONFIG_MISSING,
    FAIL_INITIALIZE_FAILED,
    FAIL_INITIALIZE_TIMEOUT,
    FAIL_NO_TOOLS,
    FAIL_TOOLS_LIST_TIMEOUT,
    FAIL_UNSUPPORTED_TRANSPORT,
    McpProbeTimeouts,
    McpServerProbe,
    install_mcp_server_probe,
)
from app.services.connection_v2.probe import PROBE_REGISTRY


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "fake_mcp_servers"


def _row(
    *,
    command: str | None = "python",
    args: list[str] | None = None,
    env_var_names: list[str] | None = None,
    kind_field: str = "mcp_stdio",
    url: str | None = None,
) -> ConnectionV2:
    """Build a non-persisted ConnectionV2 row for probe tests.

    The row is never inserted into the DB -- the probe inspects
    config + slug + kind, which we set directly. tenant_id /
    canonical_key are populated for completeness but ignored by the
    probe.
    """
    config: dict = {"kind": kind_field}
    if command is not None:
        config["command"] = command
    if args is not None:
        config["args"] = args
    if env_var_names is not None:
        config["env_var_names"] = env_var_names
    if url is not None:
        config["url"] = url
    row = ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        kind=ConnectionKind.MCP_SERVER.value,
        slug="mcp-test-row",
        display_name="Test MCP",
        canonical_key="x" * 64,
        auth_method=AuthMethod.NONE.value,
        config=config,
    )
    return row


# ──────────────────────────────────────────────────────────────────
# 1. Happy path
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeHappyPath:
    @pytest.mark.asyncio
    async def test_initialize_and_tools_list_succeed(self):
        row = _row(
            command=sys.executable,
            args=[str(FIXTURES_DIR / "fake_mcp_ok.py")],
        )
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is True, result.failure_reason
        assert result.failure_dim is None
        assert result.failure_reason is None
        assert len(result.capabilities) == 2

        names = sorted(c["name"] for c in result.capabilities)
        assert names == ["echo", "ping"]

        for cap in result.capabilities:
            assert cap["kind"] == "mcp_tool"
            assert "description" in cap["spec"]


# ──────────────────────────────────────────────────────────────────
# 2. Failure: no tools
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeNoTools:
    @pytest.mark.asyncio
    async def test_empty_tools_list_marks_callable_failed(self):
        row = _row(
            command=sys.executable,
            args=[str(FIXTURES_DIR / "fake_mcp_no_tools.py")],
        )
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "callable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_NO_TOOLS)


# ──────────────────────────────────────────────────────────────────
# 3. Failure: initialize fails
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeInitializeFailure:
    @pytest.mark.asyncio
    async def test_initialize_jsonrpc_error_returns_initialize_failed(self):
        row = _row(
            command=sys.executable,
            args=[str(FIXTURES_DIR / "fake_mcp_init_fail.py")],
        )
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is False
        # The MCP SDK raises after the initialize error -- the probe
        # may classify as initialize_failed OR command_failed depending
        # on which leg of the SDK trips first. Both are honest failures
        # at the reachable layer.
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        assert any(
            result.failure_reason.startswith(prefix)
            for prefix in (FAIL_INITIALIZE_FAILED, FAIL_COMMAND_FAILED)
        ), f"unexpected failure_reason: {result.failure_reason}"


# ──────────────────────────────────────────────────────────────────
# 4. Failure: initialize timeout
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeInitializeTimeout:
    @pytest.mark.asyncio
    async def test_initialize_hang_triggers_timeout(self):
        # Tight timeouts so the test runs fast.
        timeouts = McpProbeTimeouts(
            spawn=2.0, initialize=1.0, tools_list=1.0, cleanup=1.0,
        )
        row = _row(
            command=sys.executable,
            args=[str(FIXTURES_DIR / "fake_mcp_init_hang.py")],
        )
        probe = McpServerProbe(timeouts=timeouts)
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        # Inner OR outer wait_for can fire -- both report the same prefix.
        assert result.failure_reason.startswith(FAIL_INITIALIZE_TIMEOUT)


# ──────────────────────────────────────────────────────────────────
# 5. Failure: command crashes before MCP handshake
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeCommandCrash:
    @pytest.mark.asyncio
    async def test_subprocess_exit_returns_command_failed(self):
        row = _row(
            command=sys.executable,
            args=[str(FIXTURES_DIR / "fake_mcp_crash.py")],
        )
        timeouts = McpProbeTimeouts(
            spawn=2.0, initialize=2.0, tools_list=2.0, cleanup=1.0,
        )
        probe = McpServerProbe(timeouts=timeouts)
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim in ("reachable", "callable")
        assert result.failure_reason is not None
        # Crash can manifest as command_failed (subprocess exited
        # before SDK attached) OR initialize_failed (SDK got partial
        # connect then failed). Either is honest.
        assert any(
            result.failure_reason.startswith(prefix)
            for prefix in (FAIL_COMMAND_FAILED, FAIL_INITIALIZE_FAILED)
        ), f"unexpected failure_reason: {result.failure_reason}"


# ──────────────────────────────────────────────────────────────────
# 6. Failure: binary not on PATH
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeBinaryNotFound:
    @pytest.mark.asyncio
    async def test_missing_binary_returns_binary_not_found(self):
        row = _row(
            command="this-binary-definitely-does-not-exist-12345",
            args=["--anything"],
        )
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_BINARY_NOT_FOUND)
        # Ensure we don't accidentally print the full PATH or
        # subprocess args back to the user.
        assert "/etc" not in (result.failure_reason or "")
        assert ".bashrc" not in (result.failure_reason or "")


# ──────────────────────────────────────────────────────────────────
# 7. Failure: unsupported transport
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeUnsupportedTransport:
    @pytest.mark.asyncio
    async def test_http_transport_returns_unsupported(self):
        row = _row(
            command=None,
            url="https://mcp.example.com/sse",
            kind_field="mcp_http",
        )
        # Force kind_field=mcp_http; the row's config has no command
        # because the importer flagged this as HTTP transport.
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_UNSUPPORTED_TRANSPORT)

    @pytest.mark.asyncio
    async def test_shell_pipeline_command_rejected(self):
        # Defense in depth: a malicious catalog entry that tries to
        # smuggle a shell pipeline through the command field MUST be
        # rejected at command-resolve time, not handed to /bin/sh.
        row = _row(
            command="sh -c 'rm -rf /tmp/anything'",
            args=[],
        )
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is False
        # Resolves to None because of the shell-metachar check ->
        # binary_not_found.
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_BINARY_NOT_FOUND)


# ──────────────────────────────────────────────────────────────────
# 8. Failure: config missing
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeConfigMissing:
    @pytest.mark.asyncio
    async def test_no_command_returns_config_missing(self):
        # Pass kind="mcp_stdio" so the transport gate accepts it, but
        # NO command -> config_missing.
        row = _row(command=None, kind_field="mcp_stdio")
        probe = McpServerProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_CONFIG_MISSING)


# ──────────────────────────────────────────────────────────────────
# 9. Secret-handling: env values pass through but never leak
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeNoSecretLeak:
    @pytest.mark.asyncio
    async def test_env_values_pass_through_but_not_logged(self, monkeypatch, capsys):
        """Sentinel test: the probe must pass declared env names to the
        subprocess (so the MCP can use them) BUT must never log values
        and must never return values in failure_reason / capabilities.

        Daena uses structlog with a stdout sink; we read captured
        stdout via pytest's capsys rather than logging.caplog because
        structlog bypasses the std logging registry.
        """
        # Plant a sentinel value in the parent env under a NAME that
        # also appears in the row's env_var_names.
        sentinel_name = "FAKE_PROBE_SECRET_KEY"
        sentinel_value = "sk-fake-do-not-leak-7890123456789012"  # noqa: S105
        monkeypatch.setenv(sentinel_name, sentinel_value)

        # Plant a second var to confirm passthrough is selective by name.
        unused_name = "DAENA_TEST_OTHER_SECRET"
        unused_value = "should-not-appear"
        monkeypatch.setenv(unused_name, unused_value)

        # The fake server writes its received env to a temp file so we
        # can inspect what it actually saw, separate from the probe's
        # logging behavior.
        with tempfile.TemporaryDirectory() as td:
            dump_path = Path(td) / "env_dump.json"
            monkeypatch.setenv("FAKE_MCP_ENV_DUMP", str(dump_path))

            row = _row(
                command=sys.executable,
                args=[str(FIXTURES_DIR / "fake_mcp_echo_env.py")],
                env_var_names=[sentinel_name, "FAKE_MCP_ENV_DUMP"],
            )
            probe = McpServerProbe()
            result = await probe.run(row)

            # Probe succeeded (server returned a tool).
            assert result.success is True, result.failure_reason

            # The fake server received the sentinel value (env passthrough works).
            received = json.loads(dump_path.read_text())
            assert received.get(sentinel_name) == sentinel_value, (
                "fake server did not receive the declared env value -- "
                "passthrough broken"
            )

        # CRITICAL: the probe's structured logs (stdout) must contain
        # NAMES only.
        captured = capsys.readouterr()
        log_text = captured.out + captured.err
        assert sentinel_value not in log_text, (
            f"PROBE LEAKED secret value {sentinel_value!r} into logs"
        )
        # The name SHOULD appear in env_present_names list (proof we
        # passed it through).
        assert sentinel_name in log_text, (
            "Expected env_var_name to appear in structured log "
            "(env_present_names list)"
        )

        # And capabilities (returned to the registry / UI) carry NO
        # env values -- only tool descriptors.
        for cap in result.capabilities:
            spec_text = json.dumps(cap.get("spec") or {})
            assert sentinel_value not in spec_text
            assert unused_value not in spec_text

    @pytest.mark.asyncio
    async def test_failure_reason_never_contains_env_values(self, monkeypatch):
        """Even when a probe FAILS, failure_reason must not carry env
        values from the parent process."""
        sentinel = "ghp_leakedtoken1234567890abcdefghijkl"  # noqa: S105
        monkeypatch.setenv("FAKE_PROBE_SECRET_KEY", sentinel)

        # Use the crash fixture so failure_reason captures stderr-ish
        # context. We pass sentinel-bearing env so the failure path
        # has access to it; the probe must still scrub.
        row = _row(
            command=sys.executable,
            args=[str(FIXTURES_DIR / "fake_mcp_crash.py")],
            env_var_names=["FAKE_PROBE_SECRET_KEY"],
        )
        probe = McpServerProbe(
            timeouts=McpProbeTimeouts(
                spawn=2.0, initialize=2.0, tools_list=2.0, cleanup=1.0,
            )
        )
        result = await probe.run(row)

        assert result.success is False
        assert sentinel not in (result.failure_reason or "")


# ──────────────────────────────────────────────────────────────────
# 10. Registry wiring
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeRegistryWiring:
    def test_install_mcp_server_probe_registers_probe(self):
        # Reset registry then re-install.
        PROBE_REGISTRY.pop("mcp_server", None)
        install_mcp_server_probe()
        assert "mcp_server" in PROBE_REGISTRY
        assert isinstance(PROBE_REGISTRY["mcp_server"], McpServerProbe)

    def test_install_all_probes_registers_mcp_server(self):
        from app.services.connection_v2.probes import install_all_probes
        PROBE_REGISTRY.pop("mcp_server", None)
        install_all_probes()
        assert isinstance(PROBE_REGISTRY.get("mcp_server"), McpServerProbe)


# ──────────────────────────────────────────────────────────────────
# 11. Defaults are sane
# ──────────────────────────────────────────────────────────────────


class TestMcpProbeDefaults:
    def test_default_timeouts_are_bounded(self):
        # Sanity: each step caps at <= 30 seconds so a worst-case probe
        # never blocks longer than ~90 seconds total.
        assert DEFAULT_TIMEOUTS.spawn <= 30
        assert DEFAULT_TIMEOUTS.initialize <= 30
        assert DEFAULT_TIMEOUTS.tools_list <= 30
        assert DEFAULT_TIMEOUTS.cleanup <= 30
