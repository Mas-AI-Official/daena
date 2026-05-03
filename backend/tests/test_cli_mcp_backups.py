"""PR-CONN-MCP-INSTALL-RESTORE -- backup discovery + restore tests.

Pins the contract of ``cli_mcp_backups``:

  1. _is_valid_backup_filename rejects path traversal, accepts the
     strict daena-backup pattern only
  2. list_backups returns empty list when no backups exist
  3. list_backups discovers + parses + sorts newest-first
  4. list_backups never returns file contents (only metadata)
  5. restore_backup rejects unsupported target -> target_unsupported
  6. restore_backup rejects backup with path components -> backup_invalid_filename
  7. restore_backup rejects backup not matching pattern -> backup_invalid_filename
  8. restore_backup rejects backup outside config dir -> backup_outside_config_dir
  9. restore_backup rejects malformed backup JSON -> backup_parse_error
 10. restore_backup creates a pre-restore backup of CURRENT config
 11. restore_backup atomically writes the backup payload over current config
 12. restore_backup never returns file contents
 13. Endpoint: list returns backups
 14. Endpoint: restore happy path
 15. Endpoint: invalid target -> 400
 16. Endpoint: path traversal blocked
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.identity import Tenant
from app.services.connection_v2.cli_mcp_backups import (
    FAIL_BACKUP_INVALID,
    FAIL_BACKUP_INVALID_FILENAME,
    FAIL_BACKUP_NOT_FOUND,
    FAIL_BACKUP_OUTSIDE_CONFIG_DIR,
    FAIL_BACKUP_PARSE_ERROR,
    FAIL_TARGET_UNSUPPORTED,
    _is_valid_backup_filename,
    list_backups,
    restore_backup,
)
from app.services.connection_v2.cli_mcp_writer import reset_target_cache


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """Idempotent + flush-only so we don't pollute downstream tests."""
    from sqlalchemy import select
    existing = (
        await db_session.execute(select(Tenant).where(Tenant.id == test_tenant_id))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    tenant = Tenant(id=test_tenant_id, name="T", slug="t", settings={})
    db_session.add(tenant)
    await db_session.flush()
    return tenant


@pytest.fixture
def patched_home(monkeypatch, tmp_path: Path):
    """Repoint Path.home() + reset writer cache so each test uses tmp."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    reset_target_cache()
    yield tmp_path
    reset_target_cache()


def _seed_config(tmp_path: Path, name: str, payload: dict) -> Path:
    """Drop a JSON config in tmp_path / name."""
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return p


def _seed_backup(config_path: Path, timestamp: str, payload: dict) -> Path:
    """Drop a `<config>.daena-backup-<TS>.json` next to config_path."""
    name = f"{config_path.name}.daena-backup-{timestamp}.json"
    p = config_path.with_name(name)
    p.write_text(json.dumps(payload))
    return p


# ──────────────────────────────────────────────────────────────────
# 1. Filename validation
# ──────────────────────────────────────────────────────────────────


class TestFilenameValidation:
    def test_valid_pattern_accepted(self):
        assert _is_valid_backup_filename(
            ".claude.json.daena-backup-20260502T203134Z.json",
            ".claude.json",
        )

    def test_path_traversal_rejected(self):
        for danger in (
            "../../etc/passwd",
            "..\\..\\Windows\\System32\\config",
            "subdir/.claude.json.daena-backup-20260502T203134Z.json",
            "subdir\\.claude.json.daena-backup-20260502T203134Z.json",
            ".",
            "..",
        ):
            assert not _is_valid_backup_filename(danger, ".claude.json"), (
                f"validator should reject {danger!r}"
            )

    def test_wrong_basename_rejected(self):
        # Backup for a DIFFERENT config -- should not list against
        # this target.
        assert not _is_valid_backup_filename(
            "settings.json.daena-backup-20260502T203134Z.json",
            ".claude.json",
        )

    def test_bad_timestamp_rejected(self):
        for bad_ts in (
            ".claude.json.daena-backup-foo.json",
            ".claude.json.daena-backup-20260502.json",
            ".claude.json.daena-backup-20260502T203134.json",  # no Z
            ".claude.json.daena-backup-2026-05-02T20:31:34Z.json",  # ISO format
        ):
            assert not _is_valid_backup_filename(bad_ts, ".claude.json"), (
                f"validator should reject {bad_ts!r}"
            )

    def test_non_json_rejected(self):
        assert not _is_valid_backup_filename(
            ".claude.json.daena-backup-20260502T203134Z.txt",
            ".claude.json",
        )


# ──────────────────────────────────────────────────────────────────
# 2-4. list_backups
# ──────────────────────────────────────────────────────────────────


class TestListBackups:
    def test_empty_when_no_backups_exist(self, patched_home):
        # No config + no backups -- list returns empty.
        report = list_backups(target="claude_code")
        assert report.failure_reason is None
        assert report.backups == []

    def test_finds_and_sorts_newest_first(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {"keep": "me"})
        # Three backups with strict-pattern timestamps, written out of order.
        _seed_backup(cfg, "20260101T120000Z", {"v": 1})
        _seed_backup(cfg, "20260301T120000Z", {"v": 3})
        _seed_backup(cfg, "20260201T120000Z", {"v": 2})

        report = list_backups(target="claude_code")
        assert report.failure_reason is None
        assert len(report.backups) == 3
        # Newest first
        ts = [b.timestamp for b in report.backups]
        assert ts == sorted(ts, reverse=True)
        # Each entry carries a basename, never a path
        for b in report.backups:
            assert "/" not in b.filename
            assert "\\" not in b.filename
            assert b.filename.endswith(".json")
            assert b.size_bytes > 0
            assert b.valid_json is True

    def test_ignores_non_backup_files(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {})
        # A bunch of random siblings the operator might have lying
        # around -- list should ignore them.
        (patched_home / "random.txt").write_text("noise")
        (patched_home / ".claude.json.bak").write_text("old-style backup")
        (patched_home / "settings.json.daena-backup-20260101T000000Z.json").write_text("{}")
        # And one valid backup so the result isn't empty.
        _seed_backup(cfg, "20260301T120000Z", {})

        report = list_backups(target="claude_code")
        assert len(report.backups) == 1
        assert report.backups[0].filename == ".claude.json.daena-backup-20260301T120000Z.json"

    def test_marks_malformed_backup_as_invalid_json(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {})
        bad = cfg.with_name(f"{cfg.name}.daena-backup-20260301T120000Z.json")
        bad.write_text("{ this is not json")

        report = list_backups(target="claude_code")
        assert len(report.backups) == 1
        assert report.backups[0].valid_json is False

    def test_payload_never_carries_file_contents(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {})
        # Plant a sentinel inside the backup. The list payload must
        # not echo it.
        sentinel = "sk-secret-value-do-not-leak-7777"  # noqa: S105
        _seed_backup(cfg, "20260301T120000Z", {
            "mcpServers": {"x": {"command": "y", "env": {"K": sentinel}}},
        })

        report = list_backups(target="claude_code")
        body = json.dumps(report.to_dict())
        assert sentinel not in body, (
            "list_backups LEAKED file contents into response payload"
        )


# ──────────────────────────────────────────────────────────────────
# 5-9. restore_backup safety rules
# ──────────────────────────────────────────────────────────────────


class TestRestoreSafety:
    def test_unsupported_target(self, patched_home):
        report = restore_backup(
            target="not-a-target",
            backup_filename=".claude.json.daena-backup-20260101T000000Z.json",
        )
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_TARGET_UNSUPPORTED)

    def test_path_components_rejected(self, patched_home):
        _seed_config(patched_home, ".claude.json", {})
        for danger in (
            "../../etc/passwd",
            "..\\..\\Windows\\System32",
            "subdir/.claude.json.daena-backup-20260101T000000Z.json",
        ):
            report = restore_backup(target="claude_code", backup_filename=danger)
            assert report.success is False
            assert report.failure_reason.startswith(FAIL_BACKUP_INVALID_FILENAME)

    def test_wrong_pattern_rejected(self, patched_home):
        _seed_config(patched_home, ".claude.json", {})
        report = restore_backup(
            target="claude_code",
            backup_filename=".claude.json.bak",  # not the daena pattern
        )
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_BACKUP_INVALID_FILENAME)

    def test_missing_backup_file(self, patched_home):
        _seed_config(patched_home, ".claude.json", {})
        report = restore_backup(
            target="claude_code",
            backup_filename=".claude.json.daena-backup-20260101T000000Z.json",
        )
        # File does not exist on disk.
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_BACKUP_NOT_FOUND)

    def test_malformed_backup_rejected(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {"keep": "me"})
        bad = cfg.with_name(f"{cfg.name}.daena-backup-20260101T000000Z.json")
        bad.write_text("{ broken json")

        report = restore_backup(
            target="claude_code",
            backup_filename=bad.name,
        )
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_BACKUP_PARSE_ERROR)
        # Live config was not touched.
        assert json.loads(cfg.read_text()) == {"keep": "me"}

    def test_non_object_root_rejected(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {"keep": "me"})
        bad = cfg.with_name(f"{cfg.name}.daena-backup-20260101T000000Z.json")
        bad.write_text(json.dumps([1, 2, 3]))

        report = restore_backup(
            target="claude_code",
            backup_filename=bad.name,
        )
        assert report.success is False
        assert report.failure_reason.startswith(FAIL_BACKUP_INVALID)


# ──────────────────────────────────────────────────────────────────
# 10-12. Restore happy path
# ──────────────────────────────────────────────────────────────────


class TestRestoreHappyPath:
    def test_pre_restore_backup_is_created_and_atomic_write(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {
            "current_state": "live",
            "mcpServers": {"installed-after-backup": {"command": "x"}},
        })
        backup = _seed_backup(cfg, "20260101T120000Z", {
            "current_state": "saved",
            "mcpServers": {"was-here-before": {"command": "y"}},
        })

        report = restore_backup(
            target="claude_code",
            backup_filename=backup.name,
        )
        assert report.success is True, report.failure_reason
        assert report.restored_from == backup.name
        # Pre-restore backup got created (path returned to caller)
        assert report.pre_restore_backup is not None
        pre_backup = Path(report.pre_restore_backup)
        assert pre_backup.exists()
        # Pre-backup carries the LIVE state we just overwrote
        pre_data = json.loads(pre_backup.read_text())
        assert pre_data["current_state"] == "live"
        assert "installed-after-backup" in pre_data["mcpServers"]
        # Live config now matches the backup
        live = json.loads(cfg.read_text())
        assert live["current_state"] == "saved"
        assert "was-here-before" in live["mcpServers"]
        assert "installed-after-backup" not in live["mcpServers"]

    def test_response_payload_carries_no_file_contents(self, patched_home):
        cfg = _seed_config(patched_home, ".claude.json", {"x": 1})
        sentinel = "sk-restore-sentinel-do-not-leak-1111"  # noqa: S105
        backup = _seed_backup(cfg, "20260101T120000Z", {
            "mcpServers": {"x": {"command": "y", "env": {"k": sentinel}}},
        })

        report = restore_backup(
            target="claude_code", backup_filename=backup.name,
        )
        body = json.dumps(report.to_dict())
        assert sentinel not in body, (
            "restore_backup LEAKED file contents into response"
        )

    def test_idempotent_restore_is_safe(self, patched_home):
        # Restoring the SAME backup twice should both succeed (the
        # second call still creates a pre-restore backup of what's
        # now the same content).
        cfg = _seed_config(patched_home, ".claude.json", {"v": 1})
        backup = _seed_backup(cfg, "20260101T120000Z", {"v": 2})

        first = restore_backup(
            target="claude_code", backup_filename=backup.name,
        )
        assert first.success is True
        second = restore_backup(
            target="claude_code", backup_filename=backup.name,
        )
        assert second.success is True


# ──────────────────────────────────────────────────────────────────
# 13-16. Endpoint integration
# ──────────────────────────────────────────────────────────────────


class TestEndpoint:
    async def test_list_endpoint_returns_backups(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        cfg = _seed_config(patched_home, ".claude.json", {})
        _seed_backup(cfg, "20260301T120000Z", {})
        _seed_backup(cfg, "20260101T120000Z", {})

        res = await client.get(
            "/api/v1/connections/v2/marketplace/install-backups?target=claude_code",
            headers=auth_headers,
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        data = body["data"]
        assert data["target"] == "claude_code"
        assert len(data["backups"]) == 2
        # Newest first
        assert data["backups"][0]["timestamp"] >= data["backups"][1]["timestamp"]

    async def test_list_endpoint_unsupported_target_400(
        self, client, auth_headers, seeded_tenant,
    ):
        res = await client.get(
            "/api/v1/connections/v2/marketplace/install-backups?target=vim",
            headers=auth_headers,
        )
        assert res.status_code == 400

    async def test_restore_endpoint_happy_path(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        cfg = _seed_config(patched_home, ".claude.json", {"now": "live"})
        backup = _seed_backup(cfg, "20260101T120000Z", {"now": "old"})

        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-backups/restore",
            headers=auth_headers,
            json={
                "target": "claude_code",
                "backup_filename": backup.name,
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["success"] is True
        assert body["data"]["restored_from"] == backup.name
        # Live config now matches the backup
        assert json.loads(cfg.read_text()) == {"now": "old"}

    async def test_restore_endpoint_path_traversal_blocked(
        self, client, auth_headers, seeded_tenant, patched_home,
    ):
        _seed_config(patched_home, ".claude.json", {"v": 1})
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-backups/restore",
            headers=auth_headers,
            json={
                "target": "claude_code",
                "backup_filename": "../../etc/passwd",
            },
        )
        # Endpoint accepts the request shape (200) but the inner
        # restore returns success=False with backup_invalid_filename.
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is False
        assert body["data"]["failure_reason"].startswith(FAIL_BACKUP_INVALID_FILENAME)

    async def test_restore_endpoint_invalid_target_returns_422(
        self, client, auth_headers, seeded_tenant,
    ):
        # Pydantic Literal validation -> 422
        res = await client.post(
            "/api/v1/connections/v2/marketplace/install-backups/restore",
            headers=auth_headers,
            json={
                "target": "vim",
                "backup_filename": ".claude.json.daena-backup-20260101T000000Z.json",
            },
        )
        assert res.status_code == 422
