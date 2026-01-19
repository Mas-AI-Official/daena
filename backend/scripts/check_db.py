#!/usr/bin/env python3
"""Check database contents."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, Department, Agent

def main():
    print("🔍 Checking Database Contents...")
    
    try:
        db = next(get_db())
        
        # Check departments
        dept_count = db.query(Department).count()
        print(f"📊 Departments: {dept_count}")
        
        # Check agents
        agent_count = db.query(Agent).count()
        print(f"🤖 Agents: {agent_count}")
        
        # List department names
        print("\n📋 Department Names:")
        departments = db.query(Department).all()
        for dept in departments:
            print(f"   - {dept.name} (slug: {dept.slug})")
        
        # List some agent names
        print(f"\n🤖 Sample Agents (first 10):")
        agents = db.query(Agent).limit(10).all()
        for agent in agents:
            print(f"   - {agent.name} ({agent.department})")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 