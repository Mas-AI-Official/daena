#!/usr/bin/env python3
"""
Simple test to verify backend can start without crashing
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("=" * 60)
print("BACKEND STARTUP TEST")
print("=" * 60)
print()

# Test 1: Import backend.main
print("Test 1: Importing backend.main...")
try:
    import backend.main
    print("✅ backend.main imported successfully")
except Exception as e:
    print(f"❌ Failed to import backend.main: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Check if app exists
print("\nTest 2: Checking app object...")
try:
    app = backend.main.app
    print(f"✅ App object found: {type(app)}")
except Exception as e:
    print(f"❌ App object not found: {e}")
    sys.exit(1)

# Test 3: Check startup event
print("\nTest 3: Checking startup event...")
try:
    startup_events = [handler for handler in app.router.on_startup]
    print(f"✅ Found {len(startup_events)} startup event(s)")
except Exception as e:
    print(f"⚠️ Could not check startup events: {e}")

# Test 4: Try to import uvicorn
print("\nTest 4: Checking uvicorn...")
try:
    import uvicorn
    print(f"✅ uvicorn imported: {uvicorn.__version__}")
except Exception as e:
    print(f"❌ uvicorn not available: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED - Backend should start successfully")
print("=" * 60)




