#!/usr/bin/env python3
"""
Check Environment - Verify Python version and critical modules load.
"""
from __future__ import annotations

import sys
from pathlib import Path

def check_import(module_name: str, package_name: str | None = None) -> tuple[bool, str]:
    """Try to import a module and return (success, message)"""
    try:
        __import__(module_name)
        return True, f"✅ {package_name or module_name}"
    except ImportError as e:
        return False, f"❌ {package_name or module_name}: {e}"
    except Exception as e:
        return False, f"⚠️  {package_name or module_name}: {e}"

def main() -> int:
    """Check environment"""
    root = Path(__file__).parent.parent.resolve()
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "backend"))
    
    print("=" * 60)
    print("CHECK ENVIRONMENT")
    print("=" * 60)
    print()
    
    # Check Python version
    print(f"Python Version: {sys.version.split()[0]}")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        print("❌ Python 3.8+ required")
        return 1
    print("✅ Python version OK")
    print()
    
    # Check critical packages
    print("Checking Critical Packages:")
    critical = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("httpx", "HTTPX"),
        ("pydantic", "Pydantic"),
    ]
    
    all_ok = True
    for module, name in critical:
        ok, msg = check_import(module, name)
        print(f"  {msg}")
        if not ok:
            all_ok = False
    
    print()
    
    # Check backend modules (may fail if not all deps installed, but try)
    print("Checking Backend Modules:")
    backend_modules = [
        ("backend.daena_brain", "Daena Brain"),
        ("backend.main", "Backend Main"),
    ]
    
    for module, name in backend_modules:
        ok, msg = check_import(module, name)
        print(f"  {msg}")
        # Don't fail on backend modules - they may have optional deps
    
    print()
    
    if not all_ok:
        print("=" * 60)
        print("❌ ENVIRONMENT CHECK FAILED")
        print("=" * 60)
        print()
        print("Run: python scripts\\setup_env.py")
        return 1
    
    print("=" * 60)
    print("✅ ENVIRONMENT CHECK PASSED")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())









