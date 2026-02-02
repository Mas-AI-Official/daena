import sys
import os

# Set up path so imports work
sys.path.append(os.getcwd())

try:
    print("Importing skill_registry...")
    from backend.services.skill_registry import get_skill_registry
    print("Getting registry...")
    registry = get_skill_registry()
    print("Listing skills...")
    skills = registry.list_skills()
    print(f"Registry skills count: {len(skills)}")
    for s in skills:
        print(f" - {s['name']} ({s['category']})")
        
    # print("\nImporting static SKILL_DEFS...")
    # from backend.routes.skills import SKILL_DEFS
    # print(f"Static skills count: {len(SKILL_DEFS)}")
    # for s in SKILL_DEFS:
    #    print(f" - {s['name']} ({s.get('category')})")
        
except Exception as e:
    print(f"CRASH: {e}")
    import traceback
    traceback.print_exc()
