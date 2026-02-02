"""
Governance Loop — System-Wide Decision Control

This is the CENTRAL governance gate for ALL agent actions in Daena.
Every action flows through here to assess risk, consult council if needed,
and enforce founder approval for high-risk operations.

Powers of ClawBot/MoltBot/MiniMax are constrained by this loop.

Key Features:
- Autopilot mode for low-risk operations (report only)
- Council consultation for medium-risk decisions
- Founder approval required for high-risk actions
- All decisions tracked for learning loop

Part of DAENA_FULL_POWER.md implementation.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
import uuid

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk levels for actions"""
    SAFE = "safe"           # No approval needed
    LOW = "low"             # Autopilot mode: execute + report
    MEDIUM = "medium"       # Council consult required
    HIGH = "high"           # Founder approval required
    CRITICAL = "critical"   # Immediate escalation + block


class ActionType(Enum):
    """Types of actions governed"""
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    PACKAGE_INSTALL = "package_install"
    SKILL_CREATE = "skill_create"
    SKILL_EXECUTE = "skill_execute"
    EXTERNAL_API = "external_api"
    RESEARCH_QUERY = "research_query"
    DEFI_SCAN = "defi_scan"
    TREASURY_SPEND = "treasury_spend"
    MODEL_UPDATE = "model_update"
    SYSTEM_CONFIG = "system_config"
    NETWORK_REQUEST = "network_request"
    DATABASE_WRITE = "database_write"
    UNKNOWN = "unknown"


class DecisionOutcome(Enum):
    """Possible outcomes from governance evaluation"""
    EXECUTE = "execute"             # Proceed with action
    EXECUTE_REPORT = "execute_report"  # Proceed + notify founder
    DEFER = "defer"                 # Wait for council
    PENDING_APPROVAL = "pending_approval"  # Wait for founder
    BLOCKED = "blocked"             # Not allowed
    ESCALATED = "escalated"         # Sent to higher authority


@dataclass
class GovernanceDecision:
    """Result of governance evaluation"""
    decision_id: str
    action_type: str
    risk_level: str
    outcome: str
    requires: Optional[str] = None  # "council_vote", "founder_approval"
    executed: bool = False
    escalated_to: Optional[str] = None
    report_to: Optional[str] = None
    council_result: Optional[Dict[str, Any]] = None
    reason: str = ""
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class ActionRequest:
    """An action to be evaluated by governance"""
    action_id: str
    action_type: ActionType
    agent_id: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    requested_at: str = ""
    
    def __post_init__(self):
        if not self.requested_at:
            self.requested_at = datetime.now(timezone.utc).isoformat()


# Risk assessment rules per action type
RISK_RULES = {
    # Low risk - autopilot
    ActionType.FILE_READ: RiskLevel.LOW,
    ActionType.RESEARCH_QUERY: RiskLevel.LOW,
    ActionType.DEFI_SCAN: RiskLevel.LOW,
    
    # Medium risk - council consult
    ActionType.FILE_WRITE: RiskLevel.MEDIUM,
    ActionType.PACKAGE_INSTALL: RiskLevel.MEDIUM,
    ActionType.SKILL_EXECUTE: RiskLevel.MEDIUM,
    ActionType.EXTERNAL_API: RiskLevel.MEDIUM,
    ActionType.NETWORK_REQUEST: RiskLevel.MEDIUM,
    
    # High risk - founder approval
    ActionType.FILE_DELETE: RiskLevel.HIGH,
    ActionType.SKILL_CREATE: RiskLevel.HIGH,
    ActionType.DATABASE_WRITE: RiskLevel.HIGH,
    ActionType.SYSTEM_CONFIG: RiskLevel.HIGH,
    ActionType.MODEL_UPDATE: RiskLevel.HIGH,
    
    # Critical - always block without explicit approval
    ActionType.TREASURY_SPEND: RiskLevel.CRITICAL,
}

# Path patterns that elevate risk
SENSITIVE_PATHS = [
    ".env", ".git", "secrets", "credentials", "keys",
    "config/prod", "production", ".ssh", "__pycache__"
]


class GovernanceLoop:
    """
    Central governance engine for all Daena agent actions.
    
    Mode Settings:
    - autopilot = True: low-risk actions execute with reports
    - autopilot = False: all actions require approval
    
    Features:
    - Risk assessment per action type
    - Path sensitivity escalation
    - Council consultation for medium risk
    - Founder approval for high/critical
    - Full audit trail
    """
    
    def __init__(self, autopilot: bool = True, founder_id: str = "founder"):
        self.autopilot = autopilot
        self.founder_id = founder_id
        
        # Storage
        self._pending_approvals: Dict[str, ActionRequest] = {}
        self._decision_log: List[GovernanceDecision] = []
        
        # Load persistent state
        self._storage_path = Path(__file__).parent.parent.parent / ".ledger" / "governance.json"
        self._load_state()
    
    def _load_state(self):
        """Load persistent governance state."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                    self._decision_log = [
                        GovernanceDecision(**d) for d in data.get("decisions", [])[-1000:]
                    ]
            except Exception as e:
                logger.error(f"Failed to load governance state: {e}")
    
    def _save_state(self):
        """Save governance state."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {
                "decisions": [d.__dict__ for d in self._decision_log[-1000:]],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(self._storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save governance state: {e}")
    
    def evaluate(self, request: ActionRequest) -> GovernanceDecision:
        """
        Evaluate an action request and return governance decision.
        
        This is the main entry point for all agent actions.
        """
        decision_id = str(uuid.uuid4())
        
        # Step 1: Assess base risk level
        base_risk = RISK_RULES.get(request.action_type, RiskLevel.HIGH)
        
        # Step 2: Check for risk elevations
        risk = self._check_elevations(request, base_risk)
        
        # Step 3: Route based on risk level
        if risk == RiskLevel.SAFE:
            decision = self._handle_safe(decision_id, request)
        elif risk == RiskLevel.LOW:
            decision = self._handle_low_risk(decision_id, request)
        elif risk == RiskLevel.MEDIUM:
            decision = self._handle_medium_risk(decision_id, request)
        elif risk == RiskLevel.HIGH:
            decision = self._handle_high_risk(decision_id, request)
        else:  # CRITICAL
            decision = self._handle_critical(decision_id, request)
        
        # Step 4: Log and track
        decision.risk_level = risk.value
        decision.action_type = request.action_type.value
        self._decision_log.append(decision)
        self._save_state()
        
        # Step 5: Track in outcome system
        self._track_outcome(request, decision)
        
        return decision
    
    def _check_elevations(self, request: ActionRequest, base_risk: RiskLevel) -> RiskLevel:
        """Check if risk should be elevated based on context."""
        risk = base_risk
        
        # Check path sensitivity
        path = request.parameters.get("path", "")
        for sensitive in SENSITIVE_PATHS:
            if sensitive in str(path).lower():
                risk = max(risk, RiskLevel.HIGH, key=lambda x: list(RiskLevel).index(x))
                logger.info(f"Elevated risk to {risk.value} due to sensitive path: {sensitive}")
                break
        
        # Check if action affects production
        if request.context.get("environment") == "production":
            risk = max(risk, RiskLevel.HIGH, key=lambda x: list(RiskLevel).index(x))
        
        # Check if external-facing
        if request.context.get("external", False):
            risk = max(risk, RiskLevel.MEDIUM, key=lambda x: list(RiskLevel).index(x))
        
        return risk
    
    def _handle_safe(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle SAFE risk - always execute."""
        return GovernanceDecision(
            decision_id=decision_id,
            action_type=request.action_type.value,
            risk_level=RiskLevel.SAFE.value,
            outcome=DecisionOutcome.EXECUTE.value,
            executed=True,
            reason="Safe operation - no approval needed"
        )
    
    def _handle_low_risk(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle LOW risk - autopilot mode."""
        if self.autopilot:
            return GovernanceDecision(
                decision_id=decision_id,
                action_type=request.action_type.value,
                risk_level=RiskLevel.LOW.value,
                outcome=DecisionOutcome.EXECUTE_REPORT.value,
                executed=True,
                report_to=self.founder_id,
                reason="Autopilot mode - executing and reporting"
            )
        else:
            return GovernanceDecision(
                decision_id=decision_id,
                action_type=request.action_type.value,
                risk_level=RiskLevel.LOW.value,
                outcome=DecisionOutcome.PENDING_APPROVAL.value,
                requires="founder_approval",
                reason="Manual mode - awaiting approval"
            )
    
    def _handle_medium_risk(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle MEDIUM risk - council consultation."""
        # Consult the council
        council_result = self._consult_council(request)
        
        if council_result.get("recommendation") == "APPROVE":
            return GovernanceDecision(
                decision_id=decision_id,
                action_type=request.action_type.value,
                risk_level=RiskLevel.MEDIUM.value,
                outcome=DecisionOutcome.EXECUTE_REPORT.value,
                executed=True,
                council_result=council_result,
                report_to=self.founder_id,
                reason=f"Council approved with {council_result.get('confidence', 0)*100:.0f}% confidence"
            )
        elif council_result.get("recommendation") == "REVIEW":
            return GovernanceDecision(
                decision_id=decision_id,
                action_type=request.action_type.value,
                risk_level=RiskLevel.MEDIUM.value,
                outcome=DecisionOutcome.DEFER.value,
                requires="founder_approval",
                council_result=council_result,
                reason="Council uncertain - deferring to founder"
            )
        else:  # DENY
            return GovernanceDecision(
                decision_id=decision_id,
                action_type=request.action_type.value,
                risk_level=RiskLevel.MEDIUM.value,
                outcome=DecisionOutcome.BLOCKED.value,
                council_result=council_result,
                reason=f"Council denied: {council_result.get('consensus', 'No consensus')}"
            )
    
    def _handle_high_risk(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle HIGH risk - founder approval required."""
        # Store for pending approval
        self._pending_approvals[decision_id] = request
        
        return GovernanceDecision(
            decision_id=decision_id,
            action_type=request.action_type.value,
            risk_level=RiskLevel.HIGH.value,
            outcome=DecisionOutcome.PENDING_APPROVAL.value,
            requires="founder_approval",
            reason="High-risk action requires founder approval"
        )
    
    def _handle_critical(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle CRITICAL risk - block and escalate."""
        # Store and escalate
        self._pending_approvals[decision_id] = request
        
        return GovernanceDecision(
            decision_id=decision_id,
            action_type=request.action_type.value,
            risk_level=RiskLevel.CRITICAL.value,
            outcome=DecisionOutcome.ESCALATED.value,
            escalated_to=self.founder_id,
            requires="founder_approval",
            reason="Critical-risk action blocked - requires explicit founder approval"
        )
    
    def _consult_council(self, request: ActionRequest) -> Dict[str, Any]:
        """Consult the council on a medium-risk decision."""
        try:
            from backend.services.mcp.mcp_server import get_mcp_server
            import asyncio
            
            server = get_mcp_server()
            
            # Build council consult request
            args = {
                "decision": f"{request.action_type.value}: {request.description}",
                "domain": self._get_domain(request.action_type),
                "context": json.dumps(request.parameters)[:500]
            }
            
            # Run async call synchronously
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    server.handle_tool_call("daena_council_consult", args, "governance_loop")
                )
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Council consultation failed: {e}")
            return {
                "recommendation": "REVIEW",
                "confidence": 0.5,
                "error": str(e)
            }
    
    def _get_domain(self, action_type: ActionType) -> str:
        """Map action type to council domain."""
        domain_map = {
            ActionType.DEFI_SCAN: "defi",
            ActionType.TREASURY_SPEND: "defi",
            ActionType.PACKAGE_INSTALL: "security",
            ActionType.SKILL_CREATE: "engineering",
            ActionType.FILE_DELETE: "security",
            ActionType.SYSTEM_CONFIG: "engineering",
            ActionType.EXTERNAL_API: "security",
            ActionType.NETWORK_REQUEST: "security",
        }
        return domain_map.get(action_type, "general")
    
    def _track_outcome(self, request: ActionRequest, decision: GovernanceDecision):
        """Track decision in outcome system for learning."""
        try:
            from backend.services.outcome_tracker import get_outcome_tracker
            
            tracker = get_outcome_tracker()
            tracker.track_decision(
                outcome_id=decision.decision_id,
                decision_type="governance",
                category=request.action_type.value,
                recommendation=decision.outcome,
                metadata={
                    "risk_level": decision.risk_level,
                    "agent_id": request.agent_id,
                    "description": request.description[:200]
                }
            )
        except Exception as e:
            logger.error(f"Failed to track outcome: {e}")
    
    def approve(self, decision_id: str, approver_id: str, notes: str = "") -> bool:
        """
        Founder approves a pending action.
        
        Returns True if action can now proceed.
        """
        if decision_id not in self._pending_approvals:
            logger.warning(f"No pending approval found: {decision_id}")
            return False
        
        request = self._pending_approvals.pop(decision_id)
        
        # Find and update decision
        for dec in self._decision_log:
            if dec.decision_id == decision_id:
                dec.outcome = DecisionOutcome.EXECUTE.value
                dec.executed = True
                dec.reason = f"Approved by {approver_id}: {notes}"
        
        self._save_state()
        logger.info(f"Action {decision_id} approved by {approver_id}")
        return True
    
    def reject(self, decision_id: str, approver_id: str, reason: str = "") -> bool:
        """
        Founder rejects a pending action.
        """
        if decision_id not in self._pending_approvals:
            return False
        
        self._pending_approvals.pop(decision_id)
        
        for dec in self._decision_log:
            if dec.decision_id == decision_id:
                dec.outcome = DecisionOutcome.BLOCKED.value
                dec.reason = f"Rejected by {approver_id}: {reason}"
        
        self._save_state()
        logger.info(f"Action {decision_id} rejected by {approver_id}")
        return True
    
    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests."""
        result = []
        for dec_id, request in self._pending_approvals.items():
            # Find the decision
            for dec in self._decision_log:
                if dec.decision_id == dec_id:
                    result.append({
                        "decision_id": dec_id,
                        "action_type": request.action_type.value,
                        "agent_id": request.agent_id,
                        "description": request.description,
                        "risk_level": dec.risk_level,
                        "requires": dec.requires,
                        "requested_at": request.requested_at
                    })
                    break
        return result
    
    def assess(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple assessment for chat/pipeline: action dict with service, description, risk.
        Returns { risk, autopilot, decision } for use by chat.py and other callers.
        """
        risk = (action.get("risk") or "low").lower()
        if risk in ("high", "critical"):
            return {"risk": risk, "autopilot": False, "decision": "blocked"}
        if self.autopilot:
            return {"risk": risk, "autopilot": True, "decision": "approve"}
        return {"risk": risk, "autopilot": False, "decision": "pending"}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get governance statistics."""
        total = len(self._decision_log)
        executed = sum(1 for d in self._decision_log if d.executed)
        blocked = sum(1 for d in self._decision_log if d.outcome == DecisionOutcome.BLOCKED.value)
        pending = len(self._pending_approvals)
        
        by_risk = {}
        for d in self._decision_log:
            by_risk[d.risk_level] = by_risk.get(d.risk_level, 0) + 1
        
        by_action = {}
        for d in self._decision_log:
            by_action[d.action_type] = by_action.get(d.action_type, 0) + 1
        
        return {
            "total_decisions": total,
            "executed": executed,
            "blocked": blocked,
            "pending": pending,
            "autopilot_enabled": self.autopilot,
            "by_risk_level": by_risk,
            "by_action_type": by_action
        }


# =============================================
# SINGLETON
# =============================================

_governance: Optional[GovernanceLoop] = None


def get_governance_loop(autopilot: bool = True) -> GovernanceLoop:
    """Get the global governance loop instance."""
    global _governance
    if _governance is None:
        _governance = GovernanceLoop(autopilot=autopilot)
    return _governance
