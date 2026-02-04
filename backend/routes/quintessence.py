
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, Any, List, Optional
from backend.services.quintessence.council import get_quintessence_council
from backend.services.quintessence.experts import EXPERT_PROFILES
from backend.services.quintessence.precedent_engine import get_precedent_engine

router = APIRouter(prefix="/api/v1/quintessence", tags=["quintessence"])

@router.post("/deliberate")
async def deliberate(payload: Dict[str, Any] = Body(...)):
    """Invoke Tier 2 Supreme Deliberation."""
    problem = payload.get("problem")
    domain = payload.get("domain", "general")
    
    if not problem:
        raise HTTPException(status_code=400, detail="Missing problem description")
        
    council = get_quintessence_council()
    result = await council.supreme_deliberation(problem, domain)
    return result

@router.get("/experts")
async def get_experts():
    """Get profiles of the 5 Quintessence experts."""
    return {"experts": EXPERT_PROFILES}

@router.get("/precedents/search")
async def search_precedents(q: str, domain: Optional[str] = None):
    """Search the precedent library."""
    engine = get_precedent_engine()
    results = engine.find_similar(q, domain)
    return {"precedents": results}

@router.get("/precedents/{id}")
async def get_precedent(id: str):
    """Retrieve a specific precedent by ID."""
    engine = get_precedent_engine()
    # For now we'll just search by ID using find_similar logic or simple DB lookup
    # Implementation simplified for MVP
    results = engine.find_similar(id)
    if results:
        return results[0]
    raise HTTPException(status_code=404, detail="Precedent not found")
