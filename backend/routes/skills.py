"""
Skills API - Server-side skills that call Execution Layer (no direct tool calls).
GET /api/v1/skills, POST /api/v1/skills/toggle, POST /api/v1/skills/run.
Skills produce artifacts (report) stored under data/skill_artifacts/.
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import json
import time

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])

_SKILL_ARTIFACTS_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "skill_artifacts"

# In-memory skill definitions (6 starter skills). In production use DB.
SKILL_DEFS = [
    {"id": "repo_health_check", "name": "Repo Health Check", "enabled": True, "risk": "low", "description": "Read-only repo status and diff summary"},
    {"id": "fix_build_errors", "name": "Fix Build Errors", "enabled": True, "risk": "medium", "description": "Apply patches to fix build errors"},
    {"id": "write_unit_tests", "name": "Write Unit Tests", "enabled": True, "risk": "medium", "description": "Filesystem write + apply_patch for tests"},
    {"id": "security_scan", "name": "Security Scan", "enabled": True, "risk": "low", "description": "Read-only security scan"},
    {"id": "daily_briefing", "name": "Daily Briefing", "enabled": True, "risk": "low", "description": "Proactive daily summary"},
    {"id": "investor_outreach_draft", "name": "Investor Outreach Draft", "enabled": True, "risk": "low", "description": "Draft only, no sending"},
]

_skills_state: Dict[str, bool] = {s["id"]: s["enabled"] for s in SKILL_DEFS}


def _verify_execution_token(x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token")):
    from backend.config.settings import settings
    if not settings.execution_token:
        raise HTTPException(status_code=401, detail="EXECUTION_TOKEN not set")
    if not x_execution_token or x_execution_token != settings.execution_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Execution-Token")


@router.get("")
async def list_skills() -> Dict[str, Any]:
    """List all skills with enabled/disabled state."""
    skills = []
    for s in SKILL_DEFS:
        skills.append({
            **s,
            "enabled": _skills_state.get(s["id"], s["enabled"]),
        })
    return {"success": True, "skills": skills}


class ToggleBody(BaseModel):
    skill_id: str
    enabled: bool


@router.post("/toggle")
async def toggle_skill(body: ToggleBody) -> Dict[str, Any]:
    """Enable or disable a skill."""
    if not any(s["id"] == body.skill_id for s in SKILL_DEFS):
        raise HTTPException(status_code=404, detail="Skill not found")
    _skills_state[body.skill_id] = body.enabled
    return {"success": True, "skill_id": body.skill_id, "enabled": body.enabled}


class RunBody(BaseModel):
    skill_id: str
    params: Dict[str, Any] = {}
    dry_run: bool = True


@router.post("/run")
async def run_skill(
    body: RunBody,
    x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token"),
) -> Dict[str, Any]:
    """Run a skill via Execution Layer. Requires X-Execution-Token."""
    _verify_execution_token(x_execution_token)
    from backend.config.security_state import is_lockdown_active
    if is_lockdown_active():
        raise HTTPException(status_code=423, detail="Execution blocked: system in lockdown")
    skill = next((s for s in SKILL_DEFS if s["id"] == body.skill_id), None)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if not _skills_state.get(skill["id"], True):
        raise HTTPException(status_code=400, detail="Skill is disabled")
    # Map skill to execution layer tool(s) - stub: call execution run with appropriate tool
    tool_map = {
        "repo_health_check": "git_status",
        "fix_build_errors": "apply_patch",
        "write_unit_tests": "filesystem_write",
        "security_scan": "filesystem_read",
        "daily_briefing": "consult_ui",
        "investor_outreach_draft": "consult_ui",
    }
    tool_name = tool_map.get(body.skill_id, "consult_ui")
    try:
        from backend.tools.registry import execute_tool
        out = await execute_tool(
            tool_name=tool_name,
            args=body.params or {},
            department=None,
            agent_id=None,
            reason=f"skill:{body.skill_id}",
            trace_id=None,
            dry_run=body.dry_run,
        )
        # Produce artifact (report) for UI
        artifact_path = None
        _SKILL_ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
        safe_id = body.skill_id.replace("/", "_").replace("..", "_")[:64]
        artifact_name = f"{safe_id}_{ts}.json"
        artifact_file = _SKILL_ARTIFACTS_ROOT / artifact_name
        try:
            report = {
                "skill_id": body.skill_id,
                "tool_name": tool_name,
                "timestamp": ts,
                "dry_run": body.dry_run,
                "status": out.get("status"),
                "result_summary": str(out.get("result", out.get("error", "")))[:2000],
            }
            artifact_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
            artifact_path = artifact_name
        except Exception:
            pass
        return {
            "success": out.get("status") == "ok",
            "skill_id": body.skill_id,
            "result": out,
            "artifact_path": artifact_path,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artifacts")
async def list_skill_artifacts(
    x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token"),
    limit: int = 20,
) -> Dict[str, Any]:
    """List recent skill artifact filenames (newest first). Requires X-Execution-Token."""
    _verify_execution_token(x_execution_token)
    _SKILL_ARTIFACTS_ROOT.mkdir(parents=True, exist_ok=True)
    files: List[Dict[str, Any]] = []
    try:
        for p in sorted(_SKILL_ARTIFACTS_ROOT.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file() and _SKILL_ARTIFACTS_ROOT in p.resolve().parents:
                files.append({"filename": p.name, "mtime": p.stat().st_mtime})
            if len(files) >= limit:
                break
    except Exception:
        pass
    return {"success": True, "artifacts": [f["filename"] for f in files]}


@router.get("/artifacts/{filename}")
async def get_skill_artifact(
    filename: str,
    x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token"),
):
    """Serve a skill artifact file. Requires X-Execution-Token."""
    _verify_execution_token(x_execution_token)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _SKILL_ARTIFACTS_ROOT / filename
    if not path.is_file() or _SKILL_ARTIFACTS_ROOT not in path.resolve().parents:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path, filename=filename)
