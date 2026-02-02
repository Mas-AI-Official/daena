"""
Patch Proposal Schema - Models for two-phase commit auto-fix system

Implements the patch proposal schema from QA_GUARDIAN_CHARTER.md Section E & I
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field
import uuid


class FileChange(BaseModel):
    """A single file change in a patch"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "file_path": "backend/config/settings.py",
            "change_type": "modify",
            "diff": "@@ -42,3 +42,3 @@\n-TIMEOUT = 5\n+TIMEOUT = 30",
            "reasoning": "Increase timeout to prevent external API timeouts"
        }
    })

    file_path: str
    change_type: Literal["modify", "create", "delete"]
    diff: str
    reasoning: str
    lines_affected: Optional[List[int]] = None


class VerificationPlan(BaseModel):
    """Plan for verifying a patch before commit"""
    tests: List[str] = Field(default_factory=list, description="Test files to run")
    golden_workflows: List[str] = Field(default_factory=list, description="Workflow IDs to execute")
    success_criteria: dict = Field(
        default_factory=lambda: {
            "min_test_pass_rate": 1.0,
            "max_new_errors": 0
        }
    )
    estimated_duration_seconds: int = 60

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "tests": ["tests/test_config.py", "tests/test_api.py"],
            "golden_workflows": ["golden_core_task_flow"],
            "success_criteria": {
                "min_test_pass_rate": 1.0,
                "max_new_errors": 0
            }
        }
    })


class RollbackPlan(BaseModel):
    """Plan for rolling back a patch if verification fails"""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "steps": [
                "Revert file backend/config/settings.py to backup",
                "Restart affected services",
                "Verify rollback with smoke test"
            ],
            "backup_location": ".backups/settings.py.20260121",
            "estimated_time_seconds": 30,
            "tested": True
        }
    })

    steps: List[str]
    backup_location: Optional[str] = None
    estimated_time_seconds: int = 30
    tested: bool = False


class TestResult(BaseModel):
    """Result of a single test execution"""
    test_name: str
    file_path: str
    status: Literal["passed", "failed", "skipped", "error"]
    duration_ms: int
    error_message: Optional[str] = None
    
    
class WorkflowResult(BaseModel):
    """Result of a golden workflow execution"""
    workflow_id: str
    workflow_name: str
    status: Literal["passed", "failed", "error"]
    duration_ms: int
    steps_completed: int
    total_steps: int
    failure_step: Optional[str] = None
    error_message: Optional[str] = None


class VerificationReport(BaseModel):
    """Report from verification phase of two-phase commit"""
    report_id: str = Field(default_factory=lambda: f"ver_{uuid.uuid4().hex[:8]}")
    proposal_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Results
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    golden_workflows_run: int = 0
    golden_workflows_passed: int = 0
    
    # Verdict
    success: bool = False
    failure_reasons: List[str] = Field(default_factory=list)
    
    # Details
    test_results: List[TestResult] = Field(default_factory=list)
    workflow_results: List[WorkflowResult] = Field(default_factory=list)
    new_errors_detected: List[str] = Field(default_factory=list)
    
    # Timing
    duration_ms: int = 0
    
    def evaluate_success(self, min_pass_rate: float = 1.0, max_new_errors: int = 0) -> bool:
        """Evaluate if verification passed based on criteria"""
        if self.tests_run == 0:
            # No tests = fail
            self.failure_reasons.append("No tests were executed")
            self.success = False
            return False
        
        pass_rate = self.tests_passed / self.tests_run
        
        if pass_rate < min_pass_rate:
            self.failure_reasons.append(
                f"Test pass rate {pass_rate:.2%} below threshold {min_pass_rate:.2%}"
            )
            self.success = False
            return False
        
        if len(self.new_errors_detected) > max_new_errors:
            self.failure_reasons.append(
                f"Detected {len(self.new_errors_detected)} new errors (max allowed: {max_new_errors})"
            )
            self.success = False
            return False
        
        if self.golden_workflows_run > 0 and self.golden_workflows_passed < self.golden_workflows_run:
            failed_count = self.golden_workflows_run - self.golden_workflows_passed
            self.failure_reasons.append(f"{failed_count} golden workflow(s) failed")
            self.success = False
            return False
        
        self.success = True
        return True


class PatchProposal(BaseModel):
    """Complete patch proposal for two-phase commit"""
    # Identity
    proposal_id: str = Field(default_factory=lambda: f"patch_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}")
    incident_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Changes
    files: List[FileChange]
    
    # Plans
    verification_plan: VerificationPlan
    rollback_plan: RollbackPlan
    
    # Assessment
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    deny_list_touched: List[str] = Field(default_factory=list)
    estimated_impact: str = ""
    
    # Status
    status: Literal[
        "proposed", "verifying", "verified", "awaiting_approval",
        "applying", "applied", "failed", "rolled_back"
    ] = "proposed"
    verification_result: Optional[VerificationReport] = None
    
    # Execution
    applied_at: Optional[datetime] = None
    applied_by: Optional[str] = None
    approval_by: Optional[str] = None
    approval_reason: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "proposal_id": "patch_20260121_abc123",
            "incident_id": "inc_20260121_def456",
            "risk_level": "LOW",
            "status": "proposed"
        }
    })

    def requires_approval(self) -> bool:
        """Check if this proposal requires founder approval"""
        return (
            self.risk_level in ["HIGH", "CRITICAL"] or
            len(self.deny_list_touched) > 0
        )
    
    def can_auto_apply(self) -> bool:
        """Check if this proposal can be auto-applied without approval"""
        return (
            not self.requires_approval() and
            self.status == "verified" and
            self.verification_result is not None and
            self.verification_result.success
        )


class ApprovalRequest(BaseModel):
    """Request for founder approval of a risky patch"""
    approval_request_id: str = Field(default_factory=lambda: f"apr_{uuid.uuid4().hex[:8]}")
    incident_id: str
    proposal_id: str
    severity: str
    risk_level: str
    
    # Context
    summary: str
    proposed_files: List[str]
    deny_list_areas_touched: List[str]
    
    # Verification
    verification_status: Literal["pending", "passed", "failed"]
    verification_report_id: Optional[str] = None
    
    # Timing
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = None
    
    # Decision
    founder_action: Optional[Literal["approved", "denied", "request_more_info"]] = None
    founder_reason: Optional[str] = None
    decided_at: Optional[datetime] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "incident_id": "inc_20260121_abc123",
            "proposal_id": "patch_20260121_def456",
            "severity": "P1",
            "risk_level": "HIGH",
            "summary": "Fix session validation bug in auth module",
            "deny_list_areas_touched": ["authentication"],
            "verification_status": "passed"
        }
    })
