#!/usr/bin/env python3
"""
Verify organization structure: 8 departments × 6 agents (48 total).
Idempotent verification script that confirms exact structure matches canonical config.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from backend.config.council_config import COUNCIL_CONFIG
from backend.database import SessionLocal, Department, Agent
from sqlalchemy import func


def verify_structure() -> dict:
    """
    Verify organization structure matches canonical 8×6 configuration.
    
    Returns:
        Dict with verification results and diffs
    """
    session = SessionLocal()
    
    try:
        # Get actual counts
        dept_count = session.query(func.count(Department.id)).scalar()
        agent_count = session.query(func.count(Agent.id)).scalar()
        
        # Get departments
        departments = session.query(Department).all()
        dept_slugs = {dept.slug for dept in departments}
        expected_slugs = set(COUNCIL_CONFIG.DEPARTMENT_SLUGS)
        
        # Get agents by department
        agents_by_dept = {}
        for dept in departments:
            agents = session.query(Agent).filter(Agent.department == dept.slug).all()
            agents_by_dept[dept.slug] = {
                "count": len(agents),
                "roles": {agent.role for agent in agents if agent.role}
            }
        
        # Verify counts
        expected_depts = COUNCIL_CONFIG.TOTAL_DEPARTMENTS
        expected_agents = COUNCIL_CONFIG.TOTAL_AGENTS
        expected_agents_per_dept = COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT
        expected_roles = set(COUNCIL_CONFIG.AGENT_ROLES)
        
        # Build results
        results = {
            "pass": True,
            "departments": {
                "expected": expected_depts,
                "actual": dept_count,
                "match": dept_count == expected_depts,
                "missing_slugs": list(expected_slugs - dept_slugs),
                "extra_slugs": list(dept_slugs - expected_slugs)
            },
            "agents": {
                "expected_total": expected_agents,
                "actual_total": agent_count,
                "match": agent_count == expected_agents,
                "expected_per_dept": expected_agents_per_dept
            },
            "departments_detail": {},
            "diffs": []
        }
        
        # Check each department
        for dept_slug in COUNCIL_CONFIG.DEPARTMENT_SLUGS:
            dept_info = agents_by_dept.get(dept_slug, {"count": 0, "roles": set()})
            actual_count = dept_info["count"]
            actual_roles = dept_info["roles"]
            
            dept_result = {
                "slug": dept_slug,
                "expected_agents": expected_agents_per_dept,
                "actual_agents": actual_count,
                "match": actual_count == expected_agents_per_dept,
                "expected_roles": list(expected_roles),
                "actual_roles": list(actual_roles),
                "missing_roles": list(expected_roles - actual_roles),
                "extra_roles": list(actual_roles - expected_roles)
            }
            
            results["departments_detail"][dept_slug] = dept_result
            
            # Record diffs
            if actual_count != expected_agents_per_dept:
                results["diffs"].append(
                    f"Department {dept_slug}: expected {expected_agents_per_dept} agents, found {actual_count}"
                )
                results["pass"] = False
            
            if actual_roles != expected_roles:
                missing = expected_roles - actual_roles
                extra = actual_roles - expected_roles
                if missing:
                    results["diffs"].append(
                        f"Department {dept_slug}: missing roles {list(missing)}"
                    )
                    results["pass"] = False
                if extra:
                    results["diffs"].append(
                        f"Department {dept_slug}: unexpected roles {list(extra)}"
                    )
        
        # Check for missing departments
        if dept_slugs != expected_slugs:
            results["pass"] = False
        
        # Check total agent count
        if agent_count != expected_agents:
            results["diffs"].append(
                f"Total agents: expected {expected_agents}, found {agent_count}"
            )
            results["pass"] = False
        
        return results
    
    finally:
        session.close()


def main():
    """Main entry point."""
    print("=" * 60)
    print("ORGANIZATION STRUCTURE VERIFICATION")
    print("=" * 60)
    print(f"Expected: {COUNCIL_CONFIG.TOTAL_DEPARTMENTS} departments × {COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT} agents = {COUNCIL_CONFIG.TOTAL_AGENTS} total")
    print()
    
    results = verify_structure()
    
    # Print summary
    if results["pass"]:
        print("✅ Structure verification PASSED")
        print(f"   Departments: {results['departments']['actual']}/{results['departments']['expected']}")
        print(f"   Agents: {results['agents']['actual_total']}/{results['agents']['expected_total']}")
    else:
        print("❌ Structure verification FAILED")
        print()
        print("Diffs:")
        for diff in results["diffs"]:
            print(f"   - {diff}")
        print()
        print("Department Details:")
        for dept_slug, dept_info in results["departments_detail"].items():
            status = "✅" if dept_info["match"] else "❌"
            print(f"   {status} {dept_slug}: {dept_info['actual_agents']}/{dept_info['expected_agents']} agents")
            if dept_info["missing_roles"]:
                print(f"      Missing roles: {dept_info['missing_roles']}")
            if dept_info["extra_roles"]:
                print(f"      Extra roles: {dept_info['extra_roles']}")
    
    print()
    print("=" * 60)
    
    # Return exit code
    return 0 if results["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

