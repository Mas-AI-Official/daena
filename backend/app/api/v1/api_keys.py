"""API key management endpoints: create, list (masked), revoke.

Keys use dna_ prefix + 40 hex chars. Only the SHA-256 hash is stored.
The raw key is returned exactly once at creation.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.api_key import ApiKey

router = APIRouter()

_PREFIX = "dna_"


def _generate_key() -> str:
    """Generate a raw API key: dna_ + 40 hex chars."""
    return _PREFIX + secrets.token_hex(20)


def _hash_key(raw: str) -> str:
    """SHA-256 hash of the raw key."""
    return hashlib.sha256(raw.encode()).hexdigest()


def _mask_prefix(prefix: str) -> str:
    """Show prefix like dna_a1b2...xxxx."""
    return prefix


# --- Request / Response schemas ---

class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None


class CreateKeyResponse(ApiKeyResponse):
    raw_key: str  # shown exactly once


# --- Endpoints ---

@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all API keys for the current user (masked)."""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.user_id == user.id, ApiKey.tenant_id == user.tenant_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        {
            "id": str(k.id),
            "name": k.name,
            "key_prefix": k.key_prefix,
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat() if k.created_at else "",
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
        }
        for k in keys
    ]


@router.post("", response_model=CreateKeyResponse, status_code=201)
async def create_api_key(
    body: CreateKeyRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new API key. The raw key is returned exactly once."""
    raw_key = _generate_key()
    key_hash = _hash_key(raw_key)
    # Prefix for display: dna_ + first 8 chars of the hex portion
    display_prefix = raw_key[:12]  # "dna_" (4) + 8 hex chars

    key = ApiKey(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=user.tenant_id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=display_prefix,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)

    return {
        "id": str(key.id),
        "name": key.name,
        "key_prefix": key.key_prefix,
        "is_active": True,
        "created_at": key.created_at.isoformat() if key.created_at else "",
        "last_used_at": None,
        "revoked_at": None,
        "raw_key": raw_key,
    }


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke (soft-delete) an API key."""
    try:
        uid = uuid.UUID(key_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid key ID")

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == uid,
            ApiKey.user_id == user.id,
            ApiKey.tenant_id == user.tenant_id,
        )
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    if key.revoked_at:
        raise HTTPException(status_code=400, detail="Key already revoked")

    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == uid)
        .values(
            is_active=False,
            revoked_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    return {"status": "revoked", "id": key_id}
