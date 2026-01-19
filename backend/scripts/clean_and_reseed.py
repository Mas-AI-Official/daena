#!/usr/bin/env python3
"""
Clean and re-seed the database to fix integrity issues
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from database import engine, Base, Department, Agent, CellAdjacency
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def clean_database():
    """Clean all data from the database"""
    print("🧹 Cleaning database...")
    
    session = SessionLocal()
    try:
        # Delete all data in correct order (respecting foreign keys)
        session.execute(text("DELETE FROM cell_adjacency"))
        session.execute(text("DELETE FROM agents"))
        session.execute(text("DELETE FROM departments"))
        
        # Reset auto-increment counters
        session.execute(text("DELETE FROM sqlite_sequence WHERE name IN ('departments', 'agents', 'cell_adjacency')"))
        
        session.commit()
        print("✅ Database cleaned successfully")
        
    except Exception as e:
        print(f"❌ Error cleaning database: {e}")
        session.rollback()
        raise
    finally:
        session.close()

async def main():
    """Main function to clean and re-seed"""
    print("🚀 Starting database cleanup and re-seeding...")
    
    try:
        # Clean the database
        await clean_database()
        
        print("\n🎯 Database cleaned. Now run the seeding script:")
        print("   python scripts/seed_6x8_council.py")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 