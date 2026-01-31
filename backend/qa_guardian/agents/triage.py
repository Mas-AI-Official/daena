"""
QA Triage Agent - Collects errors and categorizes them

This agent is responsible for:
- Collecting runtime errors from various sources
- Categorizing errors: bug, config, security, dependency, data, workflow, agent_conflict
- Producing incident objects with proper classification
- Initial severity assessment
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from backend.qa_guardian import Severity, RiskLevel, IncidentCategory
from backend.qa_guardian.schemas.agent_schemas import TriageInput, TriageOutput
from backend.qa_guardian.schemas.incident import Incident, IncidentCreate, Evidence
from backend.qa_guardian.decision_engine import DecisionEngine

logger = logging.getLogger("qa_guardian.agents.triage")


class QATriageAgent:
    """
    QA Triage Agent
    
    Collects errors and categorizes them into proper incident objects.
    
    Permission Boundaries:
    - CAN READ: All logs, error outputs, tool call history
    - CAN WRITE: Incident store (create incidents only)
    - CANNOT: Modify code, access secrets, change configs
    """
    
    AGENT_ID = "qa_triage_agent"
    DEPARTMENT = "qa_guardian"
    
    # Tool access policy
    ALLOWED_TOOLS = [
        "read_logs",
        "read_error_history",
        "read_tool_call_log",
        "create_incident"
    ]
    
    DENIED_TOOLS = [
        "write_file",
        "execute_code",
        "access_secrets",
        "modify_config"
    ]
    
    def __init__(self):
        self.decision_engine = DecisionEngine()
    
    async def process(self, input: TriageInput) -> TriageOutput:
        """
        Process an error signal and categorize it.
        
        Args:
            input: TriageInput with error details
            
        Returns:
            TriageOutput with classification and incident ID
        """
        start_time = datetime.utcnow()
        
        try:
            # Classify severity
            severity = self._classify_severity(input)
            
            # Classify category
            category = self._classify_category(input)
            
            # Determine subsystem
            subsystem = self._determine_subsystem(input)
            
            # Check deny list
            deny_list_areas = self._check_deny_list(input)
            touches_deny_list = len(deny_list_areas) > 0
            
            # Assess risk
            risk_level = self._assess_risk(severity, category, touches_deny_list)
            
            # Generate summary
            summary = self._generate_summary(input)
            
            # Determine recommended action
            recommended_action = self._recommend_action(
                severity, risk_level, touches_deny_list
            )
            
            # Create incident
            incident = await self._create_incident(
                input, severity, category, subsystem, risk_level, summary
            )
            
            # Calculate execution time
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return TriageOutput(
                request_id=input.request_id,
                success=True,
                execution_time_ms=exec_time,
                incident_id=incident.incident_id if incident else None,
                category=category,
                severity=severity,
                risk_level=risk_level,
                subsystem=subsystem,
                summary=summary,
                suspected_root_cause=self._guess_root_cause(input),
                recommended_action=recommended_action,
                touches_deny_list=touches_deny_list,
                deny_list_areas=deny_list_areas
            )
            
        except Exception as e:
            logger.error(f"Triage agent error: {e}")
            return TriageOutput(
                request_id=input.request_id,
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                category="bug",
                severity="P3",
                risk_level="MEDIUM",
                subsystem="unknown",
                summary=f"Triage failed: {str(e)}",
                recommended_action="escalate"
            )
    
    def _classify_severity(self, input: TriageInput) -> str:
        """Classify severity based on error type and message"""
        error_type = input.error_type.lower()
        error_msg = input.error_message.lower()
        
        # P0: Critical
        if any(kw in error_msg for kw in [
            'database corruption', 'data loss', 'security breach',
            'memory exhausted', 'system crash'
        ]):
            return Severity.P0
        
        # P1: High
        if any(kw in error_type for kw in [
            'databaseerror', 'connectionerror', 'authenticationerror',
            'permissionerror'
        ]):
            return Severity.P1
        
        if any(kw in error_msg for kw in [
            'connection refused', 'pool exhausted', 'timeout exceeded',
            'critical', 'fatal'
        ]):
            return Severity.P1
        
        # P2: Medium
        if any(kw in error_type for kw in [
            'timeout', 'httperror', 'apierror', 'notfounderror'
        ]):
            return Severity.P2
        
        # P3: Low
        if any(kw in error_type for kw in [
            'validationerror', 'valueerror', 'typeerror', 'keyerror'
        ]):
            return Severity.P3
        
        # Default to P3
        return Severity.P3
    
    def _classify_category(self, input: TriageInput) -> str:
        """Classify category based on error context"""
        error_type = input.error_type.lower()
        error_msg = input.error_message.lower()
        stack = (input.stack_trace or '').lower()
        
        # Security
        if any(kw in error_msg for kw in ['security', 'unauthorized', 'forbidden', 'auth']):
            return IncidentCategory.SECURITY
        
        # Config
        if any(kw in error_msg for kw in ['config', 'environment', 'setting', 'missing variable']):
            return IncidentCategory.CONFIG
        
        # Dependency
        if any(kw in error_type for kw in ['importerror', 'modulenotfound']):
            return IncidentCategory.DEPENDENCY
        
        if 'dependency' in error_msg or 'package' in error_msg:
            return IncidentCategory.DEPENDENCY
        
        # Data
        if any(kw in error_msg for kw in ['database', 'sql', 'query', 'data']):
            return IncidentCategory.DATA
        
        if 'database' in stack or 'sql' in stack:
            return IncidentCategory.DATA
        
        # Workflow
        if any(kw in stack for kw in ['workflow', 'task', 'pipeline', 'job']):
            return IncidentCategory.WORKFLOW
        
        # Agent conflict
        if 'agent' in stack and any(kw in error_msg for kw in ['conflict', 'collision', 'deadlock']):
            return IncidentCategory.AGENT_CONFLICT
        
        # Default to bug
        return IncidentCategory.BUG
    
    def _determine_subsystem(self, input: TriageInput) -> str:
        """Determine which subsystem the error originated from"""
        if input.subsystem:
            return input.subsystem
        
        stack = (input.stack_trace or '').lower()
        
        # Check stack trace for subsystem hints
        if 'backend/routes/' in stack:
            return 'api'
        if 'backend/services/' in stack:
            return 'services'
        if 'database' in stack:
            return 'database'
        if 'qa_guardian' in stack:
            return 'qa_guardian'
        if 'frontend' in stack:
            return 'frontend'
        if 'core/' in stack:
            return 'core'
        if 'memory_service' in stack:
            return 'memory'
        if 'tools' in stack:
            return 'tools'
        
        return 'unknown'
    
    def _check_deny_list(self, input: TriageInput) -> List[str]:
        """Check if error involves deny-list areas"""
        deny_areas = []
        
        file_path = (input.affected_file or '').lower()
        error_msg = input.error_message.lower()
        stack = (input.stack_trace or '').lower()
        
        combined = f"{file_path} {error_msg} {stack}"
        
        # Check for deny-list keywords
        if any(kw in combined for kw in ['auth', 'login', 'session', 'jwt', 'oauth']):
            deny_areas.append('authentication')
        if any(kw in combined for kw in ['permission', 'role', 'access control']):
            deny_areas.append('authorization')
        if any(kw in combined for kw in ['billing', 'payment', 'stripe', 'subscription']):
            deny_areas.append('billing')
        if any(kw in combined for kw in ['secret', 'credential', 'api_key', 'password']):
            deny_areas.append('secrets')
        if any(kw in combined for kw in ['migration', 'alembic', 'schema change']):
            deny_areas.append('database')
        if any(kw in combined for kw in ['deploy', 'production', 'terraform']):
            deny_areas.append('deployment')
        
        return deny_areas
    
    def _assess_risk(self, severity: str, category: str, touches_deny_list: bool) -> str:
        """Assess risk level"""
        if touches_deny_list or severity == Severity.P0:
            return RiskLevel.CRITICAL
        
        if severity == Severity.P1 or category == IncidentCategory.SECURITY:
            return RiskLevel.HIGH
        
        if severity == Severity.P2 or category in [IncidentCategory.DATA, IncidentCategory.WORKFLOW]:
            return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _generate_summary(self, input: TriageInput) -> str:
        """Generate a concise summary"""
        return f"{input.error_type}: {input.error_message[:100]}"
    
    def _guess_root_cause(self, input: TriageInput) -> Optional[str]:
        """Attempt to guess root cause from error context"""
        error_msg = input.error_message.lower()
        
        if 'connection refused' in error_msg:
            return "Service or database not running or unreachable"
        if 'timeout' in error_msg:
            return "External service too slow or network issues"
        if 'key error' in error_msg or 'keyerror' in input.error_type.lower():
            return "Missing expected key in dictionary or config"
        if 'import' in error_msg or 'module' in error_msg:
            return "Missing dependency or incorrect import path"
        if 'permission' in error_msg:
            return "Insufficient permissions or access rights"
        
        return None
    
    def _recommend_action(self, severity: str, risk_level: str, 
                          touches_deny_list: bool) -> str:
        """Recommend action based on classification"""
        if touches_deny_list or severity in [Severity.P0, Severity.P1]:
            return "escalate"
        
        if risk_level == RiskLevel.CRITICAL:
            return "escalate"
        
        if risk_level == RiskLevel.HIGH:
            return "escalate"
        
        if severity in [Severity.P3, Severity.P4] and risk_level == RiskLevel.LOW:
            return "auto_fix"
        
        return "observe"
    
    async def _create_incident(
        self, input: TriageInput, severity: str, category: str,
        subsystem: str, risk_level: str, summary: str
    ) -> Optional[Incident]:
        """Create an incident object"""
        try:
            evidence = []
            
            if input.stack_trace:
                evidence.append(Evidence(
                    type="stack_trace",
                    content=input.stack_trace,
                    file=input.affected_file,
                    line=input.affected_line,
                    timestamp=input.timestamp
                ))
            
            if input.tool_call_log:
                evidence.append(Evidence(
                    type="tool_call",
                    content=str(input.tool_call_log),
                    timestamp=input.timestamp
                ))
            
            create = IncidentCreate(
                severity=severity,
                subsystem=subsystem,
                category=category,
                source=input.source,
                summary=summary,
                description=input.error_message,
                evidence=evidence,
                suspected_root_cause=self._guess_root_cause(input)
            )
            
            return Incident.from_create(create, risk_level)
            
        except Exception as e:
            logger.error(f"Failed to create incident: {e}")
            return None
