"""
QA Reporter Agent - Publishes reports and creates issues

Produces dashboard updates, log entries, and optional GitHub issues.
"""

import logging
import json
import os
from datetime import datetime
from pathlib import Path

from backend.qa_guardian.schemas.agent_schemas import ReporterInput, ReporterOutput

logger = logging.getLogger("qa_guardian.agents.reporter")


class QAReporterAgent:
    """QA Reporter Agent - Publishes reports"""
    
    AGENT_ID = "qa_reporter_agent"
    DEPARTMENT = "qa_guardian"
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    LOG_DIR = PROJECT_ROOT / "logs"
    
    async def process(self, input: ReporterInput) -> ReporterOutput:
        start_time = datetime.utcnow()
        try:
            log_written = False
            log_file = None
            
            # Write to log file
            if input.post_to_log:
                log_file = self.LOG_DIR / "qa_guardian_reports.jsonl"
                os.makedirs(self.LOG_DIR, exist_ok=True)
                
                entry = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "report_type": input.report_type,
                    "incident_id": input.incident_id,
                    "proposal_id": input.proposal_id,
                    "title": input.title,
                    "severity": input.severity,
                    "tags": input.tags
                }
                
                with open(log_file, 'a') as f:
                    f.write(json.dumps(entry, default=str) + "\n")
                log_written = True
            
            # Generate formatted report
            report = self._format_report(input)
            report_id = f"rpt_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            return ReporterOutput(
                request_id=input.request_id, success=True,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                dashboard_posted=input.post_to_dashboard,
                log_written=log_written, log_file=str(log_file) if log_file else None,
                report_id=report_id, formatted_report=report
            )
        except Exception as e:
            logger.error(f"Reporter agent error: {e}")
            return ReporterOutput(request_id=input.request_id, success=False, error=str(e))
    
    def _format_report(self, input: ReporterInput) -> str:
        """Format report for display"""
        lines = [f"# QA Guardian Report: {input.report_type.title()}", ""]
        
        if input.title:
            lines.append(f"**{input.title}**")
        if input.severity:
            lines.append(f"Severity: {input.severity}")
        if input.incident_id:
            lines.append(f"Incident: {input.incident_id}")
        if input.content:
            lines.extend(["", input.content])
        
        return "\n".join(lines)
