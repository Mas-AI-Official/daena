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

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, get_current_user
from app.services.connection_v2.plugin_governance_presets import (
    list_presets_for_api,
)


router = APIRouter()


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


__all__ = ["router"]
