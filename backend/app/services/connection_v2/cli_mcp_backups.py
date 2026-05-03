"""CliMcpBackups -- discover + restore backups created by the MCP writer.

PR-CONN-MCP-INSTALL-RESTORE (2026-05-02). Counterpart to
``cli_mcp_writer.atomic_write_json``: that function lays down
``<config>.daena-backup-<TS>.json`` files before each overwrite, and
this module:

  1. Lists every backup that lives next to a supported target config.
  2. Restores a selected backup with the same safety contract the
     original write used (pre-restore backup of CURRENT config, temp
     file in same directory, atomic rename).

Hard rules honored (founder):
  * NEVER returns file contents -- only filename / timestamp / size.
  * NEVER restores from a path outside the target's config directory
    (defense against path traversal).
  * NEVER restores a backup whose filename does not match the strict
    pattern ``<config_basename>.daena-backup-<UTC-TIMESTAMP>.json``.
  * NEVER restores a backup whose JSON is malformed (validates parse
    BEFORE touching the live config).
  * NEVER skips the pre-restore backup. Even if the operator
    "Restore"s by accident they can roll forward to the previous
    state.
  * Atomic rename via the same ``atomic_write_json`` helper used by
    the original writer -- one source of truth for "how Daena writes
    a JSON file safely."

Failure prefixes (frontend matches without parsing free-form text):
  - target_unsupported
  - config_path_missing
  - backup_invalid_filename
  - backup_outside_config_dir
  - backup_not_found
  - backup_parse_error
  - backup_invalid
  - restore_write_failed
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.connection_v2.cli_mcp_writer import (
    SUPPORTED_TARGETS,
    atomic_write_json,
    get_target_spec,
    resolve_path,
)

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Failure prefixes
# ──────────────────────────────────────────────────────────────────


FAIL_TARGET_UNSUPPORTED = "target_unsupported"
FAIL_CONFIG_PATH_MISSING = "config_path_missing"
FAIL_BACKUP_INVALID_FILENAME = "backup_invalid_filename"
FAIL_BACKUP_OUTSIDE_CONFIG_DIR = "backup_outside_config_dir"
FAIL_BACKUP_NOT_FOUND = "backup_not_found"
FAIL_BACKUP_PARSE_ERROR = "backup_parse_error"
FAIL_BACKUP_INVALID = "backup_invalid"
FAIL_RESTORE_WRITE_FAILED = "restore_write_failed"


_REASON_PREVIEW = 200


def _reason(prefix: str, detail: str = "") -> str:
    if not detail:
        return prefix
    cleaned = detail.replace("\n", " ").replace("\r", " ").strip()
    if len(cleaned) > _REASON_PREVIEW:
        cleaned = cleaned[:_REASON_PREVIEW] + "..."
    return f"{prefix}: {cleaned}"


# Strict pattern for a Daena backup filename:
#   <config_basename>.daena-backup-YYYYMMDDTHHMMSSZ.json
# Examples that match:
#   .claude.json.daena-backup-20260502T203134Z.json
#   config.json.daena-backup-20260502T203134Z.json
# Examples that DO NOT match:
#   ..\\..\\evil.daena-backup-20260502T203134Z.json (path components)
#   .claude.json.daena-backup-foo.json (timestamp shape wrong)
#   .claude.json (not a backup)
_BACKUP_TIMESTAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")


def _is_valid_backup_filename(filename: str, config_basename: str) -> bool:
    """True iff filename is a Daena backup for the given config basename.

    Filename MUST be a basename (no path components) and MUST match
    the strict ``<config_basename>.daena-backup-<TS>.json`` pattern.
    """
    if not filename:
        return False
    # Reject anything with a path component -- defends against
    # "..\\..\\etc\\passwd"-style traversal.
    if "/" in filename or "\\" in filename:
        return False
    if filename in (".", ".."):
        return False
    suffix = ".daena-backup-"
    expected_prefix = f"{config_basename}{suffix}"
    if not filename.startswith(expected_prefix):
        return False
    if not filename.endswith(".json"):
        return False
    # Extract the timestamp segment between the prefix and .json
    middle = filename[len(expected_prefix): -len(".json")]
    return bool(_BACKUP_TIMESTAMP_RE.match(middle))


def _parse_backup_timestamp(filename: str, config_basename: str) -> datetime | None:
    """Pull the UTC timestamp out of a validated backup filename."""
    suffix = ".daena-backup-"
    prefix = f"{config_basename}{suffix}"
    if not filename.startswith(prefix) or not filename.endswith(".json"):
        return None
    middle = filename[len(prefix): -len(".json")]
    if not _BACKUP_TIMESTAMP_RE.match(middle):
        return None
    try:
        return datetime.strptime(middle, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────────
# Discovery
# ──────────────────────────────────────────────────────────────────


@dataclass
class BackupEntry:
    """One backup file we found next to a target's config.

    NEVER carries file contents. ``size_bytes`` is the only payload
    measurement -- helpful for the operator to spot wildly different
    backup sizes (could indicate a partial write from before backup
    safety was added).
    """

    filename: str           # basename only (no directory)
    timestamp: str          # ISO8601 UTC parsed from filename
    size_bytes: int
    valid_json: bool        # cheap parse-check at list time

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "timestamp": self.timestamp,
            "size_bytes": self.size_bytes,
            "valid_json": self.valid_json,
        }


@dataclass
class ListReport:
    """Outcome of listing backups for a target."""

    target: str
    target_display_name: str
    config_path: str | None
    backups: list[BackupEntry] = field(default_factory=list)
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_display_name": self.target_display_name,
            "config_path": self.config_path,
            "backups": [b.to_dict() for b in self.backups],
            "failure_reason": self.failure_reason,
        }


def list_backups(*, target: str) -> ListReport:
    """Find every Daena backup that lives next to the target's config.

    Returns a ListReport with the backups sorted newest-first.
    Resolves the target's config path the same way the writer does:
    prefers an existing candidate; if NONE exist we still return an
    empty list (no backups can exist where there is no config).
    """
    spec = get_target_spec(target)
    if spec is None:
        return ListReport(
            target=target, target_display_name=target,
            config_path=None,
            failure_reason=_reason(
                FAIL_TARGET_UNSUPPORTED,
                f"{target!r} not in {SUPPORTED_TARGETS}",
            ),
        )

    # We list backups that live next to ANY candidate path that
    # currently exists OR (when none exist) the first candidate. This
    # mirrors the writer's resolution policy so list <-> restore are
    # always operating on the same directory.
    resolution = resolve_path(spec, allow_create=False)
    target_path = resolution.existing
    if target_path is None and resolution.candidates_tried:
        # No config exists yet; backups still might exist at the
        # first candidate's location if the operator deleted the
        # config but kept the backup. Honor that.
        target_path = resolution.candidates_tried[0]

    if target_path is None:
        return ListReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=None,
            failure_reason=_reason(
                FAIL_CONFIG_PATH_MISSING,
                "no candidate paths defined for target",
            ),
        )

    config_basename = target_path.name
    parent = target_path.parent
    backups: list[BackupEntry] = []
    if parent.is_dir():
        try:
            for entry in parent.iterdir():
                if not entry.is_file():
                    continue
                if not _is_valid_backup_filename(entry.name, config_basename):
                    continue
                ts = _parse_backup_timestamp(entry.name, config_basename)
                if ts is None:
                    continue
                size = 0
                valid_json = False
                try:
                    raw = entry.read_text(encoding="utf-8")
                    size = len(raw.encode("utf-8"))
                    json.loads(raw)
                    valid_json = True
                except (OSError, json.JSONDecodeError):
                    valid_json = False
                backups.append(BackupEntry(
                    filename=entry.name,
                    timestamp=ts.isoformat(),
                    size_bytes=size,
                    valid_json=valid_json,
                ))
        except OSError as exc:
            logger.warning(
                "cli_mcp_backups.list_failed",
                target=target,
                error_type=type(exc).__name__,
            )

    backups.sort(key=lambda b: b.timestamp, reverse=True)
    return ListReport(
        target=spec.target, target_display_name=spec.display_name,
        config_path=str(target_path),
        backups=backups,
    )


# ──────────────────────────────────────────────────────────────────
# Restore
# ──────────────────────────────────────────────────────────────────


@dataclass
class RestoreReport:
    """Outcome of a restore attempt. Never includes file contents."""

    target: str
    target_display_name: str
    config_path: str | None
    restored_from: str | None        # backup filename that was restored
    pre_restore_backup: str | None   # full path of the safety net we wrote
    success: bool
    failure_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "target_display_name": self.target_display_name,
            "config_path": self.config_path,
            "restored_from": self.restored_from,
            "pre_restore_backup": self.pre_restore_backup,
            "success": self.success,
            "failure_reason": self.failure_reason,
        }


def restore_backup(*, target: str, backup_filename: str) -> RestoreReport:
    """Restore the chosen backup over the target's current config.

    Sequence (every step fail-closed):
      1. Resolve target spec + config path. Refuse on
         ``target_unsupported`` / ``config_path_missing``.
      2. Validate ``backup_filename`` against the strict pattern AND
         confirm it has no path components. Defends against
         ``..\\..\\etc\\passwd``-style traversal.
      3. Resolve the backup file path = ``<config_dir> / backup_filename``.
         Confirm the resolved path's parent IS the config directory
         (defense in depth -- catches symlink trickery).
      4. Confirm the backup file exists.
      5. Read the backup + validate it parses as JSON. Refuse on
         ``backup_parse_error``.
      6. Confirm the parsed root is a JSON object (matches what the
         writer ever produces). Refuse on ``backup_invalid``.
      7. Write a pre-restore backup of the CURRENT config (when the
         current config exists) using the same atomic_write_json
         helper -- this re-uses the writer's backup naming so the
         operator can roll forward by re-restoring.
      8. Write the backup payload to the live config via
         atomic_write_json (with ``backup=False`` because step 7
         already created the safety net).
    """
    spec = get_target_spec(target)
    if spec is None:
        return RestoreReport(
            target=target, target_display_name=target,
            config_path=None, restored_from=None, pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_TARGET_UNSUPPORTED,
                f"{target!r} not in {SUPPORTED_TARGETS}",
            ),
        )

    resolution = resolve_path(spec, allow_create=False)
    target_path = resolution.existing
    if target_path is None and resolution.candidates_tried:
        target_path = resolution.candidates_tried[0]
    if target_path is None:
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=None, restored_from=None, pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_CONFIG_PATH_MISSING,
                "no candidate paths defined for target",
            ),
        )

    config_basename = target_path.name
    if not _is_valid_backup_filename(backup_filename, config_basename):
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=None, pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_INVALID_FILENAME,
                "filename does not match daena-backup pattern OR contains path components",
            ),
        )

    backup_path = target_path.parent / backup_filename
    # Defense in depth: resolve symlinks + confirm parent matches.
    try:
        resolved_backup = backup_path.resolve(strict=False)
        resolved_parent = target_path.parent.resolve(strict=False)
    except OSError:
        # If resolve raises, fail closed.
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=None, pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_OUTSIDE_CONFIG_DIR,
                "backup path could not be resolved safely",
            ),
        )
    if resolved_backup.parent != resolved_parent:
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=None, pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_OUTSIDE_CONFIG_DIR,
                "backup file's parent directory does not match config dir",
            ),
        )

    if not backup_path.exists() or not backup_path.is_file():
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=backup_filename,
            pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_NOT_FOUND,
                "selected backup file does not exist",
            ),
        )

    try:
        raw = backup_path.read_text(encoding="utf-8")
    except OSError as exc:
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=backup_filename,
            pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_PARSE_ERROR,
                f"backup unreadable ({type(exc).__name__})",
            ),
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=backup_filename,
            pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_PARSE_ERROR,
                f"json: {exc.msg} at line {exc.lineno}",
            ),
        )
    if not isinstance(payload, dict):
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=backup_filename,
            pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_BACKUP_INVALID,
                "backup root is not a JSON object",
            ),
        )

    # ── Pre-restore backup of CURRENT config + atomic write ──
    # atomic_write_json writes the backup of `target_path` (when it
    # exists) automatically. We pass the parsed payload as the new
    # contents.
    try:
        pre_restore_backup_path = atomic_write_json(
            target_path, payload, backup=target_path.exists(),
        )
    except OSError as exc:
        logger.error(
            "cli_mcp_backups.restore_write_failed",
            target=target, backup=backup_filename,
            error_type=type(exc).__name__,
        )
        return RestoreReport(
            target=spec.target, target_display_name=spec.display_name,
            config_path=str(target_path),
            restored_from=backup_filename,
            pre_restore_backup=None,
            success=False,
            failure_reason=_reason(
                FAIL_RESTORE_WRITE_FAILED,
                type(exc).__name__,
            ),
        )

    logger.info(
        "cli_mcp_backups.restored",
        target=target,
        backup_filename=backup_filename,
        pre_restore_backup=str(pre_restore_backup_path) if pre_restore_backup_path else None,
        config_path=str(target_path),
    )
    return RestoreReport(
        target=spec.target, target_display_name=spec.display_name,
        config_path=str(target_path),
        restored_from=backup_filename,
        pre_restore_backup=str(pre_restore_backup_path) if pre_restore_backup_path else None,
        success=True,
        failure_reason=None,
    )


__all__ = [
    "BackupEntry",
    "FAIL_BACKUP_INVALID",
    "FAIL_BACKUP_INVALID_FILENAME",
    "FAIL_BACKUP_NOT_FOUND",
    "FAIL_BACKUP_OUTSIDE_CONFIG_DIR",
    "FAIL_BACKUP_PARSE_ERROR",
    "FAIL_CONFIG_PATH_MISSING",
    "FAIL_RESTORE_WRITE_FAILED",
    "FAIL_TARGET_UNSUPPORTED",
    "ListReport",
    "RestoreReport",
    "list_backups",
    "restore_backup",
]
