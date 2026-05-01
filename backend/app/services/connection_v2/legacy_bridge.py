"""Phase 4b PR 2: legacy /connections/* <-> ConnectionV2 bridge.

When ``settings.use_connection_registry_v2`` is True, the legacy
ConnectionService routes mirror writes into ConnectionV2 rows AND
derive their response ``status`` from the V2 derived_label instead of
the heuristic ``_status_for_install`` (per ADR-002 D-010).

When the flag is False (production default), this module is a no-op
shim and legacy behavior is preserved byte-for-byte. This is the
soak-window contract per PHASE_4B_DEV_ONLY_GUARDRAILS.

Bridge mapping (legacy ConnectorInstance -> V2 ConnectionV2):
  * tenant_id -> tenant_id
  * connector_id -> resolved via Connector.name -> slug derivation
  * kind        -> PROVIDER (api_key) | OAUTH_APP (oauth) | PLUGIN (none/other)
  * slug        -> "{name-lower-dashed}-{user-id-prefix-8}" (unique per user)
  * auth_method -> connector.auth_type -> AuthMethod enum
  * imported    -> True iff a ConnectorInstance row was written
  * detected/configured -> True (legacy path created the row)
  * reachable/authenticated/callable -> NOT touched here -- only a
    real probe (Phase 4b PR 2 adapters) can flip these. The label
    we report back is therefore "installable" / "needs_auth" /
    "healthy" depending on the probe state, NOT on credential
    presence (which is the D-010 violation).

V2 label -> legacy ConnectorStatus:
  healthy / healthy_stale / degraded / degraded_stale -> CONNECTED
  needs_auth / auth_pending                           -> NEEDS_REAUTH
  installable / needs_config / installing             -> INSTALLED
  failed / unreachable / unknown                      -> ERROR
  disabled                                            -> DISCONNECTED
  archived                                            -> DISCONNECTED
  probing                                             -> CONNECTED (op in flight)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import ConnectorStatus
from app.core.logging import get_logger
from app.core.vault_boot import load_kek_from_env
from app.models.connection_v2 import (
    AuthMethod as V2AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.models.connections import Connector
from app.services.connection_v2 import ConnectionRegistryV2

logger = get_logger(__name__)


def is_v2_enabled() -> bool:
    """Return True iff USE_CONNECTION_REGISTRY_V2 is on.

    Reading get_settings() is dirt cheap (cached), so this is fine in
    request hot paths.
    """
    try:
        return bool(get_settings().use_connection_registry_v2)
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────
# Bridge derivations
# ──────────────────────────────────────────────────────────────────


def _kind_for_connector(connector: Connector) -> ConnectionKind:
    """Map legacy connector.auth_type -> V2 ConnectionKind.

    Most legacy "connectors" are PROVIDERs (cloud APIs). OAuth-flow
    connectors are OAUTH_APPs. None-auth is PLUGIN.
    """
    auth = (connector.auth_type or "").strip().lower()
    if auth in {"oauth2", "oauth", "oauth_managed"}:
        return ConnectionKind.OAUTH_APP
    if auth in {"none", "no_auth", "no-auth"}:
        return ConnectionKind.PLUGIN
    return ConnectionKind.PROVIDER


def _auth_method_for_connector(connector: Connector) -> V2AuthMethod:
    """Map legacy connector.auth_type -> V2 AuthMethod."""
    auth = (connector.auth_type or "").strip().lower()
    if auth in {"oauth2", "oauth"}:
        return V2AuthMethod.OAUTH_MANAGED
    if auth in {"none", "no_auth", "no-auth"}:
        return V2AuthMethod.NONE
    return V2AuthMethod.API_TOKEN


def _slug_for_instance(connector: Connector, user_id: UUID) -> str:
    """Derive a stable V2 slug for a legacy ConnectorInstance.

    Slug shape: ``<name>-<user_id_prefix>``. The user prefix keeps the
    UniqueConstraint(tenant_id, kind, slug) valid for multi-user
    tenants (each user has at most one instance per connector by
    legacy unique constraint, mirrored here).
    """
    name = (connector.name or "connector").lower().replace(" ", "-").replace("_", "-")
    name = "".join(ch for ch in name if ch.isalnum() or ch == "-")[:96]
    short_uid = str(user_id).replace("-", "")[:8]
    return f"{name}-{short_uid}"


# Map V2 label -> legacy ConnectorStatus.
_LABEL_TO_LEGACY_STATUS: dict[str, str] = {
    "healthy": ConnectorStatus.CONNECTED.value,
    "healthy_stale": ConnectorStatus.CONNECTED.value,
    "degraded": ConnectorStatus.CONNECTED.value,
    "degraded_stale": ConnectorStatus.CONNECTED.value,
    "probing": ConnectorStatus.CONNECTED.value,
    "needs_auth": ConnectorStatus.NEEDS_REAUTH.value,
    "auth_pending": ConnectorStatus.NEEDS_REAUTH.value,
    "installable": ConnectorStatus.INSTALLED.value,
    "needs_config": ConnectorStatus.INSTALLED.value,
    "installing": ConnectorStatus.INSTALLED.value,
    "failed": ConnectorStatus.ERROR.value,
    "unknown": ConnectorStatus.ERROR.value,
    "disabled": ConnectorStatus.DISCONNECTED.value,
    "archived": ConnectorStatus.DISCONNECTED.value,
}


def label_to_legacy_status(label: str) -> str:
    """Map a V2 derived label to a legacy ConnectorStatus value."""
    return _LABEL_TO_LEGACY_STATUS.get(label, ConnectorStatus.INSTALLED.value)


# ──────────────────────────────────────────────────────────────────
# Mirror writes
# ──────────────────────────────────────────────────────────────────


def _build_registry(db: AsyncSession) -> ConnectionRegistryV2:
    """Build a ConnectionRegistryV2 with the boot KEK.

    The KEK is loaded under the live ``is_production`` flag; in dev
    this returns the DEV_FALLBACK_KEK (with warning), in prod boot
    fails earlier so this never gets a bad KEK.
    """
    settings = get_settings()
    kek = load_kek_from_env(is_production=settings.is_production)
    return ConnectionRegistryV2(db, kek_seed=kek)


async def mirror_legacy_install(
    *,
    db: AsyncSession,
    connector: Connector,
    tenant_id: UUID,
    user_id: UUID,
) -> ConnectionV2 | None:
    """Mirror a legacy ``install``/``connect`` into a V2 row.

    Returns the V2 row (created or existing). Returns None and logs
    on failure -- this MUST NOT raise into the legacy path.
    """
    if not is_v2_enabled():
        return None

    try:
        registry = _build_registry(db)
        kind = _kind_for_connector(connector)
        slug = _slug_for_instance(connector, user_id)
        result = await registry.import_connection(
            tenant_id=tenant_id,
            kind=kind,
            slug=slug,
            display_name=connector.name or slug,
            auth_method=_auth_method_for_connector(connector),
            config={
                "_legacy_connector_id": str(connector.id),
                "_legacy_user_id": str(user_id),
                "category": connector.category or "",
            },
        )
        return result.connection
    except Exception as exc:  # noqa: BLE001 -- legacy path stays alive
        logger.warning(
            "legacy_bridge.mirror_install_failed",
            tenant_id=str(tenant_id),
            connector=connector.name,
            error_type=type(exc).__name__,
        )
        return None


async def derive_legacy_status_from_v2(
    *,
    db: AsyncSession,
    connector: Connector,
    tenant_id: UUID,
    user_id: UUID,
) -> str | None:
    """Compute the legacy status string from V2 truth + label.

    Returns None if no V2 row exists or any error occurs (so the
    caller can fall back to legacy ``_status_for_install``).
    """
    if not is_v2_enabled():
        return None

    try:
        registry = _build_registry(db)
        kind = _kind_for_connector(connector)
        slug = _slug_for_instance(connector, user_id)
        row = await registry.find_by_slug(tenant_id=tenant_id, kind=kind, slug=slug)
        if row is None:
            return None
        label = await registry.label_for(row)
        return label_to_legacy_status(label)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "legacy_bridge.derive_status_failed",
            tenant_id=str(tenant_id),
            connector=connector.name,
            error_type=type(exc).__name__,
        )
        return None


__all__ = [
    "is_v2_enabled",
    "label_to_legacy_status",
    "mirror_legacy_install",
    "derive_legacy_status_from_v2",
]
