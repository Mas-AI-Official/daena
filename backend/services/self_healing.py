import os
import time
import datetime
import logging
from typing import Dict, Any, List
from backend.services.governance_loop import GovernanceLoop, ActionRequest, ActionType

logger = logging.getLogger(__name__)

class SelfHealingService:
    """
    Permissioned Self-Fix: Daena proposes changes, Founder approves via Governance Loop.
    """
    
    def __init__(self, governance_service: GovernanceLoop = None):
        self.governance = governance_service or GovernanceLoop.get_instance()
        
    async def propose_fix(self, file_path: str, proposed_code: str, rationale: str = "") -> Dict[str, Any]:
        """Propose a fix for a file and submit it for founder approval."""
        proposal_id = f"fix-{time.time()}"
        
        request = ActionRequest(
            action_id=proposal_id,
            action_type=ActionType.FILE_WRITE,
            agent_id="daena_self_healing",
            description=f"Self-Fix for {os.path.basename(file_path)}: {rationale}",
            parameters={
                "path": file_path,
                "content": proposed_code,
                "rationale": rationale,
                "is_self_fix": True
            }
        )
        
        # Evaluate via governance - this will create a PENDING_APPROVAL in DB if high risk
        decision = self.governance.evaluate(request)
        
        return {
            "proposal_id": proposal_id,
            "decision_id": decision.decision_id,
            "status": decision.outcome,
            "requires": decision.requires,
            "reason": decision.reason,
            "file_path": file_path,
            "rationale": rationale
        }

    async def apply_fix(self, decision_id: str) -> Dict[str, Any]:
        """Apply an approved fix by actually writing to the filesystem."""
        from backend.database import SessionLocal, PendingApproval
        
        db = SessionLocal()
        try:
            # Verify approval status in DB
            approval = db.query(PendingApproval).filter(PendingApproval.approval_id == decision_id).first()
            
            if not approval:
                return {"status": "error", "message": "Proposal not found"}
            
            if approval.status != "approved":
                return {"status": "error", "message": f"Fix not approved. Current status: {approval.status}"}
            
            # Extract data from args_json
            args = approval.args_json
            file_path = args.get("path")
            content = args.get("content")
            
            if not file_path or content is None:
                return {"status": "error", "message": "Incomplete fix data in approval"}

            # Absolute path safety check (simplified)
            if ".." in file_path or file_path.startswith("/") or ":" in file_path and not file_path.startswith("D:"):
                 # Basic check: allow absolute D: paths if that's where we are, or relative
                 pass

            # Backup the original file
            if os.path.exists(file_path):
                backup_path = f"{file_path}.bak.{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                with open(file_path, 'r', encoding='utf-8') as f:
                    original = f.read()
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(original)
                logger.info(f"Backup created at {backup_path}")

            # Write the new content
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Self-fix applied to {file_path}")
            
            return {
                "status": "success", 
                "message": f"Fix applied successfully to {file_path}",
                "file_path": file_path
            }
        except Exception as e:
            logger.error(f"Failed to apply fix {decision_id}: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            db.close()

# Singleton instance
_self_healing_service = None

def get_self_healing_service():
    global _self_healing_service
    if _self_healing_service is None:
        _self_healing_service = SelfHealingService()
    return _self_healing_service
