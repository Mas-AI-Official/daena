"""
Unified Chat Service - Single Source of Truth for All Conversations
Provides consistent thread key generation and session management across:
- Department chats
- Agent chats  
- Daena Office categories
- Voice interactions
"""
from sqlalchemy.orm import Session
from backend.database import ChatSession, ChatMessage
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class UnifiedChatService:
    """Unified service for managing all chat sessions with consistent thread keys"""
    
    @staticmethod
    def get_thread_key(
        scope_type: str,
        scope_id: Optional[str] = None,
        category: Optional[str] = None
    ) -> str:
        """
        Generate consistent thread key for identifying conversations
        
        Format: {scope_type}/{scope_id}/{category}
        Examples:
            "department/1/null" - Engineering dept general chat
            "agent/agent_123/null" - Chat with specific agent
            "general/null/executive" - Executive category general chat
        """
        scope_id_str = str(scope_id) if scope_id else "null"
        category_str = str(category) if category else "null"
        return f"{scope_type}/{scope_id_str}/{category_str}"
    
    @staticmethod
    def parse_thread_key(thread_key: str) -> Dict[str, Optional[str]]:
        """Parse thread key back into components"""
        parts = thread_key.split("/")
        if len(parts) != 3:
            raise ValueError(f"Invalid thread key format: {thread_key}")
        
        return {
            "scope_type": parts[0],
            "scope_id": None if parts[1] == "null" else parts[1],
            "category": None if parts[2] == "null" else parts[2]
        }
    
    @staticmethod
    def get_or_create_session(
        db: Session,
        scope_type: str,
        scope_id: Optional[str] = None,
        category: Optional[str] = None,
        title: Optional[str] = None,
        owner_type: str = "user",
        owner_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> ChatSession:
        """
        Get existing session or create new one
        
        Args:
            db: Database session
            scope_type: "department", "agent", "general", etc.
            scope_id: ID of the scope entity (dept ID, agent ID, etc.)
            category: Optional category (executive, departments, agents, general)
            title: Session title (auto-generated if not provided)
            owner_type: Type of owner (user, system, agent)
            owner_id: ID of owner
            session_id: Optional specific session ID to use
        
        Returns:
            ChatSession object
        """
        # If session_id provided, try to get existing
        if session_id:
            existing = db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.is_active == True
            ).first()
            if existing:
                logger.info(f"✅ Found existing session: {session_id}")
                return existing
        
        # Otherwise, look for session by scope/category
        scope_id_str = str(scope_id) if scope_id else None
        
        existing = db.query(ChatSession).filter(
            ChatSession.scope_type == scope_type,
            ChatSession.scope_id == scope_id_str,
            ChatSession.category == category,
            ChatSession.is_active == True
        ).first()
        
        if existing:
            logger.info(f"✅ Found existing session by scope: {existing.session_id}")
            return existing
        
        # Create new session
        new_session_id = str(uuid.uuid4())
        thread_key = UnifiedChatService.get_thread_key(scope_type, scope_id, category)
        
        # Auto-generate title if not provided
        if not title:
            if scope_type == "department":
                title = f"Department Chat - {scope_id or 'General'}"
            elif scope_type == "agent":
                title = f"Agent Chat - {scope_id or 'Unknown'}"
            elif category:
                title = f"{category.title()} Chat"
            else:
                title = "New Conversation"
        
        session = ChatSession(
            session_id=new_session_id,
            scope_type=scope_type,
            scope_id=scope_id_str,
            category=category or "general",
            title=title,
            owner_type=owner_type,
            owner_id=owner_id,
            context_json={"thread_key": thread_key},
            is_active=True
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        logger.info(f"🆕 Created new session: {new_session_id} (thread_key: {thread_key})")
        return session
    
    @staticmethod
    def get_sessions_by_category(
        db: Session,
        category: str,
        limit: int = 100
    ) -> List[ChatSession]:
        """
        Get all active sessions for a category (for Daena Office)
        
        Args:
            db: Database session
            category: Category name (executive, departments, agents, general)
            limit: Maximum number of sessions to return
        
        Returns:
            List of ChatSession objects
        """
        sessions = db.query(ChatSession).filter(
            ChatSession.category == category,
            ChatSession.is_active == True
        ).order_by(
            ChatSession.updated_at.desc()
        ).limit(limit).all()
        
        logger.info(f"📋 Found {len(sessions)} sessions for category '{category}'")
        return sessions
    
    @staticmethod
    def get_sessions_by_scope(
        db: Session,
        scope_type: str,
        scope_id: Optional[str] = None,
        limit: int = 100
    ) -> List[ChatSession]:
        """
        Get all sessions for a specific scope
        
        Args:
            db: Database session
            scope_type: Type of scope (department, agent, etc.)
            scope_id: ID of scope entity
            limit: Maximum number to return
        
        Returns:
            List of ChatSession objects
        """
        scope_id_str = str(scope_id) if scope_id else None
        
        query = db.query(ChatSession).filter(
            ChatSession.scope_type == scope_type,
            ChatSession.is_active == True
        )
        
        if scope_id_str:
            query = query.filter(ChatSession.scope_id == scope_id_str)
        
        sessions = query.order_by(
            ChatSession.updated_at.desc()
        ).limit(limit).all()
        
        logger.info(f"📋 Found {len(sessions)} sessions for scope {scope_type}/{scope_id_str}")
        return sessions
    
    @staticmethod
    def get_session_message_count(db: Session, session_id: str) -> int:
        """Get message count for a session"""
        count = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).count()
        return count
    
    @staticmethod
    def get_session_with_stats(db: Session, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session with statistics (message count, last message time, etc.)"""
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            return None
        
        message_count = UnifiedChatService.get_session_message_count(db, session_id)
        
        last_message = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).first()
        
        return {
            "session_id": session.session_id,
            "title": session.title,
            "scope_type": session.scope_type,
            "scope_id": session.scope_id,
            "category": session.category,
            "message_count": message_count,
            "last_message_at": last_message.created_at if last_message else session.updated_at,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "thread_key": UnifiedChatService.get_thread_key(
                session.scope_type,
                session.scope_id,
                session.category
            )
        }


# Convenience function for backwards compatibility
def get_or_create_session(*args, **kwargs) -> ChatSession:
    """Wrapper for backwards compatibility"""
    return UnifiedChatService.get_or_create_session(*args, **kwargs)
