"""Plain-English Policy API.

Phase 2 F8 (2026-04-24). Endpoints for the redesigned PoliciesPage:

* ``POST /api/v1/policies/compile`` -- translate plain English to a
  compiled policy preview. Does NOT save. Used by the live editor.
* ``GET /api/v1/policies/seeds`` -- canonical starter pack.
* ``GET /api/v1/policies`` -- list current policies for the tenant.
* ``POST /api/v1/policies`` -- save a compiled policy (or one the user
  has manually edited after compilation).
* ``PUT /api/v1/policies/{id}`` -- update fields, bumps version.
* ``DELETE /api/v1/policies/{id}`` -- remove from disk + cache.
* ``POST /api/v1/policies/seeds/load`` -- bulk-create the seed pack
  for first-run setup.

These endpoints are FOUNDER-only by design -- governance authoring is
not delegated. SecurityGate reads the YAML pack at request time so a
restart isn't required between save and effect.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, require_role
from app.core.logging import get_logger
from app.services.policy_compiler import CompiledPolicy, compile_policy
from app.services.policy_store import list_seeds, policy_store

logger = get_logger(__name__)

router = APIRouter()


def _tenant_key(user: CurrentUser) -> str:
    return str(getattr(user, "tenant_id", "") or "founder")


# ── Compile (no save) ─────────────────────────────────────────────


class CompileRequest(BaseModel):
    plain_english: str = Field(..., min_length=3, max_length=2000)
    name_hint: str = Field(default="", max_length=120)
    department_id: str | None = Field(default=None, max_length=120)


@router.post("/compile")
async def compile_endpoint(
    body: CompileRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Compile plain-English to a structured policy preview."""
    _ = user
    try:
        compiled: CompiledPolicy = await compile_policy(
            body.plain_english, name_hint=body.name_hint,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("policies.compile_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="compile_failed") from exc
    return compiled.to_dict()


# ── Seeds ─────────────────────────────────────────────────────────


@router.get("/seeds")
async def seeds_endpoint(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> list[dict[str, Any]]:
    """Return canonical seed templates for the Load defaults button."""
    _ = user
    return list_seeds()


@router.post("/seeds/load")
async def seeds_load_endpoint(
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    """Bulk-create the seed pack for the active tenant.

    Idempotent on (tenant_id, name): if a policy with the same name
    already exists, the seed is skipped rather than duplicated.
    """
    tenant_id = _tenant_key(user)
    existing = {p.name: p for p in policy_store.list(tenant_id)}
    created: list[str] = []
    skipped: list[str] = []

    for seed in list_seeds():
        if seed["name"] in existing:
            skipped.append(seed["name"])
            continue
        seed_payload = dict(seed)
        seed_payload.setdefault("compiled_by", "seed")
        seed_payload.setdefault("confidence", 1.0)
        policy = policy_store.create(tenant_id, seed_payload)
        created.append(policy.name)

    return {"created": created, "skipped": skipped}


# ── CRUD ──────────────────────────────────────────────────────────


@router.get("")
async def list_endpoint(
    user: CurrentUser = Depends(require_role("FOUNDER")),
    only_enabled: bool = False,
    department_id: str | None = Query(default=None),
) -> dict[str, Any]:
    tenant_id = _tenant_key(user)
    policies = policy_store.list(
        tenant_id,
        only_enabled=only_enabled,
        department_id=department_id,
    )
    return {
        "data": [p.to_dict() for p in policies],
        "meta": {"count": len(policies)},
    }


@router.get("/{policy_id}")
async def get_endpoint(
    policy_id: str,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    tenant_id = _tenant_key(user)
    policy = policy_store.get(tenant_id, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="policy_not_found")
    return policy.to_dict()


class CreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    plain_english: str = Field(..., min_length=3, max_length=2000)
    trigger: str
    condition: str = Field(..., min_length=1, max_length=400)
    action: str
    enforcement_mode: str = Field(default="ALWAYS")
    governance_tier: int = Field(default=1, ge=0, le=4)
    enabled: bool = True
    notes: str = Field(default="", max_length=2000)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    compiled_by: str = Field(default="manual", max_length=80)
    matched_intents: list[str] = Field(default_factory=list)
    department_id: str | None = Field(default=None, max_length=120)


@router.post("")
async def create_endpoint(
    body: CreateRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    tenant_id = _tenant_key(user)
    policy = policy_store.create(tenant_id, body.model_dump())
    return policy.to_dict()


class UpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    plain_english: str | None = Field(default=None, max_length=2000)
    trigger: str | None = None
    condition: str | None = Field(default=None, max_length=400)
    action: str | None = None
    enforcement_mode: str | None = None
    governance_tier: int | None = Field(default=None, ge=0, le=4)
    enabled: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


@router.put("/{policy_id}")
async def update_endpoint(
    policy_id: str,
    body: UpdateRequest,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    tenant_id = _tenant_key(user)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="empty_patch")
    try:
        policy = policy_store.update(tenant_id, policy_id, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="policy_not_found") from None
    return policy.to_dict()


@router.delete("/{policy_id}")
async def delete_endpoint(
    policy_id: str,
    user: CurrentUser = Depends(require_role("FOUNDER")),
) -> dict[str, Any]:
    tenant_id = _tenant_key(user)
    ok = policy_store.delete(tenant_id, policy_id)
    if not ok:
        raise HTTPException(status_code=404, detail="policy_not_found")
    return {"ok": True}
