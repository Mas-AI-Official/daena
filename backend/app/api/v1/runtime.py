"""Runtime truth API.

Singular `/runtime` routes back the RuntimeTruthRegistry. The existing
plural `/runtimes` endpoint remains for backward compatibility with
older UI components.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user
from app.services.runtime_truth_registry import runtime_truth_registry

router = APIRouter()


class RuntimeImportRequest(BaseModel):
    id: str = Field(..., min_length=1)


class RuntimeHealthCheckRequest(BaseModel):
    id: str | None = None


class RuntimeTestCallRequest(BaseModel):
    id: str = Field(..., min_length=1)


class RuntimePatchRequest(BaseModel):
    governance_tier: int | None = Field(default=None, ge=0, le=5)
    approval_required: bool | None = None
    imported_state: str | None = None
    persisted: bool | None = None
    metadata: dict[str, Any] | None = None


@router.get("/truth")
async def get_runtime_truth(
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the persisted runtime truth registry."""
    return {"success": True, "data": await runtime_truth_registry.get_truth()}


@router.post("/refresh")
async def refresh_runtime_truth(
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Re-scan runtimes, providers, MCP configs, and local model endpoints."""
    return {"success": True, "data": await runtime_truth_registry.refresh()}


@router.post("/import")
async def import_runtime_item(
    body: RuntimeImportRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark a detected runtime item as persisted in Daena's truth registry."""
    try:
        data = await runtime_truth_registry.import_item(body.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"runtime item not found: {body.id}") from exc
    return {"success": True, "data": data}


@router.post("/health-check")
async def health_check_runtime_truth(
    body: RuntimeHealthCheckRequest | None = None,
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Run health checks for all items or one item."""
    try:
        data = await runtime_truth_registry.health_check(body.id if body else None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"runtime item not found: {body.id}") from exc
    return {"success": True, "data": data}


@router.post("/test-call")
async def test_call_runtime_item(
    body: RuntimeTestCallRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Run a safe, bounded test call for a runtime item when possible."""
    try:
        data = await runtime_truth_registry.test_call(body.id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"runtime item not found: {body.id}") from exc
    return {"success": True, "data": data}


@router.patch("/{item_id}")
async def patch_runtime_item(
    item_id: str,
    body: RuntimePatchRequest,
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Patch operator-controlled runtime metadata."""
    patch = body.model_dump(exclude_none=True)
    try:
        data = await runtime_truth_registry.patch_item(item_id, patch)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"runtime item not found: {item_id}") from exc
    return {"success": True, "data": data}


@router.get("/events")
async def get_runtime_events(
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return recent runtime truth events."""
    return {"success": True, "data": await runtime_truth_registry.events()}
