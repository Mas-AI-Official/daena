"""
Recreate Database Schema - Complete Fix
This ensures all columns exist by recreating tables if needed
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "daena.db"

def recreate_schema():
    """Ensure all required columns exist"""
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Fix council_members
        cursor.execute("PRAGMA table_info(council_members)")
        cm_columns = [col[1] for col in cursor.fetchall()]
        
        if 'category_id' not in cm_columns:
            print("[+] Adding category_id to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN category_id INTEGER")
            print("[OK] Added category_id")
        
        # Fix agents - check all required columns
        cursor.execute("PRAGMA table_info(agents)")
        agent_columns = [col[1] for col in cursor.fetchall()]
        
        required_agent_columns = {
            'voice_id': 'TEXT',
            'last_seen': 'DATETIME',
            'metadata_json': 'TEXT'
        }
        
        for col_name, col_type in required_agent_columns.items():
            if col_name not in agent_columns:
                print(f"[+] Adding {col_name} to agents...")
                cursor.execute(f"ALTER TABLE agents ADD COLUMN {col_name} {col_type}")
                print(f"[OK] Added {col_name}")
        
        conn.commit()
        print("\n[OK] Database schema fix complete")
        
        # Verify
        cursor.execute("PRAGMA table_info(council_members)")
        cm_columns = [col[1] for col in cursor.fetchall()]
        cursor.execute("PRAGMA table_info(agents)")
        agent_columns = [col[1] for col in cursor.fetchall()]
        
        print(f"\n[VERIFY] council_members columns: {', '.join(cm_columns)}")
        print(f"[VERIFY] agents columns: {', '.join(agent_columns)}")
        
        if 'category_id' in cm_columns and 'voice_id' in agent_columns:
            print("\n[SUCCESS] All required columns exist!")
            return True
        else:
            print("\n[WARNING] Some columns still missing")
            return False
        
    except Exception as e:
        print(f"[ERROR] Error fixing schema: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    recreate_schema()



