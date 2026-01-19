"""
Agent Activity API - Real-time agent status and task tracking
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

class AgentStatus(str, Enum):
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    OFFLINE = "offline"

class TaskInfo(BaseModel):
    task_id: str
    description: str
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    progress: float = 0.0  # 0.0 to 1.0

class AgentActivity(BaseModel):
    agent_id: str
    agent_name: str
    department: str
    status: AgentStatus
    current_task: Optional[TaskInfo] = None
    last_activity: datetime
    metrics: Dict[str, Any] = {}

# In-memory activity store (replace with Redis/database in production)
_activity_store: Dict[str, AgentActivity] = {}

def _get_mock_activity() -> List[AgentActivity]:
    """
    Get activity from sunflower registry + governance queue.
    This pulls REAL data from the backend.
    """
    from backend.utils.sunflower_registry import sunflower_registry
    from backend.core.brain.store import brain_store
    
    activities = []
    
    # Get all agents from registry
    for agent_id, agent_data in sunflower_registry.agents.items():
        dept = agent_data.get('department', 'Unknown')
        name = agent_data.get('name', agent_id)
        
        # Check if agent has pending tasks in governance queue
        queue = brain_store.get_queue()
        agent_tasks = [p for p in queue if p.get('source_agent_id') == agent_id]
        
        if agent_tasks:
            # Agent has active proposal
            latest_task = agent_tasks[0]
            status = AgentStatus.WAITING
            task = TaskInfo(
                task_id=latest_task['id'],
                description=latest_task['reason'],
                started_at=datetime.fromisoformat(latest_task['created_at']),
                progress=0.5
            )
        else:
            # Agent is idle
            status = AgentStatus.IDLE
            task = None
        
        activity = AgentActivity(
            agent_id=agent_id,
            agent_name=name,
            department=dept,
            status=status,
            current_task=task,
            last_activity=datetime.utcnow(),
            metrics={
                "tasks_completed": agent_data.get('tasks_completed', 0),
                "success_rate": agent_data.get('success_rate', 0.95)
            }
        )
        activities.append(activity)
    
    return activities

@router.get("/activity", response_model=List[AgentActivity])
async def get_agent_activity():
    """
    Get real-time agent activity across all departments.
    
    Returns activity pulled from:
    - Sunflower registry (agent metadata)
    - Governance queue (active tasks)
    """
    try:
        return _get_mock_activity()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch agent activity: {str(e)}")

@router.get("/activity/{agent_id}", response_model=AgentActivity)
async def get_agent_activity_by_id(agent_id: str):
    """Get activity for a specific agent"""
    activities = _get_mock_activity()
    for activity in activities:
        if activity.agent_id == agent_id:
            return activity
    raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")

@router.get("/departments/{department}/activity", response_model=List[AgentActivity])
async def get_department_activity(department: str):
    """Get activity for all agents in a department"""
    activities = _get_mock_activity()
    dept_activities = [a for a in activities if a.department.lower() == department.lower()]
    if not dept_activities:
        raise HTTPException(status_code=404, detail=f"No agents found in department: {department}")
    return dept_activities
