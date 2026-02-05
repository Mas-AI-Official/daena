from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import logging

from backend.services.council_service import council_service
from backend.services.auth_service import auth_service, User
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
security = HTTPBearer()
logger = logging.getLogger(__name__)

# Models
class CouncilStatus(BaseModel):
    department: str
    status: str
    active_advisors: int
    active_scouts: int
    last_round_at: Optional[datetime]
    consensus_met: bool

class DebateRequest(BaseModel):
    topic: str
    context: Optional[Dict[str, Any]] = None

class SynthesisRequest(BaseModel):
    debate_id: str
    include_scout_findings: bool = True

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    return auth_service.get_current_user(credentials)

@router.get("/")
async def list_councils():
    """List all available department councils"""
    departments = ["engineering", "product", "marketing", "sales", "finance", "hr", "operations", "legal"]
    results = []
    for dept in departments:
        name = council_service.get_department_display_name(dept)
        results.append({
            "id": dept,
            "name": name,
            "agent_count": 6,
            "status": "ready"
        })
    return results

@router.get("/{department}")
async def get_council_details(department: str):
    """Get details for a specific department council"""
    try:
        details = council_service.get_department_councilors(department)
        return details
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Council for {department} not found")

@router.get("/{department}/status")
async def get_council_status(department: str):
    """Get real-time status of a department council"""
    # In a real app, this would check live agent heartbeats
    return {
        "department": department,
        "status": "active",
        "advisors_online": 5,
        "scouts_online": 2,
        "synthesizer_online": True,
        "last_synthesis": datetime.now().isoformat(),
        "health": 0.98
    }

@router.post("/{department}/debate")
async def run_debate(department: str, request: DebateRequest, user: User = Depends(get_current_user)):
    """Initiate a council debate on a specific topic"""
    try:
        councilors = council_service.get_department_councilors(department)
        from backend.models.council import AdvisorModel
        
        advisors = []
        for adv_data in councilors["advisors"]:
            advisors.append(AdvisorModel(
                name=adv_data["name"],
                persona=adv_data["persona"],
                expertise=adv_data["expertise"]
            ))
            
        record = await council_service.run_debate(department, request.topic, advisors)
        return record
    except Exception as e:
        logger.error(f"Error running debate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{department}/synthesis")
async def run_synthesis(department: str, request: SynthesisRequest, user: User = Depends(get_current_user)):
    """Initiate synthesis based on a debate"""
    # This would normally pull the debate from a store using request.debate_id
    # For now, we'll return a mock or error if not found
    raise HTTPException(status_code=501, detail="Synthesis from ID not yet implemented. Use full pipeline instead.")

@router.get("/history")
async def get_council_history(limit: int = Query(10, ge=1)):
    """Get recent council synthesis results from knowledge base"""
    # Mock history for now
    return [
        {
            "id": f"synth-{i}",
            "department": "engineering",
            "topic": "Scaling Infrastructure for Q1",
            "outcome": "Success",
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.92
        } for i in range(limit)
    ]
