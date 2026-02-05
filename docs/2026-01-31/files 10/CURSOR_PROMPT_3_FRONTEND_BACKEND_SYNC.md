# CURSOR PROMPT 3: FRONTEND-BACKEND SYNC

You are working in the Mas-AI-Official/daena repository. Sync the frontend with real backend data so it shows actual system state instead of hardcoded demo data.

## GOAL
Replace all hardcoded frontend data with real API calls to backend endpoints. Make frontend a true real-time view of backend state.

## CURRENT PROBLEMS
- Frontend shows 48 hardcoded agents
- Frontend shows hardcoded projects
- Tool actions don't reflect real backend state
- No real-time updates when backend changes

## ACTIONS

### A) Create/Update backend/routes/agents.py:
```python
from fastapi import APIRouter
from typing import List
import asyncio

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])

@router.get("/")
async def get_all_agents():
    """Get all 48 agents with current status"""
    # TODO: Replace with database query
    agents = []
    departments = ["Engineering", "Product", "Sales", "Marketing", "Finance", "HR", "Legal", "Customer"]
    roles = ["Advisor A", "Advisor B", "Scout Internal", "Scout External", "Synthesizer", "Executor"]
    
    agent_id = 1
    for dept in departments:
        for role in roles:
            agent = {
                "id": agent_id,
                "name": f"{dept} - {role}",
                "department": dept,
                "role": role,
                "status": "active",  # Get from actual agent process
                "current_task": None,
                "last_active": datetime.now().isoformat()
            }
            agents.append(agent)
            agent_id += 1
    
    return {"agents": agents, "total": len(agents)}

@router.get("/{agent_id}")
async def get_agent(agent_id: int):
    """Get individual agent details"""
    # TODO: Query database for agent
    return {
        "id": agent_id,
        "name": f"Agent {agent_id}",
        "status": "active",
        "current_task": "Processing task...",
        "metrics": {
            "tasks_completed": 42,
            "success_rate": 0.95,
            "avg_response_time_ms": 234
        }
    }

@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: int):
    """Get real-time agent status"""
    # TODO: Query actual agent process
    return {
        "agent_id": agent_id,
        "status": "active",
        "current_task": "Waiting for input",
        "cpu_usage": 15.3,
        "memory_usage_mb": 120
    }
```

### B) Create/Update backend/routes/departments.py:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/departments", tags=["Departments"])

@router.get("/")
async def get_all_departments():
    """Get all departments"""
    departments = [
        {
            "id": 1,
            "name": "Engineering",
            "agent_count": 6,
            "status": "operational",
            "current_projects": 3
        },
        # ... repeat for all 8 departments
    ]
    return {"departments": departments}

@router.get("/{dept_id}/agents")
async def get_department_agents(dept_id: int):
    """Get all agents in a department"""
    # Filter agents by department
    return {"agents": []}  # TODO: Implement
```

### C) Create/Update backend/routes/projects.py:
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

class ProjectCreate(BaseModel):
    title: str
    description: str
    assigned_agents: List[int]
    priority: str

@router.get("/")
async def get_all_projects():
    """Get all projects"""
    # TODO: Query database
    return {"projects": [], "total": 0}

@router.post("/")
async def create_project(project: ProjectCreate):
    """Create new project"""
    # TODO: Save to database
    new_project = {
        "id": 1,
        "title": project.title,
        "description": project.description,
        "status": "not_started",
        "created_at": datetime.now().isoformat()
    }
    return new_project

@router.get("/{project_id}")
async def get_project(project_id: int):
    """Get project details"""
    # TODO: Query database
    return {"id": project_id, "title": "Project"}

@router.get("/{project_id}/tasks")
async def get_project_tasks(project_id: int):
    """Get all tasks for a project"""
    # TODO: Query database
    return {"tasks": []}
```

### D) Create/Update backend/routes/tools.py:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])

@router.get("/")
async def get_all_tools():
    """Get all available tools"""
    # TODO: Query tool registry
    tools = [
        {
            "id": "screenshot",
            "name": "Take Screenshot",
            "category": "Desktop",
            "risk_level": "LOW",
            "executors": ["founder", "daena"],
            "approval_policy": "auto"
        },
        # Add all tools
    ]
    return {"tools": tools}

@router.get("/categories")
async def get_tool_categories():
    """Get tool categories"""
    return {
        "categories": ["Desktop", "Browser", "Shell", "API", "Database"]
    }
```

### E) Create/Update backend/routes/approvals.py:
```python
from fastapi import APIRouter, Depends
from backend.services.hands_approval_queue import get_approval_queue

router = APIRouter(prefix="/api/v1/approvals", tags=["Approvals"])

@router.get("/pending")
async def get_pending_approvals():
    """Get all pending approvals"""
    queue = get_approval_queue()
    pending = await queue.get_pending()
    return {"pending_approvals": pending, "count": len(pending)}

@router.post("/{request_id}/approve")
async def approve_request(request_id: str, founder_token: str):
    """Approve a pending request"""
    queue = get_approval_queue()
    success = await queue.approve(request_id, founder_token)
    if success:
        return {"status": "approved", "request_id": request_id}
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/{request_id}/reject")
async def reject_request(request_id: str, founder_token: str, reason: str = ""):
    """Reject a pending request"""
    queue = get_approval_queue()
    success = await queue.reject(request_id, founder_token, reason)
    if success:
        return {"status": "rejected", "request_id": request_id}
    else:
        raise HTTPException(status_code=401, detail="Unauthorized")
```

### F) Update frontend/templates/command_center.html:
Replace hardcoded data with API calls:

```javascript
// OLD (hardcoded):
const agents = [
    {id: 1, name: "Engineering Advisor A", ...},
    // 47 more hardcoded agents
];

// NEW (fetch from backend):
async function loadAgents() {
    try {
        const response = await fetch('http://localhost:8000/api/v1/agents');
        const data = await response.json();
        displayAgents(data.agents);
    } catch (error) {
        console.error('Failed to load agents:', error);
        showError('Could not load agents. Is backend running?');
    }
}

async function loadProjects() {
    try {
        const response = await fetch('http://localhost:8000/api/v1/projects');
        const data = await response.json();
        displayProjects(data.projects);
    } catch (error) {
        console.error('Failed to load projects:', error);
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', () => {
    loadAgents();
    loadProjects();
    connectWebSocket();
});
```

### G) Add WebSocket support in backend/services/websocket_server.py:
```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import json

class WebSocketManager:
    """
    Manages WebSocket connections for real-time frontend updates
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"WebSocket connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, event_type: str, data: dict):
        """Broadcast event to all connected clients"""
        message = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

# Singleton
_ws_manager = WebSocketManager()

def get_ws_manager() -> WebSocketManager:
    return _ws_manager

# Add to backend/main.py:
from backend.services.websocket_server import get_ws_manager

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    manager = get_ws_manager()
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Usage: Broadcast events when things change
async def on_agent_status_change(agent_id: int, new_status: str):
    ws_manager = get_ws_manager()
    await ws_manager.broadcast("agent_status_changed", {
        "agent_id": agent_id,
        "status": new_status
    })
```

### H) Update frontend to listen to WebSocket:
```javascript
let ws = null;

function connectWebSocket() {
    ws = new WebSocket('ws://localhost:8000/ws');
    
    ws.onopen = () => {
        console.log('✓ Connected to backend WebSocket');
    };
    
    ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        handleWebSocketEvent(message);
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        console.log('WebSocket closed. Reconnecting in 5s...');
        setTimeout(connectWebSocket, 5000);
    };
}

function handleWebSocketEvent(message) {
    switch (message.type) {
        case 'agent_status_changed':
            updateAgentStatus(message.data.agent_id, message.data.status);
            break;
        case 'tool_execution_complete':
            updateToolStatus(message.data);
            break;
        case 'approval_requested':
            showApprovalNotification(message.data);
            break;
    }
}
```

## CONSTRAINTS
- Use async/await for all API calls
- Show loading spinners while fetching
- Handle errors gracefully (show error toast, don't crash)
- Update frontend every 5 seconds OR on WebSocket event (whichever is more appropriate)
- CORS must be configured correctly to allow frontend origin

## DELIVERABLE
1. All new/updated backend route files
2. Updated frontend HTML/JS files
3. WebSocket server implementation
4. Demo showing real-time updates (change something in backend → frontend updates automatically)

## TESTING CHECKLIST
- [ ] Start backend on port 8000
- [ ] Open frontend (localhost:3000 or wherever it's served)
- [ ] Frontend loads actual agents from backend (not hardcoded)
- [ ] Frontend loads actual projects from backend
- [ ] WebSocket connection established
- [ ] Change agent status in backend → Frontend updates without refresh
- [ ] Submit tool action → Frontend shows result
- [ ] Approval request appears in real-time
