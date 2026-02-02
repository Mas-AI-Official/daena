# Launcher Checkpoints Guide

**Date**: 2025-12-13  
**Status**: ✅ Implemented

---

## Overview

The Daena launcher (`LAUNCH_DAENA_COMPLETE.bat`) includes critical checkpoints to ensure code quality and prevent common issues before starting the server.

---

## Checkpoint Order

The launcher runs checkpoints in this exact order:

1. **Environment Setup** (`setup_environments.bat`)
2. **Python/Pip Verification**
3. **Import Checks** (FastAPI, httpx)
4. **Truncation Check** (`verify_no_truncation.py`)
5. **Duplicate Check** (`verify_no_duplicates.py`)
6. **Requirements Update** (optional, if `DAENA_UPDATE_REQUIREMENTS=1`)
7. **Server Start**

---

## Checkpoint Details

### 1. Truncation Check

**Script**: `scripts/verify_no_truncation.py`

**What it checks:**
- No "truncated" markers in `.py` files
- No merge conflict markers (`<<<<<<<`, `>>>>>>>`)
- No placeholder text indicating truncation

**Failure behavior:**
- Launcher stops
- Error message displayed
- Window stays open (if `DAENA_LAUNCHER_STAY_OPEN=1`)

**Why it matters:**
- Prevents running with broken/cut-off code
- Catches Cursor truncation issues early

---

### 2. Duplicate Check

**Script**: `scripts/verify_no_duplicates.py`

**What it checks:**
- No duplicate route modules
- No duplicate "same purpose" files
- No conflicting implementations

**Failure behavior:**
- Launcher stops
- Error message displayed
- Window stays open (if `DAENA_LAUNCHER_STAY_OPEN=1`)

**Why it matters:**
- Prevents confusion from duplicate code
- Ensures single source of truth

---

### 3. Requirements Update (Optional)

**Script**: `scripts/update_requirements.py`

**When it runs:**
- Only if `DAENA_UPDATE_REQUIREMENTS=1`

**What it does:**
- Freezes current environment to `requirements.lock.txt`
- Optionally updates `requirements.txt` from lockfile

**Failure behavior:**
- Warning displayed
- Launcher continues (non-blocking)

**Why it's optional:**
- Not critical for launch
- Useful for keeping requirements in sync

---

## Pre-Commit Guard

**Script**: `scripts/pre_commit_guard.bat`

**Purpose**: Run checkpoints before committing code

**What it does:**
1. Runs truncation check
2. Runs duplicate check
3. Exits with error if either fails

**Usage:**
```batch
REM Before committing
scripts\pre_commit_guard.bat
if errorlevel 1 (
    echo Fix errors before committing
    exit /b 1
)
```

**Integration:**
- Can be added to git hooks
- Can be run manually before commits
- Can be run in CI/CD pipelines

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DAENA_UPDATE_REQUIREMENTS` | `0` | Run requirements update checkpoint |
| `DAENA_LAUNCHER_STAY_OPEN` | `1` | Keep window open on error |
| `DAENA_RUN_TESTS` | `0` | Run tests before launch (if implemented) |

---

## Checkpoint Output

### Success
```
[4d/12] Verifying no truncation markers...
OK: no truncation placeholder patterns detected in .py files

[4e/12] Verifying no duplicate modules/files...
OK: no duplicate/same-purpose files detected
```

### Failure
```
[4d/12] Verifying no truncation markers...
FAIL: Truncation markers detected:
 - backend/middleware/auth.py: contains "contents have been truncated"

[FATAL] Truncation markers detected in .py files. Fix before proceeding.
```

---

## Manual Checkpoint Execution

You can run checkpoints manually:

```batch
REM Truncation check
python scripts\verify_no_truncation.py

REM Duplicate check
python scripts\verify_no_duplicates.py

REM Pre-commit guard (both checks)
scripts\pre_commit_guard.bat
```

---

## Best Practices

1. **Run checkpoints before committing**
   ```batch
   scripts\pre_commit_guard.bat
   ```

2. **Fix errors immediately**
   - Don't bypass checkpoints
   - Fix truncation/duplicate issues before proceeding

3. **Keep checkpoints fast**
   - Checkpoints should complete in < 5 seconds
   - If slow, optimize the scripts

4. **Document new checkpoints**
   - Add to this guide
   - Update launcher comments
   - Add to pre-commit guard if needed

---

## Adding New Checkpoints

To add a new checkpoint:

1. **Create the script** (e.g., `scripts/verify_new_thing.py`)
2. **Add to launcher** (`LAUNCH_DAENA_COMPLETE.bat`):
   ```batch
   echo [X/12] Verifying new thing...
   "%PY_MAIN%" scripts\verify_new_thing.py
   if errorlevel 1 (
       call :FATAL "New thing check failed. Fix before proceeding."
   )
   ```
3. **Add to pre-commit guard** (if critical):
   ```batch
   "%PY_MAIN%" scripts\verify_new_thing.py
   if errorlevel 1 (
       echo [FATAL] New thing check failed
       exit /b 1
   )
   ```
4. **Document in this guide**

---

## Troubleshooting

### "Checkpoint script not found"

**Cause**: Script missing or path incorrect

**Solution**: Verify script exists at `scripts/verify_*.py`

### "Checkpoint takes too long"

**Cause**: Script is scanning too many files

**Solution**: Optimize script to exclude vendored directories

### "Checkpoint fails but code works"

**Cause**: False positive in check

**Solution**: Review check logic, may need refinement

---

**STATUS: ✅ LAUNCHER CHECKPOINTS COMPLETE**









