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
# Registry skill id -> enabled (override; default from status active/approved)
_registry_enabled: Dict[str, bool] = {}


def _verify_execution_token(x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token")):
    from backend.config.settings import settings
    if not settings.execution_token:
        raise HTTPException(status_code=401, detail="EXECUTION_TOKEN not set")
    if not x_execution_token or x_execution_token != settings.execution_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Execution-Token")


def _registry_skills_for_list() -> List[Dict[str, Any]]:
    """Get skills from skill_registry and map to same shape as SKILL_DEFS for Control Panel."""
    out: List[Dict[str, Any]] = []
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        for s in registry.list_skills():
            sid = s.get("id") or ""
            status = (s.get("status") or "").lower()
            default_enabled = status in ("active", "approved")
            enabled = _registry_enabled.get(sid, default_enabled)
            out.append({
                "id": sid,
                "name": s.get("display_name") or s.get("name") or sid,
                "enabled": enabled,
                "risk": s.get("risk_level") or "medium",
                "description": s.get("description") or "",
                "creator": s.get("creator") or "registry",
                "source": "registry",
            })
    except Exception:
        pass
    return out


@router.get("")
async def list_skills() -> Dict[str, Any]:
    """List all skills: static SKILL_DEFS + skill_registry. Control Panel shows add/remove from registry."""
    skills: List[Dict[str, Any]] = []
    for s in SKILL_DEFS:
        skills.append({
            **s,
            "enabled": _skills_state.get(s["id"], s["enabled"]),
            "creator": s.get("creator", "founder"),
        })
    skills.extend(_registry_skills_for_list())
    return {"success": True, "skills": skills}


@router.get("/stats")
async def skill_stats() -> Dict[str, Any]:
    """Registry-wide statistics for Control Panel dashboard (static + skill_registry)."""
    static_total = len(SKILL_DEFS)
    static_active = sum(1 for s in SKILL_DEFS if _skills_state.get(s["id"], s["enabled"]))
    reg_skills = _registry_skills_for_list()
    reg_total = len(reg_skills)
    reg_active = sum(1 for s in reg_skills if s.get("enabled", True))
    try:
        from backend.services.skill_registry import get_skill_registry
        from backend.services.skill_registry import SkillStatus
        registry = get_skill_registry()
        all_reg = registry.list_skills()
        pending = sum(1 for s in all_reg if (s.get("status") or "").lower() in ("pending_review", "draft", "sandbox_test"))
        self_created = sum(1 for s in all_reg if (s.get("creator") or "").lower() == "daena")
    except Exception:
        pending = 0
        self_created = 0
    return {
        "success": True,
        "total": static_total + reg_total,
        "active": static_active + reg_active,
        "pending": pending,
        "self_created": self_created,
    }


class ToggleBody(BaseModel):
    skill_id: str
    enabled: bool


@router.post("/toggle")
async def toggle_skill(body: ToggleBody) -> Dict[str, Any]:
    """Enable or disable a skill (static list or registry)."""
    if any(s["id"] == body.skill_id for s in SKILL_DEFS):
        _skills_state[body.skill_id] = body.enabled
        return {"success": True, "skill_id": body.skill_id, "enabled": body.enabled}
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        if registry.get_skill(body.skill_id) is not None:
            _registry_enabled[body.skill_id] = body.enabled
            return {"success": True, "skill_id": body.skill_id, "enabled": body.enabled}
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Skill not found")


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
