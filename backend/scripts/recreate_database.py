"""
Recreate database with proper schema.

This script drops and recreates all tables to ensure schema matches the models.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from database import engine, Base

def recreate_database():
    """Drop and recreate all tables."""
    print("Dropping all existing tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating all tables with proper schema...")
    Base.metadata.create_all(bind=engine)
    
    print("Database recreated successfully!")
    return True

if __name__ == "__main__":
    success = recreate_database()
    sys.exit(0 if success else 1)

