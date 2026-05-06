"""Trust-aware VP chat endpoint -- Sprint-18 PR-5 (2026-05-06).

  POST /api/v1/trust/chat
  Body: {"text": "what can you do without asking me"}

Five deterministic commands handled by ``trust_chat_commands.parse_and_run``.
NO LLM in the path. Returns ``matched=False`` if no pattern matches;
the chat orchestrator can fall back to /vp-commands or LLM if it
wants. The contract here is: structured response from authoritative
state, never hallucinated permissions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.trust_chat_commands import parse_and_run

logger = get_logger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    matched: bool
    command: str | None
    summary: str
    structured: dict


@router.post("", response_model=ChatResponse)
async def trust_chat(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
) -> ChatResponse:
    result = parse_and_run(body.text)
    logger.info(
        "trust.chat.command",
        matched=result.matched, command=result.command,
        by=str(user.id),
    )
    return ChatResponse(
        matched=result.matched,
        command=result.command,
        summary=result.summary,
        structured=result.structured or {},
    )
