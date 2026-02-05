# CURSOR PROMPT 4: REPOSITORY CLEANUP

You are working in the Mas-AI-Official/daena repository. Clean up duplicate folders, outdated files, and organize the codebase for clarity.

## GOAL
Remove duplicates, consolidate scattered files, and create a clean, understandable repo structure.

## ANALYSIS PHASE (Do this first, don't delete anything yet)

Create a file called `CLEANUP_ANALYSIS.md` with:

### 1. Compare Folder Pairs
For each pair, determine: Are they duplicates? Different purposes? One obsolete?

- `/backend` vs `/backend_external`
- `/Governance` vs `/Governance_external`
- `/Tools` vs `/Tools_external`
- `/memory_service` vs `/memory_service_external`
- `/monitoring` vs `/monitoring_external`
- `/tests` vs `/tests_external`

### 2. Environment Files
List all .env files:
- `.env`
- `.env.example`
- `_env`
- `_env.example`
- `_env_azure_openai`
- `.env_azure_openai`

Determine: Which is canonical? Which are examples/templates?

### 3. Documentation
- `/docs` vs `/docs-Previous version`
- Determine: Is Previous version needed? Archive vs delete?

### 4. Root Directory Files
List all:
- `.bat` scripts
- `.ps1` scripts
- Standalone `.py` scripts
- `.txt` files
- `.md` files

Categorize:
- Essential (keep in root)
- Move to `/scripts`
- Move to `/docs`
- Delete (obsolete)

### 5. Startup Scripts
Find all startup scripts:
```bash
find . -name "*start*.bat" -o -name "*start*.sh" -o -name "*start*.ps1"
```

Determine: Consolidate to ONE cross-platform starter?

## CLEANUP ACTIONS (Only after analysis)

### A) Folder Consolidation

**IF `_external` folders are duplicates:**
```bash
# Backup first!
git add .
git commit -m "Pre-cleanup checkpoint"

# Remove duplicates
rm -rf backend_external
rm -rf Governance_external
rm -rf Tools_external
rm -rf memory_service_external
rm -rf monitoring_external
rm -rf tests_external

# Update any imports
find . -name "*.py" -exec sed -i 's/from backend_external/from backend/g' {} \;
```

**IF `_external` folders serve a purpose:**
Create README.md in each explaining:
```markdown
# Backend External

This folder contains external-facing backend services that are separate from internal Daena core.

## Purpose
- Public API endpoints
- External tool integrations
- Third-party service connectors

## Difference from `/backend`
- `/backend`: Internal Daena core services
- `/backend_external`: External-facing APIs
```

### B) Environment File Consolidation

Create ONE canonical `.env` file:
```bash
# Merge all settings from various .env files
cat _env _env.example .env_azure_openai > .env.merged

# Review manually, keep only unique + latest settings

# Keep these:
.env                 # Main config (not committed to git)
.env.example         # Template for new users

# Delete these:
_env
_env.example
_env_azure_openai
.env_azure_openai
```

Update `.gitignore`:
```
.env
!.env.example
```

### C) Documentation Cleanup

```bash
# Archive old docs
mv "docs-Previous version" archive/docs-old-$(date +%Y%m%d)

# OR delete if truly obsolete
rm -rf "docs-Previous version"

# Ensure current docs are up to date
# Review and update:
docs/README.md
docs/QUICKSTART.md
docs/API.md
```

### D) Root Directory Cleanup

Create proper folder structure:
```
/
├── backend/
├── frontend/
├── scripts/          ← Move all .bat, .ps1, .py scripts here
├── docs/             ← Move all .md documentation here
├── tools/            ← Move utility .py scripts here
├── tests/
├── .env.example
├── README.md
├── LICENSE
└── .gitignore
```

Move files:
```bash
# Move scripts
mv *.bat scripts/
mv *.ps1 scripts/
mv start_*.py scripts/

# Move docs
mv *.md docs/ (except README.md, LICENSE.md, CONTRIBUTING.md)

# Move utilities
mv check_api.py tools/
mv brain_status.json data/
```

### E) Startup Script Consolidation

Create ONE cross-platform starter: `start.py`
```python
#!/usr/bin/env python3
"""
Universal Daena startup script
Detects OS and runs appropriate commands
"""

import os
import sys
import platform
import subprocess

def start_backend():
    """Start backend server"""
    print("Starting Daena backend...")
    if platform.system() == "Windows":
        subprocess.Popen(["python", "backend/main.py"], shell=True)
    else:
        subprocess.Popen(["python3", "backend/main.py"])

def start_frontend():
    """Start frontend server"""
    print("Starting frontend...")
    os.chdir("frontend")
    if platform.system() == "Windows":
        subprocess.Popen(["python", "-m", "http.server", "3000"], shell=True)
    else:
        subprocess.Popen(["python3", "-m", "http.server", "3000"])

def start_daenabot_hands():
    """Start DaenaBot Hands service"""
    print("Starting DaenaBot Hands...")
    subprocess.Popen(["python", "scripts/start_daenabot_hands.py"])

def main():
    print("""
╔══════════════════════════════════════════╗
║           DAENA STARTUP v2.0             ║
╚══════════════════════════════════════════╝
""")
    
    # Check .env exists
    if not os.path.exists(".env"):
        print("❌ .env file not found!")
        print("   Copy .env.example to .env and configure it.")
        sys.exit(1)
    
    # Start components
    start_backend()
    start_frontend()
    start_daenabot_hands()
    
    print("""
✓ All components started!

Access:
- Frontend:  http://localhost:3000
- Backend:   http://localhost:8000
- API Docs:  http://localhost:8000/docs

Press Ctrl+C to stop all services.
""")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down...")

if __name__ == "__main__":
    main()
```

Delete old starters:
```bash
rm _start_backend.bat
rm START_DAENA.bat
rm START_DEMO.bat
```

### F) Git Cleanup

Update `.gitignore` to exclude junk:
```gitignore
# Environment
.env
*.local

# Logs
*.log
logs/
backend_debug_output.txt
compile_log.txt

# Cache
__pycache__/
*.pyc
*.pyo
.pytest_cache/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp

# Build artifacts
dist/
build/
*.egg-info/

# Temporary
*.tmp
*.bak
*~

# Secrets
*.key
*.pem
```

## DELIVERABLE

1. **CLEANUP_ANALYSIS.md** - Analysis of what to keep/delete
2. **DELETION_REPORT.md** - List of deleted files with reasons
3. **Updated README.md** - Reflecting new structure
4. **Consolidated `start.py`** - Single entry point
5. **Clean repo** - No duplicates, organized folders

## CONSTRAINTS

- Do NOT delete anything until analysis is complete
- Create `DELETION_REPORT.md` logging what was removed
- Backup repo before starting: `git add . && git commit -m "Pre-cleanup backup"`
- Run tests after cleanup to ensure nothing broke
- Update all documentation to reflect new structure

## TESTING CHECKLIST
After cleanup:
- [ ] Run `python start.py` → Should start all services
- [ ] Run `python -m pytest tests/` → Should pass
- [ ] Check `git status` → No untracked junk files
- [ ] Review `DELETION_REPORT.md` → Understand what was removed
- [ ] Open frontend → Should work
- [ ] Open backend API docs → Should work
- [ ] All imports still work (no broken references to deleted folders)
