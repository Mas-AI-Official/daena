"""
Fix database schema - add missing columns
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "daena.db"

def fix_schema():
    """Add missing columns to database tables"""
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        # Check and add category_id to council_members
        cursor.execute("PRAGMA table_info(council_members)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'category_id' not in columns:
            print("[+] Adding category_id to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN category_id INTEGER")
            print("[OK] Added category_id to council_members")
        else:
            print("[OK] category_id already exists in council_members")
        
        # Check and add voice_id to agents
        cursor.execute("PRAGMA table_info(agents)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'voice_id' not in columns:
            print("[+] Adding voice_id to agents...")
            cursor.execute("ALTER TABLE agents ADD COLUMN voice_id TEXT")
            print("[OK] Added voice_id to agents")
        else:
            print("[OK] voice_id already exists in agents")
        
        # Check and add persona_source to council_members
        cursor.execute("PRAGMA table_info(council_members)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'persona_source' not in columns:
            print("[+] Adding persona_source to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN persona_source TEXT")
            print("[OK] Added persona_source to council_members")
        else:
            print("[OK] persona_source already exists in council_members")
        
        # Check and add enabled to council_members
        if 'enabled' not in columns:
            print("[+] Adding enabled to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN enabled BOOLEAN DEFAULT 1")
            print("[OK] Added enabled to council_members")
        else:
            print("[OK] enabled already exists in council_members")
        
        # Check and add settings_json to council_members
        if 'settings_json' not in columns:
            print("[+] Adding settings_json to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN settings_json JSON")
            print("[OK] Added settings_json to council_members")
        else:
            print("[OK] settings_json already exists in council_members")
        
        # Check and add display_order to council_members
        if 'display_order' not in columns:
            print("[+] Adding display_order to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN display_order INTEGER DEFAULT 0")
            print("[OK] Added display_order to council_members")
        else:
            print("[OK] display_order already exists in council_members")
        
        # Check and add created_at/updated_at to council_members
        if 'created_at' not in columns:
            print("[+] Adding created_at to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN created_at DATETIME")
            print("[OK] Added created_at to council_members")
        else:
            print("[OK] created_at already exists in council_members")
        
        if 'updated_at' not in columns:
            print("[+] Adding updated_at to council_members...")
            cursor.execute("ALTER TABLE council_members ADD COLUMN updated_at DATETIME")
            print("[OK] Added updated_at to council_members")
        else:
            print("[OK] updated_at already exists in council_members")
        
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
    fix_schema()

