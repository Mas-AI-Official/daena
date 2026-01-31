"""
Execution Layer task store: persistent tasks for autonomy loop.
Tasks are stored in the DB (Task model). Approvals queue and execution requests
remain in config/execution_tasks.json for now.
Fields (API shape): task_id, goal, status, step_count, max_steps, max_retries,
required_approvals, artifacts, created_at, updated_at.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STORE_PATH = _PROJECT_ROOT / "config" / "execution_tasks.json"

# Only approvals and execution requests use JSON file; tasks use DB
_approvals_queue: List[Dict[str, Any]] = []
_execution_requests: List[Dict[str, Any]] = []


def _task_row_to_dict(row: Any) -> Dict[str, Any]:
    """Convert DB Task row to API-shaped task dict."""
    payload = row.payload_json or {}
    created_ts = row.created_at.timestamp() if row.created_at else time.time()
    updated_ts = row.updated_at.timestamp() if row.updated_at else time.time()
    return {
        "task_id": row.task_id,
        "goal": row.title or "",
        "status": row.status or "pending",
        "step_count": payload.get("step_count", 0),
        "max_steps": payload.get("max_steps", 50),
        "max_retries": payload.get("max_retries", 3),
        "required_approvals": payload.get("required_approvals") or [],
        "artifacts": payload.get("artifacts") or [],
        "created_at": created_ts,
        "updated_at": updated_ts,
    }


def _load() -> None:
    """Load approvals queue and execution requests from JSON. Tasks are in DB."""
    global _approvals_queue, _execution_requests
    if not _STORE_PATH.exists():
        return
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _approvals_queue = data.get("approvals_queue") or []
        _execution_requests = data.get("execution_requests") or []
    except Exception as e:
        logger.warning("Execution task store load failed: %s", e)


def _save() -> None:
    """Persist approvals queue and execution requests to JSON. Tasks are in DB."""
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "tasks": [],
                "approvals_queue": _approvals_queue,
                "execution_requests": _execution_requests,
            }, f, indent=2)
    except Exception as e:
        logger.warning("Execution task store save failed: %s", e)


def create_task(
    goal: str,
    max_steps: int = 50,
    max_retries: int = 3,
) -> str:
    """Create a new task. Returns task_id."""
    from backend.database import SessionLocal, Task
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    db = SessionLocal()
    try:
        payload = {
            "step_count": 0,
            "max_steps": max_steps,
            "max_retries": max_retries,
            "required_approvals": [],
            "artifacts": [],
        }
        row = Task(
            task_id=task_id,
            title=goal,
            description=None,
            status="pending",
            priority="medium",
            progress=0.0,
            payload_json=payload,
            result_json={},
            owner_type="agent",
        )
        db.add(row)
        db.commit()
        return task_id
    finally:
        db.close()


def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    from backend.database import SessionLocal, Task
    db = SessionLocal()
    try:
        row = db.query(Task).filter(Task.task_id == task_id).first()
        if not row:
            return None
        return _task_row_to_dict(row)
    finally:
        db.close()


def list_tasks(limit: int = 50) -> List[Dict[str, Any]]:
    from backend.database import SessionLocal, Task
    db = SessionLocal()
    try:
        rows = (
            db.query(Task)
            .filter(Task.task_id.like("task_%"))
            .order_by(Task.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_task_row_to_dict(r) for r in rows]
    finally:
        db.close()


def update_task(task_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from backend.database import SessionLocal, Task
    db = SessionLocal()
    try:
        row = db.query(Task).filter(Task.task_id == task_id).first()
        if not row:
            return None
        if "status" in updates:
            row.status = updates["status"]
        if "goal" in updates:
            row.title = updates["goal"]
        payload = dict(row.payload_json or {})
        for k in ("step_count", "max_steps", "max_retries", "required_approvals", "artifacts"):
            if k in updates:
                payload[k] = updates[k]
        row.payload_json = payload
        db.commit()
        db.refresh(row)
        return _task_row_to_dict(row)
    finally:
        db.close()


def add_approval_request(task_id: str, tool_name: str, reason: str) -> str:
    """Add approval request. Returns approval_request_id."""
    _load()
    req_id = f"apr_{uuid.uuid4().hex[:8]}"
    _approvals_queue.append({
        "approval_request_id": req_id,
        "task_id": task_id,
        "tool_name": tool_name,
        "reason": reason,
        "status": "pending",
        "created_at": time.time(),
    })
    task = get_task(task_id)
    if task:
        approvals = list(task.get("required_approvals") or [])
        approvals.append(req_id)
        update_task(task_id, {"required_approvals": approvals})
    _save()
    return req_id


def submit_execution_request(
    tool_name: str,
    args: Dict[str, Any],
    reason: str,
    agent_id: Optional[str] = None,
    department: Optional[str] = None,
    risk_score_estimate: Optional[int] = None,
    dry_run: bool = False,
) -> str:
    """Submit an execution request (agent requests; Daena/founder approves). Returns approval_request_id."""
    _load()
    req_id = f"exr_{uuid.uuid4().hex[:10]}"
    rec = {
        "approval_request_id": req_id,
        "request_type": "execution_request",
        "tool_name": tool_name,
        "args": args,
        "reason": reason,
        "agent_id": agent_id,
        "department": department,
        "risk_score_estimate": risk_score_estimate,
        "dry_run": dry_run,
        "status": "pending",
        "created_at": time.time(),
    }
    _execution_requests.append(rec)
    _approvals_queue.append(rec)
    _save()
    return req_id


def get_approval_request(approval_request_id: str) -> Optional[Dict[str, Any]]:
    """Get any approval/execution request by id."""
    _load()
    for a in _approvals_queue:
        if a.get("approval_request_id") == approval_request_id:
            return a
    return None


def list_approvals_pending() -> List[Dict[str, Any]]:
    _load()
    return [a for a in _approvals_queue if a.get("status") == "pending"]


def list_execution_requests(limit: int = 50) -> List[Dict[str, Any]]:
    """List execution requests (newest first)."""
    _load()
    out = sorted(_execution_requests, key=lambda r: r.get("created_at", 0), reverse=True)
    return out[:limit]


def approve(approval_request_id: str, approved: bool) -> Optional[Dict[str, Any]]:
    """Mark approval as approved/denied. Returns the approval record."""
    _load()
    for a in _approvals_queue:
        if a.get("approval_request_id") == approval_request_id:
            a["status"] = "approved" if approved else "denied"
            a["decided_at"] = time.time()
            _save()
            return a
    return None


def get_next_step_plan(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Agent runtime: plan next step (tool + args) for this task.
    Returns { "tool_name", "args" } or None if done / failed.
    """
    task = get_task(task_id)
    if not task:
        return None
    status = task.get("status")
    if status not in ("pending", "running"):
        return None
    step = task.get("step_count", 0)
    max_steps = task.get("max_steps", 50)
    if step >= max_steps:
        return None
    goal = (task.get("goal") or "").lower()
    if step == 0:
        return {"tool_name": "repo_git_status", "args": {}}
    if step == 1:
        if "test" in goal or "build" in goal:
            return {"tool_name": "run_tests", "args": {"runner": "pytest"}}
        return {"tool_name": "repo_scan", "args": {"scan_deps": True, "scan_secrets": True}}
    if step == 2 and ("e2e" in goal or "browser" in goal or "ui" in goal):
        return {"tool_name": "browser_e2e_runner", "args": {"base_url": "http://127.0.0.1:8000", "steps": [{"action": "navigate"}]}}
    return None


def add_step_result(
    task_id: str,
    step_index: int,
    tool_name: str,
    result: Dict[str, Any],
    artifact_files: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """Append step result and artifact paths to task; mark completed if step was last planned."""
    task = get_task(task_id)
    if not task:
        return None
    artifacts = list(task.get("artifacts") or [])
    artifacts.append({
        "step": step_index,
        "tool_name": tool_name,
        "ts": time.time(),
        "result_status": result.get("status"),
        "result_summary": str(result.get("result", result.get("error", "")))[:500],
        "artifact_files": artifact_files or [],
    })
    update_task(task_id, {"step_count": step_index, "artifacts": artifacts})
    next_plan = get_next_step_plan(task_id)
    if next_plan is None:
        update_task(task_id, {"status": "completed"})
    else:
        update_task(task_id, {"status": "pending"})
    return get_task(task_id)


def run_task(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Agent runtime: plan next step and return task + planned_tool for the route to execute.
    The route will call execute_tool(planned_tool) then add_step_result.
    """
    task = get_task(task_id)
    if not task:
        return None
    status = task.get("status")
    if status not in ("pending", "running"):
        return task
    update_task(task_id, {"status": "running"})
    task = get_task(task_id)
    if not task:
        return None
    plan = get_next_step_plan(task_id)
    if plan is None:
        update_task(task_id, {"status": "completed"})
        return get_task(task_id)
    out = dict(get_task(task_id) or task)
    out["planned_tool"] = plan
    return out
