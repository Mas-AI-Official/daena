#!/usr/bin/env python3
"""
Fix Department Structure and Sync Issues
=======================================

This script fixes the broken department structure by:
1. Replacing d1, d2, d3... with proper named departments
2. Fixing agent roles to use the new 8-role canon
3. Ensuring proper sync between backend and frontend
4. Fixing the cell_id conflicts
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from database import get_db, create_tables
from database import Department, Agent, CellAdjacency
from sqlalchemy.orm import Session
from sqlalchemy import text
import datetime

# Proper department structure that matches frontend expectations
DEPARTMENTS = [
    {
        "slug": "hr",
        "name": "Human Resources",
        "description": "People management, recruitment, and organizational development",
        "color": "#FF6B6B",
        "sunflower_index": 1,
        "cell_id": "HR"
    },
    {
        "slug": "customer",
        "name": "Customer Success",
        "description": "Customer support, satisfaction, and relationship management",
        "color": "#4ECDC4",
        "sunflower_index": 2,
        "cell_id": "CS"
    },
    {
        "slug": "legal",
        "name": "Legal & Compliance",
        "description": "Legal affairs, regulatory compliance, and risk management",
        "color": "#9B59B6",
        "sunflower_index": 3,
        "cell_id": "LG"
    },
    {
        "slug": "finance",
        "name": "Finance & Accounting",
        "description": "Financial planning, accounting, and investment management",
        "color": "#3498DB",
        "sunflower_index": 4,
        "cell_id": "FN"
    },
    {
        "slug": "marketing",
        "name": "Marketing & Brand",
        "description": "Brand management, marketing campaigns, and market research",
        "color": "#F39C12",
        "sunflower_index": 5,
        "cell_id": "MK"
    },
    {
        "slug": "sales",
        "name": "Sales & Business Development",
        "description": "Sales operations, business development, and revenue growth",
        "color": "#2ECC71",
        "sunflower_index": 6,
        "cell_id": "SL"
    },
    {
        "slug": "product",
        "name": "Product & Innovation",
        "description": "Product development, innovation, and technology strategy",
        "color": "#E74C3C",
        "sunflower_index": 7,
        "cell_id": "PD"
    },
    {
        "slug": "engineering",
        "name": "Engineering & Technology",
        "description": "Software development, infrastructure, and technical operations",
        "color": "#34495E",
        "sunflower_index": 8,
        "cell_id": "EN"
    }
]

# New 8-role canon for each department
AGENT_ROLES = [
    "advisor_a",      # Senior Advisor
    "advisor_b",      # Strategy Advisor  
    "advisor_c",      # Technical Advisor
    "scout_internal", # Internal Scout
    "scout_external", # External Scout
    "synth",          # Knowledge Synthesizer
    "executor",       # Action Executor
    "border"          # Cross-department Bridge
]

# Council domains
COUNCIL_DOMAINS = [
    {"domain": "market", "title": "Market Intelligence Council"},
    {"domain": "finance", "title": "Financial Strategy Council"},
    {"domain": "security", "title": "Security & Compliance Council"},
    {"domain": "technology", "title": "Technology Innovation Council"},
    {"domain": "operations", "title": "Operational Excellence Council"}
]

async def fix_departments(session: Session):
    """Fix department structure to use proper names instead of d1, d2, d3..."""
    print("🔧 Fixing department structure...")
    
    # First, clear old departments
    session.query(Department).delete()
    session.query(CellAdjacency).delete()
    
    # Create new departments with proper names
    for dept_data in DEPARTMENTS:
        dept = Department(
            slug=dept_data["slug"],
            name=dept_data["name"],
            description=dept_data["description"],
            color=dept_data["color"],
            sunflower_index=dept_data["sunflower_index"],
            cell_id=dept_data["cell_id"],
            status="active"
        )
        session.add(dept)
        print(f"  ✅ Created department: {dept_data['name']} ({dept_data['slug']})")
    
    session.commit()
    print(f"  🎯 {len(DEPARTMENTS)} departments created")
    return session.query(Department).all()

async def fix_agents(session: Session):
    """Fix agent structure with proper roles and department assignments"""
    print("🤖 Fixing agent structure...")
    
    # Clear old agents
    session.query(Agent).delete()
    
    total_agents = 0
    
    for dept_data in DEPARTMENTS:
        print(f"  📍 Creating agents for {dept_data['name']}...")
        
        for i, role in enumerate(AGENT_ROLES):
            # Create descriptive names based on role canon
            role_display_names = {
                "advisor_a": f"Senior Advisor {dept_data['name']}",
                "advisor_b": f"Strategy Advisor {dept_data['name']}",
                "advisor_c": f"Technical Advisor {dept_data['name']}",
                "scout_internal": f"Internal Scout {dept_data['name']}",
                "scout_external": f"External Scout {dept_data['name']}",
                "synth": f"Knowledge Synthesizer {dept_data['name']}",
                "executor": f"Action Executor {dept_data['name']}",
                "border": f"Border Bridge {dept_data['name']}"
            }
            
            agent_name = role_display_names.get(role, f"{role.title()} {dept_data['name']}")
            
            # Generate unique cell_id
            cell_id = f"{dept_data['cell_id']}{i+1:02d}"
            
            agent = Agent(
                name=agent_name,
                role=role,
                department=dept_data["slug"],
                status="active",
                type="department",
                capabilities=f"Specialized in {role} functions for {dept_data['name']}",
                description=f"{role} for {dept_data['name']}",
                sunflower_index=dept_data["sunflower_index"] * 10 + i + 1,
                cell_id=cell_id
            )
            session.add(agent)
            total_agents += 1
            
            print(f"    ✅ Created agent: {agent_name} ({role})")
        
        session.commit()
    
    print(f"  🎯 {total_agents} agents created")
    return total_agents

async def fix_adjacency(session: Session):
    """Fix honeycomb adjacency relationships"""
    print("🍯 Fixing honeycomb adjacency...")
    
    # Clear old adjacency
    session.query(CellAdjacency).delete()
    
    # Create new adjacency based on department cell_ids
    depts = session.query(Department).all()
    cell_ids = [dept.cell_id for dept in depts]
    
    total_adjacencies = 0
    
    for i, cell_id in enumerate(cell_ids):
        # Create 6 neighbor relationships (honeycomb structure)
        for offset in [-3, -2, -1, 1, 2, 3]:
            neighbor_index = (i + offset) % len(cell_ids)
            neighbor_id = cell_ids[neighbor_index]
            
            # Calculate distance (simple for now)
            distance = abs(offset)
            
            adjacency = CellAdjacency(
                cell_id=cell_id,
                neighbor_id=neighbor_id,
                distance=distance,
                relationship_type="neighbor"
            )
            session.add(adjacency)
            total_adjacencies += 1
    
    session.commit()
    print(f"  🎯 {total_adjacencies} adjacency relationships created")
    
    # Show sample adjacency
    print("🍯 Sample adjacency (first 3 cells):")
    for i, cell_id in enumerate(cell_ids[:3]):
        neighbors = session.query(CellAdjacency).filter(CellAdjacency.cell_id == cell_id).all()
        neighbor_ids = [n.neighbor_id for n in neighbors]
        print(f"   {cell_id}: {neighbor_ids}")

async def create_council(session: Session):
    """Create council members for each domain"""
    print("👑 Creating Council of 5 per domain...")
    
    total_council = 0
    
    for domain_data in COUNCIL_DOMAINS:
        print(f"  📍 Creating {domain_data['domain']} council...")
        
        for seat in range(1, 6):
            council_id = f"council_{domain_data['domain']}_{seat}"
            council_name = f"Council Member {seat} - {domain_data['title']}"
            
            # Generate unique cell_id for council
            cell_id = f"C{domain_data['domain'][:2].upper()}{seat}"
            
            council_agent = Agent(
                name=council_name,
                role="council",
                department=f"council_{domain_data['domain']}",
                status="active",
                type="council",
                capabilities=f"Council expertise for {domain_data['title']}",
                description=f"Council member for {domain_data['title']}",
                sunflower_index=900 + total_council,
                cell_id=cell_id
            )
            session.add(council_agent)
            total_council += 1
            
            print(f"    ✅ Created council member: {council_name}")
        
        session.commit()
    
    print(f"  🎯 {total_council} council members created")
    return total_council

async def verify_fix(session: Session):
    """Verify that the fix worked correctly"""
    print("🔍 Verifying fix...")
    
    # Check departments
    depts = session.query(Department).all()
    print(f"  📊 Departments: {len(depts)}")
    for dept in depts:
        print(f"    - {dept.name} ({dept.slug}): {dept.cell_id}")
    
    # Check agents
    agents = session.query(Agent).all()
    print(f"  📊 Total Agents: {len(agents)}")
    
    # Check by department
    for dept in depts:
        dept_agents = session.query(Agent).filter(Agent.department == dept.slug).all()
        print(f"    - {dept.name}: {len(dept_agents)} agents")
    
    # Check council
    council_agents = session.query(Agent).filter(Agent.type == "council").all()
    print(f"  📊 Council Members: {len(council_agents)}")
    
    # Check adjacency
    adjacencies = session.query(CellAdjacency).all()
    print(f"  📊 Adjacencies: {len(adjacencies)}")
    
    return True

async def main():
    """Main function to fix the department structure"""
    print("🚀 Starting Department Structure Fix...")
    print("=" * 50)
    
    # Create tables if they don't exist
    create_tables()
    
    # Get database session
    db_gen = get_db()
    session = next(db_gen)
    
    try:
        # Fix departments
        await fix_departments(session)
        
        # Fix agents
        await fix_agents(session)
        
        # Fix adjacency
        await fix_adjacency(session)
        
        # Create council
        await create_council(session)
        
        # Verify fix
        await verify_fix(session)
        
        print("\n🎉 Department structure fix completed successfully!")
        print("=" * 50)
        print("📊 Final Summary:")
        print(f"   Departments: {len(DEPARTMENTS)}")
        print(f"   Agents per Department: {len(AGENT_ROLES)}")
        print(f"   Total Department Agents: {len(DEPARTMENTS) * len(AGENT_ROLES)}")
        print(f"   Council Members: {len(COUNCIL_DOMAINS) * 5}")
        print(f"   Total Agents: {len(DEPARTMENTS) * len(AGENT_ROLES) + len(COUNCIL_DOMAINS) * 5}")
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(main()) 