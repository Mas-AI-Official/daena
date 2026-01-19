"""
Verify that the database structure matches the expected 8 departments / 6 agents configuration.

Run this after seeding to ensure the structure is correct.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from database import engine, Department, Agent
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


def verify_structure():
    """Verify the 8x6 structure."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    
    try:
        departments = session.query(Department).order_by(Department.sunflower_index).all()
        # Use raw SQL to avoid department_id column issue
        total_agents_result = session.execute(text("SELECT COUNT(*) FROM agents WHERE department IS NOT NULL"))
        total_agents = total_agents_result.scalar() or 0
        
        print("=" * 60)
        print("Verifying Daena Structure (8 Departments x 6 Agents)")
        print("=" * 60)
        
        # Check department count
        if len(departments) != 8:
            print(f"ERROR: Expected 8 departments, found {len(departments)}")
            return False
        else:
            print(f"Found {len(departments)} departments")
        
        # Check each department
        expected_roles = {
            "advisor_a", "advisor_b", "scout_internal", "scout_external",
            "synth", "executor"
        }
        
        all_correct = True
        for dept in departments:
            # Use department string field (slug) not department_id
            agents = session.query(Agent).filter(Agent.department == dept.slug).all()
            agent_count = len(agents)
            agent_roles = {agent.role for agent in agents}
            
            if agent_count != 6:
                print(f"ERROR {dept.name}: Expected 6 agents, found {agent_count}")
                all_correct = False
            elif agent_roles != expected_roles:
                missing = expected_roles - agent_roles
                extra = agent_roles - expected_roles
                print(f"ERROR {dept.name}: Role mismatch")
                if missing:
                    print(f"   Missing roles: {missing}")
                if extra:
                    print(f"   Extra roles: {extra}")
                all_correct = False
            else:
                print(f"OK {dept.name}: {agent_count} agents with correct roles")
        
        # Check total agent count
        if total_agents != 48:
            print(f"ERROR: Expected 48 total agents, found {total_agents}")
            all_correct = False
        else:
            print(f"Total agents: {total_agents} (8 × 6)")
        
        # Check sunflower indices
        indices = [dept.sunflower_index for dept in departments]
        if set(indices) != set(range(1, 9)):
            print(f"ERROR: Sunflower indices incorrect: {sorted(indices)}")
            all_correct = False
        else:
            print(f"Sunflower indices: {sorted(indices)}")
        
        print("=" * 60)
        if all_correct:
            print("Structure verification PASSED")
            return True
        else:
            print("Structure verification FAILED")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = verify_structure()
    sys.exit(0 if success else 1)

