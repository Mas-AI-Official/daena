"""Seed script for 8×6 structure with Sunflower coordinates (8 departments × 6 agents = 48)."""
import asyncio
import sys
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Ensure Windows console doesn't crash on UTF-8/emoji output from sub-scripts
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Add project root to path (so we can import backend.database)
backend_path = Path(__file__).parent.parent
project_root = backend_path.parent
sys.path.append(str(project_root))

from backend.database import engine, Base, Department, Agent, CellAdjacency

from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from backend.utils.sunflower_registry import sunflower_registry

# Fix database schema before seeding
def fix_database_schema(session):
    """Ensure required columns exist in agents table"""
    try:
        # First, try to run the dedicated migration script
        try:
            import sys
            import os
            scripts_dir = os.path.join(os.path.dirname(__file__))
            sys.path.insert(0, scripts_dir)
            from fix_tenant_id_column import fix_database_columns
            if fix_database_columns():
                print("OK: Database schema fixed via migration script")
                return
        except Exception as migration_error:
            logger.warning(f"Could not run migration script: {migration_error}")
        
        # Fallback: Try direct SQL
        # Check existing columns
        result = session.execute(text("PRAGMA table_info(agents)"))
        columns = [row[1] for row in result]
        
        # Add tenant_id if missing
        if "tenant_id" not in columns:
            try:
                session.execute(text("ALTER TABLE agents ADD COLUMN tenant_id INTEGER"))
                session.commit()
                print("OK: Added tenant_id column")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    print(f"WARNING: Could not add tenant_id: {e}")
        
        # Add project_id if missing
        if "project_id" not in columns:
            try:
                session.execute(text("ALTER TABLE agents ADD COLUMN project_id INTEGER"))
                session.commit()
                print("OK: Added project_id column")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    print(f"WARNING: Could not add project_id: {e}")
    except Exception as e:
        print(f"WARNING: Error checking database schema: {e}")
from backend.config.council_config import COUNCIL_CONFIG

# Use canonical config as single source of truth
MAX_AGENTS_PER_DEPARTMENT = COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT
TOTAL_DEPARTMENTS = COUNCIL_CONFIG.TOTAL_DEPARTMENTS
MAX_TOTAL_AGENTS = COUNCIL_CONFIG.TOTAL_AGENTS
DEPARTMENT_NAMES = list(COUNCIL_CONFIG.DEPARTMENT_SLUGS)
DEPARTMENT_DISPLAY_NAMES = COUNCIL_CONFIG.DEPARTMENT_NAMES
AGENT_ROLES = list(COUNCIL_CONFIG.AGENT_ROLES)

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 8×6 Structure (8 departments × 6 agents)
DEPARTMENTS = [
    {
        "slug": "engineering",
        "name": "Engineering & Technology",
        "description": "Software development, AI/ML, cloud infrastructure, and technical innovation",
        "color": "#0066cc",
        "sunflower_index": 1
    },
    {
        "slug": "product", 
        "name": "Product & Innovation",
        "description": "Product strategy, UX/UI design, innovation management, and user research",
        "color": "#8b5cf6",
        "sunflower_index": 2
    },
    {
        "slug": "sales",
        "name": "Sales & Business Development",
        "description": "Sales strategy, customer acquisition, revenue optimization, and market expansion",
        "color": "#10b981",
        "sunflower_index": 3
    },
    {
        "slug": "marketing",
        "name": "Marketing & Brand",
        "description": "Brand strategy, digital marketing, growth hacking, and market positioning",
        "color": "#f59e0b",
        "sunflower_index": 4
    },
    {
        "slug": "finance",
        "name": "Finance & Accounting",
        "description": "Financial planning, budgeting, operations management, and strategic planning",
        "color": "#ef4444",
        "sunflower_index": 5
    },
    {
        "slug": "hr",
        "name": "Human Resources",
        "description": "Talent acquisition, employee development, culture building, and organizational design",
        "color": "#ec4899",
        "sunflower_index": 6
    },
    {
        "slug": "legal",
        "name": "Legal & Compliance",
        "description": "Legal counsel, regulatory compliance, risk management, and corporate governance",
        "color": "#8b5a2b",
        "sunflower_index": 7
    },
    {
        "slug": "customer",
        "name": "Customer Success",
        "description": "Customer support, success management, and relationship building",
        "color": "#6366f1",
        "sunflower_index": 8
    }
]

# Agent roles are now defined in COUNCIL_CONFIG (single source of truth)
# Use AGENT_ROLES from constants (which imports from COUNCIL_CONFIG)

async def seed_departments(session):
    """Seed departments with sunflower coordinates."""
    print("Seeding departments with sunflower coordinates...")
    
    # Create regular departments only (8 total for 8×6 structure: 8 departments × 6 agents)
    for dept_data in DEPARTMENTS:
        # Check if department already exists by slug OR sunflower_index
        existing = session.query(Department).filter(
            (Department.slug == dept_data["slug"]) | 
            (Department.sunflower_index == dept_data["sunflower_index"])
        ).first()
        
        if existing:
            print(f"  WARNING: Department {dept_data['slug']} already exists, checking for conflicts...")
            
            # Check if updating the name would cause a conflict
            name_conflict = session.query(Department).filter(
                Department.name == dept_data["name"],
                Department.id != existing.id
            ).first()
            
            if name_conflict:
                print(f"    WARNING: Name '{dept_data['name']}' already exists in another department, skipping name update")
                # Only update non-conflicting fields
                existing.description = dept_data["description"]
                existing.color = dept_data["color"]
                existing.cell_id = f"D{dept_data['sunflower_index']}"
                existing.status = "active"
            else:
                print(f"    OK: Updating department {dept_data['slug']}...")
                # Safe to update all fields
                existing.name = dept_data["name"]
                existing.description = dept_data["description"]
                existing.color = dept_data["color"]
                existing.cell_id = f"D{dept_data['sunflower_index']}"
                existing.status = "active"
            
            # Don't update sunflower_index if it's different to avoid constraint violations
        else:
            print(f"  OK: Creating department {dept_data['slug']}...")
            dept = Department(
                slug=dept_data["slug"],
                name=dept_data["name"],
                description=dept_data["description"],
                color=dept_data["color"],
                sunflower_index=dept_data["sunflower_index"],
                cell_id=f"D{dept_data['sunflower_index']}"
            )
            session.add(dept)
            
    session.commit()
    print(f"  OK: {len(DEPARTMENTS)} departments seeded")

async def seed_agents(session):
    """Seed agents for each department."""
    print("Seeding agents with sunflower coordinates...")
    
    total_agents = 0
    
    for dept_data in DEPARTMENTS:
        dept = session.query(Department).filter(Department.slug == dept_data["slug"]).first()
        if not dept:
            print(f"  ERROR: Department {dept_data['slug']} not found, skipping agents")
            continue
            
        print(f"  Seeding agents for {dept_data['slug']}...")
        
        for i, role in enumerate(AGENT_ROLES):
            agent_id = f"{dept_data['slug']}_{role}"
            
            # Create descriptive names based on role canon
            role_display_names = {
                "advisor_a": f"Senior Advisor {dept_data['name'].split('&')[0].strip()}",
                "advisor_b": f"Strategy Advisor {dept_data['name'].split('&')[0].strip()}",
                "advisor_c": f"Technical Advisor {dept_data['name'].split('&')[0].strip()}",
                "scout_internal": f"Internal Scout {dept_data['name'].split('&')[0].strip()}",
                "scout_external": f"External Scout {dept_data['name'].split('&')[0].strip()}",
                "synth": f"Knowledge Synthesizer {dept_data['name'].split('&')[0].strip()}",
                "executor": f"Action Executor {dept_data['name'].split('&')[0].strip()}",
                "border": f"Border Bridge {dept_data['name'].split('&')[0].strip()}"
            }
            
            agent_name = role_display_names.get(role, f"{role.title()} {dept_data['name'].split('&')[0].strip()}")
            
            # Check if agent already exists by role (not cell_id for idempotency)
            existing = session.query(Agent).filter(
                Agent.role == role,
                Agent.department == dept_data["slug"]
            ).first()
            
            # Generate unique cell_id
            cell_id = f"A{dept_data['sunflower_index']}{i+1}"
            
            # Check if cell_id is already taken by another agent
            cell_conflict = session.query(Agent).filter(Agent.cell_id == cell_id).first()
            if cell_conflict and cell_conflict.id != (existing.id if existing else None):
                # Generate alternative cell_id
                cell_id = f"A{dept_data['sunflower_index']}{i+1}_{role[:3]}"
            
            if existing:
                print(f"    WARNING: Agent {agent_id} already exists, updating...")
                existing.name = agent_name
                existing.status = "active"
                existing.capabilities = f"Specialized in {role} functions"
                existing.description = f"{role} for {dept_data['name']}"
                existing.sunflower_index = dept_data["sunflower_index"] * 10 + i + 1
                existing.cell_id = cell_id
                existing.department_id = dept.id
                existing.is_active = True
            else:
                print(f"    OK: Creating agent {agent_id}...")
                agent = Agent(
                    name=agent_name,
                    role=role,
                    department=dept_data["slug"],
                    department_id=dept.id,
                    status="active",
                    type="advisor" if "advisor" in role else "specialist",
                    capabilities=f"Specialized in {role} functions",
                    description=f"{role} for {dept_data['name']}",
                    sunflower_index=dept_data["sunflower_index"] * 10 + i + 1,
                    cell_id=cell_id
                )
                session.add(agent)
                
            total_agents += 1
    
    session.commit()
    print(f"  OK: {total_agents} agents seeded")


def prune_duplicate_department_agents(session):
    """
    Enforce canonical 8×6 department agents by removing duplicates.

    Keeps at most ONE agent per (department, role) for the 8 departments.
    """
    dept_slugs = [d["slug"] for d in DEPARTMENTS]
    roles = list(AGENT_ROLES)

    removed = 0
    for dept_slug in dept_slugs:
        for role in roles:
            agents = (
                session.query(Agent)
                .filter(Agent.department == dept_slug, Agent.role == role)
                .order_by(Agent.id.asc())
                .all()
            )
            if len(agents) <= 1:
                continue
            for extra in agents[1:]:
                session.delete(extra)
                removed += 1

    if removed:
        session.commit()
    print(f"Prune duplicates: removed {removed} extra department agents")

async def seed_adjacency(session):
    """Seed adjacency relationships."""
    print("Seeding honeycomb adjacency relationships...")
    
    # Clear existing adjacency
    session.query(CellAdjacency).delete()
    
    # Rebuild adjacency in registry (registry should be populated from DB first)
    sunflower_registry.rebuild_adjacency()
    adjacency = sunflower_registry.adjacency_cache
    
    # Store in database
    for cell_id, neighbors in adjacency.items():
        for neighbor_id in neighbors:
            adj = CellAdjacency(
                cell_id=cell_id,
                neighbor_id=neighbor_id,
                distance=1.0,  # Default distance
                relationship_type="neighbor"
            )
            session.add(adj)
    
    session.commit()
    print(f"  OK: {len(adjacency)} adjacency relationships seeded")

async def seed_council(session):
    """Seed Council of 5 per domain."""
    print("Seeding Council of 5 per domain...")
    
    # Council domains based on department functions
    council_domains = [
        {"domain": "market", "title": "Market Intelligence Council", "expertise": ["market_analysis", "competitive_intelligence", "trend_forecasting"]},
        {"domain": "finance", "title": "Financial Strategy Council", "expertise": ["financial_planning", "investment_strategy", "risk_management"]},
        {"domain": "security", "title": "Security & Compliance Council", "expertise": ["cybersecurity", "regulatory_compliance", "risk_assessment"]},
        {"domain": "technology", "title": "Technology Innovation Council", "expertise": ["ai_ml", "cloud_infrastructure", "digital_transformation"]},
        {"domain": "operations", "title": "Operational Excellence Council", "expertise": ["process_optimization", "quality_management", "efficiency_improvement"]}
    ]
    
    total_council = 0
    
    for domain_data in council_domains:
        print(f"  Seeding {domain_data['domain']} council...")
        
        for seat in range(1, 6):  # 5 seats per domain
            council_id = f"council_{domain_data['domain']}_{seat}"
            council_name = f"Council Member {seat} - {domain_data['title']}"
            
            # Check if council member already exists
            existing = session.query(Agent).filter(
                Agent.role == "council",
                Agent.department == f"council_{domain_data['domain']}"
            ).first()
            
            if existing:
                print(f"    WARNING: Council member {council_id} already exists, updating...")
                existing.name = council_name
                existing.capabilities = f"Council expertise: {', '.join(domain_data['expertise'])}"
                existing.description = f"Council member for {domain_data['title']}"
                existing.sunflower_index = 900 + total_council  # Council gets 900+ indices
                existing.cell_id = f"C{domain_data['domain'][:2].upper()}{seat}"
            else:
                print(f"    ✅ Creating council member {council_id}...")
                council_agent = Agent(
                    name=council_name,
                    role="council",
                    department=f"council_{domain_data['domain']}",
                    status="active",
                    type="council",
                    capabilities=f"Council expertise: {', '.join(domain_data['expertise'])}",
                    description=f"Council member for {domain_data['title']}",
                    sunflower_index=900 + total_council,
                    cell_id=f"C{domain_data['domain'][:2].upper()}{seat}"
                )
                session.add(council_agent)
            
            # Register in sunflower registry
            try:
                sunflower_registry.register_agent(
                    council_id,
                    council_name,
                    "council",
                    f"council_{domain_data['domain']}",
                    900 + total_council
                )
            except ValueError as e:
                print(f"      WARNING: Sunflower registry: {e}")
            
            total_council += 1
    
    session.commit()
    print(f"  OK: {total_council} council members seeded")

async def main():
    """Main seeding function."""
    print(f"Starting {TOTAL_DEPARTMENTS}x{MAX_AGENTS_PER_DEPARTMENT} seeding (8×6)...")
    print(f"Target: {MAX_TOTAL_AGENTS} total agents across {TOTAL_DEPARTMENTS} departments")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    
    # Fix database schema first
    fix_database_schema(session)
    
    try:
        await seed_departments(session)
        await seed_agents(session)
        prune_duplicate_department_agents(session)
        # Sync registry from DB (single source of truth), then compute adjacency
        sunflower_registry.populate_from_database(session)
        await seed_adjacency(session)
        # Removed council seeding - we only want 8 departments with 6 agents each
        
        # Verify counts
        dept_count = session.query(Department).count()
        agent_count = session.query(Agent).count()
        adj_count = session.query(CellAdjacency).count()
        
        print("\nSeeding completed successfully!")
        print(f"Final counts:")
        print(f"   Departments: {dept_count}/{TOTAL_DEPARTMENTS}")
        print(f"   Agents: {agent_count}/{MAX_TOTAL_AGENTS}")
        print(f"   Adjacencies: {adj_count}")
        
        # Show sample adjacency
        print(f"\nSample adjacency (first 3 cells):")
        sample_adj = list(sunflower_registry.adjacency_cache.items())[:3]
        for cell_id, neighbors in sample_adj:
            print(f"   {cell_id}: {neighbors}")
            
    except Exception as e:
        print(f"ERROR: Error during seeding: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(main()) 