#!/usr/bin/env python3
"""Debug script to check sunflower registry state."""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.sunflower_registry import sunflower_registry
from database import get_db

def main():
    print("🔍 Debugging Sunflower Registry...")
    print(f"📊 Registry state:")
    print(f"   Departments: {len(sunflower_registry.departments)}")
    print(f"   Agents: {len(sunflower_registry.agents)}")
    
    if len(sunflower_registry.departments) == 0:
        print("⚠️  Registry is empty, populating from database...")
        try:
            db = next(get_db())
            sunflower_registry.populate_from_database(db)
            print(f"✅ Registry populated:")
            print(f"   Departments: {len(sunflower_registry.departments)}")
            print(f"   Agents: {len(sunflower_registry.agents)}")
        except Exception as e:
            print(f"❌ Error populating registry: {e}")
    else:
        print("📋 Department names:")
        for dept in sunflower_registry.departments:
            print(f"   - {dept['name']} ({len(dept['agents'])} agents)")

if __name__ == "__main__":
    main() 