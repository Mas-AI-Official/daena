# Dependency Automation Guide

**Date**: 2025-12-13  
**Status**: ✅ Implemented

---

## Overview

The Daena system includes automated dependency management to ensure consistent environments across development and production.

---

## Components

### 1. `setup_environments.bat`

**Purpose**: Automated environment setup and dependency installation

**What it does:**
1. Creates venv if missing (`venv_daena_main_py310`, `venv_daena_audio_py310`)
2. Upgrades pip, setuptools, wheel
3. Installs from `requirements.txt`
4. Optionally installs automation tools (if `ENABLE_AUTOMATION_TOOLS=1`)
5. Generates `requirements.lock.txt` for reproducibility

**Error Handling:**
- Stops on failure (doesn't silently continue)
- Prints failing package name
- Keeps window open if `DAENA_LAUNCHER_STAY_OPEN=1`

**Usage:**
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
setup_environments.bat
```

**Environment Variables:**
- `ENABLE_AUTOMATION_TOOLS=1` - Install selenium, pyautogui (optional)
- `DAENA_LAUNCHER_STAY_OPEN=1` - Keep window open on error

---

### 2. `scripts/update_requirements.py`

**Purpose**: Auto-update requirements from lockfile

**What it does:**
1. Always freezes current environment to `requirements.lock.txt`
2. Optionally updates `requirements.txt` (only if `DAENA_UPDATE_REQUIREMENTS=1`)
3. Preserves critical pinned packages
4. Never removes packages unless explicitly missing

**Usage:**
```batch
REM Freeze to lockfile only (default)
python scripts\update_requirements.py

REM Freeze + update requirements.txt
set DAENA_UPDATE_REQUIREMENTS=1
python scripts\update_requirements.py
```

**Safety:**
- Never removes packages automatically
- Only updates if explicitly enabled
- Preserves comments and blank lines

---

### 3. `scripts/refresh_requirements_txt.py`

**Purpose**: Safe normalization (deduplication only)

**What it does:**
- Removes duplicate package lines
- Preserves comments and blank lines
- Does NOT guess new dependencies

**Usage:**
```batch
python scripts\refresh_requirements_txt.py
```

---

## Workflow

### Initial Setup
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
setup_environments.bat
```

### Regular Updates
```batch
REM 1. Install new packages manually
venv_daena_main_py310\Scripts\activate
pip install new-package

REM 2. Freeze to lockfile
python scripts\update_requirements.py

REM 3. (Optional) Update requirements.txt
set DAENA_UPDATE_REQUIREMENTS=1
python scripts\update_requirements.py
```

### Before Production
```batch
REM 1. Ensure lockfile is up to date
python scripts\update_requirements.py

REM 2. Verify requirements.txt matches lockfile
REM (manual review recommended)
```

---

## File Structure

```
Daena_old_upgrade_20251213/
├── requirements.txt          # Primary dependencies (human-readable)
├── requirements.lock.txt     # Exact versions (auto-generated)
├── setup_environments.bat    # Automated setup script
└── scripts/
    ├── update_requirements.py      # Freeze + optional update
    └── refresh_requirements_txt.py # Deduplication only
```

---

## Best Practices

1. **Always freeze after installing packages**
   ```batch
   pip install new-package
   python scripts\update_requirements.py
   ```

2. **Review lockfile before committing**
   - Check for unexpected version changes
   - Verify all required packages are present

3. **Use lockfile for production**
   - Install from `requirements.lock.txt` in production
   - Ensures exact version reproducibility

4. **Don't manually edit lockfile**
   - Always regenerate via `update_requirements.py`
   - Lockfile is auto-generated

---

## Troubleshooting

### "Failed to install requirements.txt"

**Cause**: A package in `requirements.txt` failed to install

**Solution**:
1. Check the error message for the failing package
2. Verify the package name and version
3. Check if the package requires system dependencies
4. Remove or update the problematic package

### "Lockfile out of sync"

**Cause**: `requirements.lock.txt` doesn't match current environment

**Solution**:
```batch
python scripts\update_requirements.py
```

### "Duplicate packages in requirements.txt"

**Cause**: Multiple entries for the same package

**Solution**:
```batch
python scripts\refresh_requirements_txt.py
```

---

## Environment Variables Summary

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENABLE_AUTOMATION_TOOLS` | `0` | Install selenium, pyautogui |
| `DAENA_UPDATE_REQUIREMENTS` | `0` | Update requirements.txt from lockfile |
| `DAENA_LAUNCHER_STAY_OPEN` | `1` | Keep window open on error |

---

**STATUS: ✅ DEPENDENCY AUTOMATION COMPLETE**









