#!/usr/bin/env python3
"""
Fix tenant_id and project_id columns in agents table
Adds the columns if they don't exist
"""
import sqlite3
import os
import sys
from pathlib import Path

def fix_database_columns():
    """Add tenant_id and project_id columns to agents table if they don't exist"""
    # Try multiple possible database locations
    possible_paths = [
        Path("daena.db"),
        Path("backend/daena.db"),
        Path.cwd() / "daena.db",
        Path(__file__).parent.parent.parent / "daena.db"
    ]
    
    db_path = None
    for path in possible_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print(f"❌ Database not found in any expected location")
        print(f"   Searched: {[str(p) for p in possible_paths]}")
        return False
    
    print(f"📁 Using database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check existing columns
        cursor.execute("PRAGMA table_info(agents)")
        columns_info = cursor.fetchall()
        columns = [col[1] for col in columns_info]
        
        print(f"📋 Current columns in agents table: {', '.join(columns)}")
        
        # Fix tenant_id column
        if "tenant_id" not in columns:
            print("📝 Adding tenant_id column to agents table...")
            try:
                cursor.execute("ALTER TABLE agents ADD COLUMN tenant_id INTEGER")
                # Refresh columns list after adding
                cursor.execute("PRAGMA table_info(agents)")
                columns = [col[1] for col in cursor.fetchall()]
                conn.commit()
                print("✅ tenant_id column added successfully")
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "duplicate column" in error_msg or "already exists" in error_msg:
                    print("✅ tenant_id column already exists")
                else:
                    print(f"⚠️ Could not add tenant_id column: {e}")
                    return False
        else:
            print("✅ tenant_id column already exists")
        
        # Fix project_id column  
        if "project_id" not in columns:
            print("📝 Adding project_id column to agents table...")
            try:
                cursor.execute("ALTER TABLE agents ADD COLUMN project_id INTEGER")
                # Refresh columns list after adding
                cursor.execute("PRAGMA table_info(agents)")
                columns = [col[1] for col in cursor.fetchall()]
                conn.commit()
                print("✅ project_id column added successfully")
            except sqlite3.OperationalError as e:
                error_msg = str(e).lower()
                if "duplicate column" in error_msg or "already exists" in error_msg:
                    print("✅ project_id column already exists")
                else:
                    print(f"⚠️ Could not add project_id column: {e}")
                    return False
        else:
            print("✅ project_id column already exists")
        
        # Verify columns exist
        cursor.execute("PRAGMA table_info(agents)")
        final_columns = [col[1] for col in cursor.fetchall()]
        has_tenant_id = "tenant_id" in final_columns
        has_project_id = "project_id" in final_columns
        
        conn.close()
        
        if has_tenant_id and has_project_id:
            print("✅ Database schema fix complete - both columns verified")
            return True
        else:
            print(f"⚠️ Schema fix incomplete - tenant_id: {has_tenant_id}, project_id: {has_project_id}")
            return False
        
    except Exception as e:
        print(f"❌ Error fixing database columns: {e}")
        import traceback
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = fix_database_columns()
    sys.exit(0 if success else 1)

