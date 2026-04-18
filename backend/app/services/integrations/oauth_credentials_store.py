"""Runtime OAuth credentials store.

When the operator pastes Google / Notion / Slack OAuth app credentials
into the setup modal on the Connections page, those values need to be
available to ``ConnectorOAuthService`` without a process restart. This
module provides a simple JSON-backed store that ``_get_credential``
checks BEFORE falling back to ``settings`` (env-based).

File location: ``backend/.daena_oauth_overrides.json`` (gitignored).
Structure::

    {
      "google_client_id": "123-abc.apps.googleusercontent.com",
      "google_client_secret": "GOCSPX-...",
      "github_client_id": "...",
      ...
    }

Thread-safety: reads are frequent, writes are rare (user clicks Save).
Guarded by a module-level asyncio lock; file writes are atomic via
write-to-temp-then-rename.

Security notes
--------------
* File is gitignored (see .gitignore entry) so credentials never land in
  version control.
* Permissions: on POSIX we ``chmod 0o600`` after write. On Windows we
  rely on user-profile ACLs.
* For production / multi-tenant, this should be replaced by the
  AES-256 secret vault (planned per CLAUDE.md). For local + single-user
  use, a 0o600 JSON file is an acceptable first step.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_STORE_PATH = Path(__file__).resolve().parents[3] / ".daena_oauth_overrides.json"
_lock = asyncio.Lock()
_cache: dict[str, str] | None = None


def _load_sync() -> dict[str, str]:
    """Read the JSON store. Returns an empty dict on first run."""
    if not _STORE_PATH.exists():
        return {}
    try:
        return json.loads(_STORE_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "oauth_creds_store.unreadable", path=str(_STORE_PATH), error=str(exc),
        )
        return {}


def get_override(field: str) -> str:
    """Return the override value for ``field`` or empty string.

    Synchronous because ``_get_credential`` (the caller) is sync. The
    cache is populated lazily on first read.
    """
    global _cache
    if _cache is None:
        _cache = _load_sync()
    return _cache.get(field, "")


async def set_override(field: str, value: str) -> None:
    """Persist a credential override and update the cache atomically."""
    global _cache
    async with _lock:
        if _cache is None:
            _cache = _load_sync()
        _cache[field] = value
        # Atomic write: write to tmp path then rename so a crash mid-write
        # cannot leave the store partially overwritten.
        tmp = _STORE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
        os.replace(tmp, _STORE_PATH)
        # POSIX only: lock down permissions. On Windows this is a no-op.
        try:
            _STORE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    logger.info(
        "oauth_creds_store.override_set",
        field=field,
        value_len=len(value),
    )


async def set_overrides(fields: dict[str, str]) -> None:
    """Persist multiple overrides in one atomic write."""
    global _cache
    async with _lock:
        if _cache is None:
            _cache = _load_sync()
        _cache.update(fields)
        tmp = _STORE_PATH.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
        os.replace(tmp, _STORE_PATH)
        try:
            _STORE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    logger.info(
        "oauth_creds_store.overrides_set",
        fields=list(fields.keys()),
    )


def list_configured_fields() -> list[str]:
    """Return names of all fields that currently have an override."""
    global _cache
    if _cache is None:
        _cache = _load_sync()
    return sorted(_cache.keys())


def reset_cache_for_tests() -> None:
    """Clear the module-level cache. Test-only; not imported at runtime."""
    global _cache
    _cache = None


def _get_settings_and_override(setting_name: str, settings_value: Any) -> str:
    """Resolution helper used by oauth_service.

    Override wins over settings value. This matches operator intent --
    when they explicitly configure via the UI, that is the source of
    truth over whatever was in .env at process start.
    """
    override = get_override(setting_name)
    if override:
        return override
    return str(settings_value or "")
