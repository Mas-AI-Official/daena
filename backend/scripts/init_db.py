import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from backend.database import Base, engine, SessionLocal, Department, Agent, ChatCategory, SystemConfig
from backend.config.constants import DEPARTMENTS, AGENTS_PER_DEPARTMENT

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    db = SessionLocal()
    try:
        # 1. Initialize Departments
        print("Initializing departments...")
        for dept_key, dept_data in DEPARTMENTS.items():
            existing = db.query(Department).filter(Department.slug == dept_key).first()
            if not existing:
                dept = Department(
                    slug=dept_key,
                    name=dept_data["name"],
                    description=dept_data["description"],
                    color=dept_data["color"],
                    sunflower_index=dept_data["index"],
                    cell_id=f"dept_{dept_key}",
                    status="active"
                )
                db.add(dept)
        db.commit()

        # 2. Initialize Agents
        print("Initializing agents...")
        departments = db.query(Department).all()
        for dept in departments:
            # Create standard agents for this department
            agent_roles = ["Advisor A", "Advisor B", "Scout Internal", "Scout External", "Synth", "Executor"]
            
            for i, role in enumerate(agent_roles):
                agent_name = f"{dept.name} {role}"
                agent_slug = f"{dept.slug}_{role.lower().replace(' ', '_')}"
                
                existing = db.query(Agent).filter(Agent.name == agent_name).first()
                if not existing:
                    agent = Agent(
                        name=agent_name,
                        department=dept.slug,
                        department_id=dept.id,
                        role=role,
                        type="specialized",
                        status="idle",
                        capabilities=f"Specialized in {dept.name} operations",
                        description=f"{role} for {dept.name} department",
                        sunflower_index=i,
                        cell_id=f"agent_{dept.slug}_{i}",
                        is_active=True
                    )
                    db.add(agent)
        db.commit()

        # 3. Initialize Chat Categories
        print("Initializing chat categories...")
        categories = [
            {"name": "Executive", "description": "High-level strategic discussions", "icon": "briefcase", "color": "#FFD700", "sort_order": 1},
            {"name": "Departments", "description": "Department-specific operations", "icon": "building", "color": "#4CAF50", "sort_order": 2},
            {"name": "Agents", "description": "Direct agent interactions", "icon": "robot", "color": "#2196F3", "sort_order": 3},
            {"name": "General", "description": "General purpose chats", "icon": "chat", "color": "#9E9E9E", "sort_order": 4}
        ]
        
        for cat in categories:
            existing = db.query(ChatCategory).filter(ChatCategory.name == cat["name"]).first()
            if not existing:
                c = ChatCategory(
                    name=cat["name"],
                    description=cat["description"],
                    icon=cat["icon"],
                    color=cat["color"],
                    sort_order=cat["sort_order"]
                )
                db.add(c)
        db.commit()
        
        print("Database initialization complete!")

    except Exception as e:
        print(f"Error initializing database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
