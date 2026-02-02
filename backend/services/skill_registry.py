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
from typing import Optional, Any
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
    
    # Access scope (who can run this skill)
    allowed_roles: list = field(default_factory=list)      # founder, daena, agent
    allowed_departments: list = field(default_factory=list)
    approval_policy: str = "auto"                          # auto | approval_required | always_approval
    requires_step_up_confirm: bool = False
    enabled: bool = True
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
        builtins = [
            {
                "name": "filesystem_read",
                "display_name": "Read File / Directory",
                "description": "Read file contents or list directory. Sandboxed to project root.",
                "category": SkillCategory.FILESYSTEM,
                "risk_level": "low",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path from project root"}
                    },
                    "required": ["path"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "is_dir": {"type": "boolean"},
                        "entries": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "code_body": "# Built-in — handled by execution engine"
            },
            {
                "name": "workspace_search",
                "display_name": "Search Workspace (grep)",
                "description": "Grep-style search across project files. Supports regex.",
                "category": SkillCategory.FILESYSTEM,
                "risk_level": "low",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string", "default": "."},
                        "recursive": {"type": "boolean", "default": True}
                    },
                    "required": ["pattern"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "matches": {"type": "array", "items": {"type": "object"}}
                    }
                },
                "code_body": "# Built-in — handled by execution engine"
            },
            {
                "name": "apply_patch",
                "display_name": "Apply Code Patch",
                "description": "Apply a unified diff or str-replace patch to a file. Requires Founder approval for production files.",
                "category": SkillCategory.CODE_EXEC,
                "risk_level": "medium",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "old_str": {"type": "string"},
                        "new_str": {"type": "string"}
                    },
                    "required": ["file_path", "old_str", "new_str"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "diff": {"type": "string"}
                    }
                },
                "code_body": "# Built-in — handled by execution engine"
            },
            {
                "name": "run_sandbox",
                "display_name": "Execute in Sandbox",
                "description": "Run code in an isolated sandbox. No network, no disk write outside /tmp/sandbox.",
                "category": SkillCategory.CODE_EXEC,
                "risk_level": "high",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string"},
                        "language": {"type": "string", "enum": ["python", "javascript", "bash"]},
                        "timeout_seconds": {"type": "integer", "default": 30}
                    },
                    "required": ["code", "language"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "exit_code": {"type": "integer"}
                    }
                },
                "code_body": "# Built-in — handled by execution engine"
            },
            {
                "name": "defi_scan",
                "display_name": "DeFi Contract Scanner",
                "description": "Scan Solidity smart contracts with Slither. Returns vulnerability report.",
                "category": SkillCategory.SECURITY,
                "risk_level": "medium",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "contract_path": {"type": "string"},
                        "output_format": {"type": "string", "enum": ["json", "human"], "default": "json"}
                    },
                    "required": ["contract_path"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "vulnerabilities": {"type": "array"},
                        "severity_summary": {"type": "object"}
                    }
                },
                "code_body": "# Built-in — delegates to Slither via defi routes"
            },
            {
                "name": "integrity_verify",
                "display_name": "Integrity Shield Verify",
                "description": "Verify data source trust score and check for prompt injection.",
                "category": SkillCategory.SECURITY,
                "risk_level": "low",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string"},
                        "source": {"type": "string"}
                    },
                    "required": ["content"]
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "trusted": {"type": "boolean"},
                        "score": {"type": "number"},
                        "injection_detected": {"type": "boolean"}
                    }
                },
                "code_body": "# Built-in — delegates to Integrity Shield"
            }
        ]

        for b in builtins:
            skill_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
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
                versions=[SkillVersion(
                    version="1.0.0",
                    code_hash=code_hash,
                    created_at=now,
                    created_by="system",
                    changelog="Initial builtin"
                )],
                current_version="1.0.0",
                created_at=now,
                updated_at=now
            )
            self._skills[skill_id] = skill
            self._name_index[b["name"]] = skill_id

    # ─── PUBLIC API ────────────────────────────────────────────────

    def list_skills(self, status_filter: Optional[str] = None,
                    category_filter: Optional[str] = None) -> list[dict]:
        """List all skills, optionally filtered."""
        results = []
        for skill in self._skills.values():
            if status_filter and skill.status.value != status_filter:
                continue
            if category_filter and skill.category.value != category_filter:
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

        # Normalize for control-panel: default input_schema, output_schema, creator_agent_id
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
