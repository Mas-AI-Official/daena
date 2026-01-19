"""
Database Seed Script
Creates default data: 8 departments, 6 agents each, chat categories, councils
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from backend.database
from backend.database import (
    SessionLocal, Base, engine,
    Department, Agent, ChatCategory, CouncilCategory, CouncilMember,
    SystemConfig, BrainModel
)
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_departments(db):
    """Seed 8 departments with 6 agents each"""
    departments_data = [
        {"slug": "engineering", "name": "Engineering", "description": "Software development and technical infrastructure", "color": "#4169E1", "sunflower_index": 0},
        {"slug": "product", "name": "Product", "description": "Product management and strategy", "color": "#9370DB", "sunflower_index": 1},
        {"slug": "sales", "name": "Sales", "description": "Sales and revenue generation", "color": "#FF8C00", "sunflower_index": 2},
        {"slug": "marketing", "name": "Marketing", "description": "Marketing and brand management", "color": "#FF8C00", "sunflower_index": 3},
        {"slug": "finance", "name": "Finance", "description": "Financial management and accounting", "color": "#00CED1", "sunflower_index": 4},
        {"slug": "hr", "name": "Human Resources", "description": "People operations and talent", "color": "#E91E7F", "sunflower_index": 5},
        {"slug": "legal", "name": "Legal", "description": "Legal affairs and compliance", "color": "#9370DB", "sunflower_index": 6},
        {"slug": "customer", "name": "Customer Success", "description": "Customer support and success", "color": "#32CD32", "sunflower_index": 7},
    ]
    
    agents_per_dept = {
        "engineering": [
            {"name": "Atlas", "role": "Chief Engineer", "type": "technical"},
            {"name": "Nexus", "role": "Senior Developer", "type": "technical"},
            {"name": "Codex", "role": "DevOps Specialist", "type": "technical"},
            {"name": "Vector", "role": "QA Lead", "type": "technical"},
            {"name": "Syntax", "role": "Architect", "type": "technical"},
            {"name": "Byte", "role": "Security Engineer", "type": "technical"},
        ],
        "product": [
            {"name": "Nova", "role": "Product Lead", "type": "strategic"},
            {"name": "Pulse", "role": "Product Manager", "type": "strategic"},
            {"name": "Flow", "role": "UX Designer", "type": "creative"},
            {"name": "Spark", "role": "Product Analyst", "type": "analytical"},
            {"name": "Lens", "role": "Research Lead", "type": "analytical"},
            {"name": "Scope", "role": "Product Strategist", "type": "strategic"},
        ],
        "sales": [
            {"name": "Hunter", "role": "Sales Director", "type": "sales"},
            {"name": "Apex", "role": "Account Executive", "type": "sales"},
            {"name": "Velocity", "role": "Sales Engineer", "type": "technical"},
            {"name": "Summit", "role": "Business Development", "type": "sales"},
            {"name": "Pivot", "role": "Sales Operations", "type": "analytical"},
            {"name": "Target", "role": "Inside Sales", "type": "sales"},
        ],
        "marketing": [
            {"name": "Aura", "role": "CMO", "type": "strategic"},
            {"name": "Brand", "role": "Brand Manager", "type": "creative"},
            {"name": "Growth", "role": "Growth Hacker", "type": "analytical"},
            {"name": "Content", "role": "Content Strategist", "type": "creative"},
            {"name": "Social", "role": "Social Media Manager", "type": "creative"},
            {"name": "Metrics", "role": "Marketing Analyst", "type": "analytical"},
        ],
        "finance": [
            {"name": "Vault", "role": "CFO", "type": "analytical"},
            {"name": "Ledger", "role": "Accountant", "type": "analytical"},
            {"name": "Budget", "role": "Financial Analyst", "type": "analytical"},
            {"name": "Audit", "role": "Auditor", "type": "analytical"},
            {"name": "Forecast", "role": "Financial Planner", "type": "analytical"},
            {"name": "Capital", "role": "Treasury Manager", "type": "analytical"},
        ],
        "hr": [
            {"name": "Harmony", "role": "People Ops", "type": "support"},
            {"name": "Talent", "role": "Recruiter", "type": "support"},
            {"name": "Culture", "role": "Culture Manager", "type": "support"},
            {"name": "Wellness", "role": "Wellness Coordinator", "type": "support"},
            {"name": "Learning", "role": "Learning & Development", "type": "support"},
            {"name": "Retention", "role": "Retention Specialist", "type": "support"},
        ],
        "legal": [
            {"name": "Justus", "role": "General Counsel", "type": "legal"},
            {"name": "Compliance", "role": "Compliance Officer", "type": "legal"},
            {"name": "Contract", "role": "Contract Manager", "type": "legal"},
            {"name": "IP", "role": "IP Specialist", "type": "legal"},
            {"name": "Regulatory", "role": "Regulatory Affairs", "type": "legal"},
            {"name": "Risk", "role": "Risk Manager", "type": "legal"},
        ],
        "customer": [
            {"name": "Echo", "role": "Success Lead", "type": "support"},
            {"name": "Support", "role": "Support Engineer", "type": "support"},
            {"name": "Onboard", "role": "Onboarding Specialist", "type": "support"},
            {"name": "Retention", "role": "Retention Manager", "type": "support"},
            {"name": "Advocate", "role": "Customer Advocate", "type": "support"},
            {"name": "Feedback", "role": "Feedback Analyst", "type": "analytical"},
        ],
    }
    
    dept_objects = {}
    for dept_data in departments_data:
        slug = dept_data["slug"]
        existing = db.query(Department).filter(Department.slug == slug).first()
        if existing:
            logger.info(f"Department {slug} already exists, skipping")
            dept_objects[slug] = existing
            continue
        
        cell_id = f"D{dept_data['sunflower_index']}"
        dept = Department(
            slug=slug,
            name=dept_data["name"],
            description=dept_data["description"],
            color=dept_data["color"],
            sunflower_index=dept_data["sunflower_index"],
            cell_id=cell_id,
            status="active",
            hidden=False
        )
        db.add(dept)
        db.flush()
        dept_objects[slug] = dept
        logger.info(f"Created department: {dept_data['name']}")
        
        # Create 6 agents for this department
        agents = agents_per_dept.get(slug, [])
        for idx, agent_data in enumerate(agents):
            agent_cell_id = f"A{dept_data['sunflower_index']}{idx+1}"
            agent = Agent(
                name=agent_data["name"],
                department=slug,
                department_id=dept.id,
                role=agent_data["role"],
                type=agent_data["type"],
                status="idle",
                is_active=True,
                sunflower_index=dept_data["sunflower_index"] * 10 + idx + 1,
                cell_id=agent_cell_id,
                description=f"{agent_data['role']} in {dept_data['name']} department"
            )
            db.add(agent)
            logger.info(f"  Created agent: {agent_data['name']} ({agent_data['role']})")
    
    db.commit()
    return dept_objects


def seed_chat_categories(db):
    """Seed chat categories"""
    categories = [
        {"name": "executive", "scope": None, "display_order": 0},
        {"name": "general", "scope": None, "display_order": 1},
        {"name": "departments", "scope": None, "display_order": 2},
        {"name": "agents", "scope": None, "display_order": 3},
    ]
    
    # Add department-specific categories
    depts = db.query(Department).filter(Department.hidden == False).all()
    order = 4
    for dept in depts:
        categories.append({
            "name": f"department:{dept.slug}",
            "scope": dept.slug,
            "display_order": order
        })
        order += 1
    
    for cat_data in categories:
        existing = db.query(ChatCategory).filter(ChatCategory.name == cat_data["name"]).first()
        if existing:
            continue
        
        cat = ChatCategory(
            name=cat_data["name"],
            scope=cat_data["scope"],
            display_order=cat_data["display_order"]
        )
        db.add(cat)
        logger.info(f"Created chat category: {cat_data['name']}")
    
    db.commit()


def seed_councils(db):
    """Seed council categories and members"""
    council_categories = [
        {
            "name": "Strategic",
            "enabled": True,
            "members": [
                {"name": "The Architect", "persona_source": "Elon Musk", "display_order": 0},
                {"name": "The Visionary", "persona_source": "Sam Altman", "display_order": 1},
                {"name": "The Builder", "persona_source": "Linus Torvalds", "display_order": 2},
                {"name": "The Product", "persona_source": "Steve Jobs", "display_order": 3},
                {"name": "The Hacker", "persona_source": "Kevin Mitnick", "display_order": 4},
            ]
        },
        {
            "name": "Technical",
            "enabled": True,
            "members": [
                {"name": "The Engineer", "persona_source": "Guido van Rossum", "display_order": 0},
                {"name": "The Scientist", "persona_source": "Alan Turing", "display_order": 1},
                {"name": "The Innovator", "persona_source": "Grace Hopper", "display_order": 2},
                {"name": "The Optimizer", "persona_source": "Donald Knuth", "display_order": 3},
                {"name": "The Architect", "persona_source": "Martin Fowler", "display_order": 4},
            ]
        },
    ]
    
    for cat_data in council_categories:
        existing = db.query(CouncilCategory).filter(CouncilCategory.name == cat_data["name"]).first()
        if existing:
            cat = existing
        else:
            cat = CouncilCategory(
                name=cat_data["name"],
                enabled=cat_data["enabled"]
            )
            db.add(cat)
            db.flush()
            logger.info(f"Created council category: {cat_data['name']}")
        
        # Add members
        for member_data in cat_data["members"]:
            existing_member = db.query(CouncilMember).filter(
                CouncilMember.category_id == cat.id,
                CouncilMember.name == member_data["name"]
            ).first()
            if existing_member:
                continue
            
            member = CouncilMember(
                category_id=cat.id,
                name=member_data["name"],
                persona_source=member_data["persona_source"],
                enabled=True,
                display_order=member_data["display_order"],
                settings_json={"training_notes": f"Trained on {member_data['persona_source']} principles"}
            )
            db.add(member)
            logger.info(f"  Created council member: {member_data['name']}")
    
    db.commit()


def seed_brain_models(db):
    """Seed default brain models"""
    models = [
        {
            "name": "qwen2.5:7b-instruct",
            "model_type": "qwen",
            "provider": "local",
            "status": "available",
            "model_size": "7B",
            "context_length": 32768
        },
        {
            "name": "qwen2.5:14b-instruct",
            "model_type": "qwen",
            "provider": "local",
            "status": "available",
            "model_size": "14B",
            "context_length": 32768
        },
    ]
    
    for model_data in models:
        existing = db.query(BrainModel).filter(BrainModel.name == model_data["name"]).first()
        if existing:
            continue
        
        model = BrainModel(**model_data)
        db.add(model)
        logger.info(f"Created brain model: {model_data['name']}")
    
    db.commit()


def main():
    """Main seed function"""
    logger.info("Starting database seed...")
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tables created/verified")
    
    db = SessionLocal()
    try:
        # Seed in order
        seed_departments(db)
        seed_chat_categories(db)
        seed_councils(db)
        seed_brain_models(db)
        
        logger.info("✅ Database seed complete!")
        
    except Exception as e:
        logger.error(f"❌ Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

