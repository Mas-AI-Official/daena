"""
Database migration to add department_id and agent_id to chat_sessions
Run this script to fix schema errors
"""
import sqlite3
import sys
from pathlib import Path

# Get project root
project_root = Path(__file__).parent.parent
db_path = project_root / "daena.db"

if not db_path.exists():
    print(f"❌ Database not found: {db_path}")
    sys.exit(1)

print(f"📁 Using database: {db_path}")

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(chat_sessions)")
    columns = [row[1] for row in cursor.fetchall()]
    
    print(f"📋 Current columns in chat_sessions: {', '.join(columns)}")
    
    needs_migration = False
    
    # Add department_id if missing
    if 'department_id' not in columns:
        print("  [+] Adding department_id column...")
        cursor.execute("""
            ALTER TABLE chat_sessions 
            ADD COLUMN department_id TEXT
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_department_id ON chat_sessions(department_id)")
        needs_migration = True
    else:
        print("  ✅ department_id column already exists")
    
    # Add agent_id if missing
    if 'agent_id' not in columns:
        print("  [+] Adding agent_id column...")
        cursor.execute("""
            ALTER TABLE chat_sessions 
            ADD COLUMN agent_id TEXT
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_agent_id ON chat_sessions(agent_id)")
        needs_migration = True
    else:
        print("  ✅ agent_id column already exists")
    
    if needs_migration:
        conn.commit()
        print("\n✅ Database migration complete!")
    else:
        print("\n✅ Database schema is already up to date")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Migration failed: {e}")
    sys.exit(1)
