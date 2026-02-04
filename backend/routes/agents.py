"""
Agents API - Database-backed agent management
Replaced in-memory sunflower_registry with SQLite persistence
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentCreate(BaseModel):
    """Create a new agent"""
    name: str
    department_id: str
    role: str = "advisor_a"
    type: Optional[str] = None
    description: Optional[str] = None


class AgentUpdate(BaseModel):
    """Update an existing agent"""
    name: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class AgentChatRequest(BaseModel):
    message: str
    context: Dict[str, Any] = {}


def get_db():
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
async def get_agents(
    limit: int = Query(100, description="Maximum number of agents to return"),
    offset: int = Query(0, description="Number of agents to skip"),
    department_id: Optional[str] = Query(None, description="Filter by department slug")
) -> Dict[str, Any]:
    """Get all agents from database"""
    from backend.database import SessionLocal, Agent, Department
    from sqlalchemy import inspect
    
    db = SessionLocal()
    try:
        # Check if voice_id column exists in database (graceful handling)
        inspector = inspect(db.bind)
        columns = [col['name'] for col in inspector.get_columns('agents')]
        has_voice_id = 'voice_id' in columns
        
        # Build query - only select columns that exist
        if has_voice_id:
            query = db.query(Agent)
        else:
            # Query without voice_id if column doesn't exist
            query = db.query(
                Agent.id, Agent.name, Agent.role, Agent.type, Agent.department,
                Agent.status, Agent.is_active, Agent.performance_score,
                Agent.cell_id, Agent.created_at, Agent.updated_at
            )
        
        # Filter by department if specified
        if department_id:
            query = query.filter(Agent.department == department_id)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        if has_voice_id:
            agents = query.offset(offset).limit(limit).all()
        else:
            # Handle tuple results when selecting specific columns
            results = query.offset(offset).limit(limit).all()
            # Convert tuples to dict-like objects
            agents = []
            for row in results:
                class AgentProxy:
                    def __init__(self, row):
                        self.id = row[0]
                        self.name = row[1]
                        self.role = row[2]
                        self.type = row[3]
                        self.department = row[4]
                        self.status = row[5]
                        self.is_active = row[6]
                        self.performance_score = row[7]
                        self.cell_id = row[8]
                        self.created_at = row[9]
                        self.updated_at = row[10]
                agents.append(AgentProxy(row))
        
        # Format response
        agent_list = []
        for agent in agents:
            agent_list.append({
                "id": agent.cell_id or str(agent.id),
                "name": agent.name,
                "role": agent.role,
                "type": agent.type,
                "department_id": agent.department,
                "status": agent.status,
                "is_active": agent.is_active,
                "efficiency": f"{agent.performance_score:.2f}" if agent.performance_score else "95.00",
                "tasks": 12,  # TODO: Get from Task table
                "uptime": "2h",  # TODO: Calculate from last_seen
                "created_at": agent.created_at.isoformat() if agent.created_at else None
            })
        
        return {
            "success": True,
            "agents": agent_list,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "returned_count": len(agent_list)
        }
    except Exception as e:
        logger.error(f"Failed to get agents: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> Dict[str, Any]:
    """Get a specific agent by ID or cell_id"""
    from backend.database import SessionLocal, Agent
    
    db = SessionLocal()
    try:
        # Try to find by cell_id first
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        
        # If not found, try by numeric ID
        if not agent:
            try:
                agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
            except ValueError:
                pass
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        return {
            "success": True,
            "agent": {
                "id": agent.cell_id or str(agent.id),
                "db_id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "type": agent.type,
                "department_id": agent.department,
                "status": agent.status,
                "is_active": agent.is_active,
                "capabilities": agent.capabilities,
                "description": agent.description,
                "performance_score": agent.performance_score,
                "efficiency": f"{agent.performance_score:.2f}" if agent.performance_score else "95.00",
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/")
async def create_agent(agent_data: AgentCreate) -> Dict[str, Any]:
    """Create a new agent"""
    from backend.database import SessionLocal, Agent, Department
    from backend.services.event_bus import event_bus
    import uuid
    
    db = SessionLocal()
    try:
        # Verify department exists
        dept = db.query(Department).filter(Department.slug == agent_data.department_id).first()
        if not dept:
            raise HTTPException(status_code=400, detail=f"Department not found: {agent_data.department_id}")
        
        # Generate cell_id
        cell_id = f"agent_{agent_data.department_id}_{agent_data.role}_{uuid.uuid4().hex[:6]}"
        
        # Get next sunflower index
        max_index = db.query(Agent).order_by(Agent.sunflower_index.desc()).first()
        next_index = (max_index.sunflower_index + 1) if max_index and max_index.sunflower_index else 56
        
        # Create agent
        agent = Agent(
            name=agent_data.name,
            department=agent_data.department_id,
            department_id=dept.id,
            role=agent_data.role,
            type=agent_data.type or agent_data.role.replace("_", " ").title(),
            description=agent_data.description,
            status="active",
            is_active=True,
            sunflower_index=next_index,
            cell_id=cell_id,
            performance_score=95.0
        )
        
        db.add(agent)
        db.commit()
        db.refresh(agent)
        
        # Publish event via WebSocket + EventLog
        try:
            from backend.core.websocket_manager import websocket_manager
            await websocket_manager.publish_event(
                event_type="agent.created",
                entity_type="agent",
                entity_id=cell_id,
                payload={
                    "id": cell_id,
                    "name": agent.name,
                    "department_id": agent_data.department_id,
                    "role": agent.role
                },
                created_by="system"
            )
        except Exception as e:
            logger.warning(f"Could not publish agent.created event: {e}")
        
        return {
            "success": True,
            "agent": {
                "id": cell_id,
                "db_id": agent.id,
                "name": agent.name,
                "department_id": agent_data.department_id,
                "role": agent.role
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{agent_id}/reset-to-default")
async def reset_agent_to_default(agent_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Reset agent to default settings (role, status, etc.)"""
    from backend.database import Agent
    
    # Try to find by cell_id first
    agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
    
    # If not found, try by numeric ID
    if not agent:
        try:
            agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
        except ValueError:
            pass
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    
    # Get default role based on department (6 roles per dept)
    default_roles = ["advisor_a", "advisor_b", "scout_internal", "scout_external", "synth", "executor"]
    agent_index = agent.sunflower_index % 6 if agent.sunflower_index else 0
    default_role = default_roles[agent_index] if agent_index < len(default_roles) else "advisor_a"
    
    # Reset to defaults
    agent.role = default_role
    agent.status = "active"
    agent.is_active = True
    agent.performance_score = 95.0
    
    db.commit()
    db.refresh(agent)
    
    # Emit WebSocket event
    try:
        from backend.core.websocket_manager import websocket_manager
        websocket_manager.emit_event("agent.reset", {
            "agent_id": agent_id,
            "role": default_role
        })
    except Exception as e:
        logger.warning(f"Could not emit reset event: {e}")
    
    return {
        "success": True,
        "message": f"Agent '{agent.name}' reset to default settings",
        "agent": {
            "id": agent.cell_id or str(agent.id),
            "name": agent.name,
            "role": agent.role,
            "status": agent.status,
            "is_active": agent.is_active
        }
    }

@router.patch("/{agent_id}")
async def update_agent(
    agent_id: str, 
    update_data: AgentUpdate, 
    db: Session = Depends(get_db),
    auto_backup: bool = True
) -> Dict[str, Any]:
    """Update an existing agent with optional auto-backup"""
    from backend.database import SessionLocal, Agent
    from backend.services.event_bus import event_bus
    from backend.services.backup_rollback import backup_service
    
    try:
        # Auto-backup before change if enabled
        if auto_backup:
            try:
                backup_service.auto_backup_before_change(
                    change_type="agent_update",
                    change_data={"agent_id": agent_id, "changes": update_data.dict(exclude_unset=True)}
                )
            except Exception as backup_error:
                logger.warning(f"Could not create backup before agent update: {backup_error}")
        
        # Find agent
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
            try:
                agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
            except ValueError:
                pass
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        # Update fields
        if update_data.name:
            agent.name = update_data.name
        if update_data.status:
            agent.status = update_data.status
        if update_data.role:
            agent.role = update_data.role
        if update_data.is_active is not None:
            agent.is_active = update_data.is_active
        
        agent.updated_at = datetime.utcnow()
        db.commit()
        
        # Publish event via WebSocket + EventLog
        try:
            from backend.core.websocket_manager import websocket_manager
            await websocket_manager.publish_event(
                event_type="agent.updated",
                entity_type="agent",
                entity_id=agent.cell_id,
                payload={
                    "id": agent.cell_id,
                    "name": agent.name,
                    "status": agent.status,
                    "department_id": agent.department
                },
                created_by="system"
            )
        except Exception as e:
            logger.warning(f"Could not publish agent.updated event: {e}")
        
        return {
            "success": True,
            "agent": {
                "id": agent.cell_id,
                "name": agent.name,
                "status": agent.status
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str) -> Dict[str, Any]:
    """Delete an agent"""
    from backend.database import SessionLocal, Agent
    from backend.services.event_bus import event_bus
    
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
            try:
                agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
            except ValueError:
                pass
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        cell_id = agent.cell_id
        name = agent.name
        
        db.delete(agent)
        db.commit()
        
        # Publish event
        try:
            await event_bus.publish_agent_event("agent.deleted", cell_id, {
                "id": cell_id,
                "name": name
            })
        except Exception as e:
            logger.warning(f"Could not publish agent.deleted event: {e}")
        
        return {"success": True, "message": f"Agent {name} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/department/{department_id}")
async def get_agents_by_department(department_id: str) -> Dict[str, Any]:
    """Get all agents for a specific department"""
    return await get_agents(department_id=department_id)


@router.post("/{agent_id}/chat")
async def chat_with_agent(agent_id: str, request: AgentChatRequest) -> Dict[str, Any]:
    """Chat with a specific agent - NOW DB-BACKED with session persistence"""
    from backend.database import SessionLocal, Agent, get_db
    from backend.services.agent_brain_router import agent_brain_router
    from backend.services.chat_service import chat_service
    
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        # Get or create chat session in DB
        session_context = request.context or {}
        session_context.update({
            "agent_id": agent_id,
            "agent_name": agent.name,
            "department_id": agent.department,
            "department_name": agent.department
        })
        
        session = chat_service.get_or_create_session(
            db=db,
            session_id=session_context.get("session_id"),
            title=f"Chat with {agent.name}",
            category="agents",
            scope_type="agent",
            scope_id=agent_id
        )
        
        # Add user message to DB
        chat_service.add_message(
            db=db,
            session_id=session.session_id,
            role="user",
            content=request.message
        )
        
        # --- NEW: CHECK FOR TOOL COMMANDS ---
        # Agents can now use the same tools as Daena
        tool_result = None
        try:
            from backend.routes.daena import detect_and_execute_tool, format_tool_result
            tool_result = await detect_and_execute_tool(request.message)
        except Exception as e:
            logger.warning(f"Tool detection failed for agent: {e}")
        
        if tool_result:
            # Tool was executed - format and return result
            response_text = format_tool_result(tool_result)
            brain_model = "tool_execution"
            
            # Log learning from tool usage
            try:
                from backend.services.learning_service import learning_service
                learning_service.log_tool_learning(
                    learned_by=agent_id,
                    tool_name=tool_result.get("tool", "unknown"),
                    action=tool_result.get("action", "execute"),
                    args={"message": request.message},
                    result=tool_result
                )
            except Exception as e:
                logger.warning(f"Failed to log agent learning: {e}")
        else:
            # --- END TOOL CHECK ---
            
            # Check Ollama availability
            ollama_available = False
            try:
                import httpx
                async with httpx.AsyncClient(timeout=2.0) as client:
                    response = await client.get("http://127.0.0.1:11434/api/tags")
                    if response.status_code == 200:
                        ollama_available = True
            except:
                pass
            
            # Invoke brain with agent context
            if ollama_available:
                try:
                    result = await agent_brain_router.invoke_brain(
                        agent_cell_id=agent.cell_id,
                        department=agent.department,
                        role=agent.role,
                        user_message=request.message,
                        session_context=session_context
                    )
                    response_text = result.get("response", "Unable to generate response")
                    brain_model = result.get("brain_model", "qwen2.5:7b-instruct")
                except Exception as e:
                    logger.warning(f"Brain invocation failed: {e}")
                    response_text = f"I'm {agent.name}. I'm experiencing some technical difficulties. Please try again in a moment."
                    brain_model = "offline"
            else:
                # Deterministic offline response
                response_text = f"Hello! I'm {agent.name}, {agent.role} in {agent.department}. I'm currently operating in offline mode (brain connection unavailable). Your message has been received. Please start Ollama to enable full AI capabilities."
                brain_model = "offline"
        
        # Add agent response to DB
        chat_service.add_message(
            db=db,
            session_id=session.session_id,
            role="assistant",
            content=response_text,
            model=brain_model
        )
        
        # Emit WebSocket events
        try:
            from backend.core.websocket_manager import emit_chat_message
            await emit_chat_message(
                session_id=session.session_id,
                sender="user",
                content=request.message,
                metadata={"type": "agent_chat", "agent_id": agent_id}
            )
            await emit_chat_message(
                session_id=session.session_id,
                sender="assistant",
                content=response_text,
                metadata={"type": "agent_chat", "agent_id": agent_id, "agent_name": agent.name}
            )
        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event: {e}")
        
        return {
            "success": True,
            "session_id": session.session_id,
            "response": response_text,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "department": agent.department,
            "brain_model": brain_model,
            "brain_available": ollama_available,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat with agent failed: {e}")
        return {
            "success": False,
            "response": f"I'm {agent.name if agent else 'an agent'}. I'm currently having trouble connecting to my brain. Please try again.",
            "agent_id": agent_id,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
    finally:
        db.close()


@router.get("/{agent_id}/brain/status")
async def get_agent_brain_status(agent_id: str) -> Dict[str, Any]:
    """Get agent's brain connection status"""
    from backend.database import SessionLocal, Agent
    from backend.services.agent_brain_router import agent_brain_router
    
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        connection_status = agent_brain_router.get_connection_status(agent_id)
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "department": agent.department,
            "brain_connection": connection_status,
            "capabilities": agent.capabilities
        }
    finally:
        db.close()


@router.get("/brain/connections")
async def get_all_brain_connections() -> Dict[str, Any]:
    """Get all agent brain connections"""
    from backend.services.agent_brain_router import agent_brain_router
    
    return {
        "success": True,
        **agent_brain_router.get_all_connections()
    }


@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str) -> Dict[str, Any]:
    """Get real-time agent status"""
    from backend.database import SessionLocal, Agent, Task
    
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
             # Try ID
             try:
                agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
             except ValueError:
                 pass
        
        if not agent:
             raise HTTPException(status_code=404, detail="Agent not found")

        # Get active task
        active_task = db.query(Task).filter(
            Task.assigned_agent_id == agent_id,
            Task.status.in_(["running", "in_progress"])
        ).first()

        return {
            "success": True,
            "agent_id": agent_id,
            "status": agent.status,
            "current_task": active_task.title if active_task else "Idle",
            "uptime": "2h", # Placeholder or calc from last_restart
            "last_seen": datetime.utcnow().isoformat()
        }
    finally:
        db.close()


@router.get("/hidden")
async def get_hidden_departments() -> Dict[str, Any]:
    """Get hidden departments (Founder access only)"""
    from backend.services.db_seeder import get_hidden_departments
    
    return {
        "success": True,
        "hidden_departments": get_hidden_departments()
    }


# Agent tasks now use DB-backed Task model (see database.py)
# Removed: _agent_chat_history: Dict[str, list] = {}
# Removed: _agent_tasks: Dict[str, list] = {}


@router.get("/{agent_id}/tasks")
async def get_agent_tasks(agent_id: str) -> Dict[str, Any]:
    """Get tasks assigned to an agent - DB-BACKED"""
    from backend.database import SessionLocal, Task
    
    db = SessionLocal()
    try:
        # Query tasks for this agent
        tasks = db.query(Task).filter(
            Task.assigned_agent_id == agent_id
        ).order_by(Task.created_at.desc()).limit(50).all()
        
        task_list = []
        for t in tasks:
            task_list.append({
                "id": t.task_id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "status_text": _get_task_status_text(t),
                "priority": t.priority,
                "created_at": t.created_at.isoformat() if t.created_at else None
            })
        
        # If no tasks exist, return empty list (no fake data)
        return {
            "success": True,
            "agent_id": agent_id,
            "tasks": task_list,
            "count": len(task_list)
        }
    finally:
        db.close()


def _get_task_status_text(task) -> str:
    """Generate human-readable status text for a task"""
    from datetime import datetime, timedelta
    
    if task.status == "completed":
        if task.updated_at:
            delta = datetime.utcnow() - task.updated_at
            if delta < timedelta(hours=1):
                return f"Completed {int(delta.total_seconds() / 60)} min ago"
            elif delta < timedelta(days=1):
                return f"Completed {int(delta.total_seconds() / 3600)} hours ago"
            else:
                return f"Completed {delta.days} days ago"
        return "Completed"
    elif task.status == "running" or task.status == "in_progress":
        return f"In progress - {int(task.progress * 100)}%"
    elif task.status == "pending":
        return "Queued"
    elif task.status == "failed":
        return "Failed"
    return task.status.replace("_", " ").title()


@router.post("/{agent_id}/tasks")
async def create_agent_task(agent_id: str, task_data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Assign a new task to an agent - DB-BACKED"""
    from backend.database import SessionLocal, Task
    import uuid
    
    db = SessionLocal()
    try:
        task_id = f"t{uuid.uuid4().hex[:8]}"
        
        task = Task(
            task_id=task_id,
            title=task_data.get("title", "Untitled Task"),
            description=task_data.get("description", ""),
            priority=task_data.get("priority", "medium"),
            status="pending",
            owner_type="agent",
            owner_id=agent_id,
            assigned_agent_id=agent_id
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Emit WebSocket event
        try:
            from backend.services.event_bus import event_bus
            await event_bus.publish_event("task.created", "task", task_id, {
                "task_id": task_id,
                "agent_id": agent_id,
                "title": task.title
            })
        except Exception as e:
            logger.warning(f"Could not emit task.created event: {e}")
        
        return {
            "success": True,
            "task": {
                "id": task_id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority,
                "status": task.status,
                "status_text": "Queued",
                "created_at": task.created_at.isoformat() if task.created_at else None
            },
            "message": f"Task assigned to agent {agent_id}"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{agent_id}/chat/history")
async def save_chat_history(agent_id: str, history_data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Save chat message to agent's history"""
    from datetime import datetime
    
    if agent_id not in _agent_chat_history:
        _agent_chat_history[agent_id] = []
    
    entry = {
        "user_message": history_data.get("user_message"),
        "agent_response": history_data.get("agent_response"),
        "department_id": history_data.get("department_id"),
        "timestamp": history_data.get("timestamp", datetime.now().isoformat())
    }
    
    _agent_chat_history[agent_id].append(entry)
    
    # Keep only last 100 messages per agent
    if len(_agent_chat_history[agent_id]) > 100:
        _agent_chat_history[agent_id] = _agent_chat_history[agent_id][-100:]
    
    return {
        "success": True,
        "message": "Chat history saved",
        "total_messages": len(_agent_chat_history[agent_id])
    }


@router.get("/{agent_id}/chat/history")
async def get_chat_history(
    agent_id: str, 
    limit: int = Query(50, description="Number of messages to return")
) -> Dict[str, Any]:
    """Get agent's chat history"""
    history = _agent_chat_history.get(agent_id, [])
    
    return {
        "success": True,
        "agent_id": agent_id,
        "messages": history[-limit:],
        "total": len(history)
    }


@router.get("/{agent_id}/performance")
async def get_agent_performance(agent_id: str) -> Dict[str, Any]:
    """Get agent performance metrics"""
    from backend.database import SessionLocal, Agent
    
    db = SessionLocal()
    try:
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
            try:
                agent = db.query(Agent).filter(Agent.id == int(agent_id)).first()
            except ValueError:
                pass
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        # Calculate metrics
        tasks_count = len(_agent_tasks.get(agent_id, []))
        completed_tasks = len([t for t in _agent_tasks.get(agent_id, []) if t.get("status") == "completed"])
        
        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "efficiency": f"{agent.performance_score:.2f}" if agent.performance_score else "95.00",
            "tasks_completed": completed_tasks,
            "tasks_total": tasks_count,
            "avg_response_time": "1.2s",
            "uptime": "99.9%",
            "status": agent.status or "active"
        }
    finally:
        db.close()

