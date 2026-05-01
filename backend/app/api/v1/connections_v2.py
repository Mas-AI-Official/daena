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

from app.api.deps import CurrentUser, get_current_user
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
