#!/usr/bin/env python3
"""
Database Initialization Script for Daena AI System
Creates the database schema and seeds it with the 8×6 structure (8 departments × 6 agents = 48 total)
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from database import Base, engine, Department, Agent, CellAdjacency
from sqlalchemy.orm import sessionmaker
from config.constants import (
    MAX_AGENTS_PER_DEPARTMENT, 
    TOTAL_DEPARTMENTS, 
    MAX_TOTAL_AGENTS,
    DEPARTMENT_NAMES,
    DEPARTMENT_DISPLAY_NAMES,
    AGENT_ROLES
)

async def init_database():
    """Initialize the database with proper schema."""
    print("🚀 Initializing Daena AI Database...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database schema created")
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        # Clear existing data
        session.query(Agent).delete()
        session.query(Department).delete()
        session.query(CellAdjacency).delete()
        session.commit()
        print("✅ Existing data cleared")
        
        # Create departments
        print(f"🏢 Creating {TOTAL_DEPARTMENTS} departments...")
        departments = {}
        
        for i, dept_slug in enumerate(DEPARTMENT_NAMES):
            dept = Department(
                slug=dept_slug,
                name=DEPARTMENT_DISPLAY_NAMES[dept_slug],
                description=f"Department responsible for {dept_slug} operations",
                color=f"#{hash(dept_slug) % 0xFFFFFF:06x}",  # Generate unique color
                sunflower_index=i + 1,
                cell_id=f"D{i+1:02d}",
                status="active"
            )
            session.add(dept)
            departments[dept_slug] = dept
        
        session.commit()
        print(f"✅ {len(departments)} departments created")
        
        # Create agents for each department
        print(f"🤖 Creating {MAX_AGENTS_PER_DEPARTMENT} agents per department...")
        total_agents = 0
        
        for dept_slug, dept in departments.items():
            print(f"  📍 Creating agents for {dept_slug}...")
            
            for i, role in enumerate(AGENT_ROLES):
                agent_id = f"{dept_slug}_{role}"
                agent_name = f"{role.replace('_', ' ').title()} - {dept.name}"
                
                # Generate unique cell_id
                cell_id = f"A{dept.sunflower_index:02d}{i+1:02d}"
                
                agent = Agent(
                    name=agent_name,
                    role=role,
                    department=dept_slug,
                    department_id=dept.id,
                    status="active",
                    type="advisor" if "advisor" in role else "specialist",
                    capabilities=f"Specialized in {role} functions for {dept.name}",
                    description=f"{role} agent for {dept.name} department",
                    sunflower_index=dept.sunflower_index * 100 + i + 1,
                    cell_id=cell_id,
                    is_active=True
                )
                session.add(agent)
                total_agents += 1
                print(f"    ✅ Created {agent_id}")
        
        session.commit()
        print(f"✅ {total_agents} agents created")
        
        # Create adjacency relationships
        print("🍯 Creating adjacency relationships...")
        for dept in departments.values():
            # Create adjacency between department and its agents
            for agent in session.query(Agent).filter(Agent.department == dept.slug).all():
                adj = CellAdjacency(
                    cell_id=dept.cell_id,
                    neighbor_id=agent.cell_id,
                    distance=1.0,
                    relationship_type="parent"
                )
                session.add(adj)
                
                # Create adjacency between agents in same department
                for other_agent in session.query(Agent).filter(Agent.department == dept.slug).all():
                    if agent.id != other_agent.id:
                        adj = CellAdjacency(
                            cell_id=agent.cell_id,
                            neighbor_id=other_agent.cell_id,
                            distance=1.0,
                            relationship_type="neighbor"
                        )
                        session.add(adj)
        
        session.commit()
        print("✅ Adjacency relationships created")
        
        # Verify the data
        dept_count = session.query(Department).count()
        agent_count = session.query(Agent).count()
        adj_count = session.query(CellAdjacency).count()
        
        print(f"\n🎯 Database Initialization Complete!")
        print(f"   Departments: {dept_count}")
        print(f"   Agents: {agent_count}")
        print(f"   Adjacency Relationships: {adj_count}")
        
        # Show agents per department
        print(f"\n📊 Agents per Department:")
        for dept in departments.values():
            agent_count = session.query(Agent).filter(Agent.department == dept.slug).count()
            print(f"   {dept.name}: {agent_count} agents")
        
    except Exception as e:
        print(f"❌ Error during database initialization: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(init_database()) 