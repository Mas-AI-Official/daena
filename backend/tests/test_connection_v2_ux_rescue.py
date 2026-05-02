"""PR-CONN-UX-RESCUE tests.

Pins the contract for the UX rescue PR:
  1. CLIMCPDetector path coverage:
     - includes WSL bridge paths when running in WSL
     - candidate cache is process-stable but resettable for tests
     - env-var overrides take priority
  2. CLIMCPDetector.discover_with_debug:
     - returns CandidatePathProbe per attempted path
     - never reads or includes env values from probed configs
     - flags exists / parse_ok / has_mcp_block / mcp_count / server_names
  3. ConnectionDiscoveryService.run_discovery:
     - populates report.mcp_paths_searched alongside the per-source rows
     - debug entries carry path metadata only -- NEVER env values
     - re-run still idempotent on the rows side
  4. Sentinel-secret audit: env values planted in mocked detector output
     never appear in the discovery report's debug payload.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.models.identity import Tenant
from app.services.connection_v2 import ConnectionDiscoveryService
from app.services.mcp_sync.detector import (
    CandidatePathProbe,
    CLIMCPDetector,
    DetectedMCP,
    _candidates,
    _is_wsl,
    _wsl_windows_user_home,
    reset_candidates_cache,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    return tenant


def _settings_for_test(**overrides) -> Settings:
    base = dict(
        ollama_enabled=False,
        ollama_base_url="",
        vllm_base_url="",
        vllm_default_model="",
        openai_api_key="",
        anthropic_api_key="",
        gemini_api_key="",
        perplexity_api_key="",
        groq_api_key="",
        openrouter_api_key="",
        together_api_key="",
        google_client_id="",
        google_client_secret="",
        github_client_id="",
        github_client_secret="",
        figma_client_id="",
        figma_client_secret="",
        slack_client_id="",
        slack_client_secret="",
        canva_client_id="",
        canva_client_secret="",
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture(autouse=True)
def _reset_detector_cache():
    """Per-test cache reset so env overrides + WSL detection don't leak."""
    reset_candidates_cache()
    yield
    reset_candidates_cache()


# ──────────────────────────────────────────────────────────────────
# 1. Path coverage
# ──────────────────────────────────────────────────────────────────


class TestCandidatePaths:
    def test_native_paths_present(self):
        cands = _candidates()
        assert "claude_code" in cands
        assert "codex" in cands
        assert "gemini_cli" in cands
        # Native must include the well-known Claude Code locations.
        cc_paths = [str(p) for p in cands["claude_code"]]
        assert any(".claude" in p for p in cc_paths)
        # Codex + Gemini have their canonical paths.
        assert any(".codex" in str(p) for p in cands["codex"])
        assert any(".gemini" in str(p) for p in cands["gemini_cli"])

    def test_env_override_takes_priority(self, monkeypatch, tmp_path):
        override_path = tmp_path / "custom-claude-mcp.json"
        override_path.write_text("{}", encoding="utf-8")
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(override_path))
        reset_candidates_cache()
        cands = _candidates()
        # Env override is inserted at index 0.
        assert str(cands["claude_code"][0]) == str(override_path)

    def test_paths_are_deduplicated(self):
        cands = _candidates()
        for cli, paths in cands.items():
            seen: set[str] = set()
            for p in paths:
                key = str(p)
                assert key not in seen, f"Duplicate path in {cli}: {key}"
                seen.add(key)

    def test_wsl_bridge_only_when_in_wsl(self, monkeypatch):
        """WSL bridge paths must NOT appear when not running in WSL."""
        # Force native (non-WSL).
        with patch("app.services.mcp_sync.detector._is_wsl", return_value=False):
            reset_candidates_cache()
            cands = _candidates()
            for paths in cands.values():
                for p in paths:
                    assert "/mnt/c/" not in str(p), f"Bridge leaked: {p}"

    def test_wsl_bridge_added_when_wsl_and_user_home_resolves(self, tmp_path):
        """WSL detection adds /mnt/c/Users/<user>/AppData/... paths."""
        fake_win_home = tmp_path / "WindowsUser"
        (fake_win_home / "AppData" / "Roaming").mkdir(parents=True)
        with patch(
            "app.services.mcp_sync.detector._is_wsl", return_value=True,
        ), patch(
            "app.services.mcp_sync.detector._wsl_windows_user_home",
            return_value=fake_win_home,
        ):
            reset_candidates_cache()
            cands = _candidates()
            cc_strs = [str(p) for p in cands["claude_code"]]
            # The bridge added the AppData/Roaming/Claude path.
            assert any(
                str(fake_win_home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json") == p
                for p in cc_strs
            )

    def test_wsl_detection_safe_on_native(self):
        """_is_wsl() must not raise on Windows / macOS / native Linux."""
        # Just call it; the assertion is that it returns a bool and
        # doesn't raise. Real value depends on the test host.
        result = _is_wsl()
        assert isinstance(result, bool)


# ──────────────────────────────────────────────────────────────────
# 2. discover_with_debug contract
# ──────────────────────────────────────────────────────────────────


class TestDiscoverWithDebug:
    @pytest.mark.asyncio
    async def test_returns_probe_per_candidate(self, tmp_path, monkeypatch):
        # Provide a single override so the debug list shape is predictable.
        config = tmp_path / "claude.json"
        config.write_text(
            '{"mcpServers": {"sample": {"command": "npx", "args": ["-y", "@sample"]}}}',
            encoding="utf-8",
        )
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(config))
        reset_candidates_cache()
        det = CLIMCPDetector()
        mcps, probes = await det.discover_with_debug()
        # The override is at the head of claude_code, so it parses + has_block.
        head = next(p for p in probes if p.path == str(config))
        assert head.exists is True
        assert head.parse_ok is True
        assert head.has_mcp_block is True
        assert head.mcp_count == 1
        assert head.server_names == ["sample"]
        # MCPs include the sample one.
        names = sorted(m.name for m in mcps)
        assert "sample" in names

    @pytest.mark.asyncio
    async def test_missing_path_marked_not_found(self, tmp_path, monkeypatch):
        bogus = tmp_path / "does-not-exist.json"
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(bogus))
        reset_candidates_cache()
        det = CLIMCPDetector()
        _, probes = await det.discover_with_debug()
        head = next(p for p in probes if p.path == str(bogus))
        assert head.exists is False
        assert head.parse_ok is False
        assert head.has_mcp_block is False
        assert head.skip_reason == "not_found"

    @pytest.mark.asyncio
    async def test_invalid_json_marked_parse_error(self, tmp_path, monkeypatch):
        broken = tmp_path / "broken.json"
        broken.write_text("{ this is not json", encoding="utf-8")
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(broken))
        reset_candidates_cache()
        det = CLIMCPDetector()
        _, probes = await det.discover_with_debug()
        head = next(p for p in probes if p.path == str(broken))
        assert head.exists is True
        assert head.parse_ok is False
        assert head.has_mcp_block is False
        assert head.skip_reason.startswith("parse_error:")

    @pytest.mark.asyncio
    async def test_no_mcp_block_marked_explicitly(self, tmp_path, monkeypatch):
        # Valid JSON but no mcpServers / mcp_servers block.
        plain = tmp_path / "plain.json"
        plain.write_text('{"theme": "dark", "telemetry": false}', encoding="utf-8")
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(plain))
        reset_candidates_cache()
        det = CLIMCPDetector()
        _, probes = await det.discover_with_debug()
        head = next(p for p in probes if p.path == str(plain))
        assert head.exists is True
        assert head.parse_ok is True
        assert head.has_mcp_block is False
        assert head.mcp_count == 0
        assert head.skip_reason == "no_mcp_block"

    @pytest.mark.asyncio
    async def test_debug_payload_never_contains_env_values(
        self, tmp_path, monkeypatch,
    ):
        """SENTINEL test: env value planted in source must NOT appear in
        the debug payload (server_names list nor any field)."""
        sentinel = "MUST_NOT_APPEAR_IN_DEBUG_OUTPUT"
        config = tmp_path / "leaky.json"
        config.write_text(
            '{"mcpServers": {"leaky": {"command": "npx", "args": ["-y", "@leaky"], '
            f'"env": {{"SECRET_TOKEN": "{sentinel}"}}}}}}',
            encoding="utf-8",
        )
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(config))
        reset_candidates_cache()
        det = CLIMCPDetector()
        mcps, probes = await det.discover_with_debug()
        # The detector's DetectedMCP DOES carry env (downstream callers
        # decide whether to persist it; the seeder does not). But the
        # CandidatePathProbe debug payload MUST never include it.
        for probe in probes:
            blob = (
                probe.path + probe.skip_reason +
                " ".join(probe.server_names)
            )
            assert sentinel not in blob, (
                f"Sentinel leaked in CandidatePathProbe: {probe!r}"
            )


# ──────────────────────────────────────────────────────────────────
# 3. ConnectionDiscoveryService report shape + secret-leak audit
# ──────────────────────────────────────────────────────────────────


class TestDiscoveryReportShape:
    @pytest.mark.asyncio
    async def test_report_includes_mcp_paths_searched(
        self, db_session, seeded_tenant, test_tenant_id, tmp_path, monkeypatch,
    ):
        config = tmp_path / "real-claude.json"
        config.write_text(
            '{"mcpServers": {"figma": {"command": "npx", "args": ["-y", "@figma/server"]}}}',
            encoding="utf-8",
        )
        monkeypatch.setenv("DAENA_CLAUDE_CONFIG", str(config))
        reset_candidates_cache()

        # Force shutil.which to return None to keep cli_runtimes empty
        # so the test focuses on MCP path debug.
        with patch.object(shutil, "which", return_value=None):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            report = await svc.run_discovery()

        d = report.to_dict()
        assert "mcp_paths_searched" in d
        assert isinstance(d["mcp_paths_searched"], list)
        assert len(d["mcp_paths_searched"]) >= 1
        head = next(p for p in d["mcp_paths_searched"] if p["path"] == str(config))
        assert head["exists"] is True
        assert head["parse_ok"] is True
        assert head["has_mcp_block"] is True
        assert head["mcp_count"] == 1
        assert head["server_names"] == ["figma"]

    @pytest.mark.asyncio
    async def test_report_debug_payload_never_leaks_env_values(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        """Sentinel-secret audit: an env value present in a detected MCP
        must NEVER appear in report.mcp_paths_searched."""
        sentinel = "REPORT_DEBUG_SENTINEL_VALUE"
        leaky_mcp = DetectedMCP(
            source_cli="claude_code",
            config_path="/fake/.claude/mcp.json",
            name="leaky-mcp",
            command="npx",
            args=["-y", "leaky"],
            env={"SECRET_TOKEN": sentinel},
        )
        # Mock both the merged MCP list AND the per-path probes (which
        # is where the debug payload comes from).
        leaky_probe = CandidatePathProbe(
            cli="claude_code",
            path="/fake/.claude/mcp.json",
            exists=True, parse_ok=True, has_mcp_block=True,
            mcp_count=1, server_names=["leaky-mcp"],
        )
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_with_debug",
            new=AsyncMock(return_value=([leaky_mcp], [leaky_probe])),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            report = await svc.run_discovery()

        # Walk every dict in the debug payload + every nested string.
        d = report.to_dict()
        for entry in d["mcp_paths_searched"]:
            blob = "|".join(
                str(v) if not isinstance(v, list) else "|".join(map(str, v))
                for v in entry.values()
            )
            assert sentinel not in blob, (
                f"Sentinel leaked into mcp_paths_searched entry: {entry!r}"
            )

    @pytest.mark.asyncio
    async def test_backward_compat_import_mcp_servers_still_works(
        self, db_session, seeded_tenant, test_tenant_id,
    ):
        """The old _import_mcp_servers wrapper still returns SourceReport."""
        with patch.object(shutil, "which", return_value=None), patch(
            "app.services.mcp_sync.detector.CLIMCPDetector.discover_with_debug",
            new=AsyncMock(return_value=([], [])),
        ):
            svc = ConnectionDiscoveryService(
                db_session,
                tenant_id=test_tenant_id,
                settings=_settings_for_test(),
            )
            source_report = await svc._import_mcp_servers()
        assert source_report.source == "mcp_servers"
