"""VP business chat endpoint -- Sprint-19 PR-7 (2026-05-06).

  POST /api/v1/business/chat
  Body: {"text": "find grants for MAS-AI"}

Eight deterministic commands handled by
``vp_business_commands.parse_and_run``. NO LLM. Authoritative
state from Opportunity + GoaRequest tables.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.services.vp_business_commands import parse_and_run

logger = get_logger(__name__)
router = APIRouter()


class BusinessChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class BusinessChatResponse(BaseModel):
    matched: bool
    command: str | None
    summary: str
    structured: dict


@router.post("", response_model=BusinessChatResponse)
async def business_chat(
    body: BusinessChatRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessChatResponse:
    result = await parse_and_run(
        body.text, db=db, tenant_id=user.tenant_id, user_id=user.id,
    )
    # Sprint-20 PR-7: explicit-id commands mutate state. Persist on
    # success so the workstream / draft / approval row survives the
    # request (the outer dependency injection rolls back on exception
    # but does not auto-commit on success).
    if result.matched and result.command in {
        "create_workstream_from_opp_by_id",
        "draft_outreach_for_opp_to",
        "send_approved_draft_by_id",
    }:
        await db.commit()
    logger.info(
        "business.chat.command",
        matched=result.matched, command=result.command,
        by=str(user.id),
    )
    return BusinessChatResponse(
        matched=result.matched,
        command=result.command,
        summary=result.summary,
        structured=result.structured or {},
    )
