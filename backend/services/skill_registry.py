"""
Skill Registry — Daena's dynamic skill engine.
Now backed by SQLAlchemy DB for persistence and advanced filtering.
"""

import uuid
import json
import time
import hashlib
import traceback
import logging
from enum import Enum
from typing import Optional, Any, Tuple, List
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

from backend.database import SessionLocal, Skill, SkillAuditLog
from sqlalchemy.orm import Session
from sqlalchemy import or_

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class SkillStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SANDBOX_TEST = "sandbox_test"
    APPROVED = "approved"
    ACTIVE = "active"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"

class SkillCategory(str, Enum):
    FILESYSTEM = "filesystem"
    NETWORK = "network"
    CODE_EXEC = "code_exec"
    DATA_TRANSFORM = "data_transform"
    EXTERNAL_API = "external_api"
    AI_TOOL = "ai_tool"
    SECURITY = "security"
    RESEARCH = "research"
    UTILITY = "utility"
    CUSTOM = "custom"

class SkillCreator(str, Enum):
    FOUNDER = "founder"          # Masoud — highest trust
    DAENA = "daena"              # Self-created — needs Council approval
    COUNCIL = "council"          # Council-proposed
    AGENT = "agent"              # Sub-agent proposed — needs Daena + Council

# ─────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────

class SkillRegistry:
    """
    DB-backed registry with audit logging.
    """

    def __init__(self):
        # We ensure built-ins are in the DB on startup
        self._ensure_builtins()

    def _ensure_builtins(self):
        """Ensure core skills exist in DB. ACTIVE by default."""
        db = SessionLocal()
        try:
            # Logic similar to old _load_builtins but checking DB
            builtins = [
                {
                    "name": "defi_scan",
                    "display_name": "DeFi Contract Scanner",
                    "description": "Scan Solidity smart contracts with Slither. Returns vulnerability report.",
                    "category": SkillCategory.SECURITY,
                    "risk_level": "medium",
                    "input_schema": {"type": "object", "properties": {"contract_path": {"type": "string"}}, "required": ["contract_path"]},
                    "output_schema": {"type": "object", "properties": {"vulnerabilities": {"type": "array"}}},
                    "code_body": "# Built-in — delegates to Slither"
                },
                {
                    "name": "integrity_verify",
                    "display_name": "Integrity Shield Verify",
                    "description": "Verify data source trust score and check for prompt injection.",
                    "category": SkillCategory.SECURITY,
                    "risk_level": "low",
                    "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
                    "output_schema": {"type": "object", "properties": {"trusted": {"type": "boolean"}}},
                    "code_body": "# Built-in — delegates to Integrity Shield"
                },
                {
                    "name": "web_search",
                    "display_name": "Web Search (Tavily/Google)",
                    "description": "Research information online via real-time search engines.",
                    "category": SkillCategory.RESEARCH,
                    "risk_level": "low",
                    "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}},
                    "output_schema": {"type": "object", "properties": {"results": {"type": "array"}}},
                    "code_body": "# Built-in search tool",
                    "allowed_operators": ["founder", "daena", "agent"]
                },
                {
                    "name": "filesystem_read",
                    "display_name": "File System Read",
                    "description": "Read local files from the project workspace.",
                    "category": SkillCategory.FILESYSTEM,
                    "risk_level": "low",
                    "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
                    "output_schema": {"type": "object", "properties": {"content": {"type": "string"}}},
                    "code_body": "# Built-in file tool",
                    "allowed_operators": ["founder", "daena"]
                }
            ]

            # Heuristic for generic tools might be too slow on every startup, 
            # so we'll just check these specific ones or a subset.
            
            for b in builtins:
                existing = db.query(Skill).filter(Skill.name == b["name"]).first()
                if not existing:
                    skill_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, b["name"]))
                    new_skill = Skill(
                        id=skill_id,
                        name=b["name"],
                        display_name=b["display_name"],
                        description=b["description"],
                        category=b["category"].value,
                        creator="founder",
                        creator_agent_id="system",
                        status="active",
                        input_schema=b["input_schema"],
                        output_schema=b["output_schema"],
                        code_body=b["code_body"],
                        risk_level=b["risk_level"],
                        approval_policy="auto",
                        allowed_operators=b.get("allowed_operators", ["founder", "daena"]),
                        enabled=True
                    )
                    db.add(new_skill)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to ensure built-ins: {e}")
            db.rollback()
        finally:
            db.close()

    # ─── PUBLIC API ────────────────────────────────────────────────

    def list_skills(self, status_filter: Optional[str] = None,
                    category_filter: Optional[str] = None,
                    operator_role: Optional[str] = None,
                    include_archived: bool = False) -> List[Dict[str, Any]]:
        """List skills. operator_role filters by allowed_operators."""
        db = SessionLocal()
        try:
            query = db.query(Skill)
            if not include_archived:
                query = query.filter(Skill.archived == False)
            if status_filter:
                query = query.filter(Skill.status == status_filter)
            if category_filter:
                query = query.filter(Skill.category == category_filter)
            
            skills = query.all()
            
            # Post-filter for JSON column allowed_operators
            if operator_role:
                op = operator_role.lower()
                # Simple check within the JSON list
                skills = [s for s in skills if s.allowed_operators and op in [x.lower() for x in s.allowed_operators]]
            
            return [self._to_dict(s) for s in skills]
        finally:
            db.close()

    def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get skill by ID."""
        db = SessionLocal()
        try:
            skill = db.query(Skill).filter(Skill.id == skill_id).first()
            return self._to_dict(skill) if skill else None
        finally:
            db.close()

    def get_skill_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get skill by unique name."""
        db = SessionLocal()
        try:
            skill = db.query(Skill).filter(Skill.name == name).first()
            return self._to_dict(skill) if skill else None
        finally:
            db.close()

    def create_skill(self, payload: Dict[str, Any], actor: str = "founder", ip: str = None, session_id: str = None) -> Dict[str, Any]:
        """
        Create a new skill.
        """
        required = ["name", "display_name", "description", "category", "creator", "code_body"]
        for f in required:
            if f not in payload:
                return {"error": f"Missing required field: {f}"}

        db = SessionLocal()
        try:
            name = payload["name"]
            existing = db.query(Skill).filter(Skill.name == name).first()
            if existing:
                return {"error": f"Skill name '{name}' already exists"}

            # Risk Assessment
            risk = payload.get("risk_level") or self._assess_risk(payload)
            
            # Approval Policy Logic
            # High-risk skills must default to needs_approval unless Founder sets always.
            # Only Founder can set approval_policy="auto" for high-risk skills.
            approval_policy = payload.get("approval_policy") or "needs_approval"
            if risk in ("high", "critical"):
                if actor != "founder" or approval_policy == "auto":
                    approval_policy = "needs_approval" # Force override for safety
            
            # Initial status
            status = "active" if (actor == "founder" and risk != "critical") else "pending_review"

            skill_id = str(uuid.uuid4())
            new_skill = Skill(
                id=skill_id,
                name=name,
                display_name=payload["display_name"],
                description=payload["description"],
                category=payload["category"],
                creator=payload["creator"],
                creator_agent_id=payload.get("creator_agent_id", actor),
                status=status,
                input_schema=payload.get("input_schema", {}),
                output_schema=payload.get("output_schema", {}),
                code_body=payload["code_body"],
                risk_level=risk,
                approval_policy=approval_policy,
                allowed_operators=payload.get("allowed_operators", ["founder", "daena"]),
                allowed_departments=payload.get("allowed_departments", []),
                allowed_agents=payload.get("allowed_agents", []),
                enabled=payload.get("enabled", True)
            )
            db.add(new_skill)
            
            # Audit Log
            log = SkillAuditLog(
                skill_id=skill_id,
                action="create",
                changed_by=actor,
                after_json=self._to_dict(new_skill),
                ip_address=ip,
                session_id=session_id
            )
            db.add(log)
            
            db.commit()
            return {"success": True, "id": skill_id, "status": status}
        except Exception as e:
            db.rollback()
            logger.error(f"Create skill failed: {e}")
            return {"error": str(e)}
        finally:
            db.close()

    def update_skill(self, skill_id: str, payload: Dict[str, Any], actor: str = "founder", ip: str = None, session_id: str = None) -> Dict[str, Any]:
        """Full update with auditing."""
        db = SessionLocal()
        try:
            skill = db.query(Skill).filter(Skill.id == skill_id).first()
            if not skill:
                return {"error": "Skill not found"}
            
            before_data = self._to_dict(skill)
            
            # Update fields
            if "display_name" in payload: skill.display_name = payload["display_name"]
            if "description" in payload: skill.description = payload["description"]
            if "category" in payload: skill.category = payload["category"]
            if "code_body" in payload: skill.code_body = payload["code_body"]
            
            if "allowed_operators" in payload: 
                skill.allowed_operators = payload["allowed_operators"]
            
            if "approval_policy" in payload:
                # Validation: Only Founder can set auto for high-risk
                ap = payload["approval_policy"]
                if skill.risk_level in ("high", "critical") and ap == "auto" and actor != "founder":
                    ap = "needs_approval"
                skill.approval_policy = ap
                
            if "risk_level" in payload:
                skill.risk_level = payload["risk_level"]
                
            if "enabled" in payload:
                skill.enabled = payload["enabled"]
            
            skill.updated_at = datetime.utcnow()
            
            # Audit Log
            log = SkillAuditLog(
                skill_id=skill_id,
                action="update",
                changed_by=actor,
                before_json=before_data,
                after_json=self._to_dict(skill),
                ip_address=ip,
                session_id=session_id
            )
            db.add(log)
            
            db.commit()
            return {"success": True, "message": "Skill updated"}
        except Exception as e:
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def set_enabled(self, skill_id: str, enabled: bool, actor: str = "founder") -> Dict[str, Any]:
        """Toggle enabled state."""
        return self.update_skill(skill_id, {"enabled": enabled}, actor=actor)

    def archive_skill(self, skill_id: str, actor: str = "founder") -> Dict[str, Any]:
        """Soft-delete."""
        return self.update_skill(skill_id, {"archived": True, "enabled": False}, actor=actor)

    def get_manifest(self) -> List[Dict[str, Any]]:
        """Compact list for agents."""
        db = SessionLocal()
        try:
            skills = db.query(Skill).filter(Skill.archived == False, Skill.enabled == True).all()
            return [{
                "id": s.id,
                "name": s.name,
                "display_name": s.display_name,
                "allowed_operators": s.allowed_operators,
                "risk_level": s.risk_level,
                "approval_policy": s.approval_policy
            } for s in skills]
        finally:
            db.close()

    def check_caller_access(self, skill_id: str, role: str, dept: Optional[str] = None, agent_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Check access."""
        db = SessionLocal()
        try:
            skill = db.query(Skill).filter(Skill.id == skill_id).first()
            if not skill:
                return False, "Skill not found"
            if skill.archived or not skill.enabled:
                return False, "Skill disabled"
            
            allowed_roles = [r.lower() for r in (skill.allowed_operators or [])]
            if role.lower() not in allowed_roles:
                return False, f"Role '{role}' not authorized"
            
            return True, None
        finally:
            db.close()

    def _assess_risk(self, payload: Dict[str, Any]) -> str:
        """Heuristic risk assessment."""
        cat = payload.get("category", "custom")
        code = payload.get("code_body", "")
        if cat in ("code_exec", "network"): return "high"
        if "os.system" in code or "subprocess" in code: return "critical"
        return "low"

    def _to_dict(self, skill: Skill) -> Dict[str, Any]:
        if not skill: return None
        return {
            "id": skill.id,
            "name": skill.name,
            "display_name": skill.display_name,
            "description": skill.description,
            "category": skill.category,
            "creator": skill.creator,
            "creator_agent_id": skill.creator_agent_id,
            "status": skill.status,
            "risk_level": skill.risk_level,
            "approval_policy": skill.approval_policy,
            "allowed_operators": skill.allowed_operators,
            "enabled": skill.enabled,
            "archived": skill.archived,
            "usage_count": skill.usage_count,
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
            "updated_at": skill.updated_at.isoformat() if skill.updated_at else None
        }

    def get_stats(self) -> Dict[str, Any]:
        """Stats for dashboard."""
        db = SessionLocal()
        try:
            total = db.query(Skill).count()
            active = db.query(Skill).filter(Skill.enabled == True).count()
            return {"total": total, "active": active}
        finally:
            db.close()

# Singleton
_registry = None

def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
