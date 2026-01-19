#!/usr/bin/env python3
"""
Initialize Sunflower Registry from Database
This script populates the sunflower registry with actual data from the database.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from database import engine, Base, Department, Agent
from sqlalchemy.orm import sessionmaker
from backend.utils.sunflower_registry import sunflower_registry

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def init_sunflower_registry():
    """Initialize the sunflower registry from database data."""
    print("🌻 Initializing Sunflower Registry from Database...")
    
    # Create database session
    session = SessionLocal()
    
    try:
        # Check if we have data in the database
        dept_count = session.query(Department).count()
        agent_count = session.query(Agent).count()
        
        print(f"📊 Database contains: {dept_count} departments, {agent_count} agents")
        
        if dept_count == 0 or agent_count == 0:
            print("⚠️  No data found in database. Please run the seeding script first.")
            return False
        
        # Populate sunflower registry from database
        sunflower_registry.populate_from_database(session)
        
        # Verify population
        final_dept_count = len(sunflower_registry.departments)
        final_agent_count = len(sunflower_registry.agents)
        
        print(f"✅ Sunflower Registry initialized successfully!")
        print(f"   Departments: {final_dept_count}")
        print(f"   Agents: {final_agent_count}")
        print(f"   Total Cells: {len(sunflower_registry.cells)}")
        
        # Show department details
        print("\n🏢 Department Details:")
        for dept_id, dept_data in sunflower_registry.departments.items():
            agent_count = len(dept_data["agents"])
            print(f"   {dept_data['name']}: {agent_count} agents")
        
        # Show Daena's structure info
        print("\n🤖 Daena's Structure Information:")
        structure_info = sunflower_registry.get_daena_structure_info()
        print(f"   Identity: {structure_info['daena_identity']['name']} - {structure_info['daena_identity']['title']}")
        print(f"   Company: {structure_info['daena_identity']['company']}")
        print(f"   Creator: {structure_info['daena_identity']['creator']}")
        print(f"   Architecture: {structure_info['daena_identity']['structure_type']}")
        print(f"   Root Directory: {structure_info['folder_structure']['root_directory']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error initializing sunflower registry: {e}")
        return False
        
    finally:
        session.close()

async def main():
    """Main function."""
    success = await init_sunflower_registry()
    
    if success:
        print("\n🎉 Sunflower Registry initialization completed successfully!")
        print("   Daena now has full knowledge of her structure and capabilities.")
    else:
        print("\n❌ Sunflower Registry initialization failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 