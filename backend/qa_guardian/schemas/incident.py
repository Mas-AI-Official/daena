"""
Incident Schema - Core data model for QA Guardian incidents

Implements the incident schema from QA_GUARDIAN_CHARTER.md Section I
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field
import uuid
import hashlib


class Evidence(BaseModel):
    """Evidence attached to an incident"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "type": "stack_trace",
            "content": "Traceback (most recent call last):\n  File...",
            "file": "backend/routes/tasks.py",
            "line": 142
        }
    })

    type: Literal["stack_trace", "log_entry", "tool_call", "code_reference"]
    content: str
    file: Optional[str] = None
    line: Optional[int] = None
    timestamp: Optional[datetime] = None


class Action(BaseModel):
    """Proposed action for an incident"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "action_type": "auto_fix",
            "description": "Apply retry configuration fix",
            "approval_status": "pending"
        }
    })

    action_type: Literal["observe", "auto_fix", "escalate", "quarantine"]
    description: str
    patch_id: Optional[str] = None
    approval_status: Optional[Literal["pending", "approved", "denied"]] = None


class IncidentCreate(BaseModel):
    """Schema for creating a new incident"""
    severity: Literal["P0", "P1", "P2", "P3", "P4"]
    subsystem: str
    category: Literal["bug", "config", "security", "dependency", "data", "workflow", "agent_conflict"]
    source: Literal["runtime", "ci", "user_report", "scheduled_scan"]
    summary: str
    description: str
    evidence: List[Evidence] = Field(default_factory=list)
    affected_agent: Optional[str] = None
    affected_department: Optional[str] = None
    suspected_root_cause: Optional[str] = None
    reproduction_steps: Optional[List[str]] = None
    
    def generate_idempotency_key(self) -> str:
        """Generate idempotency key from incident signature"""
        signature = f"{self.subsystem}:{self.category}:{self.summary}"
        return hashlib.sha256(signature.encode()).hexdigest()[:16]


class IncidentUpdate(BaseModel):
    """Schema for updating an incident"""
    severity: Optional[Literal["P0", "P1", "P2", "P3", "P4"]] = None
    status: Optional[Literal[
        "open", "triaging", "proposed", "awaiting_approval",
        "verified", "committed", "rolled_back", "closed"
    ]] = None
    risk_level: Optional[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]] = None
    owner: Optional[str] = None
    suspected_root_cause: Optional[str] = None
    resolution: Optional[str] = None
    proposed_actions: Optional[List[Action]] = None


class Incident(BaseModel):
    """Complete incident record"""
    # Identity
    incident_id: str = Field(default_factory=lambda: f"inc_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}")
    idempotency_key: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Classification
    severity: Literal["P0", "P1", "P2", "P3", "P4"]
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"] = "LOW"
    subsystem: str
    category: Literal["bug", "config", "security", "dependency", "data", "workflow", "agent_conflict"]
    
    # Source
    source: Literal["runtime", "ci", "user_report", "scheduled_scan"]
    affected_agent: Optional[str] = None
    affected_department: Optional[str] = None
    
    # Details
    summary: str
    description: str
    evidence: List[Evidence] = Field(default_factory=list)
    suspected_root_cause: Optional[str] = None
    reproduction_steps: Optional[List[str]] = None
    
    # Response
    proposed_actions: List[Action] = Field(default_factory=list)
    approval_required: bool = False
    owner: Optional[str] = None
    
    # Lifecycle
    status: Literal[
        "open", "triaging", "proposed", "awaiting_approval",
        "verified", "committed", "rolled_back", "closed"
    ] = "open"
    resolution: Optional[str] = None
    closed_at: Optional[datetime] = None
    
    # Lock for concurrent access
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "incident_id": "inc_20260121_abc123",
            "idempotency_key": "a1b2c3d4e5f67890",
            "severity": "P2",
            "risk_level": "LOW",
            "subsystem": "api",
            "category": "config",
            "source": "runtime",
            "summary": "Timeout too short for external API calls",
            "description": "HTTP requests to external services timing out due to 5s limit",
            "status": "open"
        }
    })

    @classmethod
    def from_create(cls, create: IncidentCreate, risk_level: str = "LOW") -> "Incident":
        """Create an Incident from IncidentCreate schema"""
        return cls(
            idempotency_key=create.generate_idempotency_key(),
            severity=create.severity,
            risk_level=risk_level,
            subsystem=create.subsystem,
            category=create.category,
            source=create.source,
            affected_agent=create.affected_agent,
            affected_department=create.affected_department,
            summary=create.summary,
            description=create.description,
            evidence=create.evidence,
            suspected_root_cause=create.suspected_root_cause,
            reproduction_steps=create.reproduction_steps,
            approval_required=(risk_level in ["HIGH", "CRITICAL"])
        )
    
    def acquire_lock(self, owner: str) -> bool:
        """Attempt to acquire lock for exclusive modification"""
        if self.locked_by is None:
            self.locked_by = owner
            self.locked_at = datetime.utcnow()
            return True
        return False
    
    def release_lock(self):
        """Release the lock"""
        self.locked_by = None
        self.locked_at = None
    
    def is_locked(self) -> bool:
        """Check if incident is locked"""
        return self.locked_by is not None
    
    def can_auto_fix(self) -> bool:
        """Check if incident is eligible for auto-fix per Charter rules"""
        # Per Charter: P3/P4 + LOW risk + NOT require approval
        return (
            self.severity in ["P3", "P4"] and
            self.risk_level == "LOW" and
            not self.approval_required and
            self.status in ["open", "triaging", "proposed"]
        )
