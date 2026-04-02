"""Waitlist API for early access signups.

Public endpoints (no auth required) for collecting email signups
from the landing page and app. Rate-limited to prevent abuse.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.models.waitlist import WaitlistEntry

logger = get_logger(__name__)

router = APIRouter()

# Community base: represents pre-launch interest (demo viewers, inquiries,
# contact form submissions, social followers). Real signups start after this.
COMMUNITY_BASE = 150


class WaitlistSignup(BaseModel):
    email: EmailStr
    source: str = "landing"


class WaitlistResponse(BaseModel):
    position: int
    message: str


@router.post("", response_model=WaitlistResponse)
async def join_waitlist(body: WaitlistSignup) -> WaitlistResponse:
    """Add an email to the early-access waitlist.

    Returns the signup position. Duplicate emails get their existing position.
    """
    async with async_session_factory() as db:
        # Check for existing signup
        existing = await db.execute(
            select(WaitlistEntry).where(WaitlistEntry.email == body.email)
        )
        entry = existing.scalar_one_or_none()
        if entry:
            display_pos = entry.position + COMMUNITY_BASE
            return WaitlistResponse(
                position=display_pos,
                message=f"Already on the list at position {display_pos}.",
            )

        # Get next position
        count_result = await db.execute(select(func.count(WaitlistEntry.id)))
        next_position = (count_result.scalar() or 0) + 1

        # Create entry
        new_entry = WaitlistEntry(
            email=body.email,
            source=body.source,
            position=next_position,
        )
        db.add(new_entry)
        await db.commit()

        display_pos = next_position + COMMUNITY_BASE
        logger.info(
            "waitlist.signup",
            email=body.email,
            position=next_position,
            display_position=display_pos,
            source=body.source,
        )

        return WaitlistResponse(
            position=display_pos,
            message=f"You are number {display_pos} in our community. We will email you when access is ready.",
        )


@router.get("/count")
async def waitlist_count() -> dict:
    """Return the current waitlist size. Public endpoint for the landing page counter."""
    async with async_session_factory() as db:
        result = await db.execute(select(func.count(WaitlistEntry.id)))
        count = result.scalar() or 0
    display_count = count + COMMUNITY_BASE
    return {"count": display_count, "actual_signups": count}
