"""
Skill Packs — named bundles of skill_ids for Use Cases.
GET/POST/PUT /api/v1/skill-packs, GET /api/v1/skill-packs/{id}.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/skill-packs", tags=["skill-packs"])

_STORE: Dict[str, Dict[str, Any]] = {}

# Seed curated packs (match Use Case Library and Daena tools)
SEED_PACKS = [
    {"id": "pack-workspace", "name": "Workspace Pack", "description": "Read, search, tree, patch. Safe for file ops.", "skill_ids": ["filesystem_read", "workspace_search", "repo_health_check", "apply_patch"], "operator_scope": "all", "approval_profile": "auto"},
    {"id": "pack-browser-hands", "name": "Browser Hands Pack", "description": "Open, click, type, screenshot via DaenaBot Hands.", "skill_ids": ["browser.navigate", "browser.screenshot"], "operator_scope": "all", "approval_profile": "approval_required"},
    {"id": "pack-dev", "name": "Dev Pack", "description": "Build, test, lint, typecheck.", "skill_ids": ["fix_build_errors", "write_unit_tests", "security_scan"], "operator_scope": "all", "approval_profile": "approval_required"},
    {"id": "pack-security", "name": "Security Pack", "description": "Secret scan, dependency audit, SBOM.", "skill_ids": ["security_scan"], "operator_scope": "founder", "approval_profile": "approval_required"},
    {"id": "pack-content", "name": "Content Pack", "description": "Caption, scripts, outlines.", "skill_ids": ["daily_briefing", "investor_outreach_draft"], "operator_scope": "all", "approval_profile": "auto"},
    {"id": "pack-ops", "name": "Ops Pack", "description": "Email drafting, docs update.", "skill_ids": ["daily_briefing", "investor_outreach_draft"], "operator_scope": "all", "approval_profile": "auto"},
    {"id": "pack-web3", "name": "Web3 Pack", "description": "Read-only scanning, reporting.", "skill_ids": [], "operator_scope": "all", "approval_profile": "auto"},
]


def _ensure_seeded() -> None:
    for p in SEED_PACKS:
        if p["id"] not in _STORE:
            _STORE[p["id"]] = dict(p)


def get_skill_packs_for_prompt() -> List[Dict[str, Any]]:
    """Sync list of skill pack id/name for system prompt (Daena awareness)."""
    _ensure_seeded()
    return [{"id": p["id"], "name": p.get("name", "")} for p in _STORE.values()]


class SkillPackBody(BaseModel):
    name: str
    description: str = ""
    skill_ids: List[str] = []
    operator_scope: str = "all"
    approval_profile: str = "auto"


@router.get("")
async def list_skill_packs() -> Dict[str, Any]:
    """List all skill packs."""
    _ensure_seeded()
    return {"success": True, "skill_packs": list(_STORE.values())}


@router.post("")
async def create_skill_pack(body: SkillPackBody) -> Dict[str, Any]:
    """Create a new skill pack."""
    _ensure_seeded()
    uid = "pack-" + uuid.uuid4().hex[:8]
    _STORE[uid] = {
        "id": uid,
        "name": body.name,
        "description": body.description,
        "skill_ids": body.skill_ids,
        "operator_scope": body.operator_scope,
        "approval_profile": body.approval_profile,
    }
    return {"success": True, "id": uid, "skill_pack": _STORE[uid]}


@router.get("/{pack_id}")
async def get_skill_pack(pack_id: str) -> Dict[str, Any]:
    """Get one skill pack by id."""
    _ensure_seeded()
    if pack_id not in _STORE:
        raise HTTPException(status_code=404, detail="Skill pack not found")
    return {"success": True, "skill_pack": _STORE[pack_id]}


@router.put("/{pack_id}")
async def update_skill_pack(pack_id: str, body: SkillPackBody) -> Dict[str, Any]:
    """Update a skill pack."""
    _ensure_seeded()
    if pack_id not in _STORE:
        raise HTTPException(status_code=404, detail="Skill pack not found")
    _STORE[pack_id].update({
        "name": body.name,
        "description": body.description,
        "skill_ids": body.skill_ids,
        "operator_scope": body.operator_scope,
        "approval_profile": body.approval_profile,
    })
    return {"success": True, "skill_pack": _STORE[pack_id]}
