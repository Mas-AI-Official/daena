"""Runtime LLM provider API-key store.

PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT (2026-05-03): the operator pastes
provider API keys (Anthropic / OpenAI / Gemini / Groq / Perplexity /
OpenRouter / Together) into Connections -> Configure or
/account#provider-keys. Those values need to be available to the
ModelRegistry without a process restart AND must survive restart so the
marketplace doesn't flip back to Configure on every reboot.

This module is the SIBLING of ``oauth_credentials_store.py``. Same
mechanism (atomic JSON file + asyncio lock + cache + chmod 0600), same
override-wins-over-settings semantics. Kept separate because:

* OAuth client credentials and provider API keys have different
  lifecycles (OAuth client ids enable a consent flow; API keys are
  pasted once and read every request).
* Mixing them in one file would complicate audit + future migration
  to the AES-256 vault (vault_v2.encrypt_secret).
* ``oauth_credentials_store.py`` is a CLAUDE.md Rule 18 protected file;
  extending it without an explicit DELETE-PR is forbidden.

File location: ``backend/.daena_provider_overrides.json`` (gitignored).

Structure::

    {
      "anthropic_api_key": "sk-ant-...",
      "openai_api_key": "sk-...",
      "gemini_api_key": "...",
      ...
    }

Field names mirror ``app.core.config.Settings`` attribute names so the
hydration step can do ``setattr(settings, name, value)`` without a
mapping table.

Honesty contract (per project Rule 17):
* The cache + file are the SOLE persistence for runtime-pasted keys.
* No endpoint EVER returns the raw key value after save. The store
  exposes only ``configured: bool`` and ``last_updated`` per provider.
* The ``register_fingerprint`` hook into Asset Shield runs on every
  save so the egress filter can scan outbound bytes for accidental
  leaks (per Asset Shield asset_class="api_keys").

Security notes
--------------
* File is gitignored so credentials never land in version control.
* Permissions: on POSIX we ``chmod 0o600`` after write. On Windows we
  rely on user-profile ACLs.
* For production / multi-tenant, this should be replaced by the
  vault_v2 envelope-encrypted ``Secret`` model (per ADR-002 D-003,
  Phase 4b). For local + single-user use, a 0o600 JSON file is the
  same acceptable first step that ``oauth_credentials_store.py`` ships
  with today.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

# ──────────────────────────────────────────────────────────────────
# Field allowlist
# ──────────────────────────────────────────────────────────────────


# Only fields in this set may be written through the store. Each maps
# 1:1 to a Settings attribute and to a ModelProvider key consumer.
# Keeping this explicit (not derived from Settings introspection)
# blocks accidental writes of unrelated settings (e.g. session secrets,
# JWT keys) through the same code path.
PROVIDER_KEY_FIELDS: tuple[str, ...] = (
    "anthropic_api_key",
    "openai_api_key",
    "gemini_api_key",
    "groq_api_key",
    "perplexity_api_key",
    "openrouter_api_key",
    "together_api_key",
)


# Display metadata mirrors marketplace_catalog.py's provider entries
# so the UI doesn't need a second source of truth. Slug is the
# /account/provider-keys/{slug} path segment; settings_field is the
# Settings attribute the override applies to.
PROVIDER_DISPLAY: dict[str, dict[str, str]] = {
    "anthropic": {
        "settings_field": "anthropic_api_key",
        "display_name": "Anthropic",
        "marketplace_id": "provider-anthropic",
        "key_hint": "sk-ant-...",
    },
    "openai": {
        "settings_field": "openai_api_key",
        "display_name": "OpenAI",
        "marketplace_id": "provider-openai",
        "key_hint": "sk-...",
    },
    "gemini": {
        "settings_field": "gemini_api_key",
        "display_name": "Google Gemini",
        "marketplace_id": "provider-google-gemini",
        "key_hint": "AI...",
    },
    "groq": {
        "settings_field": "groq_api_key",
        "display_name": "Groq",
        "marketplace_id": "provider-groq",
        "key_hint": "gsk_...",
    },
    "perplexity": {
        "settings_field": "perplexity_api_key",
        "display_name": "Perplexity",
        "marketplace_id": "provider-perplexity",
        "key_hint": "pplx-...",
    },
    "openrouter": {
        "settings_field": "openrouter_api_key",
        "display_name": "OpenRouter",
        "marketplace_id": "provider-openrouter",
        "key_hint": "sk-or-...",
    },
    "together": {
        "settings_field": "together_api_key",
        "display_name": "Together",
        "marketplace_id": "provider-together",
        "key_hint": "...",
    },
}

SLUG_TO_FIELD: dict[str, str] = {
    slug: meta["settings_field"] for slug, meta in PROVIDER_DISPLAY.items()
}
FIELD_TO_SLUG: dict[str, str] = {
    meta["settings_field"]: slug for slug, meta in PROVIDER_DISPLAY.items()
}


# ──────────────────────────────────────────────────────────────────
# File-backed store
# ──────────────────────────────────────────────────────────────────


_STORE_PATH = Path(__file__).resolve().parents[3] / ".daena_provider_overrides.json"
_lock = asyncio.Lock()
_cache: dict[str, dict[str, str]] | None = None


def _load_sync() -> dict[str, dict[str, str]]:
    """Read the JSON store. Returns an empty dict on first run.

    Schema is ``{field_name: {"value": str, "updated_at": iso8601}}``.
    Legacy plain-string format ``{field_name: "value"}`` is migrated
    on read so we can roll forward without data loss.
    """
    if not _STORE_PATH.exists():
        return {}
    try:
        raw = json.loads(_STORE_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "provider_keys_store.unreadable",
            path=str(_STORE_PATH),
            error=str(exc),
        )
        return {}

    out: dict[str, dict[str, str]] = {}
    for field, payload in (raw or {}).items():
        if field not in PROVIDER_KEY_FIELDS:
            continue
        if isinstance(payload, str):
            # Legacy migration
            out[field] = {"value": payload, "updated_at": ""}
        elif isinstance(payload, dict) and "value" in payload:
            out[field] = {
                "value": str(payload.get("value", "")),
                "updated_at": str(payload.get("updated_at", "")),
            }
    return out


def _ensure_cache() -> dict[str, dict[str, str]]:
    global _cache
    if _cache is None:
        _cache = _load_sync()
    return _cache


def _atomic_write(payload: dict[str, dict[str, str]]) -> None:
    tmp = _STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, _STORE_PATH)
    try:
        _STORE_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Windows / non-POSIX: rely on user-profile ACLs.
        pass


def get_override(field: str) -> str:
    """Return the stored value for ``field`` or empty string.

    Read-only, synchronous. The cache hydrates on first call. Callers
    in the hot path (settings hydration, dynamic_model_service)
    consume this to merge stored overrides over the .env baseline.
    """
    if field not in PROVIDER_KEY_FIELDS:
        return ""
    cache = _ensure_cache()
    return cache.get(field, {}).get("value", "")


def get_metadata(field: str) -> dict[str, str | bool]:
    """Return display-safe metadata for ``field`` -- never the value.

    Shape: ``{"configured": bool, "last_updated": iso8601 | ""}``.
    Used by the /account/provider-keys list endpoint.
    """
    if field not in PROVIDER_KEY_FIELDS:
        return {"configured": False, "last_updated": ""}
    cache = _ensure_cache()
    entry = cache.get(field, {})
    return {
        "configured": bool(entry.get("value")),
        "last_updated": entry.get("updated_at", ""),
    }


async def set_override(field: str, value: str) -> None:
    """Persist a provider key override and update the cache atomically.

    Writes to a temp file then renames so a crash mid-write cannot
    leave the store partially overwritten. Refuses fields outside
    ``PROVIDER_KEY_FIELDS`` to block accidental writes of unrelated
    settings via this code path.
    """
    if field not in PROVIDER_KEY_FIELDS:
        raise ValueError(
            f"provider_keys_store: refused write to unknown field {field!r}; "
            f"allowed: {sorted(PROVIDER_KEY_FIELDS)}"
        )
    if not value:
        raise ValueError("provider_keys_store: refused to write empty value")

    global _cache
    async with _lock:
        cache = _ensure_cache()
        cache[field] = {
            "value": value,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        _atomic_write(cache)
        _cache = cache

    # Egress-filter fingerprint registration. Asset Shield's
    # ``register_fingerprint`` stores SHA-256 prefixes only -- the raw
    # value never leaves this process. Best-effort: if the asset shield
    # isn't loaded we still complete the save. Logged length only.
    try:
        from app.services.security.asset_shield.vault_adapter import (
            register_fingerprint,
        )
        register_fingerprint(
            asset_id=f"provider_key:{field}",
            raw_value=value,
            asset_class="api_keys",
        )
    except Exception:
        # Don't fail the user-facing save if the asset shield import
        # isn't wired in this environment (tests / minimal boot).
        logger.debug(
            "provider_keys_store.fingerprint_skipped", field=field, exc_info=True,
        )

    logger.info(
        "provider_keys_store.override_set",
        field=field,
        value_len=len(value),
        # ^^ length only -- never log the value itself.
    )


async def clear_override(field: str) -> bool:
    """Remove an override. Returns True if a value was removed."""
    if field not in PROVIDER_KEY_FIELDS:
        return False

    global _cache
    async with _lock:
        cache = _ensure_cache()
        if field not in cache:
            return False
        cache.pop(field, None)
        _atomic_write(cache)
        _cache = cache

    logger.info("provider_keys_store.override_cleared", field=field)
    return True


def list_configured_fields() -> list[str]:
    """Return field names that currently have a non-empty override."""
    cache = _ensure_cache()
    return sorted(
        field for field, entry in cache.items() if entry.get("value")
    )


def list_provider_status() -> list[dict[str, str | bool]]:
    """Return display-safe status rows for every supported provider.

    Each row carries: slug, settings_field, display_name,
    marketplace_id, key_hint, configured (bool), last_updated (iso).
    Never carries the value.
    """
    return [
        {
            "slug": slug,
            "settings_field": meta["settings_field"],
            "display_name": meta["display_name"],
            "marketplace_id": meta["marketplace_id"],
            "key_hint": meta["key_hint"],
            **get_metadata(meta["settings_field"]),
        }
        for slug, meta in PROVIDER_DISPLAY.items()
    ]


def hydrate_settings(settings_obj) -> list[str]:
    """Apply every stored override onto a Settings instance in place.

    Called once at startup, BEFORE ``ModelRegistry.initialize()``,
    so the registry sees stored keys naturally and registers the
    corresponding providers without a separate provision step.

    Returns the list of fields that were applied. Idempotent: calling
    twice with the same store contents is safe.
    """
    applied: list[str] = []
    cache = _ensure_cache()
    for field in PROVIDER_KEY_FIELDS:
        entry = cache.get(field, {})
        value = entry.get("value", "")
        if not value:
            continue
        setattr(settings_obj, field, value)
        applied.append(field)
    if applied:
        logger.info(
            "provider_keys_store.hydrated",
            fields=applied,
            count=len(applied),
        )
    return applied


def reset_cache_for_tests() -> None:
    """Clear the module-level cache. Test-only; not imported at runtime."""
    global _cache
    _cache = None


def _store_path_for_tests() -> Path:
    """Expose the store path so tests can monkeypatch it cleanly."""
    return _STORE_PATH


__all__ = [
    "FIELD_TO_SLUG",
    "PROVIDER_DISPLAY",
    "PROVIDER_KEY_FIELDS",
    "SLUG_TO_FIELD",
    "clear_override",
    "get_metadata",
    "get_override",
    "hydrate_settings",
    "list_configured_fields",
    "list_provider_status",
    "reset_cache_for_tests",
    "set_override",
]
