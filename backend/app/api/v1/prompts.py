"""Interactive prompt API endpoints.

Bridges the frontend UI to the InteractivePromptManager. When the
AgentLoop sends a prompt (via SSE), the frontend shows it. When the
user responds, the frontend POSTs here, which unblocks the agent.

Endpoints:
  GET  /pending       -- all prompts waiting for user response
  POST /{id}/respond  -- submit user response to a prompt
  GET  /history       -- recent prompt+response log
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_current_user

router = APIRouter()


def _get_manager():
    from app.services.agent_core.interactive_prompts import InteractivePromptManager

    return InteractivePromptManager.get_instance()


class PromptResponse(BaseModel):
    """Payload when user responds to a prompt."""

    selected: str | None = None  # For choice/approval/verification/confirm
    fields: dict[str, str] | None = None  # For credential type
    text: str | None = None  # For text_input type


@router.get("/pending")
async def list_pending_prompts(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get all prompts currently waiting for user response."""
    manager = _get_manager()
    return {"success": True, "data": manager.get_pending()}


@router.post("/{prompt_id}/respond")
async def respond_to_prompt(
    prompt_id: str,
    body: PromptResponse,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Submit user response to an interactive prompt.

    This unblocks the AgentLoop that is waiting on this prompt.
    """
    manager = _get_manager()

    response_data: dict = {}
    if body.selected is not None:
        response_data["selected"] = body.selected
    if body.fields is not None:
        response_data["fields"] = body.fields
    if body.text is not None:
        response_data["text"] = body.text

    success = manager.respond(prompt_id, response_data)

    if not success:
        return {
            "success": False,
            "error": {
                "code": "PROMPT_NOT_FOUND",
                "message": f"Prompt '{prompt_id}' not found or already responded to",
            },
        }

    return {"success": True, "data": {"prompt_id": prompt_id, "acknowledged": True}}


@router.get("/history")
async def prompt_history(
    limit: int = 50,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get recent interactive prompt history."""
    manager = _get_manager()
    return {"success": True, "data": manager.get_history(limit=limit)}
