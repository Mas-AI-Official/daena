"""
Migration script to add department_id column to agents table.

This migration adds the department_id foreign key column if it doesn't exist.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database import engine, Agent, Department
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def migrate_add_department_id():
    """Add department_id column if it doesn't exist and populate it."""
    session = SessionLocal()
    
    try:
        # Check if column exists using raw SQL
        result = session.execute(text("PRAGMA table_info(agents)"))
        column_names = [row[1] for row in result.fetchall()]
        
        if "department_id" not in column_names:
            print("Adding department_id column to agents table...")
            
            # Add column
            session.execute(text("ALTER TABLE agents ADD COLUMN department_id INTEGER"))
            session.commit()
            
            print("Column added successfully.")
        else:
            print("Column department_id already exists.")
        
        # Populate department_id for existing agents using raw SQL
        print("Populating department_id for existing agents...")
        
        # Use raw SQL to avoid ORM column issues
        result = session.execute(text("""
            UPDATE agents 
            SET department_id = (
                SELECT id FROM departments 
                WHERE departments.slug = agents.department
            )
            WHERE department IS NOT NULL AND department_id IS NULL
        """))
        updated = result.rowcount
        session.commit()
        print(f"Updated {updated} agents with department_id.")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = migrate_add_department_id()
    sys.exit(0 if success else 1)

