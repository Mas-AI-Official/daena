"""
QA Guardian Unit Tests - Tests for incident normalization, decision engine, and core logic

These tests verify the QA Guardian system works correctly.
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.qa_guardian import (
    Severity, RiskLevel, IncidentStatus, IncidentCategory, ActionType,
    DENY_LIST_PATTERNS
)
from backend.qa_guardian.schemas.incident import (
    Incident, IncidentCreate, Evidence
)
from backend.qa_guardian.decision_engine import DecisionEngine, Decision


class TestIncidentCreation:
    """Tests for incident creation and normalization"""
    
    def test_create_incident_basic(self):
        """Test basic incident creation"""
        create = IncidentCreate(
            severity="P3",
            subsystem="api",
            category="config",
            source="runtime",
            summary="Test timeout issue",
            description="HTTP timeout in external API"
        )
        
        incident = Incident.from_create(create)
        
        assert incident.incident_id.startswith("inc_")
        assert incident.severity == "P3"
        assert incident.subsystem == "api"
        assert incident.status == IncidentStatus.OPEN
        assert not incident.approval_required
    
    def test_create_incident_high_risk(self):
        """Test high-risk incident creation sets approval_required"""
        create = IncidentCreate(
            severity="P1",
            subsystem="database",
            category="data",
            source="runtime",
            summary="Database connection pool exhausted",
            description="All connections in use"
        )
        
        incident = Incident.from_create(create, risk_level=RiskLevel.HIGH)
        
        assert incident.risk_level == RiskLevel.HIGH
        assert incident.approval_required
    
    def test_idempotency_key_generation(self):
        """Test idempotency key is consistent for same incident signature"""
        create1 = IncidentCreate(
            severity="P3",
            subsystem="api",
            category="config",
            source="runtime",
            summary="Same error message",
            description="Details"
        )
        
        create2 = IncidentCreate(
            severity="P3",
            subsystem="api",
            category="config",
            source="runtime",
            summary="Same error message",
            description="Different details"  # Different description
        )
        
        key1 = create1.generate_idempotency_key()
        key2 = create2.generate_idempotency_key()
        
        # Same subsystem + category + summary = same key
        assert key1 == key2
    
    def test_incident_with_evidence(self):
        """Test incident with evidence attached"""
        evidence = Evidence(
            type="stack_trace",
            content="Traceback...",
            file="backend/routes/tasks.py",
            line=142
        )
        
        create = IncidentCreate(
            severity="P2",
            subsystem="api",
            category="bug",
            source="runtime",
            summary="NoneType error",
            description="NoneType has no attribute 'get'",
            evidence=[evidence]
        )
        
        incident = Incident.from_create(create)
        
        assert len(incident.evidence) == 1
        assert incident.evidence[0].file == "backend/routes/tasks.py"
        assert incident.evidence[0].line == 142
    
    def test_incident_can_auto_fix(self):
        """Test can_auto_fix logic"""
        # Low severity, low risk = can auto-fix
        incident_low = Incident.from_create(
            IncidentCreate(
                severity="P3",
                subsystem="config",
                category="config",
                source="runtime",
                summary="Config issue",
                description="Minor config mismatch"
            ),
            risk_level=RiskLevel.LOW
        )
        assert incident_low.can_auto_fix()
        
        # High severity = cannot auto-fix
        incident_high = Incident.from_create(
            IncidentCreate(
                severity="P1",
                subsystem="api",
                category="bug",
                source="runtime",
                summary="Critical bug",
                description="Major issue"
            ),
            risk_level=RiskLevel.HIGH
        )
        assert not incident_high.can_auto_fix()
    
    def test_incident_locking(self):
        """Test incident lock mechanism"""
        incident = Incident.from_create(
            IncidentCreate(
                severity="P3",
                subsystem="api",
                category="config",
                source="runtime",
                summary="Test",
                description="Test"
            )
        )
        
        assert not incident.is_locked()
        
        # First lock succeeds
        assert incident.acquire_lock("agent_1")
        assert incident.is_locked()
        assert incident.locked_by == "agent_1"
        
        # Second lock fails
        assert not incident.acquire_lock("agent_2")
        
        # Release and re-lock
        incident.release_lock()
        assert not incident.is_locked()
        assert incident.acquire_lock("agent_2")


class TestDecisionEngine:
    """Tests for the decision engine"""
    
    @pytest.fixture
    def engine(self):
        return DecisionEngine()
    
    def test_p0_always_escalates(self, engine):
        """P0 incidents always require escalation"""
        incident = Incident.from_create(
            IncidentCreate(
                severity="P0",
                subsystem="database",
                category="data",
                source="runtime",
                summary="Database corruption detected",
                description="Critical data integrity issue"
            )
        )
        
        decision = engine.decide(incident)
        
        assert decision.action == ActionType.ESCALATE
        assert decision.approval_required
        assert "P0" in decision.reasoning or "Critical" in decision.reasoning
    
    def test_p1_always_escalates(self, engine):
        """P1 incidents always require escalation"""
        incident = Incident.from_create(
            IncidentCreate(
                severity="P1",
                subsystem="api",
                category="bug",
                source="runtime",
                summary="Major API failure",
                description="Critical endpoint down"
            )
        )
        
        decision = engine.decide(incident)
        
        assert decision.action == ActionType.ESCALATE
        assert decision.approval_required
    
    def test_deny_list_detection_auth(self, engine):
        """Deny list detection for auth-related files"""
        evidence = Evidence(
            type="code_reference",
            content="error in auth check",
            file="backend/routes/auth/login.py",
            line=50
        )
        
        incident = Incident.from_create(
            IncidentCreate(
                severity="P3",
                subsystem="api",
                category="bug",
                source="runtime",
                summary="Login validation issue",
                description="Issue in login flow",
                evidence=[evidence]
            )
        )
        
        decision = engine.decide(incident)
        
        assert decision.touches_deny_list
        assert "authentication" in decision.deny_list_areas
        assert decision.action == ActionType.ESCALATE
    
    def test_deny_list_detection_billing(self, engine):
        """Deny list detection for billing keywords"""
        incident = Incident.from_create(
            IncidentCreate(
                severity="P3",
                subsystem="api",
                category="bug",
                source="runtime",
                summary="Payment processing error",
                description="Stripe API returned error during payment"
            )
        )
        
        decision = engine.decide(incident)
        
        assert decision.touches_deny_list
        assert "billing" in decision.deny_list_areas
        assert decision.action == ActionType.ESCALATE
    
    def test_low_risk_auto_fix(self, engine):
        """Low-risk P3/P4 issues can be auto-fixed"""
        # Enable auto-fix for test
        engine.auto_fix_enabled = True
        
        incident = Incident.from_create(
            IncidentCreate(
                severity="P3",
                subsystem="logging",
                category="config",
                source="runtime",
                summary="Log level misconfigured",
                description="Debug logging too verbose"
            ),
            risk_level=RiskLevel.LOW
        )
        
        decision = engine.decide(incident)
        
        assert decision.action == ActionType.AUTO_FIX
        assert not decision.approval_required
        assert decision.risk_level == RiskLevel.LOW
    
    def test_observe_when_auto_fix_disabled(self, engine):
        """When auto-fix is disabled, default to observe"""
        engine.auto_fix_enabled = False
        
        incident = Incident.from_create(
            IncidentCreate(
                severity="P4",
                subsystem="ui",
                category="bug",
                source="runtime",
                summary="Minor display issue",
                description="Button alignment off"
            ),
            risk_level=RiskLevel.LOW
        )
        
        decision = engine.decide(incident)
        
        assert decision.action == ActionType.OBSERVE
        assert not decision.approval_required
    
    def test_quarantine_on_repeated_failures(self, engine):
        """Quarantine recommended after 3+ incidents from same source"""
        # Create incident from same agent 3 times
        for i in range(3):
            incident = Incident.from_create(
                IncidentCreate(
                    severity="P3",
                    subsystem="api",
                    category="bug",
                    source="runtime",
                    summary=f"Error {i}",
                    description="Repeated error",
                    affected_agent="agent_marketing_lead"
                )
            )
            decision = engine.decide(incident)
        
        # Third decision should recommend quarantine
        assert decision.action == ActionType.QUARANTINE
        assert "quarantine" in decision.reasoning.lower()
    
    def test_security_category_high_risk(self, engine):
        """Security category issues are always high risk"""
        incident = Incident.from_create(
            IncidentCreate(
                severity="P3",
                subsystem="api",
                category="security",
                source="runtime",
                summary="Suspicious access pattern",
                description="Unusual API access detected"
            )
        )
        
        decision = engine.decide(incident)
        
        assert decision.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]


class TestSeverityClassification:
    """Tests for severity classification logic"""
    
    def test_severity_p0_keywords(self):
        """Test P0 severity for critical keywords"""
        from backend.qa_guardian.guardian_loop import GuardianLoop
        loop = GuardianLoop()
        
        signal = {
            "type": "exception",
            "error_type": "DatabaseError",
            "error_message": "Database corruption detected in user table"
        }
        
        severity = loop._classify_severity(signal)
        assert severity == Severity.P0
    
    def test_severity_p1_keywords(self):
        """Test P1 severity for high-impact errors"""
        from backend.qa_guardian.guardian_loop import GuardianLoop
        loop = GuardianLoop()
        
        signal = {
            "type": "exception",
            "error_type": "DatabaseError",
            "error_message": "Connection pool exhausted"
        }
        
        severity = loop._classify_severity(signal)
        assert severity == Severity.P1
    
    def test_category_classification(self):
        """Test category classification from signals"""
        from backend.qa_guardian.guardian_loop import GuardianLoop
        loop = GuardianLoop()
        
        # Config error
        signal_config = {
            "error_type": "ValueError",
            "error_message": "Invalid config: missing environment variable"
        }
        assert loop._classify_category(signal_config) == "config"
        
        # Dependency error
        signal_dep = {
            "error_type": "ModuleNotFoundError",
            "error_message": "No module named 'pandas'"
        }
        assert loop._classify_category(signal_dep) == "dependency"


class TestDenyListPatterns:
    """Tests for deny list pattern matching"""
    
    def test_deny_list_contains_critical_patterns(self):
        """Verify deny list contains all critical patterns"""
        critical_patterns = [
            "**/auth/**",
            "**/billing/**",
            "**/payment/**",
            "**/.env*",
            "**/secrets/**",
            "**/migrations/**"
        ]
        
        for pattern in critical_patterns:
            assert pattern in DENY_LIST_PATTERNS, f"Missing critical pattern: {pattern}"
    
    def test_deny_list_pattern_matching(self):
        """Test deny list pattern matching works"""
        import fnmatch
        
        # Auth paths should match
        auth_paths = [
            "backend/routes/auth/login.py",
            "backend/auth/session.py",
            "backend/api/oauth/callback.py"
        ]
        
        for path in auth_paths:
            matched = any(
                fnmatch.fnmatch(path.replace("\\", "/"), pattern)
                for pattern in DENY_LIST_PATTERNS
            )
            assert matched, f"Auth path should match deny list: {path}"


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
