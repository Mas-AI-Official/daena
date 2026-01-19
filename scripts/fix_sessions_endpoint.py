#!/usr/bin/env python3
"""
Fix script: Update daena.py /chat/sessions to use persistent storage
Also makes session responses more robust
"""
import codecs
import os

file_path = os.path.join(os.path.dirname(__file__), '..', 'backend', 'routes', 'daena.py')

print(f"Fixing: {file_path}")

with codecs.open(file_path, 'r', 'utf-8') as f:
    content = f.read()

# Fix 1: Update /chat/sessions to also include persisted sessions
old_sessions_endpoint = '''@router.get("/chat/sessions")
async def list_daena_chat_sessions():
    """List all Daena chat sessions"""
    sessions = []
    for session_id, session in active_sessions.items():
        sessions.append({
            "session_id": session_id,
            "user_id": session.user_id,
            "started_at": session.started_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(session.messages),
            "title": session.context.get("title", f"Chat {session_id[:8]}"),
            "category": session.context.get("category", "general")
        })
    
    # Sort by last activity (most recent first)
    sessions.sort(key=lambda x: x["last_activity"], reverse=True)
    
    return {
        "success": True,
        "sessions": sessions,
        "total": len(sessions)
    }'''

new_sessions_endpoint = '''@router.get("/chat/sessions")
async def list_daena_chat_sessions():
    """List all Daena chat sessions (in-memory + persisted)"""
    sessions = []
    seen_ids = set()
    
    # First add in-memory active sessions
    for session_id, session in active_sessions.items():
        seen_ids.add(session_id)
        sessions.append({
            "session_id": session_id,
            "user_id": session.user_id,
            "started_at": session.started_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "message_count": len(session.messages),
            "title": session.context.get("title", f"Chat {session_id[:8]}"),
            "category": session.context.get("category", "general"),
            "is_active": True
        })
    
    # Then add persisted sessions from chat_history_manager
    try:
        from backend.models.chat_history import chat_history_manager
        for persisted in chat_history_manager.get_all_sessions():
            if persisted.id not in seen_ids:
                sessions.append({
                    "session_id": persisted.id,
                    "user_id": None,
                    "started_at": persisted.created_at.isoformat(),
                    "last_activity": persisted.updated_at.isoformat(),
                    "message_count": len(persisted.messages),
                    "title": persisted.title or f"Chat {persisted.id[:8]}",
                    "category": persisted.category or "general",
                    "is_active": False
                })
    except Exception as e:
        logger.warning(f"Could not load persisted sessions: {e}")
    
    # Sort by last activity (most recent first)
    sessions.sort(key=lambda x: x["last_activity"], reverse=True)
    
    return {
        "success": True,
        "sessions": sessions,
        "total": len(sessions)
    }'''

# Normalize line endings before replacement
old_normalized = old_sessions_endpoint.replace('\n', '\r\n')
new_normalized = new_sessions_endpoint.replace('\n', '\r\n')

if old_normalized in content:
    content = content.replace(old_normalized, new_normalized)
    print("✅ Fixed /chat/sessions to include persisted sessions")
elif old_sessions_endpoint in content:
    content = content.replace(old_sessions_endpoint, new_sessions_endpoint)
    print("✅ Fixed /chat/sessions to include persisted sessions (LF)")
else:
    print("⚠️ Could not find /chat/sessions endpoint to fix")

with codecs.open(file_path, 'w', 'utf-8') as f:
    f.write(content)

print("File saved")
