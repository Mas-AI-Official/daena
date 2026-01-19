#!/usr/bin/env python3
"""
Test script to debug sunflower registry population
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from database import get_db, Department, Agent
from utils.sunflower_registry import sunflower_registry

def test_registry_population():
    """Test the sunflower registry population."""
    print("🔍 Testing Sunflower Registry Population...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Check database state
        dept_count = db.query(Department).count()
        agent_count = db.query(Agent).count()
        
        print(f"📊 Database State:")
        print(f"   Departments: {dept_count}")
        print(f"   Agents: {agent_count}")
        
        # Check a few agents
        agents = db.query(Agent).limit(5).all()
        print(f"\n🔍 Sample Agents:")
        for agent in agents:
            print(f"   {agent.name}: dept='{agent.department}', dept_id={agent.department_id}")
        
        # Check departments
        depts = db.query(Department).all()
        print(f"\n🏢 Departments:")
        for dept in depts:
            print(f"   {dept.name} ({dept.slug}): index={dept.sunflower_index}, cell_id={dept.cell_id}")
        
        # Try to populate registry
        print(f"\n🔄 Populating Sunflower Registry...")
        sunflower_registry.populate_from_database(db)
        
        print(f"\n📊 Registry State After Population:")
        print(f"   Departments: {len(sunflower_registry.departments)}")
        print(f"   Agents: {len(sunflower_registry.agents)}")
        
        # Check what's in the registry
        if sunflower_registry.departments:
            print(f"\n🏢 Registry Departments:")
            for dept_id, dept_data in sunflower_registry.departments.items():
                print(f"   {dept_id}: {dept_data['name']} - {len(dept_data['agents'])} agents")
        
        if sunflower_registry.agents:
            print(f"\n🤖 Registry Agents (first 5):")
            for i, (agent_id, agent_data) in enumerate(sunflower_registry.agents.items()):
                if i >= 5:
                    break
                print(f"   {agent_id}: {agent_data['name']} - {agent_data['department_id']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_registry_population() 