from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from datetime import datetime

router = APIRouter(prefix="/change-requests", tags=["governance"])

@router.get("/")
async def get_change_requests() -> Dict[str, Any]:
    """List all proposed system self-fixes and upgrades awaiting approval."""
    return {
        "success": True,
        "count": 1,
        "requests": [
            {
                "id": "CR_2026_001",
                "proposer": "QA_Guardian",
                "target": "backend/services/llm_service.py",
                "change_type": "SELF_HEAL",
                "description": "Fix retry logic in OpenAI provider; current logic fails on 429 too aggressively.",
                "diff": "@@ -412,5 +412,8 @@\n-    except RateLimitError:\n-        return None\n+    except RateLimitError:\n+        await asyncio.sleep(retry_delay)\n+        return await self.call_with_retry(prompt)\n",
                "status": "PENDING_FOUNDER",
                "timestamp": datetime.now().isoformat()
            }
        ]
    }

@router.post("/{request_id}/approve")
async def approve_change(request_id: str) -> Dict[str, Any]:
    """Founder approval for a proposed self-fix."""
    return {
        "success": True,
        "request_id": request_id,
        "action": "APPROVED",
        "message": "Change will be applied in the next maintenance cycle."
    }

@router.post("/{request_id}/reject")
async def reject_change(request_id: str, reason: str = "Incomplete analysis") -> Dict[str, Any]:
    """Founder rejection of a proposed self-fix."""
    return {
        "success": True,
        "request_id": request_id,
        "action": "REJECTED",
        "reason": reason
    }
