#!/usr/bin/env python3
"""
Where Am I? - Verify we're in the correct project root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

def main() -> int:
    """Print current location and verify project structure"""
    cwd = Path.cwd().resolve()
    expected_root = Path(r"D:\Ideas\Daena_old_upgrade_20251213").resolve()
    
    print("=" * 60)
    print("WHERE AM I? - Project Root Verification")
    print("=" * 60)
    print()
    print(f"Absolute CWD: {cwd}")
    print(f"Expected Root: {expected_root}")
    print()
    
    # Check if we're in the right place
    if cwd != expected_root:
        print("=" * 60)
        print("⚠️  WARNING: WRONG FOLDER DETECTED!")
        print("=" * 60)
        print()
        print(f"Current folder: {cwd}")
        print(f"Expected folder: {expected_root}")
        print()
        print("Please navigate to the correct folder:")
        print(f"  cd /d {expected_root}")
        print()
        return 1
    
    print("[OK] Working in correct project root")
    print()
    
    # Detect paths
    backend_entry = cwd / "backend" / "main.py"
    frontend_templates = cwd / "frontend" / "templates"
    python_exe = Path(sys.executable)
    
    print("Detected Paths:")
    print(f"  Backend Entrypoint: {backend_entry}")
    print(f"    Exists: {'✅' if backend_entry.exists() else '❌'}")
    print(f"  Frontend Templates: {frontend_templates}")
    print(f"    Exists: {'✅' if frontend_templates.exists() else '❌'}")
    print(f"  Python Executable: {python_exe}")
    print(f"    Version: {sys.version.split()[0]}")
    print()
    
    # Verify critical files
    critical_files = [
        "backend/main.py",
        "backend/daena_brain.py",
        "frontend/templates/dashboard.html",
        "requirements.txt",
    ]
    
    missing = []
    for rel_path in critical_files:
        full_path = cwd / rel_path
        if not full_path.exists():
            missing.append(rel_path)
    
    if missing:
        print("=" * 60)
        print("⚠️  WARNING: Missing Critical Files!")
        print("=" * 60)
        for f in missing:
            print(f"  ❌ {f}")
        print()
        return 1
    
    print("[OK] All critical files present")
    print()
    print("=" * 60)
    print("✅ VERIFICATION PASSED")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())









