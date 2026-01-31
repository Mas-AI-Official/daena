"""
Decision Engine - Determines action for each incident

Implements the decision logic from QA_GUARDIAN_CHARTER.md:
- OBSERVE: Monitor only, no action
- AUTO_FIX: Safe to apply fix automatically
- ESCALATE: Requires founder approval
- QUARANTINE: Agent/service needs isolation
"""

import fnmatch
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from . import (
    DENY_LIST_PATTERNS, Severity, RiskLevel, ActionType,
    QA_GUARDIAN_AUTO_FIX
)
from .schemas.incident import Incident, IncidentCreate

logger = logging.getLogger("qa_guardian.decision")


@dataclass
class Decision:
    """Result of decision engine evaluation"""
    action: str  # ActionType value
    reasoning: str
    risk_level: str
    touches_deny_list: bool
    deny_list_areas: List[str]
    approval_required: bool
    
    def to_dict(self):
        return {
            "action": self.action,
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "touches_deny_list": self.touches_deny_list,
            "deny_list_areas": self.deny_list_areas,
            "approval_required": self.approval_required
        }


class DecisionEngine:
    """
    Decision Engine for QA Guardian
    
    Makes decisions based on Charter rules:
    - Default: OBSERVE-ONLY
    - Auto-fix only for: P3/P4 + LOW risk + NOT deny-list
    - Escalate for: P0/P1 OR HIGH/CRITICAL risk OR deny-list
    - Quarantine for: Repeated failures from same source
    """
    
    def __init__(self):
        self.deny_list_patterns = DENY_LIST_PATTERNS
        self.incident_counts = {}  # source -> count for quarantine detection
        self.auto_fix_enabled = QA_GUARDIAN_AUTO_FIX
    
    def decide(self, incident: Incident) -> Decision:
        """Make a decision for an incident"""
        
        # Check for quarantine conditions first
        quarantine_decision = self._check_quarantine(incident)
        if quarantine_decision:
            return quarantine_decision
        
        # Check deny-list
        deny_list_areas = self._check_deny_list(incident)
        touches_deny_list = len(deny_list_areas) > 0
        
        # Assess risk
        risk_level = self._assess_risk_from_incident(incident, touches_deny_list)
        
        # Determine if approval is required
        approval_required = (
            risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] or
            touches_deny_list or
            incident.severity in [Severity.P0, Severity.P1]
        )
        
        # Make decision
        if incident.severity == Severity.P0:
            return Decision(
                action=ActionType.ESCALATE,
                reasoning=f"P0 (Critical) incident requires immediate escalation",
                risk_level=risk_level,
                touches_deny_list=touches_deny_list,
                deny_list_areas=deny_list_areas,
                approval_required=True
            )
        
        if incident.severity == Severity.P1:
            return Decision(
                action=ActionType.ESCALATE,
                reasoning=f"P1 (High) incident requires escalation for review",
                risk_level=risk_level,
                touches_deny_list=touches_deny_list,
                deny_list_areas=deny_list_areas,
                approval_required=True
            )
        
        if touches_deny_list:
            return Decision(
                action=ActionType.ESCALATE,
                reasoning=f"Incident touches deny-list areas: {', '.join(deny_list_areas)}",
                risk_level=risk_level,
                touches_deny_list=True,
                deny_list_areas=deny_list_areas,
                approval_required=True
            )
        
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            return Decision(
                action=ActionType.ESCALATE,
                reasoning=f"Risk level {risk_level} requires founder approval",
                risk_level=risk_level,
                touches_deny_list=touches_deny_list,
                deny_list_areas=deny_list_areas,
                approval_required=True
            )
        
        # Check if auto-fix is possible
        if self._can_auto_fix(incident, risk_level, touches_deny_list):
            return Decision(
                action=ActionType.AUTO_FIX,
                reasoning=f"Low-risk {incident.severity} issue eligible for auto-fix",
                risk_level=risk_level,
                touches_deny_list=False,
                deny_list_areas=[],
                approval_required=False
            )
        
        # Default: Observe only
        return Decision(
            action=ActionType.OBSERVE,
            reasoning=f"Monitoring {incident.severity} incident in {incident.subsystem}",
            risk_level=risk_level,
            touches_deny_list=touches_deny_list,
            deny_list_areas=deny_list_areas,
            approval_required=False
        )
    
    def _check_quarantine(self, incident: Incident) -> Optional[Decision]:
        """Check if source should be quarantined (3+ incidents in window)"""
        source_key = incident.affected_agent or incident.affected_department or incident.subsystem
        
        if source_key not in self.incident_counts:
            self.incident_counts[source_key] = 0
        
        self.incident_counts[source_key] += 1
        
        if self.incident_counts[source_key] >= 3:
            return Decision(
                action=ActionType.QUARANTINE,
                reasoning=f"Source '{source_key}' has {self.incident_counts[source_key]} incidents - quarantine recommended",
                risk_level=RiskLevel.HIGH,
                touches_deny_list=False,
                deny_list_areas=[],
                approval_required=True
            )
        
        return None
    
    def _check_deny_list(self, incident: Incident) -> List[str]:
        """Check if incident touches deny-list areas"""
        matched_areas = []
        
        # Collect all file paths from evidence
        files_to_check = []
        for evidence in incident.evidence:
            if evidence.file:
                files_to_check.append(evidence.file)
        
        # Also check summary and description for keywords
        text_to_check = f"{incident.summary} {incident.description}".lower()
        
        # Check file paths against patterns
        for pattern in self.deny_list_patterns:
            for file_path in files_to_check:
                # Normalize path
                file_path = file_path.replace("\\", "/")
                if fnmatch.fnmatch(file_path, pattern):
                    area = self._pattern_to_area(pattern)
                    if area not in matched_areas:
                        matched_areas.append(area)
        
        # Check keywords
        deny_keywords = {
            "auth": "authentication",
            "login": "authentication",
            "session": "authentication",
            "jwt": "authentication",
            "permission": "authorization",
            "role": "authorization",
            "billing": "billing",
            "payment": "billing",
            "stripe": "billing",
            "secret": "secrets",
            "credential": "secrets",
            "api_key": "secrets",
            "migration": "database",
            "deploy": "deployment",
            "production": "deployment"
        }
        
        for keyword, area in deny_keywords.items():
            if keyword in text_to_check and area not in matched_areas:
                matched_areas.append(area)
        
        return matched_areas
    
    def _pattern_to_area(self, pattern: str) -> str:
        """Convert deny-list pattern to area name"""
        if "auth" in pattern or "login" in pattern or "session" in pattern:
            return "authentication"
        if "permission" in pattern or "role" in pattern:
            return "authorization"
        if "billing" in pattern or "payment" in pattern:
            return "billing"
        if "secret" in pattern or "credential" in pattern:
            return "secrets"
        if "migration" in pattern or "alembic" in pattern:
            return "database"
        if "deploy" in pattern or "k8s" in pattern:
            return "deployment"
        if "crypto" in pattern or "encryption" in pattern:
            return "encryption"
        if "audit" in pattern or "ledger" in pattern:
            return "audit"
        return "sensitive"
    
    def _assess_risk_from_incident(self, incident: Incident, touches_deny_list: bool) -> str:
        """Assess risk level from incident"""
        # Critical conditions
        if incident.severity == Severity.P0 or touches_deny_list:
            return RiskLevel.CRITICAL
        
        # High conditions
        if incident.severity == Severity.P1:
            return RiskLevel.HIGH
        
        if incident.category == "security":
            return RiskLevel.HIGH
        
        # Medium conditions
        if incident.severity == Severity.P2:
            return RiskLevel.MEDIUM
        
        if incident.category in ["data", "workflow"]:
            return RiskLevel.MEDIUM
        
        # Low conditions
        return RiskLevel.LOW
    
    def assess_risk(self, create: IncidentCreate) -> str:
        """Assess risk level from IncidentCreate (before full incident exists)"""
        # Check deny-list from evidence
        for evidence in create.evidence:
            if evidence.file:
                for pattern in self.deny_list_patterns:
                    if fnmatch.fnmatch(evidence.file.replace("\\", "/"), pattern):
                        return RiskLevel.CRITICAL
        
        # Check severity
        if create.severity == Severity.P0:
            return RiskLevel.CRITICAL
        if create.severity == Severity.P1:
            return RiskLevel.HIGH
        if create.severity == Severity.P2:
            return RiskLevel.MEDIUM
        
        # Check category
        if create.category == "security":
            return RiskLevel.HIGH
        if create.category in ["data", "workflow"]:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _can_auto_fix(self, incident: Incident, risk_level: str, 
                      touches_deny_list: bool) -> bool:
        """Check if auto-fix is allowed per Charter rules"""
        if not self.auto_fix_enabled:
            return False
        
        # Per Charter: P3/P4 + LOW risk + NOT deny-list
        return (
            incident.severity in [Severity.P3, Severity.P4] and
            risk_level == RiskLevel.LOW and
            not touches_deny_list and
            incident.category in ["config", "bug"]  # Safe categories only
        )
    
    def reset_incident_counts(self, source_key: str = None):
        """Reset incident counts (for testing or after resolution)"""
        if source_key:
            self.incident_counts.pop(source_key, None)
        else:
            self.incident_counts.clear()
