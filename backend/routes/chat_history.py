
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# --- Dependencies Stubs ---
# In a real app, import these from auth/dependencies
class User(BaseModel):
    id: str = "user_123"

async def get_current_user():
    return User()

# --- DB Stub for "databases" library style ---
# If the project doesn't use 'databases', we'll need to adapt this.
# For now, we assume a global 'database' object exists or we mock it.
class MockDB:
    async def fetch_all(self, query, params=None):
        return []
    async def fetch_one(self, query, params=None):
        return None
    async def fetch_val(self, query, params=None):
        return 0
    async def execute(self, query, params=None):
        class Res:
            rowcount = 1
        return Res()

# Try to import real db, else use mock
try:
    from backend.database import database as db
except ImportError:
    db = MockDB()

router = APIRouter()

@router.get("/chat/history")
async def get_chat_history(
    limit: int = 50,
    cursor: str = None,
    search: str = None,
    current_user: User = Depends(get_current_user)
):
    """Get chat history with pagination and search"""
    
    query = """
        SELECT 
            s.id,
            s.title,
            s.created_at,
            s.updated_at,
            COUNT(m.id) as message_count,
            (SELECT content FROM messages WHERE session_id = s.id ORDER BY created_at DESC LIMIT 1) as last_message
        FROM chat_sessions s
        LEFT JOIN messages m ON m.session_id = s.id
        WHERE s.user_id = :user_id
    """
    
    params = {"user_id": current_user.id, "limit": limit}
    
    if cursor:
        query += " AND s.created_at < :cursor"
        params["cursor"] = cursor
    
    if search:
        query += " AND (s.title ILIKE :search OR EXISTS (SELECT 1 FROM messages WHERE session_id = s.id AND content ILIKE :search))"
        params["search"] = f"%{search}%"
    
    query += """
        GROUP BY s.id
        ORDER BY s.updated_at DESC
        LIMIT :limit
    """
    
    # Check if db is a mock or real
    if isinstance(db, MockDB):
        # Return dummy data for UI testing
        return {
            "sessions": [
                {
                    "id": "mock_session_1",
                    "title": "Strategy Discussion",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "message_count": 5,
                    "last_message": "Let's proceed with the plan."
                }
            ],
            "next_cursor": None,
            "total": 1
        }

    sessions = await db.fetch_all(query, params)
    
    return {
        "sessions": [dict(s) for s in sessions],
        "next_cursor": sessions[-1]["created_at"] if sessions else None,
        "total": await db.fetch_val("SELECT COUNT(*) FROM chat_sessions WHERE user_id = :user_id", {"user_id": current_user.id})
    }

@router.get("/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get full chat session with messages"""
    
    query_session = "SELECT * FROM chat_sessions WHERE id = :id AND user_id = :user_id"
    params = {"id": session_id, "user_id": current_user.id}
    
    if isinstance(db, MockDB):
         return {
            "session": {"id": session_id, "title": "Mock Session"},
            "messages": [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"}
            ]
        }

    session = await db.fetch_one(query_session, params)
    
    if not session:
        raise HTTPException(404, "Session not found")
    
    messages = await db.fetch_all(
        """
        SELECT * FROM messages 
        WHERE session_id = :session_id 
        ORDER BY created_at ASC
        """,
        {"session_id": session_id}
    )
    
    return {
        "session": dict(session),
        "messages": [dict(m) for m in messages]
    }

@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete a chat session"""
    
    if isinstance(db, MockDB):
        return {"status": "deleted"}

    result = await db.execute(
        "DELETE FROM chat_sessions WHERE id = :id AND user_id = :user_id",
        {"id": session_id, "user_id": current_user.id}
    )
    
    # Note: result.rowcount might not be available in all drivers
    # but we assume standard behavior or ignore for now
    
@router.patch("/chat/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    payload: Dict[str, str],
    current_user: User = Depends(get_current_user)
):
    """Rename a chat session"""
    title = payload.get("title")
    if not title:
        raise HTTPException(400, "Title is required")

    if isinstance(db, MockDB):
        return {"status": "renamed", "title": title}

    await db.execute(
        "UPDATE chat_sessions SET title = :title, updated_at = :updated_at WHERE id = :id AND user_id = :user_id",
        {"title": title, "updated_at": datetime.now(), "id": session_id, "user_id": current_user.id}
    )
    
    return {"status": "renamed", "title": title}