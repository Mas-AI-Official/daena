"""DaenaBot API — execute computer-control commands via REST.

Provides a dedicated endpoint for the DaenaBot frontend page
to send commands (file, terminal, browser) independently of
the chat streaming pipeline.

All commands go through governance evaluation before execution.
Tier 3+ actions return a pending approval instead of executing.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.identity import User

logger = get_logger(__name__)
router = APIRouter()


class DaenaBotCommandRequest(BaseModel):
    """A natural-language command for DaenaBot to execute."""

    command: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None


class DaenaBotCommandResponse(BaseModel):
    """Result of a DaenaBot command execution."""

    status: str  # "executed", "pending_approval", "blocked", "error", "no_match"
    agent: str | None = None
    operation: str | None = None
    description: str | None = None
    governance_tier: int = 0
    result: dict[str, Any] | None = None
    approval_id: str | None = None
    message: str | None = None


@router.post("/execute", response_model=DaenaBotCommandResponse)
async def execute_command(
    body: DaenaBotCommandRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DaenaBotCommandResponse:
    """Parse and execute a DaenaBot command.

    1. Check if DaenaBot is enabled
    2. Parse natural language into a tool call
    3. Evaluate governance tier
    4. Execute (tier 0-2) or request approval (tier 3+)
    """
    settings = get_settings()
    if not settings.enable_daenabot:
        return DaenaBotCommandResponse(
            status="error",
            message="DaenaBot is disabled. Enable it in settings.",
        )

    # Parse command into tool call
    from app.services.daenabot.router import DaenaBotRouter

    tool_call = DaenaBotRouter.match(body.command)
    if tool_call is None:
        return DaenaBotCommandResponse(
            status="no_match",
            message=(
                "Could not parse a specific action from your command. "
                "Try: 'list files in D:\\Projects', 'run `git status`', "
                "or 'open https://example.com'."
            ),
        )

    agent_name = tool_call.tool_name.split(".")[0].capitalize() + "Agent"
    operation = tool_call.tool_name.split(".")[-1]

    # Governance evaluation
    from app.services.governance import GovernanceEngine

    gov = GovernanceEngine(db)
    gov_result = await gov.evaluate(
        action_type="TOOL_EXECUTION",
        action_params={
            "tool_name": tool_call.tool_name,
            "params": tool_call.params,
            "description": tool_call.description,
        },
        governance_slider="BALANCED",
        actor_type="USER",
        actor_role=user.role,
        tenant_id=user.tenant_id,
        user_id=user.id,
    )

    governance_tier = gov_result.get("governance_tier", 0)

    if not gov_result.get("allowed", True):
        return DaenaBotCommandResponse(
            status="blocked",
            agent=agent_name,
            operation=operation,
            description=tool_call.description,
            governance_tier=governance_tier,
            message=gov_result.get("message", "Blocked by governance policy."),
        )

    # Tier 3+: needs explicit approval
    if governance_tier >= 3:
        approval_id = gov_result.get("request_id")
        return DaenaBotCommandResponse(
            status="pending_approval",
            agent=agent_name,
            operation=operation,
            description=tool_call.description,
            governance_tier=governance_tier,
            approval_id=str(approval_id) if approval_id else None,
            message=(
                f"This action requires approval (tier {governance_tier}). "
                "Review and approve in the Governance panel."
            ),
        )

    # Execute the tool
    try:
        from app.services.execution_service import ExecutionService

        exec_svc = ExecutionService(db)
        exec_result = await exec_svc.execute_tool(
            tool_name=tool_call.tool_name,
            params=tool_call.params,
            session_id=UUID(body.session_id) if body.session_id else None,
            user_id=user.id,
            tenant_id=user.tenant_id,
            governance_mode="BALANCED",
            actor_role=user.role,
        )

        logger.info(
            "daenabot.executed",
            tool=tool_call.tool_name,
            user_id=str(user.id),
            success=exec_result.get("result", {}).get("success", False),
        )

        return DaenaBotCommandResponse(
            status="executed",
            agent=agent_name,
            operation=operation,
            description=tool_call.description,
            governance_tier=governance_tier,
            result=exec_result.get("result", exec_result),
        )

    except Exception as exc:
        logger.warning(
            "daenabot.execution_failed",
            tool=tool_call.tool_name,
            error=str(exc),
        )
        return DaenaBotCommandResponse(
            status="error",
            agent=agent_name,
            operation=operation,
            description=tool_call.description,
            governance_tier=governance_tier,
            message=str(exc),
        )


@router.get("/agents")
async def list_agents(
    user: User = Depends(get_current_user),
) -> dict:
    """List available DaenaBot agents and their capabilities."""
    settings = get_settings()
    return {
        "enabled": settings.enable_daenabot,
        "agents": [
            {
                "name": "FileAgent",
                "description": "File system operations: read, write, create, list, move, archive",
                "operations": [
                    "list_directory", "read_file", "create_file",
                    "write_file", "move_file", "delete_file",
                ],
            },
            {
                "name": "TerminalAgent",
                "description": "Sandboxed shell command execution",
                "operations": ["execute_command"],
            },
            {
                "name": "BrowserAgent",
                "description": "Web automation via Playwright: navigate, screenshot, extract text",
                "operations": [
                    "navigate", "screenshot", "extract_text",
                    "fill_form", "click_element", "submit_form",
                ],
            },
            {
                "name": "VisionBrowserAgent",
                "description": (
                    "AI-powered browser with visual understanding. "
                    "Sees web pages through screenshots and navigates autonomously."
                ),
                "operations": [
                    "browse_and_act", "research_url", "screenshot_analyze",
                    "fill_form_smart", "multi_step_task",
                ],
            },
            {
                "name": "WebCrawlerAgent",
                "description": (
                    "Web crawling and data extraction. "
                    "Turns websites into clean markdown for analysis."
                ),
                "operations": [
                    "extract_page", "deep_crawl",
                    "extract_structured", "research_topic",
                ],
            },
        ],
    }
