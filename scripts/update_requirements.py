"""
Auto-update requirements: freeze to lockfile and optionally update requirements.txt.

Safe operation:
- Always freezes to requirements.lock.txt
- Only updates requirements.txt if DAENA_UPDATE_REQUIREMENTS=1
- Never removes critical pinned packages
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def freeze_to_lockfile() -> int:
    """Freeze current environment to requirements.lock.txt"""
    lockfile = Path("requirements.lock.txt")
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True,
            text=True,
            check=True,
        )
        
        lockfile.write_text(result.stdout, encoding="utf-8")
        print(f"[OK] Frozen {len(result.stdout.splitlines())} packages to requirements.lock.txt")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to freeze packages: {e.stderr}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[ERROR] Error: {e}", file=sys.stderr)
        return 1


def update_requirements_txt() -> int:
    """Safely update requirements.txt from lockfile (only if enabled)"""
    if os.getenv("DAENA_UPDATE_REQUIREMENTS", "0") != "1":
        print("[INFO] DAENA_UPDATE_REQUIREMENTS=0 - skipping requirements.txt update")
        return 0
    
    lockfile = Path("requirements.lock.txt")
    reqfile = Path("requirements.txt")
    
    if not lockfile.exists():
        print("[WARNING] requirements.lock.txt not found - run freeze first")
        return 0
    
    if not reqfile.exists():
        print("[WARNING] requirements.txt not found - skipping update")
        return 0
    
    # Read lockfile
    locked_packages = {}
    for line in lockfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            locked_packages[name.lower()] = (name, version)
    
    # Read current requirements.txt
    req_lines = reqfile.read_text(encoding="utf-8").splitlines(True)
    updated_lines = []
    seen_packages = set()
    
    for line in req_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            updated_lines.append(line)
            continue
        
        # Extract package name (handle comments, version specifiers)
        pkg_name = stripped.split("==")[0].split(">=")[0].split("<=")[0].split(">")[0].split("<")[0].split("~")[0].split("!")[0].split("#")[0].strip()
        pkg_lower = pkg_name.lower()
        
        if pkg_lower in locked_packages:
            # Update to locked version
            name, version = locked_packages[pkg_lower]
            updated_lines.append(f"{name}=={version}\n")
            seen_packages.add(pkg_lower)
        else:
            # Keep as-is (might be a URL or special format)
            updated_lines.append(line)
    
    # Write updated requirements.txt
    reqfile.write_text("".join(updated_lines), encoding="utf-8")
    print(f"[OK] Updated requirements.txt with {len(seen_packages)} packages from lockfile")
    return 0


def main() -> int:
    """Main entry point"""
    # Always freeze to lockfile
    if freeze_to_lockfile() != 0:
        return 1
    
    # Optionally update requirements.txt
    if update_requirements_txt() != 0:
        return 1
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

