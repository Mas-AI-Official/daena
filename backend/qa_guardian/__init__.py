"""
QA Guardian System - Hidden Department for Quality Assurance & Self-Healing

This module implements a production-grade QA Guardian system that:
- Detects issues and prevents regressions
- Enables safe self-correction with founder approval gates
- Enforces security policies and deny-lists
- Provides audit trails for all actions

Environment Variables:
- QA_GUARDIAN_ENABLED: Master enable (default: false)
- QA_GUARDIAN_KILL_SWITCH: Emergency stop (default: false)
- QA_GUARDIAN_AUTO_FIX: Allow automatic fixes (default: false)
- QA_GUARDIAN_LOG_LEVEL: Logging level (default: INFO)
"""

import os
from typing import Optional

# Version
__version__ = "1.0.0"

# Configuration from environment
QA_GUARDIAN_ENABLED = os.getenv("QA_GUARDIAN_ENABLED", "false").lower() == "true"
QA_GUARDIAN_KILL_SWITCH = os.getenv("QA_GUARDIAN_KILL_SWITCH", "false").lower() == "true"
QA_GUARDIAN_AUTO_FIX = os.getenv("QA_GUARDIAN_AUTO_FIX", "false").lower() == "true"
QA_GUARDIAN_LOG_LEVEL = os.getenv("QA_GUARDIAN_LOG_LEVEL", "INFO")
QA_GUARDIAN_RATE_LIMIT = int(os.getenv("QA_GUARDIAN_RATE_LIMIT", "5"))

# Model configuration
QA_MODEL_FAST = os.getenv("QA_MODEL_FAST", "gpt-4o-mini")
QA_MODEL_REASONING = os.getenv("QA_MODEL_REASONING", "o1")
QA_MODEL_CODE = os.getenv("QA_MODEL_CODE", "claude-3-5-sonnet")

# Import core components when accessed
def get_guardian_loop():
    """Get the Guardian Loop instance (lazy import to avoid circular deps)"""
    from .guardian_loop import GuardianLoop
    return GuardianLoop()

def get_decision_engine():
    """Get the Decision Engine instance"""
    from .decision_engine import DecisionEngine
    return DecisionEngine()

def is_enabled() -> bool:
    """Check if QA Guardian is enabled and not kill-switched"""
    return QA_GUARDIAN_ENABLED and not QA_GUARDIAN_KILL_SWITCH

def is_auto_fix_enabled() -> bool:
    """Check if auto-fix is allowed"""
    return is_enabled() and QA_GUARDIAN_AUTO_FIX

def get_control_api():
    """Get the Guardian Control API instance"""
    from .control_api import get_guardian_control_api
    return get_guardian_control_api()

def get_quarantine_manager():
    """Get the Quarantine Manager instance"""
    from .quarantine import get_quarantine_manager
    return get_quarantine_manager()

# High-Risk Deny List Patterns (from Charter)
DENY_LIST_PATTERNS = [
    "**/auth/**", "**/login/**", "**/session/**", "**/jwt/**", "**/oauth/**",
    "**/permissions/**", "**/roles/**", "**/rbac/**", "**/abac/**", "**/access/**",
    "**/billing/**", "**/payment/**", "**/subscription/**", "**/pricing/**", "**/stripe/**",
    "**/.env*", "**/secrets/**", "**/credentials/**", "**/keys/**",
    "**/migrations/**", "**/alembic/**",
    "**/crypto/**", "**/encryption/**", "**/ssl/**", "**/tls/**",
    "**/deploy/**", "**/k8s/**", "**/terraform/**", "**/docker-compose.prod**",
    "**/root/**", "**/admin/**", "**/founder/**",
    "**/audit/**", "**/ledger/**", "logs/*.jsonl",
    "QA_GUARDIAN_CHARTER.md"
]

# Severity definitions
class Severity:
    P0 = "P0"  # Critical - System down, data loss, security breach
    P1 = "P1"  # High - Major feature broken
    P2 = "P2"  # Medium - Feature degraded
    P3 = "P3"  # Low - Minor issue
    P4 = "P4"  # Info - Observation

# Risk levels
class RiskLevel:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

# Incident status
class IncidentStatus:
    OPEN = "open"
    TRIAGING = "triaging"
    PROPOSED = "proposed"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFIED = "verified"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    CLOSED = "closed"

# Incident categories
class IncidentCategory:
    BUG = "bug"
    CONFIG = "config"
    SECURITY = "security"
    DEPENDENCY = "dependency"
    DATA = "data"
    WORKFLOW = "workflow"
    AGENT_CONFLICT = "agent_conflict"

# Action types
class ActionType:
    OBSERVE = "observe"
    AUTO_FIX = "auto_fix"
    ESCALATE = "escalate"
    QUARANTINE = "quarantine"

# Quarantine states
class QuarantineState:
    ACTIVE = "active"
    SUSPECTED = "suspected"
    QUARANTINED = "quarantined"
    RECOVERING = "recovering"
    RESTORED = "restored"
