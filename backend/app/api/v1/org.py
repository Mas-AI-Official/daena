"""Organization management endpoints: details, members, billing summary.

Org = Tenant in Daena's multi-tenant model. These endpoints expose
tenant-level operations for the Account > Enterprise section.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.database import get_db
from app.models.identity import Tenant, User
from app.models.financial import UsageLedger

router = APIRouter()


# --- Schemas ---

class OrgDetailsResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    created_at: str | None = None
    member_count: int = 0


class UpdateOrgRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)


class OrgMemberResponse(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    role: str
    is_active: bool
    last_login: str | None = None
    created_at: str | None = None


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="MEMBER", pattern="^(MEMBER|ADMIN)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(MEMBER|ADMIN|VIEWER)$")


class OrgBillingResponse(BaseModel):
    total_spend_usd: float = 0.0
    total_tokens: int = 0
    active_members: int = 0
    spend_by_member: list[dict] = []


# --- Org Details ---

@router.get("/details", response_model=OrgDetailsResponse)
async def get_org_details(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get organization (tenant) details."""
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Organization not found")

    member_count = await db.scalar(
        select(func.count()).select_from(User).where(
            User.tenant_id == user.tenant_id, User.is_active == True  # noqa: E712
        )
    )

    return {
        "id": str(tenant.id),
        "name": tenant.name,
        "slug": tenant.slug,
        "plan": tenant.plan,
        "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
        "member_count": member_count or 0,
    }


@router.patch("/details", response_model=OrgDetailsResponse)
async def update_org_details(
    body: UpdateOrgRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update organization name. Requires ADMIN+."""
    updates: dict = {}
    if body.name is not None:
        updates["name"] = body.name

    if updates:
        await db.execute(
            update(Tenant).where(Tenant.id == user.tenant_id).values(**updates)
        )
        await db.commit()

    # Re-fetch
    return await get_org_details(user, db)


# --- Members ---

@router.get("/members", response_model=list[OrgMemberResponse])
async def list_org_members(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all members in the organization."""
    result = await db.execute(
        select(User)
        .where(User.tenant_id == user.tenant_id)
        .order_by(User.created_at.asc())
    )
    members = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "email": m.email,
            "display_name": m.display_name,
            "role": m.role,
            "is_active": m.is_active,
            "last_login": m.last_login.isoformat() if m.last_login else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in members
    ]


@router.patch("/members/{member_id}/role")
async def update_member_role(
    member_id: str,
    body: UpdateMemberRoleRequest,
    user: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change a member's role. Requires ADMIN+. Cannot demote self."""
    try:
        mid = uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid member ID")

    if mid == user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    result = await db.execute(
        select(User).where(User.id == mid, User.tenant_id == user.tenant_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot modify FOUNDER role
    if member.role == "FOUNDER":
        raise HTTPException(status_code=403, detail="Cannot modify founder role")

    await db.execute(
        update(User).where(User.id == mid).values(role=body.role)
    )
    await db.commit()
    return {"status": "updated", "member_id": member_id, "role": body.role}


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: str,
    user: CurrentUser = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deactivate a member. Requires ADMIN+. Cannot remove self."""
    try:
        mid = uuid.UUID(member_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid member ID")

    if mid == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    result = await db.execute(
        select(User).where(User.id == mid, User.tenant_id == user.tenant_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "FOUNDER":
        raise HTTPException(status_code=403, detail="Cannot remove founder")

    await db.execute(
        update(User).where(User.id == mid).values(is_active=False)
    )
    await db.commit()
    return {"status": "deactivated", "member_id": member_id}


# --- Billing ---

@router.get("/billing", response_model=OrgBillingResponse)
async def get_org_billing(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get org-level billing summary: total spend, tokens, per-member breakdown."""
    # Total spend
    total_spend = await db.scalar(
        select(func.coalesce(func.sum(UsageLedger.cost_usd), 0.0)).where(
            UsageLedger.tenant_id == user.tenant_id
        )
    ) or 0.0

    # Total tokens (input + output)
    total_tokens = await db.scalar(
        select(func.coalesce(
            func.sum(UsageLedger.tokens_input + UsageLedger.tokens_output), 0
        )).where(
            UsageLedger.tenant_id == user.tenant_id
        )
    ) or 0

    # Active members
    active_members = await db.scalar(
        select(func.count()).select_from(User).where(
            User.tenant_id == user.tenant_id, User.is_active == True  # noqa: E712
        )
    ) or 0

    # Spend by member (top 10)
    member_spend_q = (
        select(
            User.display_name,
            User.email,
            func.coalesce(func.sum(UsageLedger.cost_usd), 0.0).label("spend"),
        )
        .join(UsageLedger, UsageLedger.user_id == User.id, isouter=True)
        .where(User.tenant_id == user.tenant_id)
        .group_by(User.id, User.display_name, User.email)
        .order_by(func.sum(UsageLedger.cost_usd).desc().nullslast())
        .limit(10)
    )
    rows = (await db.execute(member_spend_q)).all()
    spend_by_member = [
        {
            "name": row.display_name or row.email,
            "email": row.email,
            "spend_usd": float(row.spend),
        }
        for row in rows
    ]

    return {
        "total_spend_usd": float(total_spend),
        "total_tokens": int(total_tokens),
        "active_members": int(active_members),
        "spend_by_member": spend_by_member,
    }
