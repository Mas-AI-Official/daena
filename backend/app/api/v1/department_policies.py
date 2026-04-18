"""REST API for cross-department policies.

Session D. Five endpoints covering the CRUD lifecycle + default seed:

* ``GET /department-policies`` -- list (optionally includes disabled)
* ``POST /department-policies`` -- create
* ``PATCH /department-policies/{id}`` -- update
* ``DELETE /department-policies/{id}`` -- delete
* ``POST /department-policies/seed`` -- install default policies for
  the current tenant (idempotent)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.department_policy import POLICY_TYPE_VALUES
from app.services.department_policy_service import DepartmentPolicyService

router = APIRouter()


# ── Schemas ─────────────────────────────────────────────────────


class PolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field("", max_length=500)
    policy_type: str = Field(..., min_length=1, max_length=40)
    trigger_condition: dict[str, Any] = Field(default_factory=dict)
    required_approvers: list[str] = Field(..., min_length=1)
    escalation_chain: list[str] = Field(default_factory=list)
    enabled: bool = True


class PolicyUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_condition: dict[str, Any] | None = None
    required_approvers: list[str] | None = None
    escalation_chain: list[str] | None = None
    enabled: bool | None = None


class PolicyResponse(BaseModel):
    id: str
    name: str
    description: str
    policy_type: str
    trigger_condition: dict[str, Any]
    required_approvers: list[str]
    escalation_chain: list[str]
    enabled: bool
    seed_key: str
    created_at: str | None = None
    updated_at: str | None = None


# ── Endpoints ───────────────────────────────────────────────────


@router.get("", response_model=list[PolicyResponse])
async def list_policies(
    include_disabled: bool = Query(False),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PolicyResponse]:
    svc = DepartmentPolicyService(db)
    rows = await svc.list_policies(
        tenant_id=user.tenant_id, include_disabled=include_disabled,
    )
    return [PolicyResponse(**p.to_dict()) for p in rows]


@router.post("", response_model=PolicyResponse, status_code=201)
async def create_policy(
    body: PolicyCreateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    svc = DepartmentPolicyService(db)
    try:
        policy = await svc.create(
            tenant_id=user.tenant_id,
            name=body.name,
            description=body.description,
            policy_type=body.policy_type,
            trigger_condition=body.trigger_condition,
            required_approvers=body.required_approvers,
            escalation_chain=body.escalation_chain,
            enabled=body.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PolicyResponse(**policy.to_dict())


@router.patch("/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: UUID,
    body: PolicyUpdateRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    svc = DepartmentPolicyService(db)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    try:
        policy = await svc.update(policy_id=policy_id, updates=updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    # Tenant check -- cannot update someone else's policy.
    if policy.tenant_id != user.tenant_id:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Policy not found")
    return PolicyResponse(**policy.to_dict())


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from sqlalchemy import select
    from app.models.department_policy import DepartmentPolicy

    # Fetch to verify tenant ownership before deleting.
    stmt = select(DepartmentPolicy).where(DepartmentPolicy.id == policy_id)
    policy = (await db.execute(stmt)).scalar_one_or_none()
    if policy is None or policy.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="Policy not found")

    svc = DepartmentPolicyService(db)
    await svc.delete(policy_id=policy_id)


class SeedResponse(BaseModel):
    inserted: int
    message: str


@router.post("/seed", response_model=SeedResponse)
async def seed_defaults(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SeedResponse:
    """Install the 5 default policies for this tenant. Idempotent --
    re-running does nothing if all defaults already exist."""
    svc = DepartmentPolicyService(db)
    inserted = await svc.ensure_defaults(tenant_id=user.tenant_id)
    return SeedResponse(
        inserted=inserted,
        message=(
            f"Installed {inserted} default policies."
            if inserted else
            "All default policies already present."
        ),
    )
