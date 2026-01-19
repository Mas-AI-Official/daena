"""
Fix chat_sessions table schema - add missing columns
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "daena.db"

def fix_chat_sessions_schema():
    """Add missing columns to chat_sessions table"""
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check current columns
        cursor.execute("PRAGMA table_info(chat_sessions)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        
        print(f"Current columns: {list(columns.keys())}")
        
        # Add missing columns
        if 'category_id' not in columns:
            print("[+] Adding category_id to chat_sessions...")
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN category_id INTEGER")
            print("[OK] Added category_id")
        else:
            print("[OK] category_id already exists")
        
        if 'scope_type' not in columns:
            print("[+] Adding scope_type to chat_sessions...")
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN scope_type VARCHAR DEFAULT 'general'")
            print("[OK] Added scope_type")
        else:
            print("[OK] scope_type already exists")
        
        if 'scope_id' not in columns:
            print("[+] Adding scope_id to chat_sessions...")
            cursor.execute("ALTER TABLE chat_sessions ADD COLUMN scope_id VARCHAR")
            print("[OK] Added scope_id")
        else:
            print("[OK] scope_id already exists")
        
        conn.commit()
        print("[OK] Database schema fix complete")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error fixing schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    fix_chat_sessions_schema()



