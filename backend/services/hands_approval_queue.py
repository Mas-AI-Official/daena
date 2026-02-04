from typing import List, Dict, Any, Optional
from backend.services.tool_request_store import list_pending, update_status, get_request
from backend.services.tool_broker import execute_approved_request
import logging

logger = logging.getLogger(__name__)

class HandsApprovalQueue:
    """
    Facade for managing tool execution approvals.
    Uses tool_request_store for persistence and tool_broker for execution.
    """
    
    @staticmethod
    def get_pending_approvals() -> List[Dict[str, Any]]:
        """Get all actions waiting for approval."""
        return list_pending()
    
    @staticmethod
    async def approve_action(request_id: str) -> Dict[str, Any]:
        """Approve and execute an action."""
        logger.info(f"Approving request {request_id}")
        # execute_approved_request handles the status update internally
        return await execute_approved_request(request_id)

    @staticmethod
    def reject_action(request_id: str) -> Dict[str, Any]:
        """Reject an action."""
        logger.info(f"Rejecting request {request_id}")
        success = update_status(request_id, "rejected", {"message": "Rejected by founder"})
        if success:
            return {"success": True, "status": "rejected"}
        return {"success": False, "error": "Request not found"}

hands_approval_queue = HandsApprovalQueue()
