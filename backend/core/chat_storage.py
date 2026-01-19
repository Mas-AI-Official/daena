"""
Chat Session Storage - SQLite Backend
Persists chat sessions and messages to database
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ChatStorage:
    def __init__(self, db_path: str = "data/chat_sessions.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Sessions table with scope support for departments/agents
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                category TEXT DEFAULT 'general',
                scope_type TEXT DEFAULT 'general',
                scope_id TEXT,
                title TEXT DEFAULT 'New Chat',
                tags TEXT,
                started_at TIMESTAMP,
                last_activity TIMESTAMP,
                context TEXT
            )
        """)
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                type TEXT,
                content TEXT,
                timestamp TIMESTAMP,
                context TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"✅ Chat storage initialized: {self.db_path}")
    
    def save_session(self, session: Dict) -> bool:
        """Save or update a session"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_id, user_id, category, title, tags, started_at, last_activity, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session.get('session_id'),
                session.get('user_id'),
                session.get('category', 'general'),
                session.get('title', 'New Chat'),
                json.dumps(session.get('tags', [])),
                session.get('started_at'),
                session.get('last_activity'),
                json.dumps(session.get('context', {}))
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving session: {e}")
            return False
    
    def save_message(self, session_id: str, message: Dict) -> bool:
        """Save a message to session"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO messages (session_id, type, content, timestamp, context)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id,
                message.get('type'),
                message.get('content'),
                message.get('timestamp', datetime.utcnow().isoformat()),
                json.dumps(message.get('context', {}))
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session with messages"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get session
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            session_row = cursor.fetchone()
            
            if not session_row:
                conn.close()
                return None
            
            session = dict(session_row)
            session['tags'] = json.loads(session['tags']) if session['tags'] else []
            session['context'] = json.loads(session['context']) if session['context'] else {}
            
            # Get messages
            cursor.execute("""
                SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC
            """, (session_id,))
            
            messages = []
            for row in cursor.fetchall():
                msg = dict(row)
                msg['context'] = json.loads(msg['context']) if msg['context'] else {}
                messages.append(msg)
            
            session['messages'] = messages
            
            conn.close()
            return session
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def list_sessions(self, user_id: Optional[str] = None, category: Optional[str] = None) -> List[Dict]:
        """List all sessions"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM sessions"
            params = []
            
            if user_id or category:
                query += " WHERE "
                conditions = []
                if user_id:
                    conditions.append("user_id = ?")
                    params.append(user_id)
                if category:
                    conditions.append("category = ?")
                    params.append(category)
                query += " AND ".join(conditions)
            
            query += " ORDER BY last_activity DESC"
            
            cursor.execute(query, params)
            sessions = []
            for row in cursor.fetchall():
                session = dict(row)
                session['tags'] = json.loads(session['tags']) if session['tags'] else []
                session['context'] = json.loads(session['context']) if session['context'] else {}
                sessions.append(session)
            
            conn.close()
            return sessions
        except Exception as e:
            logger.error(f"Error listing sessions: {e}")
            return []
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False

# Global instance
chat_storage = ChatStorage()
