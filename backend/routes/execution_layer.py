"""
Execution Layer API: tool list with enabled toggles, run (with dry_run), logs, config.
Local-first, safe by default. When EXECUTION_TOKEN is set, require X-Execution-Token header.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from backend.config.settings import settings
from backend.tools.registry import list_tools, execute_tool

router = APIRouter(prefix="/api/v1/execution", tags=["execution-layer"])

# Audit log path (same as backend/tools/audit_log.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AUDIT_PATH = _PROJECT_ROOT / "logs" / "tools_audit.jsonl"
_TASK_ARTIFACTS_ROOT = _PROJECT_ROOT / "data" / "task_artifacts"


def _is_localhost_request(request: Request) -> bool:
    """Check if request is from localhost (for ALLOW_INSECURE_EXECUTION_LOCAL)."""
    try:
        client = request.client
        if client and getattr(client, "host", None):
            return str(client.host).strip() in ("127.0.0.1", "::1", "localhost")
        # Fallback: check X-Forwarded-For / host header when behind proxy
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded and forwarded in ("127.0.0.1", "::1"):
            return True
    except Exception:
        pass
    return False


async def verify_execution_token(
    request: Request,
    x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token"),
):
    """DEFAULT DENY: Execution ALWAYS requires valid X-Execution-Token unless ALLOW_INSECURE_EXECUTION_LOCAL=1 from localhost."""
    # Dev override: localhost + ALLOW_INSECURE_EXECUTION_LOCAL=1
    if getattr(settings, "allow_insecure_execution_local", False) and request and _is_localhost_request(request):
        return x_execution_token or ""
    if not settings.execution_token:
        raise HTTPException(
            status_code=401,
            detail="Execution Layer is disabled: EXECUTION_TOKEN is not set. Set EXECUTION_TOKEN in env to enable.",
        )
    if not x_execution_token or x_execution_token != settings.execution_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Execution-Token")
    return x_execution_token


def _check_lockdown():
    """If security lockdown is active, block execution (423 Locked)."""
    try:
        from backend.config.security_state import is_lockdown_active
        if is_lockdown_active():
            raise HTTPException(
                status_code=423,
                detail="Execution blocked: system is in security lockdown. Unlock from Incident Room or Founder Panel.",
            )
    except HTTPException:
        raise
    except Exception:
        pass


class RunRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}
    dry_run: bool = False
    department: Optional[str] = None
    agent_id: Optional[str] = None
    reason: Optional[str] = None
    approval_id: Optional[str] = None


class ExecutionRequestSubmit(BaseModel):
    """Moltbot-style: non-Daena agents submit requests; Daena/founder approves and executes."""
    tool_name: str
    args: Dict[str, Any] = {}
    reason: str = ""
    risk_score_estimate: Optional[int] = None
    agent_id: Optional[str] = None
    department: Optional[str] = None
    dry_run: bool = False


class ConfigUpdate(BaseModel):
    approval_mode: Optional[str] = None
    require_approval_for_risky: Optional[bool] = None
    max_steps_per_run: Optional[int] = None
    max_retries_per_tool: Optional[int] = None
    dry_run_default: Optional[bool] = None


# Tools that sandboxed agents cannot request via /request (must be run only by Daena with token)
FORBIDDEN_FOR_REQUEST = frozenset({"shell_exec", "filesystem_write"})


@router.post("/request")
async def execution_submit_request(req: ExecutionRequestSubmit) -> Dict[str, Any]:
    """
    Moltbot-style Execution Broker: non-Daena agents submit requests here.
    No X-Execution-Token required. Request goes to Permissions Inbox; Daena/founder approves via POST /approvals/{id}.
    shell_exec and filesystem_write are forbidden from this endpoint (policy: deny for sandboxed agents).
    """
    from backend.services.execution_task_store import submit_execution_request
    from backend.tools.registry import TOOL_DEFS
    if req.tool_name not in TOOL_DEFS:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {req.tool_name}")
    if req.tool_name in FORBIDDEN_FOR_REQUEST:
        raise HTTPException(
            status_code=403,
            detail=f"Tool {req.tool_name} cannot be requested via Execution Broker; only Daena (with token) may run it.",
        )
    request_id = submit_execution_request(
        tool_name=req.tool_name,
        args=req.args,
        reason=req.reason or "Execution request",
        agent_id=req.agent_id,
        department=req.department,
        risk_score_estimate=req.risk_score_estimate,
        dry_run=req.dry_run,
    )
    return {
        "success": True,
        "request_id": request_id,
        "status": "pending",
        "message": "Requires Daena/founder approval. Check Permissions Inbox (Approvals) and approve to run.",
    }


@router.get("/tools", dependencies=[Depends(verify_execution_token)])
async def execution_list_tools() -> Dict[str, Any]:
    """List all tools with enabled/disabled state for the Execution Layer UI."""
    tools = list_tools(include_enabled=True)
    return {"success": True, "tools": tools}


@router.post("/approve", dependencies=[Depends(verify_execution_token)])
async def execution_approve(tool_name: str) -> Dict[str, Any]:
    """Create a short-lived approval for a risky tool. Returns approval_id (TTL 300s)."""
    from backend.services.execution_layer_config import create_approval, get_tool_risk_level
    risk = get_tool_risk_level(tool_name)
    if risk < 1:
        return {"success": True, "approval_id": None, "message": "Tool is low-risk, no approval needed"}
    approval_id = create_approval(tool_name)
    return {"success": True, "approval_id": approval_id, "tool_name": tool_name, "ttl_seconds": 300}


@router.post("/run", response_model=Dict[str, Any], dependencies=[Depends(verify_execution_token)])
async def execution_run(req: RunRequest) -> Dict[str, Any]:
    """Run a tool. Use dry_run=True to log without executing. Risky tools require approval_id when approval_mode is require_approval."""
    _check_lockdown()
    from backend.services.execution_layer_config import (
        get_execution_config,
        get_tool_risk_level,
        consume_approval,
    )
    cfg = get_execution_config()
    approval_mode = cfg.get("approval_mode", "auto")
    require_risky = cfg.get("require_approval_for_risky", True)
    risk = get_tool_risk_level(req.tool_name)
    if risk >= 1 and require_risky and approval_mode == "require_approval":
        if not consume_approval(req.approval_id, req.tool_name):
            raise HTTPException(
                status_code=403,
                detail="Risky tool requires approval. Call POST /api/v1/execution/approve?tool_name=... first and pass approval_id",
            )
    out = await execute_tool(
        tool_name=req.tool_name,
        args=req.args,
        department=req.department,
        agent_id=req.agent_id,
        reason=req.reason,
        trace_id=None,
        dry_run=req.dry_run,
    )
    return {"success": out.get("status") == "ok", **out}


@router.get("/logs")
async def execution_logs(limit: int = 50) -> Dict[str, Any]:
    """Return recent tool execution audit entries (timestamp, tool, args summary, result)."""
    entries: List[Dict[str, Any]] = []
    if not _AUDIT_PATH.exists():
        return {"success": True, "logs": [], "count": 0}
    try:
        lines = _AUDIT_PATH.read_text(encoding="utf-8").strip().split("\n")
        for line in reversed(lines[-limit:] if len(lines) > limit else lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read audit log: {e}")
    return {"success": True, "logs": entries, "count": len(entries)}


@router.get("/config", dependencies=[Depends(verify_execution_token)])
async def execution_get_config() -> Dict[str, Any]:
    """Get Execution Layer config: approval mode, budget guards, tool toggles."""
    from backend.services.execution_layer_config import get_execution_config
    return {"success": True, "config": get_execution_config()}


@router.patch("/config")
async def execution_update_config(updates: ConfigUpdate) -> Dict[str, Any]:
    """Update approval mode, budget guards (max_steps, max_retries)."""
    from backend.services.execution_layer_config import update_execution_config
    u = updates.model_dump(exclude_none=True)
    if not u:
        from backend.services.execution_layer_config import get_execution_config
        return {"success": True, "config": get_execution_config()}
    config = update_execution_config(u)
    return {"success": True, "config": config}


@router.patch("/tools/{tool_name}/enabled", dependencies=[Depends(verify_execution_token)])
async def execution_toggle_tool(tool_name: str, enabled: bool) -> Dict[str, Any]:
    """Enable or disable a tool."""
    from backend.services.execution_layer_config import set_tool_enabled
    set_tool_enabled(tool_name, enabled)
    return {"success": True, "tool_name": tool_name, "enabled": enabled}


@router.get("/node/health", dependencies=[Depends(verify_execution_token)])
async def execution_node_health() -> Dict[str, Any]:
    """Test Windows Node connection. Node must be running at configured URL (default 127.0.0.1:18888)."""
    from backend.services.windows_node_client import node_health
    out = await node_health()
    return {"success": out.get("status") == "ok", "node": out}


class WindowsNodeConfigBody(BaseModel):
    url: Optional[str] = None
    token: Optional[str] = None


@router.get("/node/config", dependencies=[Depends(verify_execution_token)])
async def execution_get_windows_node_config() -> Dict[str, Any]:
    """Get Windows Node config (url, has_token). Token never returned."""
    from backend.services.windows_node_client import get_node_url, get_node_token
    return {
        "success": True,
        "url": get_node_url(),
        "has_token": bool(get_node_token()),
    }


@router.post("/node/config", dependencies=[Depends(verify_execution_token)])
async def execution_set_windows_node_config(body: WindowsNodeConfigBody) -> Dict[str, Any]:
    """Save Windows Node URL and/or token (Pair Node). Stored in DB, not in .env. Omitted fields are left unchanged."""
    from backend.services.windows_node_client import save_node_config, get_node_url, get_node_token
    save_node_config(url=body.url, token=body.token)
    return {
        "success": True,
        "url": get_node_url(),
        "has_token": bool(get_node_token()),
    }


# --- Autonomy: tasks and approvals (Prompt 3) ---

class TaskCreate(BaseModel):
    goal: str
    max_steps: int = 50
    max_retries: int = 3


@router.post("/tasks", dependencies=[Depends(verify_execution_token)])
async def execution_create_task(req: TaskCreate) -> Dict[str, Any]:
    """Create a new autonomy task. Returns task_id."""
    from backend.services.execution_task_store import create_task
    task_id = create_task(goal=req.goal, max_steps=req.max_steps, max_retries=req.max_retries)
    return {"success": True, "task_id": task_id}


@router.get("/tasks", dependencies=[Depends(verify_execution_token)])
async def execution_list_tasks(limit: int = 50) -> Dict[str, Any]:
    """List recent tasks (pending, running, completed)."""
    from backend.services.execution_task_store import list_tasks
    tasks = list_tasks(limit=limit)
    return {"success": True, "tasks": tasks}


@router.get("/tasks/{task_id}", dependencies=[Depends(verify_execution_token)])
async def execution_get_task(task_id: str) -> Dict[str, Any]:
    """Get task status and artifacts."""
    from backend.services.execution_task_store import get_task
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "task": task}


@router.get("/approvals", dependencies=[Depends(verify_execution_token)])
async def execution_list_approvals() -> Dict[str, Any]:
    """List pending approvals (Approval Needed inbox)."""
    from backend.services.execution_task_store import list_approvals_pending
    pending = list_approvals_pending()
    return {"success": True, "approvals": pending}


@router.get("/requests", dependencies=[Depends(verify_execution_token)])
async def execution_list_requests(limit: int = 50) -> Dict[str, Any]:
    """List execution requests (Moltbot-style agent-submitted requests)."""
    from backend.services.execution_task_store import list_execution_requests
    requests = list_execution_requests(limit=limit)
    return {"success": True, "requests": requests}


class ApprovalDecision(BaseModel):
    approved: bool = True


@router.post("/approvals/{approval_request_id}", dependencies=[Depends(verify_execution_token)])
async def execution_approve_request(approval_request_id: str, body: ApprovalDecision) -> Dict[str, Any]:
    """Approve or deny a pending approval. When approving an execution_request, Daena runs the tool and returns execution_result."""
    _check_lockdown()
    from backend.services.execution_task_store import approve
    record = approve(approval_request_id, body.approved)
    if not record:
        raise HTTPException(status_code=404, detail="Approval request not found")
    out: Dict[str, Any] = {"success": True, "approval_request_id": approval_request_id, "approved": body.approved}
    if body.approved and record.get("request_type") == "execution_request":
        # Moltbot-style: Daena executes the requested tool and returns result
        exec_result = await execute_tool(
            tool_name=record["tool_name"],
            args=record.get("args") or {},
            department=record.get("department"),
            agent_id=record.get("agent_id"),
            reason=record.get("reason"),
            trace_id=None,
            dry_run=record.get("dry_run", False),
        )
        out["execution_result"] = exec_result
    return out


@router.post("/tasks/{task_id}/run", dependencies=[Depends(verify_execution_token)])
async def execution_run_task(task_id: str) -> Dict[str, Any]:
    """Agent runtime: plan -> execute one step -> verify -> persist artifacts. Blocked if lockdown active."""
    _check_lockdown()
    from backend.services.execution_task_store import get_task, run_task, add_step_result
    if not get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    task = run_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    planned = task.get("planned_tool")
    if not planned:
        return {"success": True, "task": get_task(task_id), "message": "Task completed or no more steps"}
    step_index = task.get("step_count", 0) + 1
    tool_name = planned.get("tool_name")
    args = dict(planned.get("args") or {})
    # Persist artifacts under data/task_artifacts/{task_id}/
    artifact_dir = _TASK_ARTIFACTS_ROOT / task_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if tool_name == "browser_e2e_runner":
        args["report_path"] = str(artifact_dir / f"step_{step_index}_e2e_report.json")
    elif tool_name == "screenshot_capture":
        args["path"] = str(artifact_dir / f"step_{step_index}_screenshot.png")
    exec_result = await execute_tool(
        tool_name=tool_name,
        args=args,
        department=task.get("department"),
        agent_id=task.get("agent_id"),
        reason=task.get("goal"),
        trace_id=None,
        dry_run=False,
    )
    artifact_files = []
    res = exec_result.get("result")
    if isinstance(res, dict):
        if res.get("report_path"):
            artifact_files.append(res["report_path"])
        if res.get("report_md_path"):
            artifact_files.append(res["report_md_path"])
        if res.get("path") and tool_name == "screenshot_capture":
            artifact_files.append(res["path"])
    add_step_result(task_id, step_index, tool_name, exec_result, artifact_files)
    return {"success": True, "task": get_task(task_id), "step_result": exec_result}


@router.get("/tasks/{task_id}/artifacts", dependencies=[Depends(verify_execution_token)])
async def execution_task_artifacts_list(task_id: str) -> Dict[str, Any]:
    """List artifact file names for a task (from step results + data/task_artifacts/{task_id}/)."""
    from backend.services.execution_task_store import get_task
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    files: List[str] = []
    for a in task.get("artifacts") or []:
        for f in a.get("artifact_files") or []:
            name = Path(f).name if f else ""
            if name and name not in files:
                files.append(name)
    task_dir = _TASK_ARTIFACTS_ROOT / task_id
    if task_dir.is_dir():
        for p in task_dir.iterdir():
            if p.is_file() and p.name not in files:
                files.append(p.name)
    return {"success": True, "task_id": task_id, "artifacts": files}


@router.get("/tasks/{task_id}/artifacts/{filename}", dependencies=[Depends(verify_execution_token)])
async def execution_task_artifact_file(task_id: str, filename: str):
    """Serve one artifact file for a task. Filename must not contain path traversal."""
    from fastapi.responses import FileResponse
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    from backend.services.execution_task_store import get_task
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    path = _TASK_ARTIFACTS_ROOT / task_id / filename
    if not path.is_file() or _TASK_ARTIFACTS_ROOT not in path.resolve().parents:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path, filename=filename)
