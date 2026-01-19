"""
Activate all agents for local development.

Run this when DISABLE_AUTH=1 to ensure all agents are visible in UIs/APIs.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.database import Agent


def activate_all_agents() -> int:
    db: Session = SessionLocal()
    try:
        updated = db.query(Agent).update({"is_active": True})
        db.commit()
        print(f"✅ Activated {updated} agents")
        return int(updated)
    except Exception as e:
        db.rollback()
        print(f"❌ Error activating agents: {e}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    activate_all_agents()











