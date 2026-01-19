#!/usr/bin/env python3
"""
Debug script for sunflower registry initialization
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

def test_sunflower_init():
    """Test sunflower registry initialization step by step."""
    print("🔍 Testing Sunflower Registry Initialization...")
    
    try:
        # Step 1: Import modules
        print("📦 Step 1: Importing modules...")
        from utils.sunflower_registry import sunflower_registry
        from database import get_db, Department, Agent
        print("✅ Modules imported successfully")
        
        # Step 2: Get database session
        print("🗄️ Step 2: Getting database session...")
        db = next(get_db())
        print("✅ Database session obtained")
        
        # Step 3: Check database state
        print("📊 Step 3: Checking database state...")
        dept_count = db.query(Department).count()
        agent_count = db.query(Agent).count()
        print(f"   Departments: {dept_count}")
        print(f"   Agents: {agent_count}")
        
        # Step 4: Check a few records
        print("🔍 Step 4: Checking sample records...")
        depts = db.query(Department).limit(3).all()
        agents = db.query(Agent).limit(3).all()
        
        print("   Sample departments:")
        for dept in depts:
            print(f"     - {dept.slug}: {dept.name} (index: {dept.sunflower_index})")
        
        print("   Sample agents:")
        for agent in agents:
            print(f"     - {agent.name}: {agent.role} in {agent.department} (index: {agent.sunflower_index})")
        
        # Step 5: Test sunflower registry population
        print("🌻 Step 5: Testing sunflower registry population...")
        print(f"   Before population: {len(sunflower_registry.departments)} depts, {len(sunflower_registry.agents)} agents")
        
        sunflower_registry.populate_from_database(db)
        
        print(f"   After population: {len(sunflower_registry.departments)} depts, {len(sunflower_registry.agents)} agents")
        
        # Step 6: Check registry contents
        print("🔍 Step 6: Checking registry contents...")
        print("   Departments in registry:")
        for dept_id, dept_data in sunflower_registry.departments.items():
            print(f"     - {dept_id}: {dept_data['name']}")
        
        print("   Agents in registry:")
        for agent_id, agent_data in sunflower_registry.agents.items():
            print(f"     - {agent_id}: {agent_data['name']} in {agent_data['department_id']}")
        
        print("✅ Sunflower registry test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during sunflower registry test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sunflower_init() 