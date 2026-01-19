"""
Complete Database Schema Fix
Fixes all missing columns and ensures database is up to date
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "daena.db"

def fix_schema_complete():
    """Fix all database schema issues"""
    if not DB_PATH.exists():
        print(f"[ERROR] Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    fixes_applied = 0
    
    try:
        # Fix 1: council_members.category_id
        cursor.execute("PRAGMA table_info(council_members)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'category_id' not in columns:
            print("[+] Adding category_id to council_members...")
            try:
                cursor.execute("ALTER TABLE council_members ADD COLUMN category_id INTEGER")
                fixes_applied += 1
                print("[OK] Added category_id to council_members")
            except Exception as e:
                print(f"[WARNING] Could not add category_id: {e}")
        else:
            print("[OK] category_id already exists in council_members")
        
        # Fix 2: agents.voice_id
        cursor.execute("PRAGMA table_info(agents)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'voice_id' not in columns:
            print("[+] Adding voice_id to agents...")
            try:
                cursor.execute("ALTER TABLE agents ADD COLUMN voice_id TEXT")
                fixes_applied += 1
                print("[OK] Added voice_id to agents")
            except Exception as e:
                print(f"[WARNING] Could not add voice_id: {e}")
        else:
            print("[OK] voice_id already exists in agents")
        
        # Fix 3: agents.last_seen
        if 'last_seen' not in columns:
            print("[+] Adding last_seen to agents...")
            try:
                cursor.execute("ALTER TABLE agents ADD COLUMN last_seen DATETIME")
                fixes_applied += 1
                print("[OK] Added last_seen to agents")
            except Exception as e:
                print(f"[WARNING] Could not add last_seen: {e}")
        else:
            print("[OK] last_seen already exists in agents")
        
        # Fix 4: agents.metadata_json
        if 'metadata_json' not in columns:
            print("[+] Adding metadata_json to agents...")
            try:
                cursor.execute("ALTER TABLE agents ADD COLUMN metadata_json TEXT")
                fixes_applied += 1
                print("[OK] Added metadata_json to agents")
            except Exception as e:
                print(f"[WARNING] Could not add metadata_json: {e}")
        else:
            print("[OK] metadata_json already exists in agents")
        
        conn.commit()
        print(f"\n[OK] Database schema fix complete - {fixes_applied} fixes applied")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error fixing schema: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema_complete()



