"""
Chat History API Routes
Manage chat sessions and messages
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.unified_chat import UnifiedChatService
from datetime import datetime
import uuid
import json
import os
from pathlib import Path
from pydantic import BaseModel
import logging

# Dynamic import based on environment
if os.getenv("USE_SQLITE_CHAT", "true").lower() == "true":
    from backend.models.chat_history_sqlite import ChatSession, ChatMessage, chat_history_manager
    logger = logging.getLogger(__name__)
    logger.info("🔧 Using SQLite-based chat history")
else:
    from backend.models.chat_history import ChatSession, ChatMessage, chat_history_manager
    logger = logging.getLogger(__name__)
    logger.info("🔧 Using file-based chat history")

router = APIRouter(prefix="/api/v1/chat-history", tags=["Chat History"])

class CreateSessionRequest(BaseModel):
    title: str
    category: Optional[str] = None
    scope_type: Optional[str] = "general"  # executive, general, department, agent
    scope_id: Optional[str] = None  # HR, Legal, Engineering, agent_id, etc

class AddMessageRequest(BaseModel):
    sender: str
    content: str
    category: Optional[str] = None

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None

# Local file storage for chat history - use BRAIN_ROOT or MODELS_ROOT/daena_brain or project local_brain
def _chat_storage_path() -> Path:
    try:
        from backend.config.settings import get_brain_root
        return get_brain_root() / "chat_history"
    except Exception:
        return Path(__file__).parent.parent.parent.parent / "local_brain" / "chat_history"


CHAT_STORAGE_PATH = _chat_storage_path()
CHAT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

@router.post("/sessions")
async def create_chat_session(request: CreateSessionRequest):
    """Create a new chat session with optional department scope"""
    # Try DB-backed chat service first (preferred for persistence)
    try:
        from backend.database import SessionLocal
        from backend.services.chat_service import chat_service
        
        db = SessionLocal()
        try:
            # Create session in DB (chat_service.create_session already commits)
            session = chat_service.create_session(
                db=db,
                title=request.title,
                category=request.category,
                scope_type=request.scope_type or "general",
                scope_id=request.scope_id
            )
            session_id = session.session_id
            
            # IMPORTANT: chat_service.create_session already commits
            # Refresh the session to ensure it's fully loaded
            db.refresh(session)
            
            # Verify the session was created correctly by querying it back
            # This ensures the commit is visible
            from backend.database import ChatSession
            verify_session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id
            ).first()
            
            # Log for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Created session {session_id} with scope_type='{request.scope_type}', scope_id='{request.scope_id}' (type: {type(request.scope_id)})")
            if verify_session:
                logger.info(f"   Verified: session exists in DB with scope_id='{verify_session.scope_id}'")
            else:
                logger.warning(f"   ⚠️ Session not found immediately after creation - commit may not be visible yet")
            
            # Also create in JSON manager for backward compatibility
            try:
                chat_history_manager.create_session(
                    title=request.title,
                    category=request.category,
                    scope_type=request.scope_type or "general",
                    scope_id=request.scope_id
                )
            except Exception:
                pass  # JSON fallback is optional
            
            return {
                "session_id": session_id, 
                "scope_type": request.scope_type or "general",
                "scope_id": request.scope_id,
                "message": "Session created successfully"
            }
        finally:
            db.close()
    except Exception as e:
        # Fallback to JSON-based manager if DB fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"DB-backed chat service unavailable, using JSON fallback: {e}")
        session_id = chat_history_manager.create_session(
            title=request.title,
            category=request.category,
            scope_type=request.scope_type or "general",
            scope_id=request.scope_id
        )
        return {
            "session_id": session_id, 
            "scope_type": request.scope_type or "general",
            "scope_id": request.scope_id,
            "message": "Session created successfully"
        }

@router.get("/sessions")
async def get_all_sessions(
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all chat sessions - NOW DB-BACKED (single source of truth)
    
    Query parameters:
    - scope_type: Filter by scope_type (executive, department, agent, general)
    - scope_id: Filter by scope_id (department_id, agent_id, etc.)
    - category: Filter by category
    """
    try:
        from backend.database import SessionLocal
        from backend.services.chat_service import chat_service
        
        db = SessionLocal()
        try:
            # Use DB-backed service
            if scope_type and scope_id:
                # Get sessions for specific scope
                if scope_type == "department":
                    sessions = chat_service.get_department_sessions(db, scope_id)
                elif scope_type == "agent":
                    sessions = chat_service.get_agent_sessions(db, scope_id)
                else:
                    sessions = chat_service.get_sessions_by_scope(db, scope_type, scope_id)
            elif scope_type:
                # Get all sessions of a specific scope type
                sessions = chat_service.get_sessions_by_scope(db, scope_type)
            elif category:
                # Get sessions by category
                sessions = chat_service.get_all_sessions(db, category)
            else:
                # Get all sessions
                sessions = chat_service.get_all_sessions(db)
            
            # Convert to response format
            sessions_list = []
            for session in sessions:
                # Get message count
                messages = chat_service.get_session_messages(db, session.session_id)
                
                sessions_list.append({
                    "session_id": session.session_id,
                    "id": session.session_id,
                    "title": session.title or "Untitled Chat",
                    "category": session.category or "general",
                    "scope_type": session.scope_type or "general",
                    "scope_id": session.scope_id,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None,
                    "message_count": len(messages),
                    "last_message": messages[-1].content[:100] if messages else None
                })
            
            # Filter out empty sessions if no filters applied
            if not scope_type and not scope_id and not category:
                sessions_with_messages = [s for s in sessions_list if s["message_count"] > 0]
                return {
                    "sessions": sessions_with_messages,
                    "total": len(sessions_with_messages),
                    "empty_sessions_filtered": len(sessions_list) - len(sessions_with_messages)
                }
            
            return {
                "sessions": sessions_list,
                "total": len(sessions_list),
                "empty_sessions_filtered": 0
            }
        finally:
            db.close()
    except Exception as e:
        # Fallback to JSON manager if DB fails
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"DB-backed chat service unavailable, using JSON fallback: {e}")
        all_sessions = chat_history_manager.get_all_sessions()
        sessions_with_messages = [s for s in all_sessions if len(s.messages) > 0]
        return {
            "sessions": [session.dict() for session in sessions_with_messages],
            "total": len(sessions_with_messages),
            "empty_sessions_filtered": len(all_sessions) - len(sessions_with_messages)
        }

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific chat session"""
    session = chat_history_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.dict()

@router.post("/sessions/{session_id}/messages")
async def add_message(session_id: str, request: AddMessageRequest):
    """Add a message to a chat session"""
    success = chat_history_manager.add_message(
        session_id=session_id,
        sender=request.sender,
        content=request.content,
        category=request.category
    )
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Emit WebSocket event for real-time updates via unified event bus
    try:
        from backend.services.event_bus import event_bus
        # Publish chat message events (persists to EventLog and broadcasts via WebSocket)
        await event_bus.publish_chat_event("chat.message", session_id, {
            "sender": request.sender,
            "content": request.content,
            "category": request.category,
            "session_id": session_id
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to emit WebSocket event: {e}")
    
    return {"message": "Message added successfully"}

@router.put("/sessions/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session title or category"""
    if request.title:
        success = chat_history_manager.update_session_title(session_id, request.title)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Update category if provided
    session = chat_history_manager.get_session(session_id)
    if session and request.category:
        session.category = request.category
        session.updated_at = datetime.now()
        chat_history_manager.save_sessions()
    
    return {"message": "Session updated successfully"}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session - DB-BACKED (single source of truth)"""
    # Try DB-backed delete first (single source of truth)
    try:
        from backend.database import SessionLocal
        from backend.services.chat_service import chat_service
        
        db = SessionLocal()
        try:
            success = chat_service.delete_session(db, session_id)
            if success:
                # Also remove from JSON fallback for consistency
                try:
                    chat_history_manager.delete_session(session_id)
                except Exception:
                    pass  # JSON fallback is optional
                
                # Emit WebSocket event for real-time UI update
                try:
                    from backend.services.event_bus import event_bus
                    await event_bus.publish_chat_event("chat.session.deleted", session_id, {
                        "session_id": session_id,
                        "deleted": True
                    })
                except Exception as e:
                    logger.warning(f"Failed to emit session delete event: {e}")
                
                return {"message": "Session deleted successfully", "deleted_from": "database"}
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"DB delete failed, trying JSON fallback: {e}")
    
    # Fallback to JSON-based manager
    success = chat_history_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted successfully", "deleted_from": "json_fallback"}

@router.post("/sessions/{session_id}/clear-context")
async def clear_session_context(session_id: str):
    """Clear conversation context for a session (resets LLM-side memory; messages stay). Frontend key: Clear Context."""
    try:
        from backend.database import SessionLocal
        from backend.services.chat_service import chat_service
        db = SessionLocal()
        try:
            session = chat_service.get_session(db, session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            # No DB field for "context" yet; acknowledge so frontend stays in sync
        finally:
            db.close()
        return {"message": "Context cleared", "session_id": session_id}
    except HTTPException:
        raise
    except Exception:
        return {"message": "Context cleared", "session_id": session_id}

@router.get("/search")
async def search_sessions(query: str):
    """Search sessions by title or content"""
    sessions = chat_history_manager.search_sessions(query)
    return {
        "sessions": [session.dict() for session in sessions],
        "query": query,
        "total": len(sessions)
    }

@router.get("/categories")
async def get_categories():
    """Get all available categories"""
    categories = chat_history_manager.get_categories()
    return {"categories": categories}

@router.get("/categories/{category}")
async def get_sessions_by_category(category: str):
    """Get sessions by category"""
    sessions = chat_history_manager.get_sessions_by_category(category)
    return {
        "sessions": [session.dict() for session in sessions],
        "category": category,
        "total": len(sessions)
    }

@router.get("/stats")
async def get_chat_stats():
    """Get chat statistics"""
    sessions = chat_history_manager.get_all_sessions()
    total_messages = sum(len(session.messages) for session in sessions)
    categories = chat_history_manager.get_categories()
    
    return {
        "total_sessions": len(sessions),
        "total_messages": total_messages,
        "categories": len(categories),
        "latest_session": sessions[0].dict() if sessions else None
    }

# New endpoint for local file storage
@router.post("/save-to-file")
async def save_chat_to_file(session_id: str):
    """Save chat session to local file for persistence"""
    try:
        session = chat_history_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Create compact file format
        file_data = {
            "id": session.id,
            "title": session.title,
            "category": session.category,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "messages": [
                {
                    "sender": msg.sender,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in session.messages
            ]
        }
        
        # Save to local file
        file_path = CHAT_STORAGE_PATH / f"{session_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(file_data, f, indent=2, ensure_ascii=False)
        
        return {
            "message": "Chat saved to file successfully",
            "file_path": str(file_path),
            "file_size": os.path.getsize(file_path)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chat to file: {str(e)}")

@router.get("/load-from-file/{session_id}")
async def load_chat_from_file(session_id: str):
    """Load chat session from local file"""
    try:
        file_path = CHAT_STORAGE_PATH / f"{session_id}.json"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Chat file not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            file_data = json.load(f)
        
        return file_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load chat from file: {str(e)}")

@router.get("/list-files")
async def list_chat_files():
    """List all saved chat files"""
    try:
        files = []
        for file_path in CHAT_STORAGE_PATH.glob("*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    files.append({
                        "session_id": data.get("id"),
                        "title": data.get("title"),
                        "category": data.get("category"),
                        "message_count": len(data.get("messages", [])),
                        "file_size": os.path.getsize(file_path),
                        "created_at": data.get("created_at")
                    })
            except Exception as e:
                print(f"Error reading file {file_path}: {e}")
        
        return {
            "files": files,
            "total_files": len(files),
            "total_size": sum(f["file_size"] for f in files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list chat files: {str(e)}")


# =============================================
# DEPARTMENT CHAT ENDPOINTS
# =============================================

@router.get("/departments/{department_id}/chats")
async def get_department_chats(department_id: str):
    """Get all chat sessions for a specific department"""
    # Try DB-backed chat service first (preferred)
    try:
        from backend.database import SessionLocal
        from backend.services.chat_service import chat_service
        
        db = SessionLocal()
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🔍 get_department_chats: Querying for department_id='{department_id}' (type: {type(department_id)})")
            
            # First, get ALL department sessions to see what we have
            from backend.database import ChatSession
            db.expire_all()  # Ensure we see latest committed data
            
            # Query all department sessions first
            all_dept_sessions = db.query(ChatSession).filter(
                ChatSession.scope_type == "department",
                ChatSession.is_active == True
            ).all()
            
            logger.info(f"  Direct query found {len(all_dept_sessions)} total department sessions")
            if all_dept_sessions:
                logger.info(f"  Sample scope_ids: {[str(s.scope_id) for s in all_dept_sessions[:5]]}")
            
            # Normalize department_id for matching
            dept_id_str = str(department_id).strip() if department_id else None
            dept_id_lower = dept_id_str.lower() if dept_id_str else None
            
            # Try to match sessions - use chat_service for consistency
            from backend.services.chat_service import chat_service
            db_sessions = chat_service.get_sessions_by_scope(db, "department", department_id)
            
            # Also do manual matching as fallback
            if not db_sessions:
                for s in all_dept_sessions:
                    if s.scope_id:
                        scope_id_str = str(s.scope_id).strip()
                        scope_id_lower = scope_id_str.lower()
                        
                        # Try exact match first (most common)
                        if scope_id_str == dept_id_str:
                            db_sessions.append(s)
                            logger.info(f"  ✓ Matched session {s.session_id[:8]}... (exact: '{scope_id_str}' == '{dept_id_str}')")
                        # Try case-insensitive match
                        elif scope_id_lower == dept_id_lower:
                            db_sessions.append(s)
                            logger.info(f"  ✓ Matched session {s.session_id[:8]}... (case-insensitive: '{scope_id_str}' == '{dept_id_str}')")
                        # Try numeric comparison if both are numeric
                        elif scope_id_str.isdigit() and dept_id_str and dept_id_str.isdigit():
                            if int(scope_id_str) == int(dept_id_str):
                                db_sessions.append(s)
                                logger.info(f"  ✓ Matched session {s.session_id[:8]}... (numeric)")
            
            logger.info(f"  Final: Found {len(db_sessions)} matching sessions for department '{department_id}'")
            
            sessions_list = []
            for session in db_sessions:
                sessions_list.append({
                    "session_id": session.session_id,
                    "id": session.session_id,
                    "title": session.title or f"Chat with {department_id}",
                    "category": session.category,
                    "scope_type": session.scope_type,
                    "scope_id": session.scope_id,
                    "created_at": session.created_at.isoformat() if session.created_at else None,
                    "updated_at": session.updated_at.isoformat() if session.updated_at else None
                })
            
            logger.info(f"  Final result: {len(sessions_list)} sessions for department '{department_id}'")
            
            # Also check JSON-based manager for backward compatibility
            json_sessions = chat_history_manager.get_department_chats(department_id)
            json_session_ids = {s.get("id") or s.get("session_id") for s in sessions_list}
            
            for json_session in json_sessions:
                json_id = json_session.id if hasattr(json_session, 'id') else (json_session.get("id") if isinstance(json_session, dict) else None)
                if json_id and json_id not in json_session_ids:
                    # Add JSON session if not already in DB list
                    if hasattr(json_session, 'dict'):
                        sessions_list.append(json_session.dict())
                    elif isinstance(json_session, dict):
                        sessions_list.append(json_session)
            
            return {
                "department_id": department_id,
                "sessions": sessions_list,
                "total": len(sessions_list)
            }
        finally:
            db.close()
    except Exception as e:
        # Fallback to JSON-based manager if DB fails
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ DB-backed chat service error: {e}", exc_info=True)
        sessions = chat_history_manager.get_department_chats(department_id)
        return {
            "department_id": department_id,
            "sessions": [session.dict() if hasattr(session, 'dict') else session for session in sessions],
            "total": len(sessions)
        }

@router.get("/departments/chats/all")
async def get_all_department_chats():
    """Get all department chats grouped by department ID"""
    dept_chats = chat_history_manager.get_all_department_chats()
    return {
        "departments": {
            dept_id: [s.dict() for s in sessions]
            for dept_id, sessions in dept_chats.items()
        },
        "total_departments": len(dept_chats),
        "total_sessions": sum(len(sessions) for sessions in dept_chats.values())
    }

@router.post("/departments/{department_id}/sessions")
async def create_department_session(department_id: str, request: CreateSessionRequest):
    """Create a chat session scoped to a specific department"""
    session_id = chat_history_manager.create_session(
        title=request.title or f"{department_id.title()} Chat",
        category=request.category or department_id,
        scope_type="department",
        scope_id=department_id
    )
    return {
        "session_id": session_id,
        "department_id": department_id,
        "scope_type": "department",
        "message": f"Department chat session created for {department_id}"
    }

@router.get("/scope/{scope_type}")
async def get_sessions_by_scope_type(scope_type: str, scope_id: Optional[str] = None):
    """Get sessions filtered by scope type (and optionally scope ID)"""
    sessions = chat_history_manager.get_sessions_by_scope(scope_type, scope_id)
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "sessions": [session.dict() for session in sessions],
        "total": len(sessions)
    }


# ===== UNIFIED CHAT ENDPOINTS (Phase 3) =====

class GetOrCreateSessionRequest(BaseModel):
    scope_type: str  # "department", "agent", "general"
    scope_id: Optional[str] = None
    category: Optional[str] = None
    title: Optional[str] = None
    session_id: Optional[str] = None

@router.post("/get-or-create-session")
async def get_or_create_unified_session(
    request: GetOrCreateSessionRequest,
    db: Session = Depends(get_db)
):
    """
    Get existing session or create new one using unified chat service
    Supports thread key pattern: {scope_type}/{scope_id}/{category}
    """
    try:
        session = UnifiedChatService.get_or_create_session(
            db=db,
            scope_type=request.scope_type,
            scope_id=request.scope_id,
            category=request.category,
            title=request.title,
            session_id=request.session_id
        )
        
        thread_key = UnifiedChatService.get_thread_key(
            request.scope_type,
            request.scope_id,
            request.category
        )
        
        return {
            "success": True,
            "session_id": session.session_id,
            "thread_key": thread_key,
            "title": session.title,
            "scope_type": session.scope_type,
            "scope_id": session.scope_id,
            "category": session.category,
            "created_at": session.created_at.isoformat() if session.created_at else None
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get-or-create-session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions-by-category/{category}")
async def get_sessions_by_category_unified(
    category: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Get all sessions for a specific category (for Daena Office)
    """
    try:
        sessions = UnifiedChatService.get_sessions_by_category(db, category, limit)
        
        sessions_with_stats = []
        for session in sessions:
            stats = UnifiedChatService.get_session_with_stats(db, session.session_id)
            if stats:
                sessions_with_stats.append(stats)
        
        return {
            "success": True,
            "category": category,
            "sessions": sessions_with_stats,
            "total": len(sessions_with_stats)
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in sessions-by-category: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
 