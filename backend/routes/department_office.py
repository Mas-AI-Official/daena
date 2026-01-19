"""
Department Office API
Handles interactions within specific department offices
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/office", tags=["office"])
logger = logging.getLogger(__name__)

# Department Representatives (Personas)
DEPT_REPS = {
    "engineering": {
        "name": "Atlas",
        "role": "Chief Engineer",
        "icon": "fa-cog",
        "color": "#4169E1",
        "personality": "Analytical, precise, technical. Focuses on system architecture and code quality."
    },
    "product": {
        "name": "Nova",
        "role": "Product Lead",
        "icon": "fa-rocket",
        "color": "#9370DB",
        "personality": "Visionary, user-centric, strategic. Focuses on roadmap and user experience."
    },
    "sales": {
        "name": "Hunter",
        "role": "Sales Director",
        "icon": "fa-dollar-sign",
        "color": "#FF8C00",
        "personality": "Persuasive, goal-oriented, energetic. Focuses on revenue and partnerships."
    },
    "marketing": {
        "name": "Aura",
        "role": "CMO",
        "icon": "fa-chart-bar",
        "color": "#FF8C00",
        "personality": "Creative, expressive, trend-aware. Focuses on brand and outreach."
    },
    "finance": {
        "name": "Vault",
        "role": "CFO",
        "icon": "fa-chart-line",
        "color": "#00CED1",
        "personality": "Cautious, detail-oriented, fiscal. Focuses on budget and ROI."
    },
    "hr": {
        "name": "Harmony",
        "role": "People Ops",
        "icon": "fa-users",
        "color": "#E91E7F",
        "personality": "Empathetic, organized, diplomatic. Focuses on culture and talent."
    },
    "legal": {
        "name": "Justus",
        "role": "General Counsel",
        "icon": "fa-balance-scale",
        "color": "#9370DB",
        "personality": "Risk-averse, formal, precise. Focuses on compliance and contracts."
    },
    "customer": {
        "name": "Echo",
        "role": "Success Lead",
        "icon": "fa-bullseye",
        "color": "#32CD32",
        "personality": "Helpful, patient, problem-solver. Focuses on satisfaction and retention."
    }
}

# Department Display Names
DEPT_NAMES = {
    "engineering": "Engineering",
    "product": "Product",
    "sales": "Sales",
    "marketing": "Marketing",
    "finance": "Finance",
    "hr": "Human Resources",
    "legal": "Legal",
    "customer": "Customer Success"
}

class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict] = {}

class OfficeResponse(BaseModel):
    response: str
    speaker: str  # "Daena" or Rep Name
    timestamp: datetime

def get_rep_initials(name: str) -> str:
    """Get initials from rep name"""
    return "".join([w[0].upper() for w in name.split()[:2]])

@router.get("/{dept_id}/info")
async def get_office_info(dept_id: str):
    """Get information about a department office"""
    if dept_id not in DEPT_REPS:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")
    
    rep = DEPT_REPS[dept_id]
    return {
        "department_id": dept_id,
        "department_name": DEPT_NAMES.get(dept_id, dept_id.title()),
        "representative": rep,
        "rep_initials": get_rep_initials(rep["name"]),
        "status": "active",
        "active_agents": 6,
        "current_projects": 3
    }

@router.post("/{dept_id}/chat")
async def chat_in_office(dept_id: str, msg: ChatMessage):
    """Chat with department rep in the office"""
    if dept_id not in DEPT_REPS:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")
    
    rep = DEPT_REPS[dept_id]
    
    # Try to use LLM via router for intelligent responses
    try:
        from utils.ai_router import ai_router
        
        # Create context for this department
        context = {
            "department": dept_id,
            "representative": rep["name"],
            "role": rep["role"],
            "personality": rep["personality"],
            "user_message": msg.message
        }
        
        # Route through AI router (will use brain if available)
        system_prompt = f"""You are {rep['name']}, the {rep['role']} for the {dept_id} department.
Your personality: {rep['personality']}
Your responses should reflect your role and personality while being helpful and knowledgeable about your department.
Daena VP is also present in this conversation.
"""
        
        # Decide who speaks
        if "daena" in msg.message.lower() or "vp" in msg.message.lower():
            speaker = "Daena VP"
            response = await ai_router.chat(msg.message, context={"role": "vp", "with_rep": rep["name"]})
        else:
            speaker = rep["name"]
            response = await ai_router.chat(msg.message, context=context, system_prompt=system_prompt)
        
        return {
            "response": response,
            "speaker": speaker,
            "timestamp": datetime.now()
        }
    except Exception as e:
        # Fallback if router not available
        logger.warning(f"AI router not available: {e}, using fallback")
        speaker = rep["name"]
        response_text = f"[{rep['role']}] I've received your request regarding '{msg.message}'. My team is on it."
        
        if "daena" in msg.message.lower() or "vp" in msg.message.lower():
            speaker = "Daena VP"
            response_text = f"I'm here with {rep['name']}. We'll handle this together."
            
        return {
            "response": response_text,
            "speaker": speaker,
            "timestamp": datetime.now()
        }

@router.get("/{dept_id}/stats")
async def get_office_stats(dept_id: str):
    """Get stats for a department"""
    if dept_id not in DEPT_REPS:
        raise HTTPException(status_code=404, detail=f"Department '{dept_id}' not found")
    
    return {
        "department_id": dept_id,
        "agents": 6,
        "efficiency": 94,
        "active_tasks": 12,
        "completed_today": 8,
        "projects": 3
    }
