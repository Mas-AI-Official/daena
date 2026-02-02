"""
Use Case Library — templates that reference skill packs/skills.
GET/POST /api/v1/use-cases, GET/PUT /api/v1/use-cases/{id}, enable/disable, soft delete.
Operator scope: who can run (founder, daena, agent). Governance: approval profile, danger_zone_rules.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/use-cases", tags=["use-cases"])

# In-memory store (seed on first access)
_USE_CASES: Dict[str, Dict[str, Any]] = {}
_SEEDED = False

USE_CASE_NAMES = [
    "Daily Workflow Automation",
    "Auto Content Machine",
    "Lead Generation Bot",
    "Customer Support Agent",
    "Website Builder",
    "Research Assistant",
    "Trading & Data Monitor",
    "File Organizer",
    "CRM Manager",
    "Personal Ops Assistant",
    "Build Full Apps While You Sleep",
    "YouTube Channel Operator",
    "Price Monitoring Sniper",
    "Ad Campaign Operator",
    "Booking & Scheduling",
    "Sales Closer Assistant",
    "Automated Bookkeeping",
    "Data Dashboard Builder",
    "AI QA Tester",
    "Desktop Automation",
]


def _seed_use_cases() -> None:
    global _USE_CASES, _SEEDED
    if _SEEDED:
        return
    _SEEDED = True
    default_skills = ["repo_health_check", "security_scan", "daily_briefing", "filesystem_read", "workspace_search"]
    for i, name in enumerate(USE_CASE_NAMES):
        uid = f"use-case-{i+1:02d}"
        _USE_CASES[uid] = {
            "id": uid,
            "name": name,
            "description": f"Template: {name}. Uses workspace, research, and automation skills.",
            "operator_scope": "all",
            "default_skills": default_skills[: min(3 + (i % 3), 5)],
            "skill_pack_ids": [],
            "triggers": ["manual"],
            "approval_profile": "auto" if i % 3 != 2 else "approval_required",
            "danger_zone_rules": ["password_entry", "money_movement"],
            "enabled": True,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }
    return None


def get_use_cases_for_prompt() -> List[Dict[str, Any]]:
    """Sync list of use case id/name for system prompt (Daena awareness)."""
    _seed_use_cases()
    return [{"id": u["id"], "name": u.get("name", "")} for u in _USE_CASES.values() if u.get("enabled", True)]


class UseCaseBody(BaseModel):
    name: str
    description: str = ""
    operator_scope: str = "all"
    default_skills: List[str] = []
    skill_pack_ids: List[str] = []
    triggers: List[str] = ["manual"]
    approval_profile: str = "auto"
    danger_zone_rules: List[str] = []
    enabled: bool = True


@router.get("")
async def list_use_cases(
    operator_scope: Optional[str] = None,
    enabled_only: bool = False,
) -> Dict[str, Any]:
    """List use case templates. operator_scope filters by who can run."""
    _seed_use_cases()
    out = list(_USE_CASES.values())
    if enabled_only:
        out = [u for u in out if u.get("enabled", True)]
    if operator_scope and operator_scope.lower() not in ("", "all"):
        scope = operator_scope.lower()
        out = [u for u in out if scope in (u.get("operator_scope") or "all").lower() or (u.get("operator_scope") or "all") == "all"]
    return {"success": True, "use_cases": out}


@router.post("")
async def create_use_case(body: UseCaseBody) -> Dict[str, Any]:
    """Create a new use case template."""
    _seed_use_cases()
    uid = "use-case-" + uuid.uuid4().hex[:8]
    now = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    _USE_CASES[uid] = {
        "id": uid,
        "name": body.name,
        "description": body.description,
        "operator_scope": body.operator_scope,
        "default_skills": body.default_skills,
        "skill_pack_ids": body.skill_pack_ids,
        "triggers": body.triggers,
        "approval_profile": body.approval_profile,
        "danger_zone_rules": body.danger_zone_rules,
        "enabled": body.enabled,
        "created_at": now,
        "updated_at": now,
    }
    return {"success": True, "id": uid, "use_case": _USE_CASES[uid]}


@router.get("/{use_case_id}")
async def get_use_case(use_case_id: str) -> Dict[str, Any]:
    """Get one use case by id."""
    _seed_use_cases()
    if use_case_id not in _USE_CASES:
        raise HTTPException(status_code=404, detail="Use case not found")
    return {"success": True, "use_case": _USE_CASES[use_case_id]}


@router.put("/{use_case_id}")
async def update_use_case(use_case_id: str, body: UseCaseBody) -> Dict[str, Any]:
    """Update a use case template."""
    _seed_use_cases()
    if use_case_id not in _USE_CASES:
        raise HTTPException(status_code=404, detail="Use case not found")
    now = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    u = _USE_CASES[use_case_id]
    u.update({
        "name": body.name,
        "description": body.description,
        "operator_scope": body.operator_scope,
        "default_skills": body.default_skills,
        "skill_pack_ids": body.skill_pack_ids,
        "triggers": body.triggers,
        "approval_profile": body.approval_profile,
        "danger_zone_rules": body.danger_zone_rules,
        "enabled": body.enabled,
        "updated_at": now,
    })
    return {"success": True, "use_case": u}


@router.post("/{use_case_id}/enable")
async def enable_use_case(use_case_id: str) -> Dict[str, Any]:
    _seed_use_cases()
    if use_case_id not in _USE_CASES:
        raise HTTPException(status_code=404, detail="Use case not found")
    _USE_CASES[use_case_id]["enabled"] = True
    return {"success": True, "id": use_case_id, "enabled": True}


@router.post("/{use_case_id}/disable")
async def disable_use_case(use_case_id: str) -> Dict[str, Any]:
    _seed_use_cases()
    if use_case_id not in _USE_CASES:
        raise HTTPException(status_code=404, detail="Use case not found")
    _USE_CASES[use_case_id]["enabled"] = False
    return {"success": True, "id": use_case_id, "enabled": False}


@router.delete("/{use_case_id}")
async def delete_use_case(use_case_id: str, soft: bool = True) -> Dict[str, Any]:
    """Soft-delete by default (mark disabled and hidden)."""
    _seed_use_cases()
    if use_case_id not in _USE_CASES:
        raise HTTPException(status_code=404, detail="Use case not found")
    if soft:
        _USE_CASES[use_case_id]["enabled"] = False
        _USE_CASES[use_case_id]["archived"] = True
        return {"success": True, "id": use_case_id, "archived": True}
    del _USE_CASES[use_case_id]
    return {"success": True, "id": use_case_id, "deleted": True}
