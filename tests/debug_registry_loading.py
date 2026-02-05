
import sys
import os
from pathlib import Path
import traceback

# Add project root to path
sys.path.append(str(Path(__file__).parent))

print(f"Python: {sys.executable}")

try:
    import pydantic
    print(f"Pydantic Version: {pydantic.VERSION}")
except ImportError:
    print("Pydantic not found")

try:
    print("\n--- Testing Tool Registry Import ---")
    try:
        from backend.tools.registry import TOOL_DEFS
        print(f"TOOL_DEFS count: {len(TOOL_DEFS)}")
        for k in list(TOOL_DEFS.keys())[:5]:
            print(f" - {k}")
    except Exception as e:
        print(f"Tool Registry Import Failed: {e}")
        traceback.print_exc()

    print("\n--- Testing CMP Registry Import ---")
    try:
        from backend.core.cmp.registry import cmp_registry
        tools = cmp_registry.list_tools()
        print(f"CMP Tools count: {len(tools)}")
        for t in tools[:5]:
            print(f" - {t.name} ({t.id})")
    except Exception as e:
        print(f"CMP Registry Import Failed: {e}")
        traceback.print_exc()
        
    print("\n--- Testing Skill Registry Logic ---")
    from backend.services.skill_registry import SkillRegistry
    registry = SkillRegistry()
    skills = registry.list_skills()
    
    print(f"\nTotal Skills Loaded: {len(skills)}")
    by_cat = {}
    for s in skills:
        cat = s['category']
        by_cat[cat] = by_cat.get(cat, 0) + 1
        
    print("Breakdown by Category:")
    for k, v in by_cat.items():
        print(f"  {k}: {v}")
        
except Exception as e:
    traceback.print_exc()
