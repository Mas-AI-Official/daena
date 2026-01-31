"""
QA Code Review Agent - Analyzes code diffs and PRs

Analyzes diffs, checks deny-list violations, and produces structured reviews.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from backend.qa_guardian.schemas.agent_schemas import CodeReviewInput, CodeReviewOutput, CodeReviewFinding
from backend.qa_guardian import DENY_LIST_PATTERNS

logger = logging.getLogger("qa_guardian.agents.code_review")


class QACodeReviewAgent:
    """QA Code Review Agent - Analyzes diffs for issues"""
    
    AGENT_ID = "qa_code_review_agent"
    DEPARTMENT = "qa_guardian"
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    
    CODE_PATTERNS = {
        'hardcoded_secret': (r'(password|secret|key)\s*=\s*["\'][^"\']+["\']', 'security', 'critical'),
        'eval_usage': (r'\beval\s*\(', 'security', 'major'),
        'bare_except': (r'except\s*:', 'bug', 'minor'),
    }
    
    async def process(self, input: CodeReviewInput) -> CodeReviewOutput:
        start_time = datetime.utcnow()
        try:
            findings = []
            if input.diff_content:
                findings, stats = await self._review_diff(input.diff_content)
            
            critical = sum(1 for f in findings if f.severity == "critical")
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return CodeReviewOutput(
                request_id=input.request_id, success=True, execution_time_ms=exec_time,
                files_reviewed=1, total_findings=len(findings), critical_count=critical,
                approve=critical == 0, requires_changes=critical > 0, findings=findings,
                summary=f"Found {len(findings)} issues"
            )
        except Exception as e:
            return CodeReviewOutput(request_id=input.request_id, success=False, error=str(e))
    
    async def _review_diff(self, diff: str) -> tuple[List[CodeReviewFinding], Dict]:
        findings, stats = [], {'files': 1}
        for pattern_name, (pattern, category, severity) in self.CODE_PATTERNS.items():
            if re.search(pattern, diff):
                findings.append(CodeReviewFinding(
                    severity=severity, category=category, file_path="diff",
                    line_start=1, title=pattern_name, description=f"Found {pattern_name}"
                ))
        return findings, stats
