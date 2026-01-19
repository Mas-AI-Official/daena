#!/usr/bin/env python3
"""
Setup Environment - Automatically install dependencies and create lock files.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

def run_command(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)

def main() -> int:
    """Setup Python environment"""
    root = Path(__file__).parent.parent.resolve()
    venv_python = root / "venv_daena_main_py310" / "Scripts" / "python.exe"
    
    # Use venv python if available, otherwise system python
    if venv_python.exists():
        python_exe = str(venv_python)
        print(f"[INFO] Using venv Python: {python_exe}")
    else:
        python_exe = sys.executable
        print(f"[INFO] Using system Python: {python_exe}")
    
    print()
    print("=" * 60)
    print("SETUP ENVIRONMENT")
    print("=" * 60)
    print()
    
    # Step 1: Upgrade pip tooling
    print("[1/4] Upgrading pip, setuptools, wheel...")
    returncode, stdout, stderr = run_command(
        [python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        root
    )
    if returncode != 0:
        print(f"[FAIL] Failed to upgrade pip tooling:\n{stderr}")
        return 1
    print("[OK] pip tooling upgraded")
    print()
    
    # Step 2: Install requirements.txt if present
    req_file = root / "requirements.txt"
    if req_file.exists():
        print("[2/4] Installing from requirements.txt...")
        returncode, stdout, stderr = run_command(
            [python_exe, "-m", "pip", "install", "-r", "requirements.txt"],
            root
        )
        if returncode != 0:
            print(f"[FAIL] Failed to install requirements:\n{stderr}")
            return 1
        print("[OK] Requirements installed")
    else:
        print("[2/4] requirements.txt not found - skipping")
    print()
    
    # Step 3: Freeze to lock file
    print("[3/4] Creating requirements.lock.txt...")
    lock_file = root / "requirements.lock.txt"
    returncode, stdout, stderr = run_command(
        [python_exe, "-m", "pip", "freeze"],
        root
    )
    if returncode != 0:
        print(f"[WARNING] Failed to freeze requirements:\n{stderr}")
    else:
        try:
            # Try to write, but handle permission errors gracefully
            if lock_file.exists():
                # Try to remove read-only attribute if present
                import os
                import stat
                try:
                    os.chmod(lock_file, stat.S_IWRITE | stat.S_IREAD)
                except Exception:
                    pass
            
            lock_file.write_text(stdout, encoding="utf-8")
            line_count = len(stdout.strip().splitlines())
            print(f"[OK] Frozen {line_count} packages to requirements.lock.txt")
        except PermissionError:
            print(f"[WARNING] Permission denied writing lock file (file may be open in another program)")
            print(f"[INFO] Skipping lock file update - this is not critical")
        except Exception as e:
            print(f"[WARNING] Failed to write lock file: {e}")
            print(f"[INFO] Skipping lock file update - this is not critical")
    print()
    
    # Step 4: Update requirements.txt only if missing or broken
    if not req_file.exists():
        print("[4/4] requirements.txt missing - creating from lock file...")
        if lock_file.exists():
            # Extract primary package names (heuristic: first part before ==)
            lock_content = lock_file.read_text(encoding="utf-8")
            primary_deps = []
            for line in lock_content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
                    if pkg_name:
                        primary_deps.append(pkg_name)
            
            # Write minimal requirements.txt
            req_file.write_text("\n".join(sorted(set(primary_deps))) + "\n", encoding="utf-8")
            print(f"[OK] Created requirements.txt with {len(primary_deps)} primary dependencies")
        else:
            print("[WARNING] Cannot create requirements.txt - no lock file available")
    else:
        print("[4/4] requirements.txt exists - skipping update")
    
    print()
    print("=" * 60)
    print("✅ ENVIRONMENT SETUP COMPLETE")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())

