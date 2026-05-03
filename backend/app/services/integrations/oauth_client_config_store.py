"""OAuth client config store -- per-provider façade over the shared
``oauth_credentials_store``.

PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS (2026-05-03): the operator pastes
OAuth client_id + client_secret for a provider (Google / GitHub / Slack /
Figma / Canva / etc.) into the Account page. Without this surface, the
only way to configure an OAuth-backed plugin is to hand-edit ``.env`` and
restart -- which means the marketplace card stays stuck on
``Configure``-with-no-input.

This module is a SIBLING of:
  * ``provider_keys_store`` -- LLM API keys (Anthropic / OpenAI / etc.)
  * ``oauth_credentials_store`` -- the underlying file-backed override
    table that ``oauth_service`` already reads from. Per CLAUDE.md
    Rule 18 (protected files), we do NOT modify it -- we wrap it.

Design choice: VALUES persist via ``oauth_credentials_store.set_override``
(unchanged contract, no new file format). METADATA (``last_updated`` per
provider slug) lives in a sidecar JSON file. This means:
  * ``oauth_service._get_credential`` keeps working with zero changes.
  * No duplicate token storage (Rule 12 of the PR brief).
  * The shape on the wire is provider-slug-centric ("google",
    "github", "slack", "figma", "canva") rather than the underlying
    settings-field-centric ("google_client_id", "google_client_secret").

Honesty contract (project Rule 17):
  * GET endpoints return ``configured: bool`` + ``client_id_present:
    bool`` + ``last_updated: iso8601`` only. The values themselves
    NEVER cross the boundary.
  * POST validates the slug against the OAUTH_PROVIDERS table and
    refuses unknown providers with 404 BEFORE touching the store.
  * No endpoint EVER returns the saved client_secret. Even on bulk
    list, the field is omitted from the response shape entirely
    (not nulled -- absent).
  * Logs only log lengths, never the values.
"""

from __future__ import annotations

import asyncio
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

from app.core.logging import get_logger
from app.services.integrations import oauth_credentials_store
from app.services.integrations.oauth_service import OAUTH_PROVIDERS

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────────────────
# Provider slug allowlist + display metadata
# ──────────────────────────────────────────────────────────────────


# One row per OAuth client config the operator can manage. Slugs
# group provider variants that share the same client (e.g. all three
# Google services share google_client_id / google_client_secret).
#
# ``provider_ids`` enumerates the OAUTH_PROVIDERS keys that the slug's
# client config is responsible for. ``client_id_field`` /
# ``client_secret_field`` are the underlying ``Settings`` attribute
# names (and oauth_credentials_store override keys).
#
# Adding a new OAuth client provider means: (a) ensuring an entry
# exists in OAUTH_PROVIDERS in oauth_service.py, (b) adding a row
# here. The two-step gate prevents accidentally exposing a provider
# whose OAuth flow isn't actually wired.
PROVIDER_DISPLAY: dict[str, dict[str, object]] = {
    "google": {
        "display_name": "Google (Gmail / Calendar / Drive)",
        "client_id_field": "google_client_id",
        "client_secret_field": "google_client_secret",
        "provider_ids": ("gmail", "google-calendar", "google-drive"),
        "console_url": "https://console.cloud.google.com/apis/credentials",
        "client_id_hint": "1234567890-abc...apps.googleusercontent.com",
    },
    "github": {
        "display_name": "GitHub",
        "client_id_field": "github_client_id",
        "client_secret_field": "github_client_secret",
        "provider_ids": ("github",),
        "console_url": "https://github.com/settings/developers",
        "client_id_hint": "Iv1.abc...",
    },
    "slack": {
        "display_name": "Slack",
        "client_id_field": "slack_client_id",
        "client_secret_field": "slack_client_secret",
        "provider_ids": ("slack",),
        "console_url": "https://api.slack.com/apps",
        "client_id_hint": "1234567890.0987654321",
    },
    "figma": {
        "display_name": "Figma",
        "client_id_field": "figma_client_id",
        "client_secret_field": "figma_client_secret",
        "provider_ids": ("figma",),
        "console_url": "https://www.figma.com/developers/apps",
        "client_id_hint": "AbCdEf123...",
    },
    "canva": {
        "display_name": "Canva",
        "client_id_field": "canva_client_id",
        "client_secret_field": "canva_client_secret",
        "provider_ids": ("canva",),
        "console_url": "https://www.canva.com/developers/",
        "client_id_hint": "OC-AzC...",
    },
}


def _validate_provider_table_at_import() -> None:
    """Refuse to import if a slug references an OAuth provider id that
    doesn't exist in oauth_service.OAUTH_PROVIDERS. Catches drift the
    moment it happens rather than at first request."""
    for slug, meta in PROVIDER_DISPLAY.items():
        provider_ids = meta["provider_ids"]
        assert isinstance(provider_ids, tuple)
        for pid in provider_ids:
            if pid not in OAUTH_PROVIDERS:
                raise RuntimeError(
                    f"oauth_client_config_store slug {slug!r} references "
                    f"provider_id {pid!r} which is not in OAUTH_PROVIDERS. "
                    f"Add it to oauth_service.OAUTH_PROVIDERS first."
                )


_validate_provider_table_at_import()


# ──────────────────────────────────────────────────────────────────
# Sidecar metadata file (last_updated per slug)
# ──────────────────────────────────────────────────────────────────


_METADATA_PATH = (
    Path(__file__).resolve().parents[3] / ".daena_oauth_client_metadata.json"
)
_lock = asyncio.Lock()
_metadata_cache: dict[str, dict[str, str]] | None = None


def _load_metadata_sync() -> dict[str, dict[str, str]]:
    if not _METADATA_PATH.exists():
        return {}
    try:
        raw = json.loads(_METADATA_PATH.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "oauth_client_config_store.metadata_unreadable",
            path=str(_METADATA_PATH),
            error=str(exc),
        )
        return {}
    out: dict[str, dict[str, str]] = {}
    for slug, payload in (raw or {}).items():
        if slug not in PROVIDER_DISPLAY:
            continue
        if not isinstance(payload, dict):
            continue
        out[slug] = {"last_updated": str(payload.get("last_updated", ""))}
    return out


def _ensure_metadata_cache() -> dict[str, dict[str, str]]:
    global _metadata_cache
    if _metadata_cache is None:
        _metadata_cache = _load_metadata_sync()
    return _metadata_cache


def _atomic_write_metadata(payload: dict[str, dict[str, str]]) -> None:
    tmp = _METADATA_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, _METADATA_PATH)
    try:
        _METADATA_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


# ──────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────


def is_configured(slug: str) -> bool:
    """Return True iff BOTH client_id and client_secret are stored for
    this slug. Either alone is not a usable config -- OAuth needs both
    to start a consent flow."""
    meta = PROVIDER_DISPLAY.get(slug)
    if meta is None:
        return False
    cid = oauth_credentials_store.get_override(str(meta["client_id_field"]))
    csec = oauth_credentials_store.get_override(str(meta["client_secret_field"]))
    return bool(cid) and bool(csec)


def has_client_id(slug: str) -> bool:
    """Tri-state helper: is the client_id alone present? Used by the
    UI to surface a softer "client_id only" warning state if needed."""
    meta = PROVIDER_DISPLAY.get(slug)
    if meta is None:
        return False
    return bool(
        oauth_credentials_store.get_override(str(meta["client_id_field"]))
    )


def get_metadata(slug: str) -> dict[str, str | bool]:
    """Return display-safe metadata for one slug -- never the values."""
    if slug not in PROVIDER_DISPLAY:
        return {"configured": False, "client_id_present": False, "last_updated": ""}
    cache = _ensure_metadata_cache()
    return {
        "configured": is_configured(slug),
        "client_id_present": has_client_id(slug),
        "last_updated": cache.get(slug, {}).get("last_updated", ""),
    }


def list_provider_status() -> list[dict[str, object]]:
    """Return display-safe status rows for every supported OAuth client.

    Each row carries: slug, display_name, client_id_field,
    client_secret_field, provider_ids, console_url, client_id_hint,
    configured, client_id_present, last_updated. NEVER the values.
    """
    rows: list[dict[str, object]] = []
    for slug, meta in PROVIDER_DISPLAY.items():
        rows.append({
            "slug": slug,
            "display_name": meta["display_name"],
            "client_id_field": meta["client_id_field"],
            "client_secret_field": meta["client_secret_field"],
            "provider_ids": list(meta["provider_ids"]),  # type: ignore[arg-type]
            "console_url": meta["console_url"],
            "client_id_hint": meta["client_id_hint"],
            **get_metadata(slug),
        })
    return rows


async def set_client_config(
    slug: str, *, client_id: str, client_secret: str,
) -> dict[str, str | bool]:
    """Persist a (client_id, client_secret) pair for ``slug``.

    Both fields are required and non-empty -- writing only one would
    leave OAuth start in a broken half-configured state. Refuses
    unknown slugs.

    Returns post-write metadata (configured + client_id_present +
    last_updated). NEVER returns the values.
    """
    meta = PROVIDER_DISPLAY.get(slug)
    if meta is None:
        raise ValueError(
            f"oauth_client_config_store: unknown provider slug {slug!r}; "
            f"allowed: {sorted(PROVIDER_DISPLAY)}"
        )
    if not client_id or not client_id.strip():
        raise ValueError("client_id is required")
    if not client_secret or not client_secret.strip():
        raise ValueError("client_secret is required")

    cid_field = str(meta["client_id_field"])
    csec_field = str(meta["client_secret_field"])

    # Atomic-ish bulk write to the underlying store. The shared store's
    # ``set_overrides`` does a single file write covering both fields.
    # Without this we'd risk a half-saved state if a crash occurred
    # between the two single-field writes.
    await oauth_credentials_store.set_overrides({
        cid_field: client_id,
        csec_field: client_secret,
    })

    # Track last_updated in our sidecar.
    global _metadata_cache
    async with _lock:
        cache = _ensure_metadata_cache()
        cache[slug] = {"last_updated": datetime.now(UTC).isoformat()}
        _atomic_write_metadata(cache)
        _metadata_cache = cache

    logger.info(
        "oauth_client_config_store.saved",
        slug=slug,
        client_id_len=len(client_id),
        client_secret_len=len(client_secret),
        # ^^ length only -- never log the value or any prefix of it.
    )

    return get_metadata(slug)


async def clear_client_config(slug: str) -> bool:
    """Remove BOTH client_id and client_secret for ``slug`` from the
    underlying store and metadata sidecar.

    Returns True iff at least one field was removed. False when the
    slug was unknown or already empty.

    Implementation note: the shared ``oauth_credentials_store`` exposes
    no explicit ``unset`` -- it always writes through ``set_override``.
    We achieve "clear" by writing empty strings and pruning the cache
    via a focused rewrite. Empty strings are treated as "no override"
    by ``oauth_service._get_credential`` (the existing fallback to
    Settings kicks in when the override is empty).
    """
    meta = PROVIDER_DISPLAY.get(slug)
    if meta is None:
        return False

    cid_field = str(meta["client_id_field"])
    csec_field = str(meta["client_secret_field"])

    cid_was_set = bool(oauth_credentials_store.get_override(cid_field))
    csec_was_set = bool(oauth_credentials_store.get_override(csec_field))
    removed_any = cid_was_set or csec_was_set

    if removed_any:
        await oauth_credentials_store.set_overrides({
            cid_field: "",
            csec_field: "",
        })

    # Drop the sidecar entry too.
    global _metadata_cache
    async with _lock:
        cache = _ensure_metadata_cache()
        if slug in cache:
            cache.pop(slug, None)
            _atomic_write_metadata(cache)
            _metadata_cache = cache

    logger.info(
        "oauth_client_config_store.cleared",
        slug=slug,
        removed_any=removed_any,
    )
    return removed_any


def reset_cache_for_tests() -> None:
    """Test-only: clear both this module's cache AND the underlying
    oauth_credentials_store cache so the next read sees a fresh file."""
    global _metadata_cache
    _metadata_cache = None
    oauth_credentials_store.reset_cache_for_tests()


def _metadata_path_for_tests() -> Path:
    return _METADATA_PATH


__all__ = [
    "PROVIDER_DISPLAY",
    "clear_client_config",
    "get_metadata",
    "has_client_id",
    "is_configured",
    "list_provider_status",
    "reset_cache_for_tests",
    "set_client_config",
]
