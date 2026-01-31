"""
Agent Schemas - Input/Output schemas for each QA Guardian agent

Each agent has explicit inputs and outputs as required by the Charter.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# Base Agent Schemas
# ═══════════════════════════════════════════════════════════════════════

class AgentInput(BaseModel):
    """Base input for all QA agents"""
    request_id: str = Field(default_factory=lambda: f"req_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = Field(default_factory=dict)
    

class AgentOutput(BaseModel):
    """Base output for all QA agents"""
    request_id: str
    agent_id: str
    success: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    execution_time_ms: int = 0
    error: Optional[str] = None
    audit_log_id: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# qa_triage_agent - Collect and categorize errors
# ═══════════════════════════════════════════════════════════════════════

class TriageInput(AgentInput):
    """Input for qa_triage_agent"""
    # Raw error data
    error_type: str
    error_message: str
    stack_trace: Optional[str] = None
    
    # Context
    source: Literal["runtime", "ci", "user_report", "scheduled_scan"]
    subsystem: Optional[str] = None
    affected_file: Optional[str] = None
    affected_line: Optional[int] = None
    
    # Related data
    recent_changes: List[str] = Field(default_factory=list)
    tool_call_log: Optional[Dict[str, Any]] = None


class TriageOutput(AgentOutput):
    """Output from qa_triage_agent"""
    agent_id: str = "qa_triage_agent"
    
    # Classification
    incident_id: Optional[str] = None
    category: Literal["bug", "config", "security", "dependency", "data", "workflow", "agent_conflict"]
    severity: Literal["P0", "P1", "P2", "P3", "P4"]
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    
    # Analysis
    subsystem: str
    summary: str
    suspected_root_cause: Optional[str] = None
    
    # Recommendation
    recommended_action: Literal["observe", "auto_fix", "escalate", "quarantine"]
    touches_deny_list: bool = False
    deny_list_areas: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# qa_regression_agent - Run golden workflows and tests
# ═══════════════════════════════════════════════════════════════════════

class RegressionInput(AgentInput):
    """Input for qa_regression_agent"""
    # What to run
    run_type: Literal["full", "golden_only", "specific_tests", "smoke"]
    specific_tests: List[str] = Field(default_factory=list)
    specific_workflows: List[str] = Field(default_factory=list)
    
    # Context
    incident_id: Optional[str] = None
    proposal_id: Optional[str] = None
    
    # Options
    timeout_seconds: int = 300
    stop_on_first_failure: bool = False


class RegressionOutput(AgentOutput):
    """Output from qa_regression_agent"""
    agent_id: str = "qa_regression_agent"
    
    # Summary
    total_tests: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    
    total_workflows: int = 0
    workflows_passed: int = 0
    workflows_failed: int = 0
    
    # Verdict
    all_passed: bool = False
    pass_rate: float = 0.0
    
    # Details
    failed_tests: List[str] = Field(default_factory=list)
    failed_workflows: List[str] = Field(default_factory=list)
    new_failures: List[str] = Field(default_factory=list)  # Failures not in baseline
    
    # Report
    verification_report_id: Optional[str] = None
    duration_ms: int = 0


# ═══════════════════════════════════════════════════════════════════════
# qa_security_agent - Security scanning
# ═══════════════════════════════════════════════════════════════════════

class SecurityInput(AgentInput):
    """Input for qa_security_agent"""
    # Scan type
    scan_type: Literal["full", "secrets", "dependencies", "static_analysis"]
    
    # Scope
    paths: List[str] = Field(default_factory=list)  # Empty = full repo
    include_gitignored: bool = False
    
    # Options
    fail_on_high: bool = True
    fail_on_critical: bool = True


class SecurityFinding(BaseModel):
    """A single security finding"""
    finding_id: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: Literal["secret", "vulnerability", "code_issue", "config_issue"]
    title: str
    description: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    recommendation: str
    cve_id: Optional[str] = None


class SecurityOutput(AgentOutput):
    """Output from qa_security_agent"""
    agent_id: str = "qa_security_agent"
    
    # Summary
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    
    # Verdicts
    secrets_clean: bool = True
    dependencies_clean: bool = True
    code_clean: bool = True
    
    # Details
    findings: List[SecurityFinding] = Field(default_factory=list)
    
    # Dependencies
    vulnerable_dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    outdated_dependencies: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Recommendations
    immediate_actions: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# qa_code_review_agent - PR/diff analysis
# ═══════════════════════════════════════════════════════════════════════

class CodeReviewInput(AgentInput):
    """Input for qa_code_review_agent"""
    # What to review
    review_type: Literal["pr", "diff", "commit", "file"]
    
    # PR/commit context
    pr_number: Optional[int] = None
    commit_sha: Optional[str] = None
    base_branch: Optional[str] = None
    
    # Direct diff
    diff_content: Optional[str] = None
    
    # Files
    files_to_review: List[str] = Field(default_factory=list)
    
    # CI context
    ci_logs: Optional[str] = None
    test_results: Optional[Dict[str, Any]] = None


class CodeReviewFinding(BaseModel):
    """A single code review finding"""
    severity: Literal["critical", "major", "minor", "suggestion"]
    category: Literal["bug", "security", "performance", "maintainability", "style"]
    file_path: str
    line_start: int
    line_end: Optional[int] = None
    title: str
    description: str
    suggested_fix: Optional[str] = None
    code_snippet: Optional[str] = None


class CodeReviewOutput(AgentOutput):
    """Output from qa_code_review_agent"""
    agent_id: str = "qa_code_review_agent"
    
    # Summary
    files_reviewed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    
    total_findings: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    
    # Verdict
    approve: bool = False
    requires_changes: bool = False
    
    # Details
    findings: List[CodeReviewFinding] = Field(default_factory=list)
    
    # Structured output for PR comment
    summary: str = ""
    detailed_review: str = ""
    recommended_tests: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════
# qa_auto_fix_agent - Generate safe patches
# ═══════════════════════════════════════════════════════════════════════

class AutoFixInput(AgentInput):
    """Input for qa_auto_fix_agent"""
    # Incident context
    incident_id: str
    incident_summary: str
    incident_category: str
    
    # Evidence
    error_message: str
    stack_trace: Optional[str] = None
    affected_files: List[str] = Field(default_factory=list)
    
    # Constraints
    max_files_to_modify: int = 3
    allow_new_files: bool = False
    allow_delete_files: bool = False


class AutoFixOutput(AgentOutput):
    """Output from qa_auto_fix_agent"""
    agent_id: str = "qa_auto_fix_agent"
    
    # Result
    fix_generated: bool = False
    proposal_id: Optional[str] = None
    
    # Assessment
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    touches_deny_list: bool = False
    deny_list_areas: List[str] = Field(default_factory=list)
    requires_approval: bool = False
    
    # Patch summary
    files_to_modify: List[str] = Field(default_factory=list)
    estimated_impact: str = ""
    
    # Reasoning
    fix_explanation: str = ""
    alternative_fixes: List[str] = Field(default_factory=list)
    
    # Status
    skip_reason: Optional[str] = None  # Why fix was not generated


# ═══════════════════════════════════════════════════════════════════════
# qa_reporter_agent - Publish reports and create issues
# ═══════════════════════════════════════════════════════════════════════

class ReporterInput(AgentInput):
    """Input for qa_reporter_agent"""
    # What to report
    report_type: Literal["incident", "fix_applied", "verification", "security", "regression", "summary"]
    
    # Subject
    incident_id: Optional[str] = None
    proposal_id: Optional[str] = None
    
    # Destinations
    post_to_dashboard: bool = True
    post_to_log: bool = True
    create_github_issue: bool = False
    send_notification: bool = False
    
    # Content
    title: Optional[str] = None
    content: Optional[str] = None
    severity: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class ReporterOutput(AgentOutput):
    """Output from qa_reporter_agent"""
    agent_id: str = "qa_reporter_agent"
    
    # Results
    dashboard_posted: bool = False
    dashboard_url: Optional[str] = None
    
    log_written: bool = False
    log_file: Optional[str] = None
    
    github_issue_created: bool = False
    github_issue_url: Optional[str] = None
    github_issue_number: Optional[int] = None
    
    notification_sent: bool = False
    notification_channels: List[str] = Field(default_factory=list)
    
    # Generated content
    report_id: Optional[str] = None
    formatted_report: Optional[str] = None
