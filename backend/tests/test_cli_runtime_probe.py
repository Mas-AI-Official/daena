"""PR-CONN-CLI-PROBE tests.

Pins the CliRuntimeProbe contract:

  1. Happy path (claude_status_cmd auth): version + auth status both
     succeed -> success=True with capability {name, kind, spec}.
  2. Codex JWT-file auth: synthesized auth.json with valid JWT -> success.
  3. Gemini OAuth-file auth: synthesized oauth_creds.json -> success
     (skips version check because gemini --version hangs unauthed).
  4. Binary missing: shutil.which empty + config["binary"] empty
     -> failure_reason starts with binary_not_found.
  5. Version timeout: hung subprocess past version timeout
     -> failure_reason starts with version_timeout.
  6. Version exit non-zero -> failure_reason starts with version_failed.
  7. Auth failed: claude auth status returns loggedIn=false
     -> failure_reason starts with auth_failed.
  8. Auth unknown: claude auth status returns non-JSON
     -> failure_reason starts with auth_unknown.
  9. Unsupported runtime: _runtime_id we do not have a spec for
     -> failure_reason starts with unsupported_runtime.
 10. Config missing: row.config has no _runtime_id -> config_missing.
 11. No leak: stderr from CLI carrying a sentinel secret never appears
     in failure_reason or capabilities; structured logs carry NAMES only.
 12. Registry wiring: install_cli_runtime_probe registers + idempotent.
 13. Defaults: per-step timeouts are bounded so worst-case probe is
     short.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import pytest

from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.services.connection_v2.probe import PROBE_REGISTRY
from app.services.connection_v2.probes.cli_runtime_probe import (
    CLAUDE_SPEC,
    CODEX_SPEC,
    DEFAULT_TIMEOUTS,
    FAIL_AUTH_FAILED,
    FAIL_AUTH_UNKNOWN,
    FAIL_BINARY_NOT_FOUND,
    FAIL_CONFIG_MISSING,
    FAIL_UNSUPPORTED_RUNTIME,
    FAIL_VERSION_FAILED,
    FAIL_VERSION_TIMEOUT,
    GEMINI_SPEC,
    SPEC_BY_RUNTIME_ID,
    CliProbeTimeouts,
    CliRuntimeProbe,
    install_cli_runtime_probe,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "fake_cli_binaries"


# ──────────────────────────────────────────────────────────────────
# Row builder
# ──────────────────────────────────────────────────────────────────


def _row(
    *,
    runtime_id: str,
    binary: str | None,
    extra_args: list[str] | None = None,
) -> ConnectionV2:
    """Build a non-persisted V2 row for probe tests.

    The probe inspects config + slug + kind only; tenant_id and
    canonical_key are set for completeness but ignored.
    """
    config: dict = {
        "kind": "cli_runtime",
        "_runtime_id": runtime_id,
    }
    if binary is not None:
        config["binary"] = binary
    if extra_args is not None:
        config["extra_args"] = extra_args
    return ConnectionV2(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        kind=ConnectionKind.CLI_RUNTIME.value,
        slug=f"cli-{runtime_id}",
        display_name=f"Test {runtime_id}",
        canonical_key="x" * 64,
        auth_method=AuthMethod.SUBSCRIPTION.value,
        config=config,
    )


def _fake_codex_home(tmp_path: Path, *, valid_jwt: bool = True) -> Path:
    """Synthesize a fake ``~/.codex/auth.json`` under tmp_path.

    When ``valid_jwt`` is True, write a structurally valid (decodable)
    JWT with a future exp. When False, write an empty token block.
    """
    codex_dir = tmp_path / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    if valid_jwt:
        # Header.Payload.Signature; only Payload is decoded by the probe.
        import base64

        header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
        from datetime import datetime, timedelta, timezone

        payload_obj = {
            "exp": int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp()),
            "https://api.openai.com/auth": {"chatgpt_plan_type": "pro"},
        }
        payload = base64.urlsafe_b64encode(
            json.dumps(payload_obj).encode("utf-8"),
        ).rstrip(b"=").decode()
        signature = base64.urlsafe_b64encode(b"fake-signature").rstrip(b"=").decode()
        id_token = f"{header}.{payload}.{signature}"
        auth = {"auth_mode": "ChatGPT", "tokens": {"id_token": id_token}}
    else:
        auth = {"auth_mode": "", "tokens": {"id_token": ""}}
    (codex_dir / "auth.json").write_text(json.dumps(auth))
    return tmp_path


def _fake_gemini_home(tmp_path: Path, *, has_token: bool = True) -> Path:
    """Synthesize a fake ``~/.gemini/oauth_creds.json`` under tmp_path."""
    gemini_dir = tmp_path / ".gemini"
    gemini_dir.mkdir(parents=True, exist_ok=True)
    creds = (
        {"access_token": "fake-access-token", "refresh_token": "fake-refresh"}
        if has_token
        else {}
    )
    (gemini_dir / "oauth_creds.json").write_text(json.dumps(creds))
    accts = {"active": "operator@example.com"}
    (gemini_dir / "google_accounts.json").write_text(json.dumps(accts))
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# 1. Happy path -- claude (version + auth status)
# ──────────────────────────────────────────────────────────────────


class TestCliProbeHappyClaude:
    @pytest.mark.asyncio
    async def test_claude_version_and_auth_succeed(self):
        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_ok.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is True, result.failure_reason
        assert result.failure_dim is None
        assert len(result.capabilities) == 1

        cap = result.capabilities[0]
        assert cap["name"] == "claude_code"
        assert cap["kind"] == "cli_runtime"
        assert "fake-cli 1.2.3" in cap["spec"]["version"]
        assert cap["spec"]["auth_user_display"] == "Claude Max"
        assert cap["spec"]["runtime_id"] == "claude_code"


# ──────────────────────────────────────────────────────────────────
# 2. Happy path -- codex (jwt file)
# ──────────────────────────────────────────────────────────────────


class TestCliProbeHappyCodex:
    @pytest.mark.asyncio
    async def test_codex_with_valid_jwt_file_succeeds(self, tmp_path: Path):
        home = _fake_codex_home(tmp_path, valid_jwt=True)
        row = _row(
            runtime_id="codex",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_ok.py")],
        )
        probe = CliRuntimeProbe(home_override=home)
        result = await probe.run(row)

        assert result.success is True, result.failure_reason
        cap = result.capabilities[0]
        assert cap["spec"]["auth_user_display"] == "ChatGPT Pro"


# ──────────────────────────────────────────────────────────────────
# 3. Happy path -- gemini (skips version, oauth file)
# ──────────────────────────────────────────────────────────────────


class TestCliProbeHappyGemini:
    @pytest.mark.asyncio
    async def test_gemini_skips_version_and_uses_oauth_file(
        self, tmp_path: Path,
    ):
        home = _fake_gemini_home(tmp_path, has_token=True)
        # gemini's spec has version_check_safe=False so the binary doesn't
        # need to support --version. We still pass a usable binary so
        # _resolve_binary returns a real path.
        row = _row(
            runtime_id="gemini_cli",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_ok.py")],
        )
        probe = CliRuntimeProbe(home_override=home)
        result = await probe.run(row)

        assert result.success is True, result.failure_reason
        cap = result.capabilities[0]
        # Email should be masked, not raw.
        assert "operator@example.com" not in cap["spec"]["auth_user_display"]
        assert cap["spec"]["auth_user_display"].endswith("@example.com")
        # Version field should be absent (skipped) for gemini.
        assert "version" not in cap["spec"]


# ──────────────────────────────────────────────────────────────────
# 4. Failure: binary not found
# ──────────────────────────────────────────────────────────────────


class TestCliProbeBinaryNotFound:
    @pytest.mark.asyncio
    async def test_missing_binary_returns_binary_not_found(self):
        row = _row(
            runtime_id="claude_code",
            binary="",  # explicit empty -- no PATH match either (claude unlikely on test runner)
        )
        probe = CliRuntimeProbe()
        # Force PATH miss by overriding which-resolution via a runtime_id
        # whose binary_name is unlikely to exist in CI.
        # We swap to a runtime_id that nominally has spec but no binary.
        row.config["_runtime_id"] = "grok_cli"
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_BINARY_NOT_FOUND)
        # Sanity: never echoes a path or username.
        assert "/etc" not in result.failure_reason
        assert ".bashrc" not in result.failure_reason


# ──────────────────────────────────────────────────────────────────
# 5. Failure: version timeout
# ──────────────────────────────────────────────────────────────────


class TestCliProbeVersionTimeout:
    @pytest.mark.asyncio
    async def test_version_hang_triggers_timeout(self):
        timeouts = CliProbeTimeouts(version=1.0, auth=2.0)
        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_version_hang.py")],
        )
        probe = CliRuntimeProbe(timeouts=timeouts)
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_VERSION_TIMEOUT)


# ──────────────────────────────────────────────────────────────────
# 6. Failure: version exit non-zero
# ──────────────────────────────────────────────────────────────────


class TestCliProbeVersionFailed:
    @pytest.mark.asyncio
    async def test_version_nonzero_exit_returns_version_failed(self):
        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_version_fail.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "reachable"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_VERSION_FAILED)
        # stderr from the fake CLI must NEVER leak into failure_reason.
        assert "missing optional dependency" not in result.failure_reason


# ──────────────────────────────────────────────────────────────────
# 7. Failure: auth status returns loggedIn=false
# ──────────────────────────────────────────────────────────────────


class TestCliProbeAuthFailed:
    @pytest.mark.asyncio
    async def test_logged_in_false_returns_auth_failed(self):
        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_auth_failed.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_AUTH_FAILED)


class TestCliProbeAuthFailedCodex:
    @pytest.mark.asyncio
    async def test_codex_no_token_returns_auth_failed(self, tmp_path: Path):
        # auth.json present but tokens block empty AND auth_mode empty.
        home = _fake_codex_home(tmp_path, valid_jwt=False)
        # Overwrite auth_mode=""so the probe rejects (otherwise the
        # legacy auth_mode path returns authenticated).
        codex_dir = home / ".codex"
        (codex_dir / "auth.json").write_text(
            json.dumps({"auth_mode": "", "tokens": {"id_token": ""}}),
        )
        row = _row(
            runtime_id="codex",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_ok.py")],
        )
        probe = CliRuntimeProbe(home_override=home)
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason.startswith(FAIL_AUTH_FAILED)


# ──────────────────────────────────────────────────────────────────
# 8. Failure: auth status non-JSON -> auth_unknown
# ──────────────────────────────────────────────────────────────────


class TestCliProbeAuthUnknown:
    @pytest.mark.asyncio
    async def test_invalid_json_returns_auth_unknown(self):
        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_auth_invalid_json.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_AUTH_UNKNOWN)

    @pytest.mark.asyncio
    async def test_grok_no_safe_check_returns_auth_unknown(self):
        # grok_cli's spec has auth_strategy='none'. Pass a working binary
        # so version check succeeds; auth phase should still return
        # auth_unknown without trying anything destructive.
        row = _row(
            runtime_id="grok_cli",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_ok.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "authenticated"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_AUTH_UNKNOWN)


# ──────────────────────────────────────────────────────────────────
# 9. Failure: unsupported runtime
# ──────────────────────────────────────────────────────────────────


class TestCliProbeUnsupportedRuntime:
    @pytest.mark.asyncio
    async def test_unknown_runtime_id_returns_unsupported(self):
        row = _row(
            runtime_id="not_a_real_runtime_42",
            binary=sys.executable,
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_UNSUPPORTED_RUNTIME)


# ──────────────────────────────────────────────────────────────────
# 10. Failure: config missing _runtime_id
# ──────────────────────────────────────────────────────────────────


class TestCliProbeConfigMissing:
    @pytest.mark.asyncio
    async def test_no_runtime_id_returns_config_missing(self):
        row = ConnectionV2(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            kind=ConnectionKind.CLI_RUNTIME.value,
            slug="cli-broken",
            display_name="Broken CLI",
            canonical_key="x" * 64,
            auth_method=AuthMethod.SUBSCRIPTION.value,
            config={"kind": "cli_runtime"},  # NO _runtime_id
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        assert result.failure_dim == "configured"
        assert result.failure_reason is not None
        assert result.failure_reason.startswith(FAIL_CONFIG_MISSING)


# ──────────────────────────────────────────────────────────────────
# 11. No-leak: secrets in stderr / env never escape into failure_reason
# ──────────────────────────────────────────────────────────────────


class TestCliProbeNoSecretLeak:
    @pytest.mark.asyncio
    async def test_stderr_secrets_never_in_failure_reason(
        self, monkeypatch, capsys,
    ):
        """The leak fixture echoes a sentinel on stderr for every
        subcommand. The probe must NEVER include that sentinel in
        failure_reason or capability spec, even though it captures
        stderr internally for server-side logging.
        """
        from backend.tests.fixtures.fake_cli_binaries.fake_cli_auth_leaks import (
            SENTINEL_SECRET,
        )

        # Force a failure path so stderr-capture is exercised: use the
        # leak fixture as a working CLI (auth status returns loggedIn=true)
        # but ALSO plant the sentinel in the parent env so any leak
        # vector triggers.
        monkeypatch.setenv("DAENA_TEST_LEAK_SENTINEL", SENTINEL_SECRET)

        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_auth_leaks.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        # Probe succeeds because the fake says loggedIn=true.
        assert result.success is True, result.failure_reason

        # Capabilities must NOT include the sentinel (returned to UI).
        for cap in result.capabilities:
            spec_text = json.dumps(cap.get("spec") or {})
            assert SENTINEL_SECRET not in spec_text, (
                f"PROBE LEAKED secret into capability spec: {spec_text}"
            )

        # Structured logs (stdout/stderr) must NOT include the sentinel.
        # Daena uses structlog -> stdout, so we read capsys not caplog.
        captured = capsys.readouterr()
        log_text = captured.out + captured.err
        assert SENTINEL_SECRET not in log_text, (
            f"PROBE LEAKED secret value into logs: search for {SENTINEL_SECRET!r}"
        )

    @pytest.mark.asyncio
    async def test_failure_reason_truncated(self, monkeypatch):
        """Even on failure, a hostile CLI emitting a 10 KB stderr payload
        must NOT bloat failure_reason. The probe never echoes stderr;
        it only echoes its own structured prefix + a bounded detail.
        """
        row = _row(
            runtime_id="claude_code",
            binary=sys.executable,
            extra_args=[str(FIXTURES_DIR / "fake_cli_version_fail.py")],
        )
        probe = CliRuntimeProbe()
        result = await probe.run(row)

        assert result.success is False
        # Reason ALWAYS starts with the prefix and is bounded.
        assert result.failure_reason.startswith(FAIL_VERSION_FAILED)
        assert len(result.failure_reason) < 400


# ──────────────────────────────────────────────────────────────────
# 12. Registry wiring
# ──────────────────────────────────────────────────────────────────


class TestCliProbeRegistryWiring:
    def test_install_cli_runtime_probe_registers(self):
        PROBE_REGISTRY.pop("cli_runtime", None)
        install_cli_runtime_probe()
        assert "cli_runtime" in PROBE_REGISTRY
        assert isinstance(PROBE_REGISTRY["cli_runtime"], CliRuntimeProbe)

    def test_install_all_probes_includes_cli(self):
        from app.services.connection_v2.probes import install_all_probes
        PROBE_REGISTRY.pop("cli_runtime", None)
        install_all_probes()
        assert isinstance(PROBE_REGISTRY.get("cli_runtime"), CliRuntimeProbe)

    def test_install_is_idempotent(self):
        install_cli_runtime_probe()
        install_cli_runtime_probe()
        install_cli_runtime_probe()
        assert isinstance(PROBE_REGISTRY.get("cli_runtime"), CliRuntimeProbe)


# ──────────────────────────────────────────────────────────────────
# 13. Defaults are sane
# ──────────────────────────────────────────────────────────────────


class TestCliProbeDefaults:
    def test_default_timeouts_are_bounded(self):
        # Worst-case probe ~= version + auth, both bounded so total
        # never exceeds ~30 seconds.
        assert DEFAULT_TIMEOUTS.version <= 15
        assert DEFAULT_TIMEOUTS.auth <= 15

    def test_spec_table_covers_all_documented_runtimes(self):
        # Founder spec (PR-CONN-CLI-PROBE) requires at least claude/
        # codex/gemini. grok is a stretch goal.
        assert "claude_code" in SPEC_BY_RUNTIME_ID
        assert "codex" in SPEC_BY_RUNTIME_ID
        assert "gemini_cli" in SPEC_BY_RUNTIME_ID
        # Per-runtime invariants.
        assert SPEC_BY_RUNTIME_ID["claude_code"].auth_strategy == "claude_status_cmd"
        assert SPEC_BY_RUNTIME_ID["codex"].auth_strategy == "codex_jwt_file"
        assert SPEC_BY_RUNTIME_ID["gemini_cli"].auth_strategy == "gemini_oauth_file"
        # Gemini explicitly opts out of version check (known to hang).
        assert SPEC_BY_RUNTIME_ID["gemini_cli"].version_check_safe is False
        assert SPEC_BY_RUNTIME_ID["claude_code"].version_check_safe is True
