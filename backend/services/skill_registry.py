"""
Skill Registry — Daena's dynamic skill engine.

Skills are typed, versioned, sandboxed capabilities that agents can use.
Daena (or any Council-approved agent) can CREATE new skills at runtime.
Every skill goes through a governance gate before it becomes active.

Lifecycle:
  DRAFT → PENDING_REVIEW → SANDBOX_TEST → APPROVED → ACTIVE
                                        └→ REJECTED
"""

import uuid
import json
import time
import hashlib
import traceback
from enum import Enum
from typing import Optional, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict


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
# DATA MODELS
# ─────────────────────────────────────────

@dataclass
class SkillVersion:
    version: str                        # semver: "1.0.0"
    code_hash: str                      # SHA-256 of the code body
    created_at: str
    created_by: str                     # agent_id or "founder"
    changelog: str = ""


@dataclass
class SkillDefinition:
    id: str
    name: str                           # unique slug: "read_csv"
    display_name: str                   # "Read CSV File"
    description: str
    category: SkillCategory
    creator: SkillCreator
    creator_agent_id: str               # which agent proposed it
    status: SkillStatus
    
    # The actual skill — typed input/output contract
    input_schema: dict                  # JSON Schema for inputs
    output_schema: dict                 # JSON Schema for outputs
    code_body: str                      # The executable code (Python)
    
    # Governance
    risk_level: str                     # "low" | "medium" | "high" | "critical"
    requires_approval: bool
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    # Versioning
    versions: list = field(default_factory=list)
    current_version: str = "1.0.0"
    
    # Usage
    dependencies: list = field(default_factory=list)  # other skill IDs it needs
    allowed_agents: list = field(default_factory=list) # [] = all agents
    usage_count: int = 0
    last_used_at: Optional[str] = None
    
    # Access scope (operators: who can run this skill; distinct from creator who authored it)
    allowed_roles: list = field(default_factory=list)      # founder, daena, agent
    allowed_departments: list = field(default_factory=list)
    approval_policy: str = "auto"                          # auto | approval_required | always_approval
    requires_step_up_confirm: bool = False
    enabled: bool = True
    archived: bool = False                                 # soft-delete; kept for audit
    category_slug: Optional[str] = None                    # UI category: utility, research, etc.
    
    # Sandbox test results
    sandbox_results: Optional[dict] = None
    
    # Timestamps
    created_at: str = ""
    updated_at: str = ""


# ─────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────

class SkillRegistry:
    """
    In-memory registry with persistence hooks.
    In production, swap _skills dict for a DB table.
    """

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}
        self._name_index: dict[str, str] = {}       # name → id
        self._load_builtins()

    # ─── BUILT-IN SKILLS (shipped with Daena) ────────────────────

    def _load_builtins(self):
        """Register core skills that ship with Daena. These are ACTIVE by default."""
        
        # 1. Custom built-ins (special implementations)
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
            }
        ]

        # 2. Auto-import from Tool Registry
        try:
            from backend.tools.registry import TOOL_DEFS
            for name, tool in TOOL_DEFS.items():
                # Skip if already in custom builtins
                if any(b["name"] == name for b in builtins):
                    continue
                
                # Heuristic categorization
                cat = SkillCategory.UTILITY
                if "filesystem" in name or "workspace" in name: cat = SkillCategory.FILESYSTEM
                if "net" in name or "web" in name or "browser" in name: cat = SkillCategory.NETWORK
                if "git" in name or "repo" in name or "patch" in name or "run" in name: cat = SkillCategory.CODE_EXEC
                if "scan" in name or "defender" in name or "security" in name: cat = SkillCategory.SECURITY
                if "consult" in name: cat = SkillCategory.AI_TOOL
                if "scrape" in name or "search" in name: cat = SkillCategory.RESEARCH
                
                # Heuristic risk
                risk = "medium"
                if cat in (SkillCategory.FILESYSTEM, SkillCategory.RESEARCH, SkillCategory.UTILITY): risk = "low"
                if "exec" in name or "shell" in name or "write" in name: risk = "high"
                if "read" in name or "list" in name or "info" in name: risk = "low"

                builtins.append({
                    "name": name,
                    "display_name": name.replace("_", " ").title(),
                    "description": tool.description,
                    "category": cat,
                    "risk_level": risk,
                    "input_schema": {"type": "object", "properties": {"args": {"type": "object"}}}, # Generic
                    "output_schema": {"type": "object", "properties": {"result": {"type": "any"}}},
                    "code_body": f"# Tool wrapper for {name}"
                })
        except Exception as e:
            print(f"Warning: Failed to auto-import tools as skills: {e}")

        for b in builtins:
            skill_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            # Stable hash for builtins so ID persists if possible? No, UUID is random.
            # Ideally we'd use a deterministic UUID based on name for builtins.
            skill_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, b["name"]))
            
            # Simple code hash
            code_hash = hashlib.sha256(b["code_body"].encode()).hexdigest()[:16]

            skill = SkillDefinition(
                id=skill_id,
                name=b["name"],
                display_name=b["display_name"],
                description=b["description"],
                category=b["category"],
                creator=SkillCreator.FOUNDER,
                creator_agent_id="system",
                status=SkillStatus.ACTIVE,
                input_schema=b["input_schema"],
                output_schema=b["output_schema"],
                code_body=b["code_body"],
                risk_level=b["risk_level"],
                requires_approval=False,
                approved_by="system_builtin",
                versions=[SkillVersion(version="1.0.0", code_hash=code_hash, created_at=now, created_by="system", changelog="Initial builtin")],
                current_version="1.0.0",
                created_at=now,
                updated_at=now,
                category_slug=b["category"].value
            )
            self._skills[skill_id] = skill
            self._name_index[b["name"]] = skill_id

    # ─── PUBLIC API ────────────────────────────────────────────────

    def list_skills(self, status_filter: Optional[str] = None,
                    category_filter: Optional[str] = None,
                    operator_role: Optional[str] = None,
                    include_archived: bool = False) -> list[dict]:
        """List skills. operator_role filters by who can execute (allowed_roles)."""
        results = []
        for skill in self._skills.values():
            if skill.archived and not include_archived:
                continue
            if status_filter and skill.status.value != status_filter:
                continue
            if category_filter and skill.category.value != category_filter:
                continue
            if operator_role:
                roles = [r.lower() for r in (skill.allowed_roles or [])]
                if operator_role.lower() not in roles:
                    continue
            results.append(self._to_dict(skill))
        return results

    def get_skill(self, skill_id: str) -> Optional[dict]:
        """Get skill by ID."""
        skill = self._skills.get(skill_id)
        return self._to_dict(skill) if skill else None

    def get_skill_by_name(self, name: str) -> Optional[dict]:
        """Get skill by unique name."""
        skill_id = self._name_index.get(name)
        if skill_id:
            return self.get_skill(skill_id)
        return None

    def create_skill(self, payload: dict) -> dict:
        """
        Create a new skill (DRAFT).
        Daena or sub-agents can propose skills.
        Founder skills bypass approval.
        Control-panel payload: name, display_name, description, category, creator, code_body;
        optional access (allowed_roles, allowed_departments, allowed_agents), risk_level,
        approval_policy, requires_step_up_confirm, enabled.
        """
        required = ["name", "display_name", "description", "category", "creator", "code_body"]
        for f in required:
            if f not in payload:
                return {"error": f"Missing required field: {f}"}

        name = payload["name"]
        if name in self._name_index:
            return {"error": f"Skill name '{name}' already exists"}
        if not name.replace("_", "").isalnum():
            return {"error": "Skill name must be alphanumeric with underscores only"}

        # Normalize for control-pannel: default input_schema, output_schema, creator_agent_id
        creator_agent_id = payload.get("creator_agent_id", "control_panel")
        input_schema = payload.get("input_schema") or {"type": "object", "properties": {}, "required": []}
        output_schema = payload.get("output_schema") or {"type": "object", "properties": {"result": {"type": "string"}}}

        # Category: UI slug (utility, research, ...) or enum value
        cat_val = payload["category"]
        try:
            category = SkillCategory(cat_val)
            category_slug = cat_val
        except ValueError:
            category = SkillCategory.CUSTOM
            category_slug = str(cat_val)

        risk = payload.get("risk_level") or self._assess_risk(payload)
        creator = SkillCreator(payload["creator"])

        if creator == SkillCreator.FOUNDER and risk in ("low", "medium"):
            initial_status = SkillStatus.ACTIVE
            requires_approval = False
            approved_by = "founder"
        else:
            initial_status = SkillStatus.PENDING_REVIEW
            requires_approval = True
            approved_by = None

        access = payload.get("access") or {}
        allowed_roles = access.get("allowed_roles") or payload.get("allowed_roles") or ["founder", "daena"]
        allowed_departments = access.get("allowed_departments") or payload.get("allowed_departments") or []
        allowed_agents = access.get("allowed_agents") or payload.get("allowed_agents") or []
        approval_policy = payload.get("approval_policy") or ("auto" if risk == "low" else "approval_required")
        requires_step_up = payload.get("requires_step_up_confirm", False)
        enabled = payload.get("enabled", True)

        now = datetime.now(timezone.utc).isoformat()
        skill_id = str(uuid.uuid4())
        code_hash = hashlib.sha256(payload["code_body"].encode()).hexdigest()[:16]

        skill = SkillDefinition(
            id=skill_id,
            name=name,
            display_name=payload["display_name"],
            description=payload["description"],
            category=category,
            creator=creator,
            creator_agent_id=creator_agent_id,
            status=initial_status,
            input_schema=input_schema,
            output_schema=output_schema,
            code_body=payload["code_body"],
            risk_level=risk,
            requires_approval=requires_approval,
            approved_by=approved_by,
            versions=[SkillVersion(
                version="1.0.0",
                code_hash=code_hash,
                created_at=now,
                created_by=creator_agent_id,
                changelog="Initial creation"
            )],
            current_version="1.0.0",
            dependencies=payload.get("dependencies", []),
            allowed_agents=allowed_agents,
            allowed_roles=allowed_roles,
            allowed_departments=allowed_departments,
            approval_policy=approval_policy,
            requires_step_up_confirm=requires_step_up,
            enabled=enabled,
            category_slug=category_slug,
            created_at=now,
            updated_at=now
        )

        self._skills[skill_id] = skill
        self._name_index[name] = skill_id

        return {
            "id": skill_id,
            "skill_id": skill_id,
            "success": True,
            "status": initial_status.value,
            "risk_level": risk,
            "requires_approval": requires_approval,
            "message": f"Skill '{name}' created. Status: {initial_status.value}"
        }

    def approve_skill(self, skill_id: str, approver: str = "founder",
                      notes: str = "") -> dict:
        """Approve a skill (Founder or Council action)."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        if skill.status not in (SkillStatus.PENDING_REVIEW, SkillStatus.SANDBOX_TEST):
            return {"error": f"Cannot approve skill in status: {skill.status.value}"}

        skill.status = SkillStatus.ACTIVE
        skill.approved_by = approver
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        return {
            "id": skill_id,
            "status": "active",
            "message": f"Skill '{skill.name}' approved by {approver}"
        }

    def reject_skill(self, skill_id: str, reason: str = "",
                     rejector: str = "founder") -> dict:
        """Reject a proposed skill."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        if skill.status not in (SkillStatus.PENDING_REVIEW, SkillStatus.SANDBOX_TEST):
            return {"error": f"Cannot reject skill in status: {skill.status.value}"}

        skill.status = SkillStatus.REJECTED
        skill.rejection_reason = reason
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        return {
            "id": skill_id,
            "status": "rejected",
            "reason": reason,
            "message": f"Skill '{skill.name}' rejected: {reason}"
        }

    def test_skill_sandbox(self, skill_id: str, test_inputs: dict) -> dict:
        """
        Run a skill in sandbox mode.
        Captures stdout/stderr, checks for errors.
        Updates sandbox_results on the skill.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        # Transition to sandbox_test if pending_review
        if skill.status == SkillStatus.PENDING_REVIEW:
            skill.status = SkillStatus.SANDBOX_TEST

        # Execute in sandbox (simulated — real impl uses subprocess with limits)
        result = self._run_in_sandbox(skill, test_inputs)

        skill.sandbox_results = result
        skill.updated_at = datetime.now(timezone.utc).isoformat()

        return {
            "id": skill_id,
            "status": skill.status.value,
            "sandbox_results": result
        }

    def deprecate_skill(self, skill_id: str, reason: str = "") -> dict:
        """Deprecate an active skill (still callable but flagged)."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        skill.status = SkillStatus.DEPRECATED
        skill.updated_at = datetime.now(timezone.utc).isoformat()
        return {"id": skill_id, "status": "deprecated", "message": f"Deprecated: {reason}"}

    def update_skill(self, skill_id: str, payload: dict) -> dict:
        """Full update: creator, access, policy, enabled, display_name, description, etc."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        now = datetime.now(timezone.utc).isoformat()
        if "display_name" in payload:
            skill.display_name = payload["display_name"]
        if "description" in payload:
            skill.description = payload["description"]
        if "creator" in payload:
            try:
                skill.creator = SkillCreator(payload["creator"])
            except ValueError:
                pass
        if "access" in payload:
            a = payload["access"]
            skill.allowed_roles = a.get("allowed_roles", skill.allowed_roles)
            skill.allowed_departments = a.get("allowed_departments", skill.allowed_departments)
            skill.allowed_agents = a.get("allowed_agents", skill.allowed_agents)
        if "policy" in payload:
            p = payload["policy"]
            if "risk_level" in p:
                skill.risk_level = p["risk_level"]
            if "approval_policy" in p:
                skill.approval_policy = p["approval_policy"]
            if "requires_step_up_confirm" in p:
                skill.requires_step_up_confirm = p["requires_step_up_confirm"]
        if "enabled" in payload:
            skill.enabled = bool(payload["enabled"])
        if "category" in payload:
            try:
                skill.category = SkillCategory(payload["category"])
            except ValueError:
                skill.category_slug = str(payload["category"])
        skill.updated_at = now
        return {"id": skill_id, "success": True, "message": "Skill updated"}

    def update_access(self, skill_id: str, access: dict) -> dict:
        """Update only access (allowed_roles, allowed_departments, allowed_agents)."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        if "allowed_roles" in access:
            skill.allowed_roles = list(access["allowed_roles"]) if isinstance(access["allowed_roles"], (list, tuple)) else skill.allowed_roles
        if "allowed_departments" in access:
            skill.allowed_departments = list(access["allowed_departments"]) if isinstance(access["allowed_departments"], (list, tuple)) else skill.allowed_departments
        if "allowed_agents" in access:
            skill.allowed_agents = list(access["allowed_agents"]) if isinstance(access["allowed_agents"], (list, tuple)) else skill.allowed_agents
        skill.updated_at = datetime.now(timezone.utc).isoformat()
        return {"id": skill_id, "success": True, "access": {"allowed_roles": skill.allowed_roles, "allowed_departments": skill.allowed_departments, "allowed_agents": skill.allowed_agents}}

    def set_enabled(self, skill_id: str, enabled: bool) -> dict:
        """Enable or disable a skill."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        skill.enabled = bool(enabled)
        skill.updated_at = datetime.now(timezone.utc).isoformat()
        return {"id": skill_id, "success": True, "enabled": skill.enabled}

    def archive_skill(self, skill_id: str) -> dict:
        """Soft-delete: set archived=True. Kept for audit."""
        skill = self._skills.get(skill_id)
        if not skill:
            return {"error": "Skill not found"}
        skill.archived = True
        skill.enabled = False
        skill.updated_at = datetime.now(timezone.utc).isoformat()
        return {"id": skill_id, "success": True, "archived": True, "message": "Skill archived"}

    def get_manifest(self) -> list[dict]:
        """Compact list for agents: id, name, access summary, policy summary. Excludes archived."""
        out = []
        for skill in self._skills.values():
            if skill.archived:
                continue
            out.append({
                "id": skill.id,
                "name": skill.name,
                "display_name": skill.display_name,
                "allowed_roles": list(skill.allowed_roles or []),
                "risk_level": skill.risk_level,
                "approval_policy": skill.approval_policy,
                "enabled": skill.enabled,
            })
        return out

    def check_caller_access(self, skill_id: str, role: str, dept: Optional[str] = None, agent_id: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Check if caller (role, dept, agent_id) is allowed to run this skill. Returns (allowed, error_message)."""
        skill = self._skills.get(skill_id)
        if not skill:
            return (False, "Skill not found")
        if skill.archived or not skill.enabled:
            return (False, "Skill is archived or disabled")
        roles = [r.lower() for r in (skill.allowed_roles or [])]
        if role.lower() not in roles:
            return (False, f"Role '{role}' not in allowed_roles {roles}")
        if skill.allowed_departments and dept and dept not in (skill.allowed_departments or []):
            return (False, f"Department '{dept}' not in allowed_departments")
        if skill.allowed_agents and agent_id and agent_id not in (skill.allowed_agents or []):
            return (False, f"Agent '{agent_id}' not in allowed_agents")
        return (True, None)

    def record_usage(self, skill_id: str):
        """Record that a skill was used."""
        skill = self._skills.get(skill_id)
        if skill:
            skill.usage_count += 1
            skill.last_used_at = datetime.now(timezone.utc).isoformat()

    def get_stats(self) -> dict:
        """Registry-wide statistics."""
        skills = list(self._skills.values())
        return {
            "total": len(skills),
            "active": sum(1 for s in skills if s.status == SkillStatus.ACTIVE),
            "pending_review": sum(1 for s in skills if s.status == SkillStatus.PENDING_REVIEW),
            "sandbox_test": sum(1 for s in skills if s.status == SkillStatus.SANDBOX_TEST),
            "rejected": sum(1 for s in skills if s.status == SkillStatus.REJECTED),
            "deprecated": sum(1 for s in skills if s.status == SkillStatus.DEPRECATED),
            "by_category": self._count_by_category(skills),
            "by_creator": self._count_by_creator(skills),
            "self_created": sum(1 for s in skills if s.creator == SkillCreator.DAENA),
            "most_used": self._most_used(skills, top=3)
        }

    # ─── PRIVATE HELPERS ──────────────────────────────────────────

    def _assess_risk(self, payload: dict) -> str:
        """Heuristic risk assessment based on category and code patterns."""
        category = payload.get("category", "custom")
        code = payload.get("code_body", "")

        # High-risk categories
        if category in ("code_exec", "network", "external_api"):
            return "high"

        # Scan code for dangerous patterns
        danger_patterns = [
            "import os", "os.system", "subprocess", "eval(", "exec(",
            "open(", "shutil", "socket", "__import__",
            "requests.get", "urllib", "http.client"
        ]
        hits = sum(1 for p in danger_patterns if p in code)

        if hits >= 3:
            return "critical"
        elif hits >= 2:
            return "high"
        elif hits >= 1:
            return "medium"
        else:
            return "low"

    def _run_in_sandbox(self, skill: SkillDefinition, inputs: dict) -> dict:
        """
        Simulated sandbox execution.
        In production: Docker container, resource limits, timeout, no network.
        """
        start = time.time()
        try:
            # For builtins, simulate success
            if "Built-in" in skill.code_body:
                return {
                    "success": True,
                    "stdout": f"[BUILTIN] {skill.name} executed with inputs: {json.dumps(inputs)}",
                    "stderr": "",
                    "exit_code": 0,
                    "duration_ms": round((time.time() - start) * 1000),
                    "security_flags": []
                }

            # For user code, simulate (real impl: subprocess with limits)
            # Basic static analysis
            flags = []
            code = skill.code_body
            if "eval(" in code or "exec(" in code:
                flags.append("WARN: Dynamic code evaluation detected")
            if "os.system" in code or "subprocess" in code:
                flags.append("WARN: System command execution detected")
            if "import socket" in code or "requests" in code:
                flags.append("WARN: Network access attempted")

            return {
                "success": len(flags) == 0,
                "stdout": f"Sandbox analysis complete for '{skill.name}'",
                "stderr": "\n".join(flags) if flags else "",
                "exit_code": 0 if not flags else 1,
                "duration_ms": round((time.time() - start) * 1000),
                "security_flags": flags
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "duration_ms": round((time.time() - start) * 1000),
                "security_flags": [f"ERROR: {str(e)}"]
            }

    def _count_by_category(self, skills: list) -> dict:
        counts = {}
        for s in skills:
            cat = s.category.value
            counts[cat] = counts.get(cat, 0) + 1
        return counts

    def _count_by_creator(self, skills: list) -> dict:
        counts = {}
        for s in skills:
            c = s.creator.value
            counts[c] = counts.get(c, 0) + 1
        return counts

    def _most_used(self, skills: list, top: int = 3) -> list:
        sorted_skills = sorted(skills, key=lambda s: s.usage_count, reverse=True)
        return [{"name": s.name, "usage_count": s.usage_count} for s in sorted_skills[:top]]

    def _to_dict(self, skill: SkillDefinition) -> dict:
        """Convert to JSON-safe dict."""
        d = asdict(skill)
        d["category"] = skill.category_slug or skill.category.value
        d["creator"] = skill.creator.value
        d["status"] = skill.status.value
        d["approval_policy"] = skill.approval_policy
        d["access"] = {"allowed_roles": skill.allowed_roles, "allowed_departments": skill.allowed_departments, "allowed_agents": skill.allowed_agents}
        d["enabled"] = skill.enabled
        d["archived"] = getattr(skill, "archived", False)
        d["requires_step_up_confirm"] = skill.requires_step_up_confirm
        if len(d.get("code_body", "")) > 200:
            d["code_body_preview"] = d["code_body"][:200] + "..."
        return d


# ─── SINGLETON ─────────────────────────────────────────────────────
_registry = None

def get_skill_registry() -> SkillRegistry:
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
