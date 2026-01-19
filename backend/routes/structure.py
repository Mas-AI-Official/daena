"""
Organization structure verification API.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from Tools.verify_org_structure import verify_structure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/structure", tags=["structure"])


@router.get("/verify")
async def verify_org_structure() -> Dict[str, Any]:
    """
    Verify organization structure matches canonical 8×6 configuration.
    Returns pass/fail status and diffs.
    """
    try:
        results = verify_structure()
        result_data = {
            "status": "ok" if results["pass"] else "failed",
            "pass": results["pass"],
            "departments": results["departments"],
            "agents": results["agents"],
            "departments_detail": results["departments_detail"],
            "diffs": results["diffs"]
        }
        
        # Emit real-time event for frontend
        try:
            from backend.routes.events import emit_structure_updated
            emit_structure_updated(results["pass"], result_data)
        except ImportError:
            pass  # Events system not available
        
        return result_data
    except Exception as e:
        logger.error(f"Error verifying structure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

