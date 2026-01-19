"""
Database Seeder - Seeds default departments, agents, and tasks
Runs on first startup or when reset is triggered
Includes HIDDEN departments (Chakra, Black Ops, Security, R&D Lab)
"""
import uuid
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# PUBLIC Department definitions with UNIQUE colors
DEPARTMENTS = [
    {"slug": "engineering", "name": "Engineering", "color": "#4169E1", "description": "Technical development and infrastructure", "hidden": False},
    {"slug": "product", "name": "Product", "color": "#9370DB", "description": "Product strategy and roadmap", "hidden": False},
    {"slug": "sales", "name": "Sales", "color": "#22C55E", "description": "Revenue and client acquisition", "hidden": False},
    {"slug": "marketing", "name": "Marketing", "color": "#FF6B6B", "description": "Brand, campaigns, and growth", "hidden": False},
    {"slug": "finance", "name": "Finance", "color": "#00CED1", "description": "Financial planning and accounting", "hidden": False},
    {"slug": "hr", "name": "HR", "color": "#E91E7F", "description": "People, culture, and talent", "hidden": False},
    {"slug": "legal", "name": "Legal", "color": "#8B5CF6", "description": "Compliance, contracts, and IP", "hidden": False},
    {"slug": "customer", "name": "Customer", "color": "#10B981", "description": "Customer success and support", "hidden": False},
]

# HIDDEN Departments (only visible in Founder Panel)
HIDDEN_DEPARTMENTS = [
    {"slug": "chakra", "name": "Chakra", "color": "#FF8C00", "description": "Spiritual intelligence and alignment center - manages organizational energy flow", "hidden": True, "icon": "fa-yin-yang"},
    {"slug": "blackops", "name": "Black Ops", "color": "#333333", "description": "Covert operations and competitive intelligence", "hidden": True, "icon": "fa-user-secret"},
    {"slug": "security", "name": "Security", "color": "#DC2626", "description": "Cybersecurity, threat detection, and system protection", "hidden": True, "icon": "fa-shield-alt"},
    {"slug": "rdlab", "name": "R&D Lab", "color": "#06B6D4", "description": "Advanced research, AI experiments, and innovation", "hidden": True, "icon": "fa-microscope"},
]

# Agent names per department (6 agents each)
AGENT_NAMES = {
    "engineering": ["Alex CodeMaster", "Emma BuildPro", "Noah DevOps", "Sophia TechLead", "Liam Backend", "Olivia Frontend"],
    "product": ["Ava Strategy", "Ethan Roadmap", "Mia ProductViz", "Lucas Innovator", "Amelia UXMaster", "Mason Metrics"],
    "sales": ["Morgan Closer", "Charlotte Deal", "Benjamin Revenue", "Harper Pipeline", "Logan ClientPro", "Ella Convert"],
    "marketing": ["DaVinci Creative", "Sofia Brand", "Jackson Campaign", "Aria Growth", "Carter SEO", "Layla Social"],
    "finance": ["Penny Wise", "Sebastian Budget", "Chloe Analytics", "Oliver Forecast", "Zoe Accounting", "Henry Capital"],
    "hr": ["Scarlett People", "Daniel Culture", "Grace Talent", "Matthew Recruiter", "Lily Learning", "Owen Benefits"],
    "legal": ["Sarah Shield", "William Contracts", "Victoria Compliance", "James Policy", "Hannah IP", "Ryan Risk"],
    "customer": ["Felix Support", "Evelyn Success", "Michael Advocate", "Abigail Solutions", "Alexander Helper", "Emily Happiness"],
    # HIDDEN department agents
    "chakra": ["Zen Master", "Harmony Keeper", "Energy Aligner", "Flow Director", "Balance Seeker", "Spirit Guide"],
    "blackops": ["Shadow Agent", "Ghost Operative", "Cipher Expert", "Phantom Analyst", "Stealth Scout", "Dark Oracle"],
    "security": ["Guard Prime", "Threat Hunter", "Shield Defender", "Sentinel Watch", "Firewall Guardian", "Breach Detector"],
    "rdlab": ["Lab Pioneer", "Quantum Thinker", "Experiment Lead", "Innovation Spark", "Research Maven", "Future Builder"],
}

AGENT_ROLES = ["advisor_a", "advisor_b", "scout_internal", "scout_external", "synth", "executor"]
AGENT_ROLE_NAMES = {
    "advisor_a": "Senior Advisor",
    "advisor_b": "Strategy Advisor",
    "scout_internal": "Internal Scout",
    "scout_external": "External Scout",
    "synth": "Knowledge Synthesizer",
    "executor": "Action Executor"
}


def seed_departments(db, include_hidden=True) -> int:
    """Seed default departments (public + optionally hidden)"""
    from backend.database import Department
    
    all_depts = DEPARTMENTS.copy()
    if include_hidden:
        all_depts.extend(HIDDEN_DEPARTMENTS)
    
    count = 0
    for i, dept_data in enumerate(all_depts):
        existing = db.query(Department).filter(Department.slug == dept_data["slug"]).first()
        if not existing:
            dept = Department(
                slug=dept_data["slug"],
                name=dept_data["name"],
                description=dept_data["description"],
                color=dept_data["color"],
                sunflower_index=i,
                cell_id=f"dept_{dept_data['slug']}",
                status="hidden" if dept_data.get("hidden") else "active"
            )
            db.add(dept)
            count += 1
    
    db.commit()
    logger.info(f"Seeded {count} departments")
    return count


def seed_agents(db, include_hidden=True) -> int:
    """Seed default agents (6 per department = 48+ total)"""
    from backend.database import Department, Agent
    
    count = 0
    sunflower_idx = 12  # Start after departments
    
    dept_slugs = list(AGENT_NAMES.keys())
    if not include_hidden:
        dept_slugs = [s for s in dept_slugs if s in [d["slug"] for d in DEPARTMENTS]]
    
    for dept_slug in dept_slugs:
        names = AGENT_NAMES.get(dept_slug, [])
        
        # Get department
        dept = db.query(Department).filter(Department.slug == dept_slug).first()
        if not dept:
            continue
        
        for i, name in enumerate(names):
            role = AGENT_ROLES[i] if i < len(AGENT_ROLES) else "executor"
            cell_id = f"agent_{dept_slug}_{role}"
            
            existing = db.query(Agent).filter(Agent.cell_id == cell_id).first()
            if not existing:
                agent = Agent(
                    name=name,
                    department=dept_slug,
                    department_id=dept.id,
                    role=role,
                    type=AGENT_ROLE_NAMES.get(role, role),
                    status="active",
                    is_active=True,
                    sunflower_index=sunflower_idx,
                    cell_id=cell_id,
                    capabilities=f"Specialized in {dept_slug} {role} tasks. Connected to brain via /api/v1/agents/{cell_id}/brain",
                    description=f"{name} - {AGENT_ROLE_NAMES.get(role, role)} for {dept.name}",
                    performance_score=95.0
                )
                db.add(agent)
                count += 1
                sunflower_idx += 1
    
    db.commit()
    logger.info(f"Seeded {count} agents")
    return count


def seed_default_tasks(db) -> int:
    """Seed some default tasks for demonstration"""
    from backend.database import Task
    
    default_tasks = [
        {"title": "Review Q4 Strategy", "department_id": "engineering", "status": "completed", "progress": 100.0},
        {"title": "Update Documentation", "department_id": "product", "status": "running", "progress": 65.0},
        {"title": "Client Onboarding", "department_id": "sales", "status": "running", "progress": 45.0},
        {"title": "Campaign Analysis", "department_id": "marketing", "status": "pending", "progress": 0.0},
        {"title": "Budget Review", "department_id": "finance", "status": "completed", "progress": 100.0},
        {"title": "Training Program", "department_id": "hr", "status": "running", "progress": 30.0},
        {"title": "Contract Review", "department_id": "legal", "status": "pending", "progress": 0.0},
        {"title": "Support Tickets", "department_id": "customer", "status": "running", "progress": 80.0},
        # Hidden department tasks
        {"title": "Energy Alignment", "department_id": "chakra", "status": "running", "progress": 75.0},
        {"title": "Threat Assessment", "department_id": "security", "status": "running", "progress": 50.0},
        {"title": "AI Experiment Alpha", "department_id": "rdlab", "status": "running", "progress": 25.0},
    ]
    
    count = 0
    for task_data in default_tasks:
        task_id = f"task_{task_data['department_id']}_{uuid.uuid4().hex[:8]}"
        existing = db.query(Task).filter(Task.department_id == task_data["department_id"]).first()
        if not existing:
            task = Task(
                task_id=task_id,
                owner_type="department",
                owner_id=task_data["department_id"],
                department_id=task_data["department_id"],
                title=task_data["title"],
                status=task_data["status"],
                progress=task_data["progress"]
            )
            db.add(task)
            count += 1
    
    db.commit()
    logger.info(f"Seeded {count} tasks")
    return count


def seed_all(db) -> dict:
    """Run all seeders"""
    results = {
        "departments": seed_departments(db),
        "agents": seed_agents(db),
        "tasks": seed_default_tasks(db)
    }
    logger.info(f"Database seeding complete: {results}")
    return results


def reset_and_seed(db) -> dict:
    """Clear tables and reseed - USE WITH CAUTION"""
    from backend.database import Department, Agent, Task, ChatSession, ChatMessage, EventLog
    
    logger.warning("Resetting database to defaults...")
    
    # Clear in reverse order of dependencies
    db.query(ChatMessage).delete()
    db.query(ChatSession).delete()
    db.query(EventLog).delete()
    db.query(Task).delete()
    db.query(Agent).delete()
    db.query(Department).delete()
    db.commit()
    
    logger.info("Tables cleared, reseeding...")
    return seed_all(db)


def ensure_seeded():
    """Ensure database has default data - called at startup"""
    from backend.database import SessionLocal, Department
    
    db = SessionLocal()
    try:
        # Check if we have departments
        dept_count = db.query(Department).count()
        if dept_count == 0:
            logger.info("No departments found, seeding defaults...")
            seed_all(db)
        else:
            logger.info(f"Found {dept_count} departments, skipping seed")
    except Exception as e:
        logger.error(f"Error checking/seeding database: {e}")
    finally:
        db.close()


def get_hidden_departments():
    """Get list of hidden departments for Founder Panel"""
    return HIDDEN_DEPARTMENTS
