#!/usr/bin/env python3
"""
Fix Agent Count Script
This script ensures Daena reports the correct number of agents (48) instead of an incorrect smaller number.
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
from backend.config.council_config import COUNCIL_CONFIG

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def fix_agent_count():
    """Fix the agent count issue by properly populating the sunflower registry"""
    print("🔧 Fixing Agent Count Issue...")
    
    # Create database session
    session = SessionLocal()
    try:
        # First, let's check what's in the database
        departments = session.query(Department).all()
        agents = session.query(Agent).all()
        
        print(f"📊 Database Status:")
        print(f"   • Departments: {len(departments)}")
        print(f"   • Agents: {len(agents)}")
        
        # Clear the sunflower registry
        sunflower_registry.departments.clear()
        sunflower_registry.agents.clear()
        sunflower_registry.cells.clear()
        sunflower_registry.adjacency_cache.clear()
        
        print("🧹 Cleared sunflower registry")
        
        # Populate departments
        for dept in departments:
            sunflower_registry.register_department(dept.name, dept.description)
            print(f"   ✅ Registered department: {dept.name}")
        
        # Populate agents
        for agent in agents:
            sunflower_registry.register_agent(
                agent.agent_id,
                agent.name,
                agent.department_name,
                agent.role,
                agent.efficiency,
                agent.status,
                agent.last_active
            )
            print(f"   ✅ Registered agent: {agent.name} ({agent.department_name})")
        
        # Verify the count
        final_agent_count = len(sunflower_registry.agents)
        final_dept_count = len(sunflower_registry.departments)
        
        print(f"\n🎯 Final Registry Status:")
        print(f"   • Departments: {final_dept_count}")
        print(f"   • Agents: {final_agent_count}")
        
        expected_agents = COUNCIL_CONFIG.TOTAL_AGENTS
        if final_agent_count == expected_agents:
            print(f"✅ SUCCESS: Agent count is now {expected_agents}!")
        else:
            print(f"⚠️  WARNING: Agent count is {final_agent_count}, expected {expected_agents}")
            
        # Test the fallback response
        print("\n🧪 Testing Daena's Response...")
        
        # Simulate what Daena would say
        try:
            agent_count = len(sunflower_registry.agents)
            dept_count = len(sunflower_registry.departments)
            
            test_response = f"""As your AI VP, I'm currently overseeing our {dept_count}-department operation with {agent_count} active agents. Our company efficiency is at 92% with strong Q4 performance."""
            
            print(f"📝 Daena would now say: {test_response}")
            
        except Exception as e:
            print(f"❌ Error testing response: {e}")
        
        print("\n🔧 Agent count fix completed!")
        
    except Exception as e:
        print(f"❌ Error fixing agent count: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(fix_agent_count()) 