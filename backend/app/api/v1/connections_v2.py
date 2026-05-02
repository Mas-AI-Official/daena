"""ConnectionV2 REST endpoints (Phase 4b PR 1).

Mounted at ``/api/v1/connections/v2/*``.

Per founder rule + ADR-002 D-003: routes are always mounted. Behavior
gating is at the LIVE-UI layer (Phase 4b PR 2 will swap legacy
``/connections/*`` routes to call this service when
``USE_CONNECTION_REGISTRY_V2`` is True). This PR exposes the V2 surface
so dev tooling can exercise it independently.

This router does NOT depend on the legacy ``connection_service.py``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import get_db
from app.core.vault_boot import load_kek_from_env
from app.models.connection_v2 import (
    AuthMethod,
    ConnectionKind,
    ConnectionV2,
)
from app.schemas.connection_v2 import (
    ConnectionTruthOut,
    ConnectionV2Out,
    ImportConnectionRequest,
    ProbeOutcome,
    TruthDimOut,
)
from app.services.connection_v2 import ConnectionRegistryV2
from app.services.connection_v2.legacy_bridge import is_v2_enabled
from app.services.connection_v2.marketplace_catalog import (
    list_catalog,
    list_categories,
)
from app.services.connection_v2.marketplace_service import (
    MarketplaceService,
    install_plan,
)
from app.services.connection_v2.reconciliation import (
    ConnectionReconciliationService,
)
from app.services.connection_v2.seeders import ConnectionDiscoveryService

router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _kek_for_request() -> bytes:
    """Load KEK using the live settings.is_production flag.

    In dev: returns DEV_FALLBACK_KEK with warning. In prod: RefuseToBoot
    raised at app startup, so this never returns invalid KEK at request
    time.
    """
    settings = get_settings()
    return load_kek_from_env(is_production=settings.is_production)


async def _registry(db: AsyncSession) -> ConnectionRegistryV2:
    return ConnectionRegistryV2(db, kek_seed=_kek_for_request())


async def _to_out(reg: ConnectionRegistryV2, row: ConnectionV2) -> ConnectionV2Out:
    label = await reg.label_for(row)
    cap_count = await reg.capabilities_count(row.id)
    truth = ConnectionTruthOut(
        detected=TruthDimOut(
            value=row.detected, at=row.detected_at,
            failure_at=row.detected_failure_at, failure_reason=row.detected_failure_reason,
        ),
        configured=TruthDimOut(
            value=row.configured, at=row.configured_at,
            failure_at=row.configured_failure_at, failure_reason=row.configured_failure_reason,
        ),
        imported=TruthDimOut(
            value=row.imported, at=row.imported_at,
            failure_at=row.imported_failure_at, failure_reason=row.imported_failure_reason,
        ),
        reachable=TruthDimOut(
            value=row.reachable, at=row.reachable_at,
            failure_at=row.reachable_failure_at, failure_reason=row.reachable_failure_reason,
        ),
        authenticated=TruthDimOut(
            value=row.authenticated, at=row.authenticated_at,
            failure_at=row.authenticated_failure_at, failure_reason=row.authenticated_failure_reason,
        ),
        callable=TruthDimOut(
            value=row.callable, at=row.callable_at,
            failure_at=row.callable_failure_at, failure_reason=row.callable_failure_reason,
        ),
    )
    return ConnectionV2Out(
        id=row.id,
        tenant_id=row.tenant_id,
        kind=ConnectionKind(row.kind),
        slug=row.slug,
        display_name=row.display_name,
        auth_method=AuthMethod(row.auth_method),
        trust_tier=row.trust_tier,
        config=row.config or {},
        truth=truth,
        label=label,
        capabilities_count=cap_count,
        healthy_call_ratio=row.healthy_call_ratio,
        archived=row.archived,
        disabled=row.disabled,
        governance_tier=row.governance_tier,
    )


# ──────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────


@router.get("", response_model=list[ConnectionV2Out])
async def list_connections(
    kind: ConnectionKind | None = Query(default=None),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConnectionV2Out]:
    """List V2 connections for the current tenant. ``?kind=`` filter optional."""
    reg = await _registry(db)
    rows = await reg.list_for_tenant(tenant_id=user.tenant_id, kind=kind)
    return [await _to_out(reg, r) for r in rows]


# ──────────────────────────────────────────────────────────────────
# Marketplace catalog (PR-CONNECTIONS-MARKETPLACE-UX, 2026-05-02)
# ──────────────────────────────────────────────────────────────────
#
# IMPORTANT: these static-path routes (/catalog, /marketplace/*) MUST
# be declared BEFORE the dynamic ``/{connection_id}`` route below.
# FastAPI matches routes in declaration order; if /{connection_id}
# came first, a GET to /catalog would be parsed as connection_id="catalog"
# and 422 with a UUID validation error -- which is what the
# PR-CONNECTIONS-MARKETPLACE-404-FIX investigation surfaced
# (test: TestMarketplaceLiveSmoke pins this).
#
# READ-ONLY: catalog metadata + lifecycle overlay. NEVER:
#   * Reads or transmits secret values (env values, client_secret, tokens).
#   * Auto-installs anything; install plans are catalog metadata only.
#   * Marks anything callable; lifecycle reflects real V2 truth.


@router.get("/catalog")
async def get_catalog(
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the curated marketplace catalog.

    Static (source-tree-versioned) list of connectors Daena knows how
    to support. Independent of tenant state -- the operator-specific
    overlay lives in ``/marketplace/cards``.
    """
    _ = user  # auth-only; no tenant filtering on the catalog itself
    return {
        "success": True,
        "data": {
            "categories": list_categories(),
            "entries": list_catalog(),
        },
    }


@router.get("/marketplace/cards")
async def get_marketplace_cards(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return one card per catalog entry, overlaid with V2 truth.

    Each card carries:
      * catalog metadata (display, vendor, install plan, capabilities)
      * lifecycle state (available / installed / configured / reachable
        / callable / enabled / failed / disabled / archived /
        skill_pack)
      * derived primary action (setup_guide / test / enable / open)

    Honesty contract per project Rule 17: no card claims callable=true
    without a real probe; cards without a V2 row stay "available."
    """
    svc = MarketplaceService(db, tenant_id=user.tenant_id)
    cards = await svc.list_cards()
    return {
        "success": True,
        "data": {"cards": [c.to_dict() for c in cards]},
    }


@router.get("/marketplace/install-plan/{entry_id}")
async def get_install_plan(
    entry_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return a Setup-Guide plan for a catalog entry.

    NEVER executes any commands. NEVER returns secret values. The plan
    is metadata-only -- the operator copy-pastes commands into their
    own terminal.
    """
    _ = user  # auth-only; plan is identical for every tenant
    plan = install_plan(entry_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="catalog_entry_not_found")
    return {"success": True, "data": plan}


@router.get("/{connection_id}", response_model=ConnectionV2Out)
async def get_connection(
    connection_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionV2Out:
    reg = await _registry(db)
    row = await reg.get(tenant_id=user.tenant_id, connection_id=connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connection_not_found")
    return await _to_out(reg, row)


@router.post("", response_model=ConnectionV2Out, status_code=201)
async def import_connection(
    body: ImportConnectionRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionV2Out:
    """Import a connection. Idempotent on (tenant_id, kind, slug) -- duplicate
    discovery returns the existing row unchanged."""
    reg = await _registry(db)
    result = await reg.import_connection(
        tenant_id=user.tenant_id,
        kind=body.kind,
        slug=body.slug,
        display_name=body.display_name,
        auth_method=body.auth_method,
        config=body.config,
        trust_tier=body.trust_tier,
        secret_value=body.secret_value,
    )
    if result.created:
        await db.commit()
    return await _to_out(reg, result.connection)


@router.post("/{connection_id}/probe", response_model=ProbeOutcome)
@router.post("/{connection_id}/test", response_model=ProbeOutcome)
async def probe_connection(
    connection_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProbeOutcome:
    """Run a live probe (alias: /test). Per V2 §15 refinement #2:
    probe and test are merged -- a probe IS a test."""
    reg = await _registry(db)
    try:
        row, label, outcome = await reg.probe_and_record(
            tenant_id=user.tenant_id, connection_id=connection_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="connection_not_found")
    await db.commit()
    return ProbeOutcome(
        success=outcome.get("success", False),
        label_after=label,
        callable_at=outcome.get("callable_at"),
        failure_dim=outcome.get("failure_dim"),
        failure_reason=outcome.get("failure_reason"),
    )


@router.post("/{connection_id}/enable", response_model=ConnectionV2Out)
async def enable_connection(
    connection_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionV2Out:
    reg = await _registry(db)
    row = await reg.enable(tenant_id=user.tenant_id, connection_id=connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connection_not_found")
    await db.commit()
    return await _to_out(reg, row)


@router.post("/{connection_id}/disable", response_model=ConnectionV2Out)
async def disable_connection(
    connection_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionV2Out:
    reg = await _registry(db)
    row = await reg.disable(tenant_id=user.tenant_id, connection_id=connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connection_not_found")
    await db.commit()
    return await _to_out(reg, row)


@router.delete("/{connection_id}", response_model=ConnectionV2Out)
async def archive_connection(
    connection_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectionV2Out:
    """Soft-delete (archive). Hard-delete is post-V2 founder-only per ADR-002 §16."""
    reg = await _registry(db)
    row = await reg.archive(tenant_id=user.tenant_id, connection_id=connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="connection_not_found")
    await db.commit()
    return await _to_out(reg, row)


# ──────────────────────────────────────────────────────────────────
# Reconciliation (Phase 4b PR 3)
# ──────────────────────────────────────────────────────────────────
#
# Surface the soak-window drift report. Read-only by default.
# Mutation requires apply=True AND USE_CONNECTION_REGISTRY_V2.
# Both endpoints are FOUNDER+ -- this is operator tooling, not a
# user-facing flow.


@router.get("/reconciliation/status")
async def reconciliation_status(
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Read-only: latest reconciliation snapshot for the current tenant.

    Always returns a fresh report (no caching) -- the cost is one
    SELECT per table. Never mutates. Never includes plaintext
    secrets / KEK / DEK material.
    """
    svc = ConnectionReconciliationService(db)
    report = await svc.run(tenant_id=user.tenant_id, apply=False)
    return {
        "success": True,
        "data": report.to_dict(),
        "v2_enabled": is_v2_enabled(),
    }


@router.post("/reconciliation/seed-providers")
async def seed_providers(
    all_tenants: bool = Query(default=False, description="Founder-only: seed every tenant; default: just the caller's"),
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Phase 6: idempotent provider V2 row seeder.

    Creates ``ConnectionV2(kind=provider, slug=<lowercase>)`` rows for
    every API provider whose key is configured in settings. Existing
    rows are NOT touched. Probe is NOT run -- caller invokes
    ``POST /api/v1/connections/v2/{id}/probe`` separately.

    Idempotent: re-running on the same tenant yields zero new rows
    when the config hasn't changed.
    """
    from app.services.connection_v2.provider_seeder import (
        seed_providers_all_tenants,
        seed_providers_for_tenant,
    )

    if all_tenants:
        reports = await seed_providers_all_tenants(db)
        await db.commit()
        return {
            "success": True,
            "data": {"reports": [r.to_dict() for r in reports]},
        }

    report = await seed_providers_for_tenant(db, tenant_id=user.tenant_id)
    await db.commit()
    return {"success": True, "data": report.to_dict()}


@router.post("/discovery/refresh")
async def discovery_refresh(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """PR-CONN-V2-SEED-IMPORT: import the real connection inventory.

    Walks the same real sources V1 already reads (CLI MCP configs, CLI
    runtime binaries, local model endpoints, API providers, OAuth
    catalog, V1 plugin catalog) and materializes V2 rows for the
    caller's tenant. Idempotent: re-running adds nothing new when
    nothing has changed on disk.

    NEVER:
      * Reads MCP env values, OAuth client_secret, or API keys.
      * Marks anything callable. The truth ladder still requires a
        real probe to flip callable=true.
      * Auto-installs anything; only writes V2 rows.

    Available to any logged-in user (not founder-gated) because the
    V2 panel is the canonical UI for everyone in dev. The endpoint
    runs against the caller's own tenant only -- it cannot be used to
    mutate other tenants' rows.
    """
    svc = ConnectionDiscoveryService(db, tenant_id=user.tenant_id)
    report = await svc.run_discovery()
    if report.total_created > 0:
        await db.commit()
    return {
        "success": True,
        "data": report.to_dict(),
        "v2_enabled": is_v2_enabled(),
    }


@router.post("/reconciliation/run")
async def reconciliation_run(
    apply: bool = Query(default=False, description="Set true to perform safe automatic remediations (orphan op-lock cleanup only)"),
    all_tenants: bool = Query(default=False, description="Founder-only: scan ALL tenants instead of just the caller's"),
    user: CurrentUser = Depends(require_role("FOUNDER")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a reconciliation run.

    Safety belts:
      * apply=True is silently downgraded to apply=False if
        USE_CONNECTION_REGISTRY_V2 is off
      * legacy ConnectorInstance rows + Secret rows are NEVER mutated
        (only ConnectionV2OpLock rows can be cleaned up automatically)
      * report never contains plaintext secrets
    """
    svc = ConnectionReconciliationService(db)
    tenant_filter = None if all_tenants else user.tenant_id
    report = await svc.run(tenant_id=tenant_filter, apply=apply)
    if report.mutations_applied > 0:
        await db.commit()
    return {
        "success": True,
        "data": report.to_dict(),
        "v2_enabled": is_v2_enabled(),
        "applied_requested": apply,
        "applied_effective": apply and is_v2_enabled(),
    }
