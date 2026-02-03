from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Any, Optional
import os
from pathlib import Path
from datetime import datetime
import uuid

from pydantic import BaseModel
from fastapi import Body
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/departments", tags=["departments"])

# Phase E: Group chat models
class ChatMessageRequest(BaseModel):
    message: str
    agent_id: str = None  # Optional: if provided, direct agent response
    context: dict = {}

class ChatMessageResponse(BaseModel):
    success: bool
    response: str
    agent_name: str = None
    agent_role: str = None
    synthesized_from: int = 0  # Number of agents consulted
    timestamp: str
    session_id: Optional[str] = None  # CRITICAL: Always return session_id for persistence

# Get templates directory
project_root = Path(__file__).parent.parent.parent
templates_dir = project_root / "frontend" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

@router.get("/")
async def get_departments(
    request: Request,
    limit: int = Query(100, description="Maximum number of departments to return"),
    offset: int = Query(0, description="Number of departments to skip"),
    include_agents: bool = Query(False, description="Include agent details"),
    include_hidden: bool = Query(False, description="Include hidden departments (Masoud only)")
) -> Dict[str, Any]:
    """Get all departments with optional agent details."""
    try:
        # Import sunflower registry
        from backend.utils.sunflower_registry import sunflower_registry
        
        # Hidden departments (not shown in frontend, Masoud-only)
        hidden_departments = ["reverse_attack_ai"]
        
        # Check if user is authorized to see hidden departments
        user_id = request.headers.get("X-User-ID", "").lower()
        is_masoud = user_id in ["masoud", "masoud.masoori", "masoud.masoori@mas-ai.co"]
        
        # Get departments from registry
        departments = []
        for dept_id, dept_data in sunflower_registry.departments.items():
            # Skip hidden departments unless explicitly requested and authorized
            if dept_id in hidden_departments and not (include_hidden and is_masoud):
                continue
            dept_info = {
                "id": dept_id,
                "name": dept_data["name"],
                "description": dept_data["description"],
                "color": dept_data["color"],
                "sunflower_index": dept_data["sunflower_index"],
                "cell_id": dept_data["cell_id"],
                "coordinates": dept_data["coordinates"],
                "agents_count": len(dept_data["agents"]),
            }
            
            if include_agents:
                dept_info["agents"] = []
                for agent_id in dept_data["agents"]:
                    agent_data = sunflower_registry.agents.get(agent_id)
                    if agent_data:
                        dept_info["agents"].append({
                            "id": agent_id,
                            "name": agent_data["name"],
                            "role": agent_data["role"],
                            "sunflower_index": agent_data["sunflower_index"],
                            "cell_id": agent_data["cell_id"],
                            "coordinates": agent_data["coordinates"]
                        })
            
            departments.append(dept_info)
        
        # Apply pagination
        total_count = len(departments)
        departments = departments[offset:offset + limit]
        
        return {
            "success": True,
            "departments": departments,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "returned_count": len(departments),
            "pagination": {
                "has_next": offset + limit < total_count,
                "has_prev": offset > 0,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "prev_offset": max(0, offset - limit) if offset > 0 else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load departments: {str(e)}")

@router.get("/{department_id}")
async def get_department(department_id: str, include_agents: bool = Query(True)) -> Dict[str, Any]:
    """Get specific department details."""
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        
        dept_data = sunflower_registry.get_department_by_id(department_id)
        if not dept_data:
            raise HTTPException(status_code=404, detail="Department not found")
        
        dept_info = {
            "id": department_id,
            "name": dept_data["name"],
            "description": dept_data["description"],
            "color": dept_data["color"],
            "sunflower_index": dept_data["sunflower_index"],
            "cell_id": dept_data["cell_id"],
            "coordinates": dept_data["coordinates"],
            "agents_count": len(dept_data["agents"])
        }
        
        if include_agents:
            dept_info["agents"] = []
            for agent_id in dept_data["agents"]:
                agent_data = sunflower_registry.agents.get(agent_id)
                if agent_data:
                    dept_info["agents"].append({
                        "id": agent_id,
                        "name": agent_data["name"],
                        "role": agent_data["role"],
                        "sunflower_index": agent_data["sunflower_index"],
                        "cell_id": agent_data["cell_id"],
                        "coordinates": agent_data["coordinates"]
                    })
        
        # Get adjacency information
        neighbors = sunflower_registry.get_neighbors(dept_data["cell_id"])
        dept_info["adjacency"] = {
            "neighbors": neighbors,
            "neighbor_count": len(neighbors)
        }
        
        return {
            "success": True,
            "department": dept_info
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load department: {str(e)}")

@router.get("/{department_id}/agents")
async def get_department_agents(
    department_id: str,
    limit: int = Query(100, description="Maximum number of agents to return"),
    offset: int = Query(0, description="Number of agents to skip")
) -> Dict[str, Any]:
    """Get all agents in a specific department."""
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        
        dept_data = sunflower_registry.get_department_by_id(department_id)
        if not dept_data:
            raise HTTPException(status_code=404, detail="Department not found")
        
        agents = []
        for agent_id in dept_data["agents"]:
            agent_data = sunflower_registry.agents.get(agent_id)
            if agent_data:
                agents.append({
                    "id": agent_id,
                    "name": agent_data["name"],
                    "role": agent_data["role"],
                    "sunflower_index": agent_data["sunflower_index"],
                    "cell_id": agent_data["cell_id"],
                    "coordinates": agent_data["coordinates"],
                    "department_id": department_id,
                    "department_name": dept_data["name"]
                })
        
        # Apply pagination
        total_count = len(agents)
        agents = agents[offset:offset + limit]
        
        return {
            "success": True,
            "department_id": department_id,
            "department_name": dept_data["name"],
            "agents": agents,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "returned_count": len(agents),
            "pagination": {
                "has_next": offset + limit < total_count,
                "has_prev": offset > 0,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "prev_offset": max(0, offset - limit) if offset > 0 else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load department agents: {str(e)}")

# Legacy HTML endpoints for backward compatibility
@router.get("/html", response_class=HTMLResponse)
async def get_departments_html(request: Request):
    """Get departments HTML view."""
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        
        # Hidden departments (not shown in frontend, Masoud-only)
        hidden_departments = ["reverse_attack_ai"]
        
        departments = []
        for dept_id, dept_data in sunflower_registry.departments.items():
            # Skip hidden departments in HTML view
            if dept_id in hidden_departments:
                continue
                
            dept_info = {
                "id": dept_id,
                "name": dept_data["name"],
                "description": dept_data["description"],
                "color": dept_data["color"],
                "sunflower_index": dept_data["sunflower_index"],
                "agents_count": len(dept_data["agents"])
            }
            departments.append(dept_info)
        
        return templates.TemplateResponse("departments.html", {
            "request": request,
            "departments": departments,
            "total_count": len(departments)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load departments HTML: {str(e)}")

@router.get("/{department_id}/html", response_class=HTMLResponse)
async def get_department_html(request: Request, department_id: str):
    """Get specific department HTML view."""
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        
        dept_data = sunflower_registry.get_department_by_id(department_id)
        if not dept_data:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Get agents for this department
        agents = []
        for agent_id in dept_data["agents"]:
            agent_data = sunflower_registry.agents.get(agent_id)
            if agent_data:
                agents.append({
                    "id": agent_id,
                    "name": agent_data["name"],
                    "role": agent_data["role"],
                    "sunflower_index": agent_data["sunflower_index"]
                })
        
        dept_info = {
            "id": department_id,
            "name": dept_data["name"],
            "description": dept_data["description"],
            "color": dept_data["color"],
            "sunflower_index": dept_data["sunflower_index"],
            "agents": agents,
            "agents_count": len(agents)
        }
        
        return templates.TemplateResponse("department_detail.html", {
            "request": request,
            "department": dept_info
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load department HTML: {str(e)}")

# Phase E: Group Speaker Logic - Department Chat with Spokesperson
@router.get("/{department_id}/chat/sessions")
async def list_department_chat_sessions(department_id: str):
    """List all chat sessions for a specific department - NOW DB-BACKED (single source of truth)"""
    from backend.database import get_db, SessionLocal
    from backend.services.chat_service import chat_service
    
    db = SessionLocal()
    try:
        # Get all department sessions from DB using scope filter
        # Use get_department_sessions for flexible matching
        sessions = chat_service.get_department_sessions(db, department_id)
        
        sessions_list = []
        for session in sessions:
            try:
                messages = chat_service.get_session_messages(db, session.session_id)
                sessions_list.append({
                    "session_id": session.session_id,
                    "title": session.title or f"Chat with {department_id}",
                    "category": session.category or "department",
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                    "message_count": len(messages),
                    "is_active": session.is_active
                })
            except Exception as e:
                logger.warning(f"Error getting messages for session {session.session_id}: {e}")
                # Still include session even if messages fail
                sessions_list.append({
                    "session_id": session.session_id,
                    "title": session.title or f"Chat with {department_id}",
                    "category": session.category or "department",
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                    "message_count": 0,
                    "is_active": session.is_active
                })
        
        # Sort by updated_at (most recent first)
        sessions_list.sort(key=lambda x: x["updated_at"] or "", reverse=True)
        
        return {
            "success": True,
            "department_id": department_id,
            "sessions": sessions_list,
            "total": len(sessions_list)
        }
    except Exception as e:
        logger.error(f"Error listing department chat sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list department chat sessions: {str(e)}")
    finally:
        db.close()

@router.get("/{department_id}/chat/sessions/{session_id}")
async def get_department_chat_session(department_id: str, session_id: str):
    """Get a specific department chat session with messages - NOW DB-BACKED (single source of truth)"""
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    
    db = next(get_db())
    try:
        # Get session from DB
        session = chat_service.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Verify it belongs to this department (department-scoped or agent-scoped with same dept)
        if session.scope_type == "department":
            if (session.scope_id or "").strip().lower() != department_id.strip().lower():
                raise HTTPException(status_code=403, detail="Session does not belong to this department")
        elif session.scope_type == "agent":
            ctx = session.context_json or {}
            if (ctx.get("department_id") or "").strip().lower() != department_id.strip().lower():
                raise HTTPException(status_code=403, detail="Session does not belong to this department")
        else:
            raise HTTPException(status_code=403, detail="Session does not belong to this department")
        
        # Get messages
        messages = chat_service.get_session_messages(db, session_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "title": session.title,
            "category": session.category,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "model": msg.model,
                    "tokens": msg.tokens
                }
                for msg in messages
            ],
            "message_count": len(messages)
        }
    finally:
        db.close()

@router.delete("/{department_id}/chat/sessions/{session_id}")
async def delete_department_chat_session(department_id: str, session_id: str):
    """Delete a department chat session"""
    try:
        try:
            from backend.models.chat_history_sqlite import chat_history_manager
        except ImportError:
            from backend.models.chat_history import chat_history_manager
        
        session = chat_history_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify session belongs to this department
        session_metadata = session.context or {}
        if session_metadata.get("department_id") != department_id and session_metadata.get("scope") != f"department:{department_id}":
            raise HTTPException(status_code=403, detail="Session does not belong to this department")
        
        success = chat_history_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete department chat session: {str(e)}")

@router.post("/{department_id}/chat", response_model=ChatMessageResponse)
async def department_chat(
    department_id: str,
    request: ChatMessageRequest = Body(...)
) -> ChatMessageResponse:
    """
    Phase E: Department group chat with spokesperson synthesis.
    
    If agent_id is provided: Direct agent response.
    If no agent_id: Group chat → Spokesperson synthesizes from all agents.
    """
    try:
        from backend.utils.sunflower_registry import sunflower_registry
        from backend.daena_brain import daena_brain
        from backend.services.llm_service import llm_service
        from backend.database import SessionLocal
        
        # Get department data
        dept_data = sunflower_registry.get_department_by_id(department_id)
        if not dept_data:
            raise HTTPException(status_code=404, detail="Department not found")
        
        # Get all agents for this department
        department_agents = sunflower_registry.get_department_agents(department_id)
        
        if not department_agents:
            raise HTTPException(status_code=404, detail="No agents found in department")
        
        user_message = request.message.strip()
        if not user_message:
            raise HTTPException(status_code=400, detail="message is required")
        
        # Phase E: If specific agent requested, use direct agent response
        if request.agent_id:
            try:
                from backend.models.chat_history_sqlite import chat_history_manager
            except ImportError:
                from backend.models.chat_history import chat_history_manager
            
            agent_data = sunflower_registry.agents.get(request.agent_id)
            if not agent_data or agent_data.get("department_id") != department_id:
                raise HTTPException(status_code=404, detail=f"Agent {request.agent_id} not found in department")
            
            # Get or create session for this agent - USE DB-BACKED SERVICE
            from backend.services.chat_service import chat_service
            db = SessionLocal()
            try:
                session_id = request.context.get("session_id")
                if not session_id:
                    # Create new session with DB-backed service
                    session = chat_service.create_session(
                        db=db,
                        title=f"Chat with {agent_data.get('name', request.agent_id)}",
                        category="agent",
                        scope_type="agent",
                        scope_id=request.agent_id,
                        context={
                            "agent_id": request.agent_id,
                            "agent_name": agent_data.get("name", ""),
                            "agent_role": agent_data.get("role", ""),
                            "department_id": department_id,
                            "department_name": dept_data.get("name", ""),
                            **request.context
                        }
                    )
                    session_id = session.session_id
                else:
                    # Verify session exists
                    session = chat_service.get_session(db, session_id)
                    if not session:
                        # Create new session if not found
                        session = chat_service.create_session(
                            db=db,
                            title=f"Chat with {agent_data.get('name', request.agent_id)}",
                            category="agent",
                            scope_type="agent",
                            scope_id=request.agent_id,
                            context={
                                "agent_id": request.agent_id,
                                "agent_name": agent_data.get("name", ""),
                                "agent_role": agent_data.get("role", ""),
                                "department_id": department_id,
                                "department_name": dept_data.get("name", ""),
                                **request.context
                            }
                        )
                        session_id = session.session_id
                
                # CRITICAL: Ensure session_id is never None
                if not session_id:
                    raise HTTPException(status_code=500, detail="Failed to create chat session")
            finally:
                db.close()
            
            # Direct agent response
            context = {
                "agent_id": request.agent_id,
                "agent_name": agent_data.get("name", ""),
                "agent_role": agent_data.get("role", ""),
                "department_id": department_id,
                "department_name": dept_data.get("name", ""),
                **request.context
            }
            
            # Use shared brain - humanized, no formal memo
            agent_prompt = f"""You are {agent_data.get('name', '')}, {agent_data.get('role', 'agent')} in {dept_data.get('name', '')} at MAS-AI. You are NOT Alibaba Cloud or Qwen. Reply in 1-4 short, natural sentences. No "Subject:", no "Dear Team", no formal letter.

User: {user_message}

Reply:"""
            response_text = await llm_service.generate_response(agent_prompt, max_tokens=400, temperature=0.6)
            if "Alibaba Cloud" in response_text or "Qwen" in response_text:
                response_text = response_text.replace("Alibaba Cloud", "we").replace("Qwen", "I")
            
            # Store messages in chat history
            chat_history_manager.add_message(session_id, "user", user_message)
            chat_history_manager.add_message(session_id, agent_data.get("name", "agent"), response_text)
            
            # Also store in database for backward compatibility
            db = SessionLocal()
            try:
                user_msg = DepartmentChatMessage(
                    department_id=department_id,
                    sender="user",
                    message=user_message,
                    created_at=datetime.now()
                )
                db.add(user_msg)
                
                agent_msg = DepartmentChatMessage(
                    department_id=department_id,
                    sender=agent_data.get("name", ""),
                    message=response_text,
                    response=response_text,
                    agent_name=agent_data.get("name", ""),
                    agent_role=agent_data.get("role", ""),
                    created_at=datetime.now()
                )
                db.add(agent_msg)
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to store chat history in DB: {e}")
                db.rollback()
            finally:
                db.close()
            
            return ChatMessageResponse(
                success=True,
                response=response_text,
                agent_name=agent_data.get("name", ""),
                agent_role=agent_data.get("role", ""),
                synthesized_from=0,  # Direct response, not synthesized
                timestamp=datetime.now().isoformat(),
                session_id=session_id
            )
        
        # Get or create session in DB - ALWAYS succeeds
        from backend.database import SessionLocal
        from backend.services.chat_service import chat_service
        
        db = SessionLocal()
        try:
            session_id = request.context.get("session_id")
            if not session_id:
                # Create new session - ALWAYS succeeds
                logger.info(f"Creating new department chat session for {department_id}")
                session = chat_service.create_session(
                    db=db,
                    title=f"Chat with {dept_data.get('name', department_id)}",
                    category="departments",
                    scope_type="department",
                    scope_id=department_id,
                    context={
                        "department_id": department_id,
                        "department_name": dept_data.get("name", ""),
                        **request.context
                    }
                )
                session_id = session.session_id
                logger.info(f"✅ Created new department session: {session_id}")
            else:
                # Verify session exists
                session = chat_service.get_session(db, session_id)
                if not session:
                    # Create new session if not found
                    logger.warning(f"Session {session_id} not found, creating new one")
                    session = chat_service.create_session(
                        db=db,
                        title=f"Chat with {dept_data.get('name', department_id)}",
                        category="department",
                        scope_type="department",
                        scope_id=department_id,
                        context={
                            "department_id": department_id,
                            "department_name": dept_data.get("name", ""),
                            **request.context
                        }
                    )
                    session_id = session.session_id
                    logger.info(f"✅ Created replacement session: {session_id}")
            
            # CRITICAL: Ensure session_id is never None
            if not session_id:
                raise HTTPException(status_code=500, detail="Failed to create or retrieve chat session")
        except Exception as e:
            logger.error(f"❌ Error in department_chat session handling: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")
        finally:
            db.close()
        
        # Phase E: Group chat - Find spokesperson and synthesize
        # Spokesperson is typically the "Synthesizer" or "Knowledge Synthesizer" agent
        spokesperson = None
        for agent in department_agents:
            role_lower = agent.get("role", "").lower()
            if "synthes" in role_lower or "synth" in role_lower:
                spokesperson = agent
                break
        
        # Fallback: Use first agent if no synthesizer found
        if not spokesperson:
            spokesperson = department_agents[0]
            logger.info(f"No synthesizer found in {department_id}, using {spokesperson.get('name', '')} as spokesperson")
        
        # Phase E: Internal consultation - Collect notes from all agents (skip for very short greetings)
        user_lower = user_message.lower().strip()
        is_simple_greeting = len(user_message.split()) <= 4 and any(
            w in user_lower for w in ["hi", "hey", "hello", "hi team", "good morning", "good afternoon"]
        )
        agent_notes = []
        if not is_simple_greeting:
            for agent in department_agents:
                if agent.get("id") == spokesperson.get("id"):
                    continue  # Skip spokesperson in consultation
                try:
                    consult_prompt = f"As {agent.get('name', '')}, {agent.get('role', 'agent')}, one short sentence on: {user_message}"
                    # Log prompt for debugging "brain sync" issues
                    logger.debug(f"Consulting agent {agent.get('name')} with prompt: {consult_prompt}")
                    
                    note = await llm_service.generate_response(
                        consult_prompt, 
                        max_tokens=80, 
                        temperature=0.6,
                        context={"skip_gate": True}
                    )
                    
                    # Sanitize: if note is numeric (e.g. "-2.0"), discard it as an error/score artifact
                    clean_note = note.strip()
                    if clean_note.replace('.','',1).replace('-','',1).isdigit():
                        logger.warning(f"Discarding invalid numeric note from {agent.get('name')}: {clean_note}")
                        continue
                        
                    agent_notes.append({
                        "agent": agent.get("name", ""),
                        "role": agent.get("role", ""),
                        "note": clean_note
                    })
                except Exception as e:
                    logger.warning(f"Failed to get note from {agent.get('name', '')}: {e}")
        
        # Phase E: Spokesperson responds - HUMANIZED: short, natural, no formal letter format
        if is_simple_greeting:
            synthesis_prompt = f"""You are {spokesperson.get('name', 'Team')}, the spokesperson for {dept_data.get('name', '')} department at MAS-AI. You are NOT Alibaba Cloud, NOT Qwen, NOT a generic AI. Reply to this greeting in 1-2 short, warm, natural sentences. No "Subject:", no "Dear Team", no formal letter. Just a human-like reply.

User said: "{user_message}"

Reply briefly:"""
        else:
            synthesis_prompt = f"""You are {spokesperson.get('name', 'Spokesperson')}, spokesperson for {dept_data.get('name', '')} department. You are NOT Alibaba Cloud or Qwen. Reply in 2-4 short, natural sentences. No "Subject:" or "Dear Team" or formal memo format.

User asked: "{user_message}"
{chr(10).join([f"- {n['agent']}: {n['note']}" for n in agent_notes]) if agent_notes else ""}

Give a concise, human reply that uses the team input above. Do not sign with "[Your Name]" or "Knowledge Synthesizer" or "Alibaba Cloud"."""
        
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
        
        if ollama_available:
            response_text = await llm_service.generate_response(
                synthesis_prompt,
                max_tokens=300 if is_simple_greeting else 500,
                temperature=0.6,
                context={"skip_gate": True}
            )
            # Strip any accidental formal prefixes (humanize: no memo style)
            formal_prefixes = ("Subject: Re:", "Subject:", "Dear Team", "Dear team", "Hi Team,", "Hello,", "Hi,", "Re:")
            while True:
                t = response_text.strip()
                stripped = False
                for prefix in formal_prefixes:
                    if t.startswith(prefix):
                        response_text = t[len(prefix):].strip()
                        stripped = True
                        break
                if not stripped:
                    break
            # Identity guards: never expose Alibaba/Qwen
            response_text = response_text.replace("Alibaba Cloud", "the team").replace("Qwen", "we")
            if "Knowledge Synthesizer" in response_text or "[Your Name]" in response_text:
                response_text = response_text.replace("Knowledge Synthesizer", spokesperson.get("name", "Team")).replace("[Your Name]", spokesperson.get("name", ""))
            # For simple greetings, cap length to keep it human and short
            if is_simple_greeting and len(response_text) > 280:
                response_text = response_text[:277].rsplit(".", 1)[0] + "." if "." in response_text[:277] else response_text[:277]
            
            # Sanitize final response
            if response_text.strip().replace('.','',1).replace('-','',1).isdigit():
                logger.warning(f"Spokesperson response was numeric error code: {response_text}. Using fallback.")
                response_text = f"I'm here! {spokesperson.get('name', 'I')} received your message: '{user_message}'. How can we help?"
        else:
            # Deterministic offline response
            response_text = f"Thank you for your message. I'm {spokesperson.get('name', 'Department Representative')} from {dept_data.get('name', '')}. I'm currently operating in offline mode (brain connection unavailable). Your message has been received and will be processed when the brain is online. In the meantime, how can I assist with department operations?"
        
        # Store messages in DB
        db = SessionLocal()
        try:
            chat_service.add_message(db, session_id, "user", user_message)
            chat_service.add_message(
                db, session_id, "assistant", response_text,
                model="qwen2.5:7b-instruct" if ollama_available else "offline"
            )
        finally:
            db.close()
        
        # Emit WebSocket events for real-time updates via unified event bus
        try:
            from backend.services.event_bus import event_bus
            # Publish chat message events (persists to EventLog and broadcasts via WebSocket)
            await event_bus.publish_chat_event("chat.message", session_id, {
                "session_id": session_id,
                "sender": "user",
                "content": user_message,
                "scope_type": "department",
                "scope_id": department_id,
                "department_id": department_id,
                "type": "department_chat"
            })
            await event_bus.publish_chat_event("chat.message", session_id, {
                "session_id": session_id,
                "sender": "assistant",
                "content": response_text,
                "scope_type": "department",
                "scope_id": department_id,
                "department_id": department_id,
                "type": "department_chat",
                "spokesperson": spokesperson.get("name")
            })
        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event: {e}")
        
        # Also store in database for backward compatibility
        db = SessionLocal()
        try:
            user_msg = DepartmentChatMessage(
                department_id=department_id,
                sender="user",
                message=user_message,
                created_at=datetime.now()
            )
            db.add(user_msg)
            
            dept_msg = DepartmentChatMessage(
                department_id=department_id,
                sender=spokesperson.get("name", "Department"),
                message=response_text,
                response=response_text,
                agent_name=spokesperson.get("name", ""),
                agent_role=spokesperson.get("role", ""),
                created_at=datetime.now()
            )
            db.add(dept_msg)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to store chat history in DB: {e}")
            db.rollback()
        finally:
            db.close()
        
        return ChatMessageResponse(
            success=True,
            response=response_text,
            agent_name=spokesperson.get("name", ""),
            agent_role=spokesperson.get("role", ""),
            synthesized_from=len(agent_notes),  # Number of agents consulted
            timestamp=datetime.now().isoformat(),
            session_id=session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in department chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process chat message: {str(e)}") 