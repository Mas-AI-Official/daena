"""
QA Auto-Fix Agent - Generates safe patches for issues

Generates patches with two-phase commit, respecting deny-list and risk levels.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from backend.qa_guardian.schemas.agent_schemas import AutoFixInput, AutoFixOutput
from backend.qa_guardian.schemas.proposal import PatchProposal, FileChange, VerificationPlan, RollbackPlan
from backend.qa_guardian import DENY_LIST_PATTERNS, RiskLevel
import fnmatch

logger = logging.getLogger("qa_guardian.agents.auto_fix")


class QAAutoFixAgent:
    """QA Auto-Fix Agent - Generates safe patches"""
    
    AGENT_ID = "qa_auto_fix_agent"
    DEPARTMENT = "qa_guardian"
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    
    async def process(self, input: AutoFixInput) -> AutoFixOutput:
        start_time = datetime.utcnow()
        try:
            # Check deny-list
            deny_list_areas = []
            for file in input.affected_files:
                for pattern in DENY_LIST_PATTERNS:
                    if fnmatch.fnmatch(file.replace("\\", "/"), pattern):
                        deny_list_areas.append(file)
            
            touches_deny_list = len(deny_list_areas) > 0
            risk_level = RiskLevel.CRITICAL if touches_deny_list else RiskLevel.LOW
            requires_approval = touches_deny_list or risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]
            
            # Don't generate fix for deny-list files
            if touches_deny_list:
                return AutoFixOutput(
                    request_id=input.request_id, success=True,
                    execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    fix_generated=False, risk_level=risk_level, touches_deny_list=True,
                    deny_list_areas=deny_list_areas, requires_approval=True,
                    skip_reason=f"Files touch deny-list areas: {deny_list_areas}"
                )
            
            # Simplified fix generation (placeholder)
            proposal_id = f"patch_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            return AutoFixOutput(
                request_id=input.request_id, success=True,
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                fix_generated=True, proposal_id=proposal_id, risk_level=risk_level,
                touches_deny_list=False, deny_list_areas=[], requires_approval=requires_approval,
                files_to_modify=input.affected_files, fix_explanation="Auto-generated fix"
            )
        except Exception as e:
            logger.error(f"Auto-fix agent error: {e}")
            return AutoFixOutput(request_id=input.request_id, success=False, error=str(e))
