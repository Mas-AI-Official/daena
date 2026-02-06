"""
Governance Loop — System-Wide Decision Control

This is the CENTRAL governance gate for ALL agent actions in Daena.
Every action flows through here to assess risk, consult council if needed,
and enforce founder approval for high-risk operations.

Powers of DaenaBot/MoltBot/MiniMax are constrained by this loop.

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
import os
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


# ... (existing imports, keep them)
from backend.database import SessionLocal, FounderPolicy, PendingApproval as DBPendingApproval, ActionType as DBActionType
# Note: PendingApproval is aliased to DBPendingApproval to avoid conflict if any local var, same for ActionType if enum conflicts (it does)

# ... (keep existing definitions up to GovernanceLoop init)

class GovernanceLoop:
    """
    Central governance engine, now integrated with Founder Policy Center (DB-backed).
    """
    
    def __init__(self, autopilot: Optional[bool] = None, founder_id: str = "founder"):
        # Prioritize env var, then arg, then default True
        env_autopilot = os.getenv("AGI_AUTOPILOT_DEFAULT", "").lower()
        if env_autopilot in ("true", "1", "on"):
            self.autopilot = True
        elif env_autopilot in ("false", "0", "off"):
            self.autopilot = False
        else:
            self.autopilot = autopilot if autopilot is not None else True
            
        self.founder_id = founder_id
        
        # Load persistent state - DEPRECATED: We now use DB mostly, but keep legacy list for non-DB compatibility
        self._decision_log: List[GovernanceDecision] = []
        
        # We don't need _pending_approvals dict anymore as we use DB, 
        # but we keep it for backward compatibility with in-memory calls if needed.
        self._pending_approvals: Dict[str, ActionRequest] = {}
        
        # self._load_state() # Legacy file load skipped in favor of DB

    @staticmethod
    def get_instance():
        """Static access to the singleton loop."""
        return get_governance_loop()
    
    # ... (keep _save_state or modify to no-op)
    def _save_state(self):
        """Legacy state saving - no-op when using DB."""
        pass

    def evaluate(self, request: ActionRequest) -> GovernanceDecision:
        """
        Evaluate an action request with Founder Policy check.
        """
        decision_id = str(uuid.uuid4())
        
        # 0. Check Founder Policies (DB)
        db = SessionLocal()
        try:
            # Check for BLOCK policies
            policies = db.query(FounderPolicy).filter(FounderPolicy.enforcement == "block").all()
            for pol in policies:
                if self._policy_matches(pol, request):
                    return GovernanceDecision(
                        decision_id=decision_id,
                        action_type=request.action_type.value,
                        risk_level="blocked_by_policy",
                        outcome=DecisionOutcome.BLOCKED.value,
                        reason=f"Blocked by Founder Policy: {pol.name}"
                    )
            
            # Check for REQUIRE_APPROVAL policies
            approval_policies = db.query(FounderPolicy).filter(FounderPolicy.enforcement == "require_approval").all()
            for pol in approval_policies:
                if self._policy_matches(pol, request):
                    # Force high risk handling
                    decision = self._handle_high_risk(decision_id, request)
                    decision.reason = f"Flagged by Founder Policy: {pol.name}"
                    return decision
                    
        except Exception as e:
            logger.error(f"Policy check failed: {e}")
        finally:
            db.close()

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
        
        # Step 4: Log (Legacy + Audit)
        decision.risk_level = risk.value
        self._decision_log.append(decision)
        # self._save_state() 
        
        # Step 5: Outcome Tracking
        self._track_outcome(request, decision)
        
        return decision

    def _policy_matches(self, policy: FounderPolicy, request: ActionRequest) -> bool:
        """Check if request matches policy scope."""
        if policy.scope == "global":
            # Match strictly by rule_type or broad category
            # Simplification: if policy rule_type matches action category
            # We map action types to policy rule types
            if policy.rule_type == "payment" and request.action_type == ActionType.TREASURY_SPEND: return True
            if policy.rule_type == "filesystem" and request.action_type in [ActionType.FILE_DELETE, ActionType.FILE_WRITE]: return True
            if policy.rule_type == "credentials" and "api_key" in str(request.parameters): return True
            return False
            
        # Specific tool scope "tool:click"
        if policy.scope.startswith("tool:") and policy.scope.split(":")[1] == request.action_type.value:
            return True
            
        return False

    # ... (keep _check_elevations, _handle_safe, _handle_low_risk, _handle_medium_risk)

    def _handle_high_risk(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle HIGH risk - save to DB for Founder Approval."""
        
        # Save to DB
        db = SessionLocal()
        try:
            pending = DBPendingApproval(
                approval_id=decision_id,
                executor_id=request.agent_id,
                executor_type="agent",
                tool_name=request.action_type.value,
                action=request.description[:50] + "...",
                args_json=request.parameters,
                impact_level="high",
                status="pending",
                created_at=datetime.utcnow()
            )
            db.add(pending)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to save pending approval: {e}")
        finally:
            db.close()
            
        return GovernanceDecision(
            decision_id=decision_id,
            action_type=request.action_type.value,
            risk_level=RiskLevel.HIGH.value,
            outcome=DecisionOutcome.PENDING_APPROVAL.value,
            requires="founder_approval",
            reason="High-risk action requires founder approval"
        )
    
    def _handle_critical(self, decision_id: str, request: ActionRequest) -> GovernanceDecision:
        """Handle CRITICAL risk - block and escalate to DB."""
        
        db = SessionLocal()
        try:
            pending = DBPendingApproval(
                approval_id=decision_id,
                executor_id=request.agent_id,
                executor_type="agent", 
                tool_name=request.action_type.value,
                action=request.description[:50],
                args_json=request.parameters,
                impact_level="critical",
                status="pending", # Even critical we might want to allow override, so pending
                created_at=datetime.utcnow()
            )
            db.add(pending)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to save critical approval: {e}")
        finally:
            db.close()

        return GovernanceDecision(
            decision_id=decision_id,
            action_type=request.action_type.value,
            risk_level=RiskLevel.CRITICAL.value,
            outcome=DecisionOutcome.ESCALATED.value,
            escalated_to=self.founder_id,
            requires="founder_approval",
            reason="Critical-risk action blocked - requires explicit founder approval"
        )

    # ... (keep _consult_council, _get_domain, _track_outcome)

    def approve(self, decision_id: str, approver_id: str, notes: str = "") -> bool:
        """Founder approves via DB."""
        db = SessionLocal()
        try:
            # Check DB first
            approval = db.query(DBPendingApproval).filter(
                (DBPendingApproval.approval_id == decision_id) | (DBPendingApproval.id == decision_id) # handle both ID types if mixed
            ).first()
            
            if approval:
                approval.status = "approved"
                approval.resolved_by = approver_id
                approval.resolved_at = datetime.utcnow()
                approval.founder_note = notes
                db.commit()
                # Update in-memory log if present
                for dec in self._decision_log:
                    if dec.decision_id == decision_id:
                        dec.outcome = DecisionOutcome.EXECUTE.value
                        dec.executed = True
                return True
        finally:
            db.close()
        return False

    def reject(self, decision_id: str, approver_id: str, reason: str = "") -> bool:
        db = SessionLocal()
        try:
            approval = db.query(DBPendingApproval).filter(
                (DBPendingApproval.approval_id == decision_id) | (DBPendingApproval.id == decision_id)
            ).first()
            if approval:
                approval.status = "rejected"
                approval.resolved_by = approver_id
                approval.resolved_at = datetime.utcnow()
                approval.founder_note = reason
                db.commit()
                for dec in self._decision_log:
                    if dec.decision_id == decision_id:
                        dec.outcome = DecisionOutcome.BLOCKED.value
                return True
        finally:
            db.close()
        return False
        
    def get_pending(self) -> List[Dict[str, Any]]:
        """Get pending from DB."""
        db = SessionLocal()
        try:
            pendings = db.query(DBPendingApproval).filter(DBPendingApproval.status == "pending").all()
            return [{
                "decision_id": p.approval_id,
                "action_type": p.tool_name,
                "agent_id": p.executor_id,
                "description": p.action,
                "risk_level": p.impact_level,
                "requested_at": p.created_at.isoformat() if p.created_at else "",
                "parameters": p.args_json
            } for p in pendings]
        finally:
            db.close()

    # ... (keep assess, get_stats, singleton)
    
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
            
        # Check if it's a self-fix (modifying system code)
        if request.parameters.get("is_self_fix"):
            risk = max(risk, RiskLevel.HIGH, key=lambda x: list(RiskLevel).index(x))
            logger.info("Elevated risk to HIGH for self-healing fix")
        
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
    
    
    def _consult_council(self, request: ActionRequest) -> Dict[str, Any]:
        """Consult the council on a medium-risk decision."""
        # Check if we should use autonomous council
        if self.autopilot:
            try:
                from backend.services.council_autonomous import get_autonomous_council
                council = get_autonomous_council()
                
                # Run async consultation in sync wrapper
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we are already in an event loop (likely), we might need a future
                    # But GovernanceLoop is often called from sync contexts.
                    # For safety, let's try to detect if we need to use a thread or future.
                    return asyncio.run_coroutine_threadsafe(
                        council.consult({
                            "action_type": request.action_type.value,
                            "description": request.description,
                            "parameters": request.parameters
                        }),
                        loop
                    ).result()
                else:
                    return asyncio.run(council.consult({
                        "action_type": request.action_type.value,
                        "description": request.description,
                        "parameters": request.parameters
                    }))
            except Exception as e:
                logger.error(f"Autonomous council failed, falling back to legacy: {e}")

        # Legacy/Fallback implementation
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
        Handles both DB-backed governance decisions and legacy/tool store requests.
        """
        # 1. Try Tool Request Store (Hands/OpenClaw)
        try:
            from backend.services.tool_request_store import get_request
            from backend.services.hands_approval_queue import hands_approval_queue
            
            tool_req = get_request(decision_id)
            if tool_req and tool_req.get("status") == "pending":
                import asyncio
                # Fire and forget / background task for execution to avoid blocking?
                # For now, we await execution since frontend expects result, but this method is sync?
                # This method is called by synchronous router usually.
                # hands_approval_queue.approve_action is async.
                
                # Create a loop to run the async approval
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(hands_approval_queue.approve_action(decision_id))
                finally:
                    loop.close()
                    
                logger.info(f"Tool Request {decision_id} approved by {approver_id}")
                return True
        except Exception as e:
            logger.warning(f"Tool store check failed for {decision_id}: {e}")

        # 2. Try DB (Governance Actions)
        db = SessionLocal()
        try:
            # Check DB first
            approval = db.query(DBPendingApproval).filter(
                (DBPendingApproval.approval_id == decision_id) | (DBPendingApproval.id == decision_id)
            ).first()
            
            if approval:
                approval.status = "approved"
                approval.resolved_by = approver_id
                approval.resolved_at = datetime.utcnow()
                approval.founder_note = notes
                db.commit()
                # Update in-memory log if present
                for dec in self._decision_log:
                    if dec.decision_id == decision_id:
                        dec.outcome = DecisionOutcome.EXECUTE.value
                        dec.executed = True
                        dec.reason = f"Approved by {approver_id}: {notes}"
                return True
            
            # 3. Try In-Memory (Legacy)
            if decision_id in self._pending_approvals:
                request = self._pending_approvals.pop(decision_id)
                for dec in self._decision_log:
                    if dec.decision_id == decision_id:
                        dec.outcome = DecisionOutcome.EXECUTE.value
                        dec.executed = True
                        dec.reason = f"Approved by {approver_id}: {notes}"
                self._save_state()
                return True
                
        finally:
            db.close()
        return False
    
    def reject(self, decision_id: str, approver_id: str, reason: str = "") -> bool:
        """
        Founder rejects a pending action.
        """
        # 1. Try Tool Request Store
        try:
            from backend.services.tool_request_store import get_request, update_status
            tool_req = get_request(decision_id)
            if tool_req and tool_req.get("status") == "pending":
                update_status(decision_id, "rejected", {"message": f"Rejected by {approver_id}: {reason}"})
                logger.info(f"Tool Request {decision_id} rejected by {approver_id}")
                return True
        except Exception as e:
            logger.warning(f"Tool store check failed for {decision_id}: {e}")

        # 2. Try DB
        db = SessionLocal()
        try:
            approval = db.query(DBPendingApproval).filter(
                (DBPendingApproval.approval_id == decision_id) | (DBPendingApproval.id == decision_id)
            ).first()
            if approval:
                approval.status = "rejected"
                approval.resolved_by = approver_id
                approval.resolved_at = datetime.utcnow()
                approval.founder_note = reason
                db.commit()
                for dec in self._decision_log:
                    if dec.decision_id == decision_id:
                        dec.outcome = DecisionOutcome.BLOCKED.value
                return True
            
            # 3. Try In-Memory
            if decision_id in self._pending_approvals:
                self._pending_approvals.pop(decision_id)
                for dec in self._decision_log:
                    if dec.decision_id == decision_id:
                        dec.outcome = DecisionOutcome.BLOCKED.value
                        dec.reason = f"Rejected by {approver_id}: {reason}"
                self._save_state()
                return True
        finally:
            db.close()
        return False
        
    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all pending approval requests (Unified: DB + ToolStore)."""
        result = []
        
        # 1. DB Pending Approvals
        db = SessionLocal()
        try:
            pendings = db.query(DBPendingApproval).filter(DBPendingApproval.status == "pending").all()
            for p in pendings:
                result.append({
                    "decision_id": p.approval_id,
                    "action_type": p.tool_name,
                    "agent_id": p.executor_id,
                    "description": p.action,
                    "risk_level": p.impact_level,
                    "requires": "founder_approval",
                    "requested_at": p.created_at.isoformat() if p.created_at else "",
                    "source": "governance"
                })
        except Exception as e:
            logger.error(f"Failed to fetch DB pending: {e}")
        finally:
            db.close()
            
        # 2. Tool Request Store Pending (Hands/OpenClaw)
        try:
            from backend.services.tool_request_store import list_pending
            tool_requests = list_pending()
            for req in tool_requests:
                action = req.get("action_json", {})
                desc = f"Execute {action.get('tool_name') or action.get('action_type')}: {str(action.get('parameters', ''))[:50]}"
                result.append({
                    "decision_id": req.get("id"),
                    "action_type": req.get("risk_level", "high").upper() + "_TOOL",
                    "agent_id": req.get("requested_by", "unknown"),
                    "description": desc,
                    "risk_level": req.get("risk_level", "high"),
                    "requires": "founder_approval",
                    "requested_at": datetime.fromtimestamp(req.get("created_at", 0)).isoformat(),
                    "source": "tool_broker"
                })
        except Exception as e:
            logger.error(f"Failed to fetch ToolStore pending: {e}")
            
        # 3. Legacy In-Memory (if any)
        for dec_id, request in self._pending_approvals.items():
            # Avoid duplicates if they are somehow also in DB (unlikely given logic)
            if not any(r["decision_id"] == dec_id for r in result):
                # Find the decision details
                risk = "high"
                requires = "founder_approval"
                for dec in self._decision_log:
                    if dec.decision_id == dec_id:
                        risk = dec.risk_level
                        requires = dec.requires
                        break
                
                result.append({
                    "decision_id": dec_id,
                    "action_type": request.action_type.value,
                    "agent_id": request.agent_id,
                    "description": request.description,
                    "risk_level": risk,
                    "requires": requires,
                    "requested_at": request.requested_at,
                    "source": "memory"
                })

        # Sort by date
        result.sort(key=lambda x: x.get("requested_at", ""), reverse=True)
        return result
    
    async def assess(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess action risk and return decision structure.
        Compatible with both sync and async callers (if awaited).
        """
        risk = (action.get("risk") or "low").lower()
        
        # 1. Critical risk is always blocked for manual review
        if risk == "critical":
            return {
                "decision": "blocked",
                "risk": "critical",
                "requires_approval": True,
                "reason": "Critical risk actions are auto-blocked"
            }
        
        # 2. High risk depends on autopilot and explicit founder approval
        elif risk == "high":
            # If autopilot is ON, we might allow some high risks? 
            # Usually high risk always needs approval. 
            # But the prompt says autopilot=True -> approve for "medium", "queue" for "high".
            
            # Let's follow strict logic: High -> Queue/Pending
            decision = "pending"
            if self.autopilot and action.get("force_auto"):
                 decision = "approve"
                 
            return {
                "decision": decision,
                "risk": "high",
                "requires_approval": True,
                "reason": "High risk action"
            }
            
        # 3. Low/Medium -> Allow if autopilot, else pending
        elif risk in ("medium", "low"):
             decision = "approve" if self.autopilot else "pending"
             return {
                 "decision": decision,
                 "risk": risk,
                 "requires_approval": decision == "pending",
                 "reason": "Autopilot active" if self.autopilot else "Manual approval required"
             }
             
        # 4. Safe -> Always approve
        return {
            "decision": "approve", 
            "risk": "safe", 
            "requires_approval": False,
            "reason": "Safe action"
        }

    
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


def get_governance_loop(autopilot: Optional[bool] = None) -> GovernanceLoop:
    """Get the global governance loop instance."""
    global _governance
    if _governance is None:
        _governance = GovernanceLoop(autopilot=autopilot)
    return _governance
