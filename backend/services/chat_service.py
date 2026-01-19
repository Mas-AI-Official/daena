"""
Chat Service - DB-backed chat session and message management
Single source of truth for all chats (Daena, departments, agents)
"""
from sqlalchemy.orm import Session
from backend.database import ChatSession, ChatMessage, ChatCategory, get_db
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat sessions and messages"""
    
    @staticmethod
    def create_session(
        db: Session,
        title: str = "New Chat",
        category: str = "general",
        owner_type: str = "user",
        owner_id: Optional[str] = None,
        scope_type: str = "general",
        scope_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ChatSession:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        
        # Get or create category (optional - category_id may not exist in schema)
        category_id = None
        try:
            category_obj = db.query(ChatCategory).filter(ChatCategory.name == category).first()
            category_id = category_obj.id if category_obj else None
        except Exception:
            # ChatCategory table may not exist or category_id column may not exist
            pass
        
        # Ensure scope_id is a string (not None) for consistency
        scope_id_str = str(scope_id).strip() if scope_id else None
        
        # Create session - only include category_id if it exists in the model
        session_data = {
            "session_id": session_id,
            "category": category,
            "title": title,
            "owner_type": owner_type,
            "owner_id": owner_id,
            "scope_type": scope_type,
            "scope_id": scope_id_str,  # Use normalized string
            "context_json": context or {},
            "is_active": True
        }
        
        # Only add category_id if the column exists (check by trying to set it)
        # We'll use a try-except approach or check the model
        try:
            # Check if ChatSession model has category_id attribute
            if hasattr(ChatSession, 'category_id'):
                session_data["category_id"] = category_id
        except Exception:
            pass
        
        session = ChatSession(**session_data)
        
        db.add(session)
        db.flush()  # Flush before commit to ensure ID is available
        db.commit()
        db.refresh(session)
        
        # Verify the session was saved correctly
        verify = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if verify:
            logger.info(f"✅ Created chat session: {session_id} (category: {category}, scope_type: {scope_type}, scope_id: '{verify.scope_id}' (stored as: {type(verify.scope_id)}))")
            logger.info(f"   Session details: title='{title}', is_active={verify.is_active}, created_at={verify.created_at}")
        else:
            logger.error(f"❌ Session {session_id} not found immediately after creation!")
        
        return session
    
    @staticmethod
    def get_session(db: Session, session_id: str) -> Optional[ChatSession]:
        """Get a chat session by ID"""
        return db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
    
    @staticmethod
    def get_or_create_session(
        db: Session,
        session_id: Optional[str] = None,
        title: str = "New Chat",
        category: str = "general",
        scope_type: str = "general",
        scope_id: Optional[str] = None
    ) -> ChatSession:
        """Get existing session or create new one"""
        if session_id:
            session = ChatService.get_session(db, session_id)
            if session:
                return session
        
        return ChatService.create_session(
            db=db,
            title=title,
            category=category,
            scope_type=scope_type,
            scope_id=scope_id
        )
    
    @staticmethod
    def add_message(
        db: Session,
        session_id: str,
        role: str,
        content: str,
        model: Optional[str] = None,
        tokens: Optional[int] = None,
        response_time_ms: Optional[int] = None
    ) -> ChatMessage:
        """Add a message to a session"""
        # Ensure session exists
        session = ChatService.get_session(db, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            model=model,
            tokens=tokens,
            response_time_ms=response_time_ms
        )
        
        db.add(message)
        
        # Update session updated_at
        session.updated_at = datetime.utcnow()
        if not session.title or session.title == "New Chat":
            # Auto-generate title from first message
            session.title = content[:50] + "..." if len(content) > 50 else content
        
        db.commit()
        db.refresh(message)
        
        # Publish event (async, don't await to avoid blocking)
        try:
            from backend.core.websocket_manager import websocket_manager
            import asyncio
            # Schedule event publishing (non-blocking)
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(websocket_manager.publish_event(
                    event_type="chat.message",
                    entity_type="chat",
                    entity_id=session_id,
                    payload={
                        "session_id": session_id,
                        "role": role,
                        "content": content[:200],  # Truncate for event log
                        "message_id": message.id
                    },
                    created_by=role
                ))
            except RuntimeError:
                # No event loop running - skip event publishing
                pass
        except Exception as e:
            # Don't fail if event publishing fails
            pass
        
        return message
    
    @staticmethod
    def get_session_messages(db: Session, session_id: str) -> List[ChatMessage]:
        """Get all messages for a session"""
        return db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()
    
    @staticmethod
    def get_sessions_by_scope(
        db: Session,
        scope_type: str,
        scope_id: Optional[str] = None
    ) -> List[ChatSession]:
        """Get sessions filtered by scope"""
        query = db.query(ChatSession).filter(
            ChatSession.scope_type == scope_type,
            ChatSession.is_active == True
        )
        if scope_id:
            # Try exact match first
            query = query.filter(ChatSession.scope_id == scope_id)
        return query.order_by(ChatSession.updated_at.desc()).all()
    
    @staticmethod
    def get_department_sessions(db: Session, department_id: str) -> List[ChatSession]:
        """Get all sessions for a department with flexible matching"""
        # Normalize the department_id for comparison
        dept_id_str = str(department_id).strip()
        dept_id_normalized = dept_id_str.lower()
        
        # First try exact match (most common case)
        sessions = db.query(ChatSession).filter(
            ChatSession.scope_type == "department",
            ChatSession.is_active == True,
            ChatSession.scope_id == dept_id_str
        ).order_by(ChatSession.updated_at.desc()).all()
        
        # If no results, get all department sessions and filter in Python for flexible matching
        if not sessions:
            all_dept_sessions = db.query(ChatSession).filter(
                ChatSession.scope_type == "department",
                ChatSession.is_active == True
            ).all()
            
            logger.info(f"get_department_sessions: Querying dept_id='{dept_id_str}', found {len(all_dept_sessions)} total department sessions")
            
            for s in all_dept_sessions:
                if s.scope_id:
                    scope_str = str(s.scope_id).strip()
                    scope_normalized = scope_str.lower()
                    
                    # Try exact match
                    if scope_str == dept_id_str:
                        sessions.append(s)
                        logger.info(f"  ✓ Matched session {s.session_id[:8]}... (exact: '{scope_str}' == '{dept_id_str}')")
                    # Try case-insensitive match
                    elif scope_normalized == dept_id_normalized:
                        sessions.append(s)
                        logger.info(f"  ✓ Matched session {s.session_id[:8]}... (case-insensitive: '{scope_str}' == '{dept_id_str}')")
        
        logger.info(f"get_department_sessions: Final result: {len(sessions)} sessions for dept_id='{department_id}'")
        if sessions:
            logger.info(f"  Sample session: id={sessions[0].session_id[:8]}..., scope_id='{sessions[0].scope_id}'")
        else:
            # Log all department sessions for debugging
            all_dept = db.query(ChatSession).filter(
                ChatSession.scope_type == "department",
                ChatSession.is_active == True
            ).all()
            logger.warning(f"  No matches found. All department sessions: {[(s.session_id[:8], s.scope_id) for s in all_dept[:5]]}")
        
        return sessions
    
    @staticmethod
    def get_agent_sessions(db: Session, agent_id: str) -> List[ChatSession]:
        """Get all sessions for an agent"""
        return ChatService.get_sessions_by_scope(db, "agent", agent_id)
    
    @staticmethod
    def get_all_sessions(db: Session, category: Optional[str] = None) -> List[ChatSession]:
        """Get all sessions, optionally filtered by category"""
        query = db.query(ChatSession).filter(ChatSession.is_active == True)
        if category:
            query = query.filter(ChatSession.category == category)
        return query.order_by(ChatSession.updated_at.desc()).all()
    
    @staticmethod
    def delete_session(db: Session, session_id: str) -> bool:
        """Delete a session permanently (hard delete - removes from database)"""
        from backend.database import ChatMessage
        
        session = ChatService.get_session(db, session_id)
        if not session:
            return False
        
        # Delete all messages in the session first (foreign key constraint)
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
        
        # Delete the session itself
        db.delete(session)
        db.commit()
        
        logger.info(f"🗑️ Hard deleted chat session: {session_id}")
        return True


# Global service instance
chat_service = ChatService()

