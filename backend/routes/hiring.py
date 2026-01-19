"""
Human Hiring Management API
Manages job positions, candidates, and interviews
"""
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import uuid

router = APIRouter(prefix="/api/v1/hiring", tags=["hiring"])
logger = logging.getLogger(__name__)

# In-memory storage (replace with database in production)
_positions: Dict[str, Dict[str, Any]] = {}
_candidates: Dict[str, Dict[str, Any]] = {}
_interviews: Dict[str, Dict[str, Any]] = {}

class PositionCreate(BaseModel):
    title: str
    department: str
    description: str
    requirements: Optional[List[str]] = None
    salary_range: Optional[str] = None

class CandidateCreate(BaseModel):
    name: str
    email: str
    position_id: str
    resume_url: Optional[str] = None
    cover_letter: Optional[str] = None

class InterviewCreate(BaseModel):
    candidate_id: str
    position_id: str
    scheduled_at: Optional[str] = None
    interviewer: Optional[str] = None
    notes: Optional[str] = None

@router.get("/positions/")
async def get_positions() -> Dict[str, Any]:
    """Get all open positions."""
    positions = list(_positions.values())
    return {
        "positions": positions,
        "total": len(positions)
    }

@router.get("/positions/{position_id}")
async def get_position(position_id: str) -> Dict[str, Any]:
    """Get specific position details."""
    if position_id not in _positions:
        raise HTTPException(status_code=404, detail="Position not found")
    
    position = _positions[position_id]
    # Add candidate count
    position["candidates_count"] = len([
        c for c in _candidates.values() 
        if c.get("position_id") == position_id
    ])
    
    return position

@router.post("/positions/")
async def create_position(position: PositionCreate) -> Dict[str, Any]:
    """Create a new job position."""
    position_id = f"pos_{uuid.uuid4().hex[:8]}"
    
    position_data = {
        "id": position_id,
        "title": position.title,
        "department": position.department,
        "description": position.description,
        "requirements": position.requirements or [],
        "salary_range": position.salary_range,
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "candidates_count": 0
    }
    
    _positions[position_id] = position_data
    logger.info(f"Position created: {position_id} - {position.title}")
    
    return position_data

@router.put("/positions/{position_id}")
async def update_position(
    position_id: str,
    title: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    status: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """Update a position."""
    if position_id not in _positions:
        raise HTTPException(status_code=404, detail="Position not found")
    
    position = _positions[position_id]
    
    if title:
        position["title"] = title
    if description:
        position["description"] = description
    if status:
        position["status"] = status
    
    position["updated_at"] = datetime.now().isoformat()
    
    return position

@router.delete("/positions/{position_id}")
async def delete_position(position_id: str) -> Dict[str, Any]:
    """Delete a position."""
    if position_id not in _positions:
        raise HTTPException(status_code=404, detail="Position not found")
    
    del _positions[position_id]
    
    return {"status": "success", "message": f"Position {position_id} deleted"}

@router.get("/candidates/")
async def get_candidates(
    position_id: Optional[str] = Query(None, description="Filter by position ID")
) -> Dict[str, Any]:
    """Get all candidates."""
    candidates = list(_candidates.values())
    
    if position_id:
        candidates = [c for c in candidates if c.get("position_id") == position_id]
    
    return {
        "candidates": candidates,
        "total": len(candidates)
    }

@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str) -> Dict[str, Any]:
    """Get specific candidate details."""
    if candidate_id not in _candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate = _candidates[candidate_id]
    
    # Add position info
    if candidate.get("position_id"):
        position = _positions.get(candidate["position_id"])
        if position:
            candidate["position_title"] = position["title"]
    
    # Add interview info
    candidate["interviews"] = [
        i for i in _interviews.values() 
        if i.get("candidate_id") == candidate_id
    ]
    
    return candidate

@router.post("/candidates/")
async def create_candidate(candidate: CandidateCreate) -> Dict[str, Any]:
    """Create a new candidate."""
    if candidate.position_id not in _positions:
        raise HTTPException(status_code=404, detail="Position not found")
    
    candidate_id = f"cand_{uuid.uuid4().hex[:8]}"
    
    candidate_data = {
        "id": candidate_id,
        "name": candidate.name,
        "email": candidate.email,
        "position_id": candidate.position_id,
        "resume_url": candidate.resume_url,
        "cover_letter": candidate.cover_letter,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    
    _candidates[candidate_id] = candidate_data
    
    # Update position candidate count
    position = _positions[candidate.position_id]
    position["candidates_count"] = len([
        c for c in _candidates.values() 
        if c.get("position_id") == candidate.position_id
    ])
    
    logger.info(f"Candidate created: {candidate_id} - {candidate.name}")
    
    return candidate_data

@router.put("/candidates/{candidate_id}")
async def update_candidate(
    candidate_id: str,
    status: Optional[str] = Body(None),
    notes: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """Update candidate status."""
    if candidate_id not in _candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate = _candidates[candidate_id]
    
    if status:
        candidate["status"] = status
    if notes:
        candidate["notes"] = notes
    
    candidate["updated_at"] = datetime.now().isoformat()
    
    return candidate

@router.get("/interviews/")
async def get_interviews(
    candidate_id: Optional[str] = Query(None),
    position_id: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Get all interviews."""
    interviews = list(_interviews.values())
    
    if candidate_id:
        interviews = [i for i in interviews if i.get("candidate_id") == candidate_id]
    if position_id:
        interviews = [i for i in interviews if i.get("position_id") == position_id]
    
    return {
        "interviews": interviews,
        "total": len(interviews)
    }

@router.get("/interviews/{interview_id}")
async def get_interview(interview_id: str) -> Dict[str, Any]:
    """Get specific interview details."""
    if interview_id not in _interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview = _interviews[interview_id]
    
    # Add candidate info
    if interview.get("candidate_id"):
        candidate = _candidates.get(interview["candidate_id"])
        if candidate:
            interview["candidate_name"] = candidate["name"]
            interview["candidate_email"] = candidate["email"]
    
    # Add position info
    if interview.get("position_id"):
        position = _positions.get(interview["position_id"])
        if position:
            interview["position_title"] = position["title"]
    
    return interview

@router.post("/interviews/")
async def create_interview(interview: InterviewCreate) -> Dict[str, Any]:
    """Schedule a new interview."""
    if interview.candidate_id not in _candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if interview.position_id not in _positions:
        raise HTTPException(status_code=404, detail="Position not found")
    
    interview_id = f"int_{uuid.uuid4().hex[:8]}"
    
    interview_data = {
        "id": interview_id,
        "candidate_id": interview.candidate_id,
        "position_id": interview.position_id,
        "scheduled_at": interview.scheduled_at or (datetime.now() + timedelta(days=7)).isoformat(),
        "interviewer": interview.interviewer,
        "notes": interview.notes,
        "status": "scheduled",
        "created_at": datetime.now().isoformat()
    }
    
    _interviews[interview_id] = interview_data
    logger.info(f"Interview scheduled: {interview_id}")
    
    return interview_data

@router.put("/interviews/{interview_id}")
async def update_interview(
    interview_id: str,
    scheduled_at: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    notes: Optional[str] = Body(None)
) -> Dict[str, Any]:
    """Update interview details."""
    if interview_id not in _interviews:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview = _interviews[interview_id]
    
    if scheduled_at:
        interview["scheduled_at"] = scheduled_at
    if status:
        interview["status"] = status
    if notes:
        interview["notes"] = notes
    
    interview["updated_at"] = datetime.now().isoformat()
    
    return interview

