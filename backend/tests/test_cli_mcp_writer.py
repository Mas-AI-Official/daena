"""PR-CONN-MCP-INSTALL-INTO-CLI writer tests.

Pins the contract of ``cli_mcp_writer``:

  1. parse_command_template happy path + reject shell metachars
  2. find_unresolved_placeholders surfaces <ALLOWED_ROOT> tokens
  3. build_mcp_block omits env (founder rule 14: never write secrets)
  4. preview reports "create" when target file does not exist + allow_create
  5. preview reports "create_file" + apply creates the file safely
  6. preview reports "skip" when entry already matches (idempotent)
  7. preview reports "update" when entry exists but differs
  8. preview reports config_parse_error when JSON is malformed
  9. apply with malformed config returns failed + leaves file untouched
 10. apply preserves unrelated config keys
 11. apply writes a backup file before overwriting
 12. apply writes atomically (no partial-write window)
 13. apply with empty allow_create=False refuses to create new file
 14. Codex target writes to ~/.codex/config.json under the same shape
 15. Gemini target writes to ~/.gemini/settings.json under the same shape
 16. Idempotent apply (re-run) returns "skipped" + no new backup
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.connection_v2.cli_mcp_writer import (
    FAIL_COMMAND_TEMPLATE_INVALID,
    FAIL_CONFIG_PARSE_ERROR,
    FAIL_CONFIG_PATH_MISSING,
    FAIL_PLACEHOLDER_UNRESOLVED,
    SUPPORTED_TARGETS,
    apply_install,
    atomic_write_json,
    build_mcp_block,
    find_unresolved_placeholders,
    get_target_spec,
    parse_command_template,
    preview_install,
    read_config,
    reset_target_cache,
    resolve_path,
    server_name_for,
)
from app.services.connection_v2.marketplace_catalog import CATALOG, CatalogEntry


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _mcp_filesystem_entry() -> CatalogEntry:
    """Pluck the real mcp-filesystem entry from the catalog."""
    entry = next((e for e in CATALOG if e.id == "mcp-filesystem"), None)
    assert entry is not None, "mcp-filesystem missing from catalog"
    return entry


def _mcp_github_entry() -> CatalogEntry:
    """mcp-github -- has required_env_vars (GITHUB_PERSONAL_ACCESS_TOKEN)."""
    entry = next((e for e in CATALOG if e.id == "mcp-github"), None)
    assert entry is not None, "mcp-github missing from catalog"
    return entry


def _mcp_time_entry() -> CatalogEntry:
    """mcp-time -- simple, no env vars, no placeholders, easy probe target."""
    entry = next((e for e in CATALOG if e.id == "mcp-time"), None)
    assert entry is not None, "mcp-time missing from catalog"
    return entry


def _patch_home(monkeypatch, tmp_path: Path) -> Path:
    """Repoint Path.home() to tmp_path so writer never touches real configs."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    reset_target_cache()
    return tmp_path


# ──────────────────────────────────────────────────────────────────
# 1-2. Template parsing
# ──────────────────────────────────────────────────────────────────


class TestParseCommandTemplate:
    def test_simple_npx_command(self):
        parsed = parse_command_template("npx -y @modelcontextprotocol/server-time")
        assert parsed is not None
        assert parsed.command == "npx"
        assert parsed.args == ["-y", "@modelcontextprotocol/server-time"]

    def test_empty_returns_none(self):
        assert parse_command_template("") is None
        assert parse_command_template("   ") is None

    def test_shell_pipeline_rejected(self):
        # ; pipe & redirect backtick subshell
        for danger in (
            "npx foo; rm -rf /",
            "npx foo | tee /tmp/x",
            "npx foo & echo bad",
            "npx foo `whoami`",
            "npx foo $(whoami)",
        ):
            assert parse_command_template(danger) is None, f"should reject: {danger}"

    def test_placeholder_token_kept(self):
        # <ALLOWED_ROOT> is a placeholder, NOT a shell redirect. Parser
        # accepts; downstream find_unresolved_placeholders surfaces it.
        parsed = parse_command_template(
            "npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>",
        )
        assert parsed is not None
        assert "<ALLOWED_ROOT>" in parsed.args

    def test_placeholder_check_finds_unresolved(self):
        parsed = parse_command_template(
            "npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>",
        )
        assert parsed is not None
        placeholders = find_unresolved_placeholders(parsed)
        assert placeholders == ["<ALLOWED_ROOT>"]

    def test_placeholder_check_ignores_normal_args(self):
        parsed = parse_command_template("npx -y @modelcontextprotocol/server-time")
        assert parsed is not None
        assert find_unresolved_placeholders(parsed) == []


# ──────────────────────────────────────────────────────────────────
# 3. build_mcp_block omits env
# ──────────────────────────────────────────────────────────────────


class TestBuildMcpBlock:
    def test_block_never_includes_env(self):
        # mcp-github has GITHUB_PERSONAL_ACCESS_TOKEN required.
        # The block we write must NOT carry an env block (founder rule 14).
        block = build_mcp_block(_mcp_github_entry())
        assert block is not None
        assert "command" in block
        assert "args" in block
        assert "env" not in block, (
            "build_mcp_block must not write env block; values stay in shell / vault"
        )

    def test_block_for_invalid_template_is_none(self):
        # An entry with an empty command_template returns None.
        from app.services.connection_v2.marketplace_catalog import CatalogEntry as CE
        bad = CE(
            id="mcp-bad", display_name="Bad", vendor="x",
            category="dev_tools", kind="mcp_server",
            short_description="", install_method="npm",
            command_template="",
        )
        assert build_mcp_block(bad) is None


class TestServerNameFor:
    def test_strips_mcp_prefix(self):
        assert server_name_for(_mcp_github_entry()) == "github"
        assert server_name_for(_mcp_filesystem_entry()) == "filesystem"
        assert server_name_for(_mcp_time_entry()) == "time"


# ──────────────────────────────────────────────────────────────────
# 4-7. Preview lifecycle: create / skip / update
# ──────────────────────────────────────────────────────────────────


class TestPreviewLifecycle:
    def test_create_when_file_missing_with_allow_create(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        report = preview_install(
            target="claude_code", entry=_mcp_time_entry(),
            allow_create=True,
        )
        assert report.failure_reason is None
        assert report.action == "create_file"
        assert report.apply_allowed is True
        assert report.proposed_block is not None
        assert report.proposed_block["command"] == "npx"
        assert "@modelcontextprotocol/server-time" in report.proposed_block["args"]
        assert report.existing_block is None

    def test_skip_when_file_already_matches(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        # Pre-populate ~/.claude.json with the exact block we'd write.
        cfg_path = tmp_path / ".claude.json"
        proposed = build_mcp_block(_mcp_time_entry())
        cfg_path.write_text(json.dumps({
            "unrelated_key": {"keep": "me"},
            "mcpServers": {"time": proposed},
        }))
        report = preview_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.failure_reason is None
        assert report.action == "skip"

    def test_update_when_existing_block_differs(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        cfg_path.write_text(json.dumps({
            "mcpServers": {"time": {"command": "OLD", "args": ["v1"]}},
        }))
        report = preview_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.failure_reason is None
        assert report.action == "update"
        assert report.existing_block == {"command": "OLD", "args": ["v1"]}
        assert report.proposed_block["command"] == "npx"

    def test_create_when_file_exists_but_no_block(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        cfg_path.write_text(json.dumps({"unrelated": {}}))
        report = preview_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.failure_reason is None
        assert report.action == "create"
        assert report.existing_block is None


# ──────────────────────────────────────────────────────────────────
# 8-9. Malformed config fail-closed
# ──────────────────────────────────────────────────────────────────


class TestMalformedConfigFailsClosed:
    def test_preview_returns_parse_error(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        cfg_path.write_text("{ this is not valid json")
        report = preview_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_CONFIG_PARSE_ERROR)
        assert report.apply_allowed is False
        assert "Daena refuses to overwrite" in " ".join(report.risk_warnings)

    def test_apply_does_not_overwrite_malformed_file(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        original = "{ malformed broken nope"
        cfg_path.write_text(original)
        report = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.action == "failed"
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_CONFIG_PARSE_ERROR)
        # File on disk is UNTOUCHED.
        assert cfg_path.read_text() == original
        # No backup was created (the writer NEVER backs up a file it
        # then refuses to write).
        backups = list(tmp_path.glob(".claude.json.daena-backup-*.json"))
        assert backups == []


# ──────────────────────────────────────────────────────────────────
# 10. Apply preserves unrelated keys
# ──────────────────────────────────────────────────────────────────


class TestApplyPreservesUnrelatedKeys:
    def test_unrelated_top_level_keys_kept(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        cfg_path.write_text(json.dumps({
            "permissions": {"allow_all": True},
            "user_settings": {"theme": "dark", "fontSize": 14},
            "mcpServers": {"already_there": {"command": "echo", "args": []}},
        }))
        report = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.action == "created"
        assert report.failure_reason is None
        # Re-read file: every unrelated key is intact AND the existing
        # MCP entry was preserved alongside the new one.
        new = json.loads(cfg_path.read_text())
        assert new["permissions"] == {"allow_all": True}
        assert new["user_settings"] == {"theme": "dark", "fontSize": 14}
        assert "already_there" in new["mcpServers"]
        assert "time" in new["mcpServers"]
        assert new["mcpServers"]["time"]["command"] == "npx"


# ──────────────────────────────────────────────────────────────────
# 11. Apply writes a backup before overwriting
# ──────────────────────────────────────────────────────────────────


class TestApplyBackup:
    def test_backup_file_created_with_original_content(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        original = {"mcpServers": {"old": {"command": "x", "args": []}}}
        cfg_path.write_text(json.dumps(original))

        report = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.action == "created"
        assert report.backup_path is not None
        backup = Path(report.backup_path)
        assert backup.exists()
        # Backup carries the ORIGINAL bytes verbatim (so the operator
        # can restore manually).
        assert json.loads(backup.read_text()) == original

    def test_no_backup_for_skipped_apply(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        cfg_path = tmp_path / ".claude.json"
        proposed = build_mcp_block(_mcp_time_entry())
        cfg_path.write_text(json.dumps({
            "mcpServers": {"time": proposed},
        }))
        report = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.action == "skipped"
        assert report.backup_path is None
        backups = list(tmp_path.glob(".claude.json.daena-backup-*"))
        assert backups == []


# ──────────────────────────────────────────────────────────────────
# 12. atomic_write_json never leaves a half-written file
# ──────────────────────────────────────────────────────────────────


class TestAtomicWrite:
    def test_atomic_write_creates_no_partial_file_on_oserror(
        self, monkeypatch, tmp_path,
    ):
        cfg_path = tmp_path / "x.json"
        cfg_path.write_text(json.dumps({"keep": "me"}))

        # Force os.replace to raise so we hit the cleanup branch.
        import os
        original_replace = os.replace

        def boom(*args, **kwargs):
            raise OSError("test-injected failure")

        monkeypatch.setattr(os, "replace", boom)
        with pytest.raises(OSError):
            atomic_write_json(cfg_path, {"new": "shape"}, backup=True)
        monkeypatch.setattr(os, "replace", original_replace)

        # Original content preserved -- temp file cleaned up.
        assert json.loads(cfg_path.read_text()) == {"keep": "me"}
        leftover_tmps = list(tmp_path.glob("x.json.daena-tmp-*"))
        assert leftover_tmps == [], "temp file leaked after replace failure"


# ──────────────────────────────────────────────────────────────────
# 13. allow_create=False refuses missing files
# ──────────────────────────────────────────────────────────────────


class TestAllowCreateGuard:
    def test_preview_refuses_missing_file_without_flag(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        report = preview_install(
            target="claude_code", entry=_mcp_time_entry(),
            allow_create=False,
        )
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_CONFIG_PATH_MISSING)
        assert report.apply_allowed is False

    def test_apply_refuses_missing_file_without_flag(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        report = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report.action == "failed"
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_CONFIG_PATH_MISSING)


# ──────────────────────────────────────────────────────────────────
# 14-15. Per-target writes (Codex + Gemini)
# ──────────────────────────────────────────────────────────────────


class TestCodexTarget:
    def test_codex_writes_to_codex_config_json(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        report = apply_install(
            target="codex", entry=_mcp_time_entry(), allow_create=True,
        )
        assert report.action == "create_file"
        assert report.failure_reason is None
        cfg_path = tmp_path / ".codex" / "config.json"
        assert cfg_path.exists()
        content = json.loads(cfg_path.read_text())
        assert "mcpServers" in content
        assert content["mcpServers"]["time"]["command"] == "npx"


class TestGeminiTarget:
    def test_gemini_writes_to_settings_json(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        report = apply_install(
            target="gemini_cli", entry=_mcp_time_entry(), allow_create=True,
        )
        assert report.action == "create_file"
        cfg_path = tmp_path / ".gemini" / "settings.json"
        assert cfg_path.exists()
        content = json.loads(cfg_path.read_text())
        assert "mcpServers" in content
        assert content["mcpServers"]["time"]["command"] == "npx"


# ──────────────────────────────────────────────────────────────────
# 16. Idempotent: re-running yields skipped + no new backup
# ──────────────────────────────────────────────────────────────────


class TestIdempotentApply:
    def test_apply_twice_yields_skipped_second_time(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        # First apply: create_file
        report1 = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
            allow_create=True,
        )
        assert report1.action == "create_file"

        # Second apply: skipped, no backup
        report2 = apply_install(
            target="claude_code", entry=_mcp_time_entry(),
        )
        assert report2.action == "skipped"
        assert report2.backup_path is None
        # Only ONE backup file at most (from the first apply if it
        # ran, but create_file doesn't backup since file was new).
        backups = list(tmp_path.glob(".claude.json.daena-backup-*"))
        assert len(backups) == 0


# ──────────────────────────────────────────────────────────────────
# 17. Required env vars surface as warnings, never as values
# ──────────────────────────────────────────────────────────────────


class TestEnvVarsSurfaceAsWarnings:
    def test_github_preview_warns_about_env_var_names_only(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        # Plant a sentinel value in env -- writer must NOT read it.
        sentinel = "ghp_test_should_never_leak_4321"  # noqa: S105
        monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", sentinel)

        report = preview_install(
            target="claude_code", entry=_mcp_github_entry(),
            allow_create=True,
        )
        assert report.failure_reason is None
        # required_env_vars in the report carries the NAME, not value.
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in report.required_env_vars
        # The proposed block has NO env block.
        assert "env" not in report.proposed_block
        # The risk warnings reference the name but never the value.
        warnings_text = " ".join(report.risk_warnings)
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in warnings_text
        assert sentinel not in warnings_text
        # Apply also doesn't write the value.
        apply_report = apply_install(
            target="claude_code", entry=_mcp_github_entry(),
            allow_create=True,
        )
        assert apply_report.action == "create_file"
        cfg = json.loads((tmp_path / ".claude.json").read_text())
        block = cfg["mcpServers"]["github"]
        assert "env" not in block
        assert sentinel not in json.dumps(cfg)


# ──────────────────────────────────────────────────────────────────
# 18. Placeholder rejection (e.g. <ALLOWED_ROOT>)
# ──────────────────────────────────────────────────────────────────


class TestPlaceholderRejection:
    def test_filesystem_entry_rejects_apply_until_placeholder_resolved(
        self, monkeypatch, tmp_path,
    ):
        _patch_home(monkeypatch, tmp_path)
        # mcp-filesystem has command_template
        # "npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>"
        report = preview_install(
            target="claude_code", entry=_mcp_filesystem_entry(),
            allow_create=True,
        )
        assert report.failure_reason is not None
        assert report.failure_reason.startswith(FAIL_PLACEHOLDER_UNRESOLVED)
        assert report.apply_allowed is False
        # Apply ALSO refuses (defense in depth).
        apply_report = apply_install(
            target="claude_code", entry=_mcp_filesystem_entry(),
            allow_create=True,
        )
        assert apply_report.action == "failed"
        assert apply_report.failure_reason.startswith(
            FAIL_PLACEHOLDER_UNRESOLVED,
        )


# ──────────────────────────────────────────────────────────────────
# 19. Target spec table covers all 4 supported CLIs
# ──────────────────────────────────────────────────────────────────


class TestTargetSpecTable:
    def test_all_supported_targets_have_specs(self, monkeypatch, tmp_path):
        _patch_home(monkeypatch, tmp_path)
        for target in SUPPORTED_TARGETS:
            spec = get_target_spec(target)
            assert spec is not None, f"missing spec for {target}"
            assert spec.target == target
            assert spec.block_key == "mcpServers"
            assert len(spec.candidates) >= 1

    def test_unknown_target_returns_none(self):
        assert get_target_spec("not_a_target") is None
