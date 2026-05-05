"""Integration API endpoints for external service tool execution.

Provides endpoints for executing tools on connected services
(Gmail, Google Calendar, Notion) through governance.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.exceptions import ApprovalRequiredError
from app.core.logging import get_logger
from app.services.integrations.integration_router import (
    IntegrationError,
    IntegrationRouter,
    NotConnectedError,
    PermissionDeniedError,
)

logger = get_logger(__name__)

router = APIRouter()


class ToolExecuteRequest(BaseModel):
    """Request body for executing an integration tool."""

    provider: str = Field(..., description="Provider slug: gmail, calendar, notion")
    tool_name: str = Field(..., description="Tool name: send_email, list_events, etc.")
    params: dict = Field(default_factory=dict, description="Tool-specific parameters")
    owner_email: str | None = Field(
        default=None,
        description=(
            "Pin which connected account to dispatch against (e.g. "
            "masoud.masoori@mas-ai.co vs daena@mas-ai.co). Required when "
            "the same provider has multiple connected instances; optional "
            "otherwise. PR-1 read-only gate (Sprint-11)."
        ),
    )


class QualifiedToolRequest(BaseModel):
    """Request body using qualified tool name like 'gmail.send_email'."""

    tool: str = Field(..., description="Qualified tool name: provider.tool_name")
    params: dict = Field(default_factory=dict, description="Tool-specific parameters")
    owner_email: str | None = Field(
        default=None,
        description="Pin which connected account to dispatch against.",
    )


@router.get("/tools")
async def list_available_tools(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all available integration tools for the current user.

    Only shows tools from connected providers.
    """
    router_svc = IntegrationRouter(db)
    available = await router_svc.list_available_tools(
        user_id=user.id, tenant_id=user.tenant_id,
    )
    return {"success": True, "data": available}


@router.post("/execute")
async def execute_tool(
    body: ToolExecuteRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute an integration tool through governance.

    Example:
        POST /api/v1/integrations/execute
        {"provider": "gmail", "tool_name": "search_emails", "params": {"query": "is:unread"}}
    """
    router_svc = IntegrationRouter(db)
    try:
        result = await router_svc.execute(
            provider=body.provider,
            tool_name=body.tool_name,
            params=body.params,
            user_id=user.id,
            tenant_id=user.tenant_id,
            owner_email=body.owner_email,
        )
        return {"success": True, "data": result}

    except ApprovalRequiredError as exc:
        return {
            "success": False,
            "error": exc.message,
            "error_type": "approval_required",
            "error_code": ApprovalRequiredError.error_code,
        }
    except NotConnectedError as exc:
        return {"success": False, "error": str(exc), "error_type": "not_connected"}
    except PermissionDeniedError as exc:
        return {"success": False, "error": str(exc), "error_type": "permission_denied"}
    except IntegrationError as exc:
        return {"success": False, "error": str(exc), "error_type": "integration_error"}


@router.post("/execute/qualified")
async def execute_qualified_tool(
    body: QualifiedToolRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Execute an integration tool using qualified name.

    Example:
        POST /api/v1/integrations/execute/qualified
        {"tool": "gmail.search_emails", "params": {"query": "from:boss@company.com"}}
    """
    router_svc = IntegrationRouter(db)
    try:
        result = await router_svc.execute_qualified(
            qualified_tool=body.tool,
            params=body.params,
            user_id=user.id,
            tenant_id=user.tenant_id,
            owner_email=body.owner_email,
        )
        return {"success": True, "data": result}

    except ApprovalRequiredError as exc:
        return {
            "success": False,
            "error": exc.message,
            "error_type": "approval_required",
            "error_code": ApprovalRequiredError.error_code,
        }
    except NotConnectedError as exc:
        return {"success": False, "error": str(exc), "error_type": "not_connected"}
    except PermissionDeniedError as exc:
        return {"success": False, "error": str(exc), "error_type": "permission_denied"}
    except IntegrationError as exc:
        return {"success": False, "error": str(exc), "error_type": "integration_error"}


@router.get("/providers")
async def list_providers() -> dict:
    """List all supported integration providers and their tools."""
    from app.services.integrations.integration_router import ALL_TOOLS

    providers = {}
    for provider, tools in ALL_TOOLS.items():
        if provider == "calendar":
            continue  # Skip alias
        providers[provider] = {
            "name": provider.replace("-", " ").title(),
            "tools": [
                {"name": name, "description": desc}
                for name, desc in tools.items()
            ],
        }
    return {"success": True, "data": providers}


# ── Department Workflows ──────────────────────────────────────


@router.get("/workflows")
async def list_workflows(
    department: str | None = None,
) -> dict:
    """List available department workflows."""
    from app.services.department_workflows import DepartmentWorkflowEngine

    workflows = DepartmentWorkflowEngine.list_workflows(department)
    return {"success": True, "data": workflows}


class WorkflowRunRequest(BaseModel):
    """Request body for running a department workflow."""

    workflow_id: str = Field(..., description="Workflow ID: ops.daily_briefing, etc.")
    extra_params: dict = Field(default_factory=dict, description="Additional parameters")


@router.post("/workflows/run")
async def run_workflow(
    body: WorkflowRunRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run a department workflow.

    Example:
        POST /api/v1/integrations/workflows/run
        {"workflow_id": "ops.daily_briefing"}
    """
    from app.services.department_workflows import DepartmentWorkflowEngine

    engine = DepartmentWorkflowEngine(db, user.id, user.tenant_id)
    result = await engine.run(body.workflow_id, body.extra_params)
    return {"success": result.status != "failed", "data": result.to_dict()}
