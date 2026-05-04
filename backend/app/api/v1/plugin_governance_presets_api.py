"""Per-plugin governance preset HTTP surface.

PR-CONN-GOV-PRESETS-API-UI (Sprint-5 PR-5, 2026-05-03).

Sprint-4 PR-5 shipped the static metadata table mapping
``(plugin_id, skill_class) -> default governance tier`` (ALLOW / ASK /
DENY). It was DORMANT for current Phase 2 read-only flows; the only
consumer was test code.

This PR exposes the same table behind a single read-only HTTP route
so the plugin drawer can render badge copy:

  GET /api/v1/connections/v2/governance/plugin-presets

Returns: ``{data: {presets: [{plugin_id, rationale, tiers: {class:
tier}}, ...]}}`` where the LAST entry is the DEFAULT_PRESET (marked
with ``_is_fallback: True``) so the UI can render "Vendor table has
no pinned preset" copy for unrecognized plugins.

Hard rules honored
------------------

  * Metadata only -- no enforcement change. The `tier` value is a
    RECOMMENDATION the operator's policy editor can override; until
    that override surface ships, the consent gate + read_only
    defense remain the actual enforcement layers (Sprint-4 PR-4 +
    Sprint-2 PR-3 respectively).
  * No new primary tabs.
  * Auth required (CurrentUser) -- preset metadata is technically
    public but a logged-in surface keeps consistency with the rest
    of /v2.
  * Pure passthrough of ``list_presets_for_api()``; no
    per-tenant overlay yet (that lands in a future per-tenant
    override PR).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, get_db, require_role
from app.core.logging import get_logger
from app.models.plugin_policy_override import PluginPolicyOverride
from app.services.connection_v2.plugin_governance_presets import (
    GovernanceTier,
    SkillClass,
    list_presets_for_api,
)


logger = get_logger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────────────────────────
# GET presets (Sprint-5 PR-5; unchanged shape)
# ──────────────────────────────────────────────────────────────────


@router.get("/plugin-presets")
async def get_plugin_governance_presets(
    user: CurrentUser = Depends(get_current_user),
) -> JSONResponse:
    """Return the static per-plugin governance preset table.

    JSON shape mirrors ``list_presets_for_api()`` exactly so the
    frontend never re-derives anything client-side.
    """
    _ = user  # auth-only
    return JSONResponse(content={
        "data": {"presets": list_presets_for_api()},
    })


# ──────────────────────────────────────────────────────────────────
# Sprint-6 PR-6: per-tenant overrides
# ──────────────────────────────────────────────────────────────────
#
# The static preset table is the BASELINE (vendor opinion). Operators
# can override one cell at a time via PUT; reads via GET return the
# operator's overrides. This layer is METADATA only -- it does not
# change Phase 2 enforcement (read_only defense + consent gate stay
# as the actual hard floors). A future PR will plumb the overrides
# into the consent-gate decision when categories overlap.


class PolicyOverridePut(BaseModel):
    """Operator-issued override for one (plugin_id, skill_class) cell.

    `plugin_id` is the catalog id (e.g. "mcp-stripe"). `skill_class`
    must match a SkillClass enum value. `tier` must match a
    GovernanceTier enum value. `rationale` is operator notes.
    """

    plugin_id: str = Field(..., min_length=1, max_length=120)
    skill_class: SkillClass
    tier: GovernanceTier
    rationale: str | None = Field(default=None, max_length=500)


def _row_to_dict(row: PluginPolicyOverride) -> dict:
    return {
        "plugin_id": row.plugin_id,
        "skill_class": row.skill_class,
        "tier": row.tier,
        "rationale": row.rationale,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "updated_by": str(row.updated_by) if row.updated_by else None,
    }


@router.get("/plugin-policy-overrides")
async def list_plugin_policy_overrides(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return the per-tenant overrides for the calling tenant.

    Empty list when no overrides have been set; the frontend should
    overlay these onto the static preset table to render the merged
    view.
    """
    rows = (await db.execute(
        select(PluginPolicyOverride).where(
            PluginPolicyOverride.tenant_id == user.tenant_id,
        ),
    )).scalars().all()
    return JSONResponse(content={
        "data": {"overrides": [_row_to_dict(r) for r in rows]},
    })


@router.put(
    "/plugin-policy-overrides",
    dependencies=[Depends(require_role("FOUNDER"))],
)
async def upsert_plugin_policy_override(
    body: PolicyOverridePut,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Insert or update one override cell.

    Founder-only (the policy editor is a sensitive surface). The
    override is upserted on the unique key
    (tenant_id, plugin_id, skill_class) so PUT is idempotent: calling
    it twice with the same body leaves exactly one row.

    Tenant binding comes from the JWT, NEVER the request body.
    """
    if body.plugin_id == "":
        raise HTTPException(status_code=400, detail="plugin_id_required")

    existing = (await db.execute(
        select(PluginPolicyOverride).where(
            PluginPolicyOverride.tenant_id == user.tenant_id,
            PluginPolicyOverride.plugin_id == body.plugin_id,
            PluginPolicyOverride.skill_class == body.skill_class.value,
        ),
    )).scalar_one_or_none()

    if existing is None:
        row = PluginPolicyOverride(
            tenant_id=user.tenant_id,
            plugin_id=body.plugin_id,
            skill_class=body.skill_class.value,
            tier=body.tier.value,
            rationale=body.rationale,
            updated_by=user.id,
        )
        db.add(row)
    else:
        existing.tier = body.tier.value
        existing.rationale = body.rationale
        existing.updated_by = user.id
        row = existing

    await db.flush()
    await db.commit()
    await db.refresh(row)
    logger.info(
        "plugin_policy_override.upserted",
        tenant_id=str(user.tenant_id),
        plugin_id=body.plugin_id,
        skill_class=body.skill_class.value,
        tier=body.tier.value,
    )
    return JSONResponse(content={"data": _row_to_dict(row)})


__all__ = ["router"]
