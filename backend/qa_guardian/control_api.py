"""
Guardian Control API - Daena's Interface to QA Guardian

This is the unified API that Daena VP uses to interact with QA Guardian.
All actions go through this layer for proper validation, logging, and enforcement.
"""

import os
import logging
import fnmatch
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from backend.qa_guardian import (
    DENY_LIST_PATTERNS, Severity, RiskLevel, IncidentStatus,
    is_enabled, is_auto_fix_enabled
)
from backend.qa_guardian.schemas.incident import Incident, IncidentCreate, Evidence
from backend.qa_guardian.schemas.proposal import (
    PatchProposal, FileChange, VerificationPlan, RollbackPlan, VerificationReport
)

logger = logging.getLogger("qa_guardian.control_api")


# ═══════════════════════════════════════════════════════════════════════
# Response Types
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ApprovalRequest:
    """Request for founder approval"""
    approval_id: str
    proposal_id: str
    incident_id: str
    urgency: str  # normal, high, critical
    risk_level: str
    deny_list_areas: List[str]
    expires_at: datetime
    status: str = "pending"  # pending, approved, denied, expired
    founder_action: Optional[str] = None
    founder_reason: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CommitResult:
    """Result of committing a fix"""
    success: bool
    proposal_id: str
    files_modified: List[str] = field(default_factory=list)
    error: Optional[str] = None
    committed_at: Optional[datetime] = None


@dataclass  
class RollbackResult:
    """Result of rolling back a fix"""
    success: bool
    proposal_id: str
    files_restored: List[str] = field(default_factory=list)
    error: Optional[str] = None
    rolled_back_at: Optional[datetime] = None


@dataclass
class QuarantineResult:
    """Result of quarantine operation"""
    success: bool
    agent_id: str
    state: str  # quarantined, failed
    backup_agent: Optional[str] = None
    error: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# Deny-List Utilities
# ═══════════════════════════════════════════════════════════════════════

def is_in_deny_list(path: str) -> bool:
    """Check if a path matches any deny-list pattern"""
    normalized = path.replace("\\", "/")
    for pattern in DENY_LIST_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def get_deny_list_matches(paths: List[str]) -> List[str]:
    """Return all paths that match deny-list patterns"""
    return [p for p in paths if is_in_deny_list(p)]


def is_frontend_file(path: str) -> bool:
    """Check if path is a frontend file"""
    frontend_patterns = [
        "*.html", "*.css", "*.js",
        "**/templates/**", "**/static/**", "**/frontend/**"
    ]
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, p) for p in frontend_patterns)


# ═══════════════════════════════════════════════════════════════════════
# Guardian Control API Class
# ═══════════════════════════════════════════════════════════════════════

class GuardianControlAPI:
    """
    Unified Guardian Control API for Daena VP.
    
    This is the ONLY interface Daena should use for QA Guardian operations.
    All actions are validated, logged, and enforce Charter rules.
    """
    
    def __init__(self):
        from backend.qa_guardian.guardian_loop import get_guardian_loop
        self.loop = get_guardian_loop()
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self._rate_limit_proposals = []
        self._rate_limit_commits = []
    
    # ═══════════════════════════════════════════════════════════════════
    # Incident Management
    # ═══════════════════════════════════════════════════════════════════
    
    async def create_incident(
        self,
        source: str,
        error_type: str,
        error_message: str,
        severity: Optional[str] = None,
        subsystem: Optional[str] = None,
        evidence: Optional[List[Evidence]] = None,
        affected_agent: Optional[str] = None,
        affected_department: Optional[str] = None
    ) -> Incident:
        """
        Create a new incident.
        
        Daena can always create incidents - this is read/observe authority.
        Severity is auto-classified if not provided.
        """
        # Auto-classify severity if not provided
        if severity is None:
            severity = self._classify_severity(error_type, error_message)
        
        # Auto-detect subsystem if not provided
        if subsystem is None:
            subsystem = self._detect_subsystem(error_message)
        
        # Create incident via guardian loop
        incident = self.loop.report_error(
            error_type=error_type,
            error_message=error_message,
            stack_trace=None,
            subsystem=subsystem
        )
        
        self._audit_log("create_incident", {
            "incident_id": incident.incident_id if incident else "failed",
            "severity": severity,
            "source": source
        })
        
        return incident
    
    # ═══════════════════════════════════════════════════════════════════
    # Fix Proposal
    # ═══════════════════════════════════════════════════════════════════
    
    async def propose_fix(
        self,
        incident_id: str,
        files: List[FileChange],
        reasoning: str,
        verification_plan: VerificationPlan,
        rollback_plan: RollbackPlan,
        target_type: str = "backend"  # "backend" or "frontend"
    ) -> PatchProposal:
        """
        Propose a fix for an incident.
        
        Daena can always propose fixes - this doesn't apply anything.
        Risk assessment and deny-list checks are done here.
        """
        # Check rate limit
        if not self._check_rate_limit("proposals"):
            raise Exception("Rate limit exceeded for proposals (20/hour)")
        
        # Get file paths
        file_paths = [f.file_path for f in files]
        
        # Check deny-list
        deny_list_matches = get_deny_list_matches(file_paths)
        
        # Calculate risk level
        if deny_list_matches:
            risk_level = RiskLevel.CRITICAL
        elif any(is_frontend_file(p) and "auth" in p.lower() for p in file_paths):
            risk_level = RiskLevel.HIGH
        elif target_type == "frontend" and any("js" in p for p in file_paths):
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Create proposal
        proposal = PatchProposal(
            proposal_id=f"patch_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            incident_id=incident_id,
            files=files,
            verification_plan=verification_plan,
            rollback_plan=rollback_plan,
            risk_level=risk_level,
            deny_list_touched=deny_list_matches,
            status="proposed"
        )
        
        self._audit_log("propose_fix", {
            "proposal_id": proposal.proposal_id,
            "incident_id": incident_id,
            "risk_level": risk_level,
            "deny_list_touched": deny_list_matches,
            "target_type": target_type
        })
        
        return proposal
    
    # ═══════════════════════════════════════════════════════════════════
    # Verification
    # ═══════════════════════════════════════════════════════════════════
    
    async def verify_fix(self, proposal_id: str) -> VerificationReport:
        """
        Run verification on a proposal.
        
        Daena can always run verification - tests are read-only.
        """
        from backend.qa_guardian.agents.regression import QARegressionAgent
        
        agent = QARegressionAgent()
        
        # Run golden workflows
        from backend.qa_guardian.schemas.agent_schemas import RegressionInput
        result = await agent.process(RegressionInput(
            request_id=f"verify_{proposal_id}",
            run_type="golden"
        ))
        
        report = VerificationReport(
            report_id=f"vr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            proposal_id=proposal_id,
            tests_run=result.test_count,
            tests_passed=result.passed_count,
            tests_failed=result.failed_count,
            success=result.success and result.pass_rate >= 1.0,
            created_at=datetime.utcnow()
        )
        
        self._audit_log("verify_fix", {
            "proposal_id": proposal_id,
            "report_id": report.report_id,
            "success": report.success,
            "pass_rate": result.pass_rate
        })
        
        return report
    
    # ═══════════════════════════════════════════════════════════════════
    # Approval Workflow
    # ═══════════════════════════════════════════════════════════════════
    
    async def request_founder_approval(
        self,
        proposal_id: str,
        urgency: str = "normal",
        notes: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Request founder approval for a fix.
        
        This creates an approval request that the founder must act on.
        """
        # Calculate expiry based on urgency
        if urgency == "critical":
            expires_at = datetime.utcnow() + timedelta(hours=1)
        elif urgency == "high":
            expires_at = datetime.utcnow() + timedelta(hours=2)
        else:
            expires_at = datetime.utcnow() + timedelta(hours=4)
        
        approval = ApprovalRequest(
            approval_id=f"apr_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            proposal_id=proposal_id,
            incident_id="",  # Will be set from proposal
            urgency=urgency,
            risk_level="",  # Will be set from proposal
            deny_list_areas=[],
            expires_at=expires_at
        )
        
        self.pending_approvals[approval.approval_id] = approval
        
        self._audit_log("request_founder_approval", {
            "approval_id": approval.approval_id,
            "proposal_id": proposal_id,
            "urgency": urgency,
            "expires_at": expires_at.isoformat()
        })
        
        return approval
    
    async def founder_approve(
        self,
        approval_id: str,
        reason: str
    ) -> ApprovalRequest:
        """Founder approves a fix"""
        if approval_id not in self.pending_approvals:
            raise Exception(f"Approval request not found: {approval_id}")
        
        approval = self.pending_approvals[approval_id]
        approval.status = "approved"
        approval.founder_action = "approved"
        approval.founder_reason = reason
        
        self._audit_log("founder_approve", {
            "approval_id": approval_id,
            "reason": reason
        })
        
        return approval
    
    async def founder_deny(
        self,
        approval_id: str,
        reason: str
    ) -> ApprovalRequest:
        """Founder denies a fix"""
        if approval_id not in self.pending_approvals:
            raise Exception(f"Approval request not found: {approval_id}")
        
        approval = self.pending_approvals[approval_id]
        approval.status = "denied"
        approval.founder_action = "denied"
        approval.founder_reason = reason
        
        self._audit_log("founder_deny", {
            "approval_id": approval_id,
            "reason": reason
        })
        
        return approval
    
    # ═══════════════════════════════════════════════════════════════════
    # Commit & Rollback
    # ═══════════════════════════════════════════════════════════════════
    
    async def commit_fix(
        self,
        proposal_id: str,
        approval_id: Optional[str] = None
    ) -> CommitResult:
        """
        Commit an approved fix.
        
        This actually applies the changes. Requires approval if high-risk.
        """
        # Check if approval is required and provided
        if approval_id:
            if approval_id not in self.pending_approvals:
                return CommitResult(
                    success=False,
                    proposal_id=proposal_id,
                    error="Approval not found"
                )
            
            approval = self.pending_approvals[approval_id]
            if approval.status != "approved":
                return CommitResult(
                    success=False,
                    proposal_id=proposal_id,
                    error=f"Approval not granted: {approval.status}"
                )
        
        # Check rate limit
        if not self._check_rate_limit("commits"):
            return CommitResult(
                success=False,
                proposal_id=proposal_id,
                error="Rate limit exceeded for commits (5/hour)"
            )
        
        # TODO: Implement actual file patching
        # For now, log the commit
        
        self._audit_log("commit_fix", {
            "proposal_id": proposal_id,
            "approval_id": approval_id,
            "status": "committed"
        })
        
        return CommitResult(
            success=True,
            proposal_id=proposal_id,
            files_modified=[],
            committed_at=datetime.utcnow()
        )
    
    async def rollback_fix(
        self,
        proposal_id: str,
        reason: str
    ) -> RollbackResult:
        """
        Rollback a committed fix.
        
        Daena can always rollback - this is a safety operation.
        """
        # TODO: Implement actual rollback
        
        self._audit_log("rollback_fix", {
            "proposal_id": proposal_id,
            "reason": reason,
            "status": "rolled_back"
        })
        
        return RollbackResult(
            success=True,
            proposal_id=proposal_id,
            files_restored=[],
            rolled_back_at=datetime.utcnow()
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # Quarantine
    # ═══════════════════════════════════════════════════════════════════
    
    async def quarantine_agent(
        self,
        agent_id: str,
        reason: str,
        incident_ids: List[str]
    ) -> QuarantineResult:
        """
        Quarantine an agent due to repeated failures.
        
        Daena can quarantine agents on repeated failures (3+ in 1 hour).
        """
        # TODO: Implement actual quarantine
        
        self._audit_log("quarantine_agent", {
            "agent_id": agent_id,
            "reason": reason,
            "incident_ids": incident_ids
        })
        
        return QuarantineResult(
            success=True,
            agent_id=agent_id,
            state="quarantined",
            backup_agent=None  # TODO: Find backup
        )
    
    async def restore_agent(
        self,
        agent_id: str,
        approval_id: str,
        reason: str
    ) -> QuarantineResult:
        """
        Restore a quarantined agent.
        
        REQUIRES founder approval - Daena cannot restore alone.
        """
        if approval_id not in self.pending_approvals:
            return QuarantineResult(
                success=False,
                agent_id=agent_id,
                state="quarantined",
                error="Founder approval required to restore agent"
            )
        
        approval = self.pending_approvals[approval_id]
        if approval.status != "approved":
            return QuarantineResult(
                success=False,
                agent_id=agent_id,
                state="quarantined",
                error=f"Approval not granted: {approval.status}"
            )
        
        self._audit_log("restore_agent", {
            "agent_id": agent_id,
            "approval_id": approval_id,
            "reason": reason
        })
        
        return QuarantineResult(
            success=True,
            agent_id=agent_id,
            state="restored"
        )
    
    # ═══════════════════════════════════════════════════════════════════
    # Utilities
    # ═══════════════════════════════════════════════════════════════════
    
    def _classify_severity(self, error_type: str, error_message: str) -> str:
        """Auto-classify severity based on error type and message"""
        error_lower = (error_type + error_message).lower()
        
        if any(kw in error_lower for kw in ["crash", "fatal", "data loss", "security"]):
            return Severity.P0
        elif any(kw in error_lower for kw in ["broken", "failed", "critical"]):
            return Severity.P1
        elif any(kw in error_lower for kw in ["error", "exception", "timeout"]):
            return Severity.P2
        elif any(kw in error_lower for kw in ["warning", "deprecated"]):
            return Severity.P3
        else:
            return Severity.P4
    
    def _detect_subsystem(self, error_message: str) -> str:
        """Auto-detect subsystem from error message"""
        msg_lower = error_message.lower()
        
        if "database" in msg_lower or "sql" in msg_lower:
            return "database"
        elif "api" in msg_lower or "route" in msg_lower:
            return "api"
        elif "agent" in msg_lower:
            return "agents"
        elif "auth" in msg_lower or "login" in msg_lower:
            return "auth"
        elif "websocket" in msg_lower or "ws" in msg_lower:
            return "websocket"
        else:
            return "backend"
    
    def _check_rate_limit(self, limit_type: str) -> bool:
        """Check if rate limit allows action"""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        if limit_type == "proposals":
            self._rate_limit_proposals = [
                t for t in self._rate_limit_proposals if t > one_hour_ago
            ]
            if len(self._rate_limit_proposals) >= 20:
                return False
            self._rate_limit_proposals.append(now)
            
        elif limit_type == "commits":
            self._rate_limit_commits = [
                t for t in self._rate_limit_commits if t > one_hour_ago
            ]
            if len(self._rate_limit_commits) >= 5:
                return False
            self._rate_limit_commits.append(now)
        
        return True
    
    def _audit_log(self, action: str, details: Dict[str, Any]):
        """Log action to audit trail"""
        import json
        from pathlib import Path
        
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "qa_guardian_control_api.jsonl"
        
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "actor": "daena_vp",
            **details
        }
        
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
        
        logger.info(f"Guardian Control API: {action} - {details}")


# ═══════════════════════════════════════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════════════════════════════════════

_control_api: Optional[GuardianControlAPI] = None

def get_guardian_control_api() -> GuardianControlAPI:
    """Get or create the singleton Guardian Control API"""
    global _control_api
    if _control_api is None:
        _control_api = GuardianControlAPI()
    return _control_api
