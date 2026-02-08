"""
Skills API - Server-side skills that call Execution Layer (no direct tool calls).
GET /api/v1/skills, POST /api/v1/skills/toggle, POST /api/v1/skills/run.
Skills produce artifacts (report) stored under data/skill_artifacts/.
"""
from fastapi import APIRouter, HTTPException, Depends, Header, Query
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
    {"id": "repo_health_check", "name": "Repo Health Check", "enabled": True, "risk": "low", "description": "Read-only repo status and diff summary", "category": "code_exec"},
    {"id": "fix_build_errors", "name": "Fix Build Errors", "enabled": True, "risk": "medium", "description": "Apply patches to fix build errors", "category": "code_exec"},
    {"id": "write_unit_tests", "name": "Write Unit Tests", "enabled": True, "risk": "medium", "description": "Filesystem write + apply_patch for tests", "category": "code_exec"},
    {"id": "security_scan", "name": "Security Scan", "enabled": True, "risk": "low", "description": "Read-only security scan", "category": "security"},
    {"id": "daily_briefing", "name": "Daily Briefing", "enabled": True, "risk": "low", "description": "Proactive daily summary", "category": "ai_tool"},
    {"id": "investor_outreach_draft", "name": "Investor Outreach Draft", "enabled": True, "risk": "low", "description": "Draft only, no sending", "category": "utility"},
]

_skills_state: Dict[str, bool] = {s["id"]: s["enabled"] for s in SKILL_DEFS}
# Registry skill id -> enabled (override; default from status active/approved)
_registry_enabled: Dict[str, bool] = {}


class CreateSkillBody(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: str = ""
    category: str = "utility"
    creator: str = "founder"
    enabled: bool = True
    code_body: str = ""
    access: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    approval_policy: Optional[str] = None
    requires_step_up_confirm: bool = False


def _verify_execution_token(x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token")):
    from backend.config.settings import settings
    if not settings.execution_token:
        raise HTTPException(status_code=401, detail="EXECUTION_TOKEN not set")
    if not x_execution_token or x_execution_token != settings.execution_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Execution-Token")


def _registry_skills_for_list(operator_role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get skills from skill_registry. operator_role filters by allowed_roles (who can run)."""
    out: List[Dict[str, Any]] = []
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        for s in registry.list_skills(operator_role=operator_role, include_archived=False):
            sid = s.get("id") or ""
            default_enabled = s.get("enabled", True)
            enabled = _registry_enabled.get(sid, default_enabled)
            out.append({
                "id": sid,
                "name": s.get("display_name") or s.get("name") or sid,
                "enabled": enabled,
                "risk": s.get("risk_level") or "medium",
                "description": s.get("description") or "",
                "creator": s.get("creator") or "registry",
                "source": "registry",
                "category": s.get("category") or "custom",
                "access": s.get("access") or {"allowed_roles": [], "allowed_departments": [], "allowed_agents": []},
                "approval_policy": s.get("approval_policy") or "auto",
                "usage_count": s.get("usage_count", 0),
                "archived": s.get("archived", False),
            })
    except Exception:
        pass
    return out


def _static_skills_for_list(operator_role: Optional[str] = None) -> List[Dict[str, Any]]:
    """Static SKILL_DEFS with optional operator filter (default allowed_roles founder, daena)."""
    roles = ["founder", "daena"] if not operator_role else [operator_role.lower()]
    out: List[Dict[str, Any]] = []
    for s in SKILL_DEFS:
        access = s.get("access") or {"allowed_roles": ["founder", "daena"], "allowed_departments": [], "allowed_agents": []}
        allowed = [r.lower() for r in access.get("allowed_roles", ["founder", "daena"])]
        if operator_role and operator_role.lower() not in allowed:
            continue
        out.append({
            **s,
            "enabled": _skills_state.get(s["id"], s["enabled"]),
            "creator": s.get("creator", "founder"),
            "risk": s.get("risk", "medium"),
            "category": s.get("category", "utility"),
            "access": access,
            "approval_policy": s.get("approval_policy", "auto"),
            "usage_count": s.get("usage_count", 0),
            "archived": False,
        })
    return out


@router.get("")
async def list_skills(
    operator_role: Optional[str] = Query(None, description="Filter by who can run: founder, daena, agent"),
    limit: int = Query(50, description="Max skills to return"),
    offset: int = Query(0, description="Skills to skip")
) -> Dict[str, Any]:
    """List skills with pagination. operator_role filters by allowed_roles (who can execute)."""
    # Get all skills first
    all_skills: List[Dict[str, Any]] = _static_skills_for_list(operator_role=operator_role)
    all_skills.extend(_registry_skills_for_list(operator_role=operator_role))
    
    total_count = len(all_skills)
    # Apply slicing (Issue 4 Fix)
    skills = all_skills[offset : offset + limit]
    
    return {
        "success": True, 
        "skills": skills,
        "total_count": total_count,
        "offset": offset,
        "limit": limit
    }


@router.post("/{skill_id}/test")
async def test_skill_execution(
    skill_id: str,
    x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token")
):
    """Diagnose skill execution failures"""
    # Authorization check - either proper token or manual override for test
    if not x_execution_token:
        # Allow testing without token if just checking structure, but for actual execution
        # we might want to be stricter. For now, let's allow it for dev ease.
        pass
    else:
        _verify_execution_token(x_execution_token)
    
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        skill = registry.get_skill(skill_id)
        
        if not skill:
            return {"success": False, "error": f"Skill {skill_id} not found in registry"}
            
        # Check enabled state
        enabled = skill.get("enabled", False)
        status = skill.get("status")
        
        # Check governance
        from backend.services.governance_loop import get_governance_loop
        gov = get_governance_loop()
        assessment = gov.assess({
            "type": "skill_execute",
            "skill_id": skill_id,
            "risk": skill.get("risk_level", "medium")
        })
        
        return {
            "success": True,
            "skill_id": skill_id,
            "registry_info": {
                "enabled": enabled,
                "status": status,
                "risk_level": skill.get("risk_level"),
                "approval_policy": skill.get("approval_policy")
            },
            "governance_assessment": assessment,
            "can_execute": enabled and assessment["decision"] == "approve"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/scan")
async def scan_skills_for_threats() -> Dict[str, Any]:
    """
    Real security scan of all registered skills.
    Checks code patterns and configuration integrity.
    """
    try:
        from backend.services.skill_registry import get_skill_registry
        from backend.database import SessionLocal, Skill
        
        registry = get_skill_registry() # Ensures built-ins are loaded
        
        db = SessionLocal()
        try:
            skills = db.query(Skill).all()
            total_count = len(skills)
            issues = []
            
            # Signatures to look for
            risk_signatures = {
                "critical": ["os.system", "subprocess.call", "eval(", "exec(", "shutil.rmtree", "socket.socket"],
                "high": ["open(", "write(", ".unlink", ".remove", "requests.post", "urllib"],
                "medium": ["print(", "logging."]
            }

            for s in skills:
                code = s.code_body or ""
                risk_level = s.risk_level
                
                # Scan code
                found_sigs = []
                detected_risk = "low"
                
                for risk, sigs in risk_signatures.items():
                    for sig in sigs:
                        if sig in code:
                            found_sigs.append(sig)
                            if risk == "critical": detected_risk = "critical"
                            elif risk == "high" and detected_risk != "critical": detected_risk = "high"
                            elif risk == "medium" and detected_risk == "low": detected_risk = "medium"

                # Check for mismatch (e.g. marked low but has critical code)
                if detected_risk == "critical" and risk_level not in ("critical", "high"):
                     issues.append({
                         "id": s.id,
                         "name": s.name,
                         "issue": f"Marked {risk_level} but contains critical signature: {found_sigs}",
                         "severity": "critical"
                     })
                elif detected_risk == "high" and risk_level == "low":
                    issues.append({
                        "id": s.id,
                        "name": s.name,
                        "issue": f"Marked low but contains high struct: {found_sigs}",
                        "severity": "high"
                     })
            
            return {
                "success": True,
                "scanned_count": total_count,
                "issues_found": len(issues),
                "issues": issues,
                "timestamp": time.time()
            }
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@router.get("/debug")
async def debug_skills():
    """Debug endpoint to check skill registry state"""
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        stats = registry.get_stats()
        
        # Check tools dir
        tools_dir = Path(__file__).parent.parent / "tools"
        
        return {
            "success": True,
            "stats": stats,
            "tools_dir_exists": tools_dir.exists(),
            "tools_dir_path": str(tools_dir),
            "sample_skills": [s["name"] for s in registry.list_skills()[:10]],
            "static_skills_count": len(SKILL_DEFS)
        }
    except Exception as e:
        import traceback
        return {"success": False, "error": str(e), "traceback": traceback.format_exc()}


@router.post("")
async def create_skill(body: CreateSkillBody) -> Dict[str, Any]:
    """Create a new skill via Control Pannel. Persists to skill_registry."""
    payload = body.model_dump(exclude_none=True)
    payload["display_name"] = payload.get("display_name") or payload.get("name", "")
    payload["code_body"] = payload.get("code_body") or ""
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        out = registry.create_skill(payload)
        if out.get("error"):
            raise HTTPException(status_code=400, detail=out["error"])
        return out
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/manifest")
async def skills_manifest() -> Dict[str, Any]:
    """Compact list for agents: id, name, access summary, policy. Excludes archived and static (registry only)."""
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        manifest = registry.get_manifest()
        return {"success": True, "skills": manifest}
    except Exception as e:
        return {"success": False, "skills": [], "error": str(e)}


@router.get("/stats")
async def skill_stats() -> Dict[str, Any]:
    """Registry-wide statistics for Control Pannel dashboard (static + skill_registry)."""
    static_total = len(SKILL_DEFS)
    static_active = sum(1 for s in SKILL_DEFS if _skills_state.get(s["id"], s["enabled"]))
    reg_skills = _registry_skills_for_list()
    reg_total = len(reg_skills)
    reg_active = sum(1 for s in reg_skills if s.get("enabled", True))
    try:
        from backend.services.skill_registry import get_skill_registry
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


class UpdateSkillBody(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    creator: Optional[str] = None
    access: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    category: Optional[str] = None


class PatchAccessBody(BaseModel):
    allowed_roles: Optional[List[str]] = None
    allowed_departments: Optional[List[str]] = None
    allowed_agents: Optional[List[str]] = None


def _registry_skill_by_id(skill_id: str) -> Optional[Dict[str, Any]]:
    """Return skill dict if in registry (not archived), else None."""
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        s = registry.get_skill(skill_id)
        if s and not s.get("archived", False):
            return s
    except Exception:
        pass
    return None


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> Dict[str, Any]:
    """Get a single skill by id (registry or static). For Control Pannel edit."""
    for s in SKILL_DEFS:
        if s.get("id") == skill_id:
            access = s.get("access") or {"allowed_roles": ["founder", "daena"], "allowed_departments": [], "allowed_agents": []}
            return {
                "success": True,
                "skill": {
                    **s,
                    "creator": s.get("creator", "founder"),
                    "access": access,
                    "source": "static",
                    "enabled": _skills_state.get(s["id"], s["enabled"]),
                },
            }
    s = _registry_skill_by_id(skill_id)
    if s:
        return {"success": True, "skill": {**s, "source": "registry"}}
    raise HTTPException(status_code=404, detail="Skill not found")


@router.put("/{skill_id}")
async def update_skill(skill_id: str, body: UpdateSkillBody) -> Dict[str, Any]:
    """Full update: creator, access, policy, enabled. Registry-only (static SKILL_DEFS not updatable)."""
    if any(s["id"] == skill_id for s in SKILL_DEFS):
        raise HTTPException(status_code=400, detail="Static skill cannot be updated; use registry skills")
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        payload = body.model_dump(exclude_none=True)
        out = registry.update_skill(skill_id, payload)
        if out.get("error"):
            raise HTTPException(status_code=404, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{skill_id}/access")
async def patch_skill_access(skill_id: str, body: PatchAccessBody) -> Dict[str, Any]:
    """Update only access (allowed_roles, allowed_departments, allowed_agents). Registry-only."""
    if any(s["id"] == skill_id for s in SKILL_DEFS):
        raise HTTPException(status_code=400, detail="Static skill access cannot be patched")
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        access = body.model_dump(exclude_none=True)
        out = registry.update_access(skill_id, access)
        if out.get("error"):
            raise HTTPException(status_code=404, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



from backend.services.auth_service import get_current_user, User

@router.patch("/{skill_id}/operators")
async def update_skill_operators(
    skill_id: str,
    operators: List[str],
    current_user: User = Depends(get_current_user)
):
    """Update who can execute this skill. Founder only."""
    # Enforce Founder access for sensitive operator changes
    if current_user.role != "founder" and current_user.role != "daena_vp":
         # In dev mode/daena_vp allows it, but strictly should be founder
         raise HTTPException(status_code=403, detail="Only Founder can update operators")
    
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        
        # Use update_skill to set allowed_operators
        out = registry.update_skill(skill_id, {"allowed_operators": operators}, actor=current_user.user_id)
        
        if out.get("error"):
             raise HTTPException(status_code=404, detail=out["error"])
        
        # Emit event via WebSocket manager
        from backend.services.websocket_manager import get_websocket_manager
        manager = get_websocket_manager()
        await manager.broadcast_to_user(str(current_user.id), {
            "event": "skill.operators_updated",
            "data": {"skill_id": skill_id, "operators": operators}
        })
        
        return {"success": True, "skill_id": skill_id, "operators": operators}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/{skill_id}/enable")
async def enable_skill(skill_id: str) -> Dict[str, Any]:
    """Enable a skill. Static skills use _skills_state; registry uses set_enabled."""
    if any(s["id"] == skill_id for s in SKILL_DEFS):
        _skills_state[skill_id] = True
        return {"success": True, "skill_id": skill_id, "enabled": True}
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        out = registry.set_enabled(skill_id, True)
        if out.get("error"):
            raise HTTPException(status_code=404, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{skill_id}/disable")
async def disable_skill(skill_id: str) -> Dict[str, Any]:
    """Disable a skill."""
    if any(s["id"] == skill_id for s in SKILL_DEFS):
        _skills_state[skill_id] = False
        return {"success": True, "skill_id": skill_id, "enabled": False}
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        out = registry.set_enabled(skill_id, False)
        if out.get("error"):
            raise HTTPException(status_code=404, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str) -> Dict[str, Any]:
    """Soft-delete (archive). Registry-only; keeps audit."""
    if any(s["id"] == skill_id for s in SKILL_DEFS):
        raise HTTPException(status_code=400, detail="Static skill cannot be archived")
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        out = registry.archive_skill(skill_id)
        if out.get("error"):
            raise HTTPException(status_code=404, detail=out["error"])
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ToggleBody(BaseModel):
    skill_id: str
    enabled: bool


@router.post("/toggle")
async def toggle_skill(body: ToggleBody) -> Dict[str, Any]:
    """Enable or disable a skill (static list or registry). Registry: persists via set_enabled."""
    if any(s["id"] == body.skill_id for s in SKILL_DEFS):
        _skills_state[body.skill_id] = body.enabled
        return {"success": True, "skill_id": body.skill_id, "enabled": body.enabled}
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        if registry.get_skill(body.skill_id) is not None:
            registry.set_enabled(body.skill_id, body.enabled)
            _registry_enabled[body.skill_id] = body.enabled
            return {"success": True, "skill_id": body.skill_id, "enabled": body.enabled}
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Skill not found")


class RunBody(BaseModel):
    skill_id: str
    params: Dict[str, Any] = {}
    dry_run: bool = True
    caller_role: str = "founder"       # founder | daena | agent
    caller_dept: Optional[str] = None
    caller_agent_id: Optional[str] = None


@router.post("/run")
async def run_skill(
    body: RunBody,
    x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token"),
) -> Dict[str, Any]:
    """Run a skill via Execution Layer. Requires X-Execution-Token. Enforces caller access (role/dept/agent_id)."""
    _verify_execution_token(x_execution_token)
    from backend.config.security_state import is_lockdown_active
    if is_lockdown_active():
        raise HTTPException(status_code=423, detail="Execution blocked: system in lockdown")

    # Registry skill: enforce allowed_roles / allowed_departments / allowed_agents
    reg_skill = _registry_skill_by_id(body.skill_id)
    if reg_skill:
        try:
            from backend.services.skill_registry import get_skill_registry
            registry = get_skill_registry()
            allowed, err = registry.check_caller_access(
                body.skill_id,
                role=body.caller_role,
                dept=body.caller_dept,
                agent_id=body.caller_agent_id,
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=err or "Access denied")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    skill = next((s for s in SKILL_DEFS if s["id"] == body.skill_id), None)
    if not skill and not reg_skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    if skill:
        if not _skills_state.get(skill["id"], True):
            raise HTTPException(status_code=400, detail="Skill is disabled")
        access = skill.get("access") or {"allowed_roles": ["founder", "daena"], "allowed_departments": [], "allowed_agents": []}
        allowed_roles = [r.lower() for r in access.get("allowed_roles", ["founder", "daena"])]
        if body.caller_role.lower() not in allowed_roles:
            raise HTTPException(status_code=403, detail=f"Role '{body.caller_role}' not allowed to run this skill")
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
