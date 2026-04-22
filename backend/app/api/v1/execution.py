"""Execution endpoints: tool execution (CMD/EXE) and task management.

Thin router — all business logic lives in ExecutionService.
Tool execution flows through the governance pipeline automatically.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.schemas.execution import (
    CreateTaskRequest,
    ExecuteToolRequest,
    GovernanceCheckResponse,
    UpdateTaskRequest,
)
from app.services.execution_service import ExecutionService

router = APIRouter()


async def get_execution_service(
    db: AsyncSession = Depends(get_db),
) -> ExecutionService:
    """Factory dependency for ExecutionService."""
    return ExecutionService(db)


# ── Governance Pre-Check ──


@router.post("/governance-check", response_model=GovernanceCheckResponse)
async def governance_pre_check(
    body: ExecuteToolRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> GovernanceCheckResponse:
    """Pre-check governance for a tool before execution.

    Returns the governance decision (allowed, tier, risk) without
    actually running the tool. Useful for UI previews and plan validation.
    """
    decision = await service.check_governance(
        tool_name=body.tool_name,
        params=body.params,
        session_id=body.session_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        actor_role=user.role,
        plan_approval_id=body.plan_approval_id,
    )
    return GovernanceCheckResponse(
        allowed=decision["allowed"],
        governance_tier=decision["governance_tier"],
        risk_level=decision["risk_level"],
        action_type=decision["action_type"],
        requires_approval=decision.get("requires_approval", False),
        message=decision.get("message", ""),
        plan_covered=decision.get("plan_covered", False),
    )


# ── Tool Execution ──


@router.post("/execute", status_code=201)
async def execute_tool(
    body: ExecuteToolRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Execute a tool within an EXE-mode session.

    The tool goes through the governance pipeline:
    1. Validates session is in EXE mode (CMD blocks execution)
    2. GovernanceEngine evaluates risk → tier → allow/block
    3. On allow: executes and records ToolExecution
    4. On block: returns governance decision with reason
    """
    result = await service.execute_tool(
        tool_name=body.tool_name,
        params=body.params,
        session_id=body.session_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
        actor_role=user.role,
        plan_approval_id=body.plan_approval_id,
    )
    return {"success": True, "data": result}


@router.get("/executions/{session_id}")
async def list_executions(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict:
    """List tool executions for a chat session."""
    result = await service.list_executions(
        session_id=session_id,
        tenant_id=user.tenant_id,
        page=page,
        page_size=page_size,
    )
    return {"success": True, "data": result.data, "pagination": result.pagination}


@router.get("/executions/detail/{execution_id}")
async def get_execution(
    execution_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Get a single tool execution record."""
    execution = await service.get_execution(execution_id, user.tenant_id)
    return {"success": True, "data": execution}


# ── Tasks (Autopilot) ──


@router.post("/tasks", status_code=201)
async def create_task(
    body: CreateTaskRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Create a background task for Autopilot mode."""
    task = await service.create_task(
        name=body.name,
        description=body.description,
        user_id=user.id,
        tenant_id=user.tenant_id,
        session_id=body.session_id,
    )
    return {"success": True, "data": task}


@router.get("/tasks")
async def list_tasks(
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    """List background tasks for the current user."""
    import logging as _logging
    _log = _logging.getLogger("execution.debug")
    try:
        result = await service.list_tasks(
            user_id=user.id,
            tenant_id=user.tenant_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return {"success": True, "data": result.data, "pagination": result.pagination}
    except Exception as exc:
        _log.exception("list_tasks failed: %s", exc)
        raise


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Get a single task by ID."""
    task = await service.get_task(task_id, user.tenant_id)
    return {"success": True, "data": task}


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: UUID,
    body: UpdateTaskRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Update a task's status or checkpoint data.

    Users can PAUSE or CANCEL tasks. The task runner updates
    progress, result, and checkpoint data.
    """
    task = await service.update_task_status(
        task_id,
        user.tenant_id,
        status=body.status,
        checkpoint_data=body.checkpoint_data,
    )
    return {"success": True, "data": task}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Delete a task."""
    await service.delete_task(task_id, user.tenant_id)
    return {"success": True}


@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> dict:
    """Kick off execution for a PENDING / FAILED / CANCELLED task.

    Returns the task in its new RUNNING state immediately; the actual
    work proceeds in a background asyncio task. Poll GET /tasks/{id}
    to watch progress or wait for COMPLETED / FAILED.
    """
    task = await service.run_task(task_id, user.tenant_id)
    return {"success": True, "data": task}


# ── Department Tasks in Execution View ──

@router.get("/department-tasks")
async def list_department_tasks_for_execution_view(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List department tasks for the Execution View.

    Returns both scheduled workflows and their recent results,
    so the Execution View can show department activity alongside
    regular tasks.
    """
    from sqlalchemy import select
    from app.models.department_task import DepartmentTask

    stmt = (
        select(DepartmentTask)
        .where(DepartmentTask.tenant_id == user.tenant_id)
        .order_by(DepartmentTask.last_run_at.desc().nullslast())
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(t.id),
                "type": "department_workflow",
                "workflow_id": t.workflow_id,
                "department": t.department,
                "name": t.name,
                "description": t.description,
                "status": t.status,
                "is_active": t.is_active,
                "cron_expression": t.cron_expression,
                "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
                "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
                "run_count": t.run_count,
                "last_error": t.last_error,
                "last_result_summary": (
                    t.last_result.get("summary", "")[:200]
                    if isinstance(t.last_result, dict) else None
                ),
            }
            for t in tasks
        ],
    }
