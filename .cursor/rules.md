# Cursor Rules - Daena Project

**CRITICAL: These rules prevent file truncation and ensure code quality.**

## Non-Negotiable Rules

### 1. NO TRUNCATION
- **NEVER** truncate, shorten, or summarize any `.py`, `.html`, or `.js` file
- **NEVER** replace large sections with placeholders like "..." or "contents truncated"
- **NEVER** delete entire functions or classes without explicit user request
- If a file is too large, use minimal diffs and patch only the necessary lines

### 2. MINIMAL DIFFS ONLY
- When editing files, make **targeted changes** only
- Preserve all existing code unless explicitly asked to remove it
- Use `search_replace` tool for precise edits, not full file rewrites
- If unsure, ask the user before making large changes

### 3. NO DUPLICATES
- **NEVER** create duplicate files (no `_v2`, `_new`, `_fixed` suffixes)
- If a similar file exists, modify the existing one
- Consolidate duplicates if found, don't create new ones

### 4. PRESERVE CORE FILES
- **NEVER** rewrite core brain files (`backend/daena_brain.py`, `backend/core/brain/store.py`)
- **NEVER** delete or replace canonical routers or services
- Use adapters/wrappers for extensions, not replacements

### 5. VERIFY BEFORE COMMITTING
- Run guard scripts before making changes:
  - `scripts/verify_no_truncation.py`
  - `scripts/verify_no_duplicates.py`
- If guard scripts fail, **STOP** and report the issue

## File Editing Guidelines

### Python Files
- Use `search_replace` for targeted edits
- Preserve all imports and existing code
- Only modify the specific function/method requested
- Never remove docstrings or comments unless explicitly requested

### Batch Files
- Preserve error handling and logging
- Keep all existing functionality
- Add new features without removing old ones

### Documentation
- Update existing docs rather than creating duplicates
- Use dated folders for versioned docs: `docs/YYYY-MM-DD/`

## Project Structure

### Canonical Paths
- Project root: `D:\Ideas\Daena_old_upgrade_20251213`
- Backend entrypoint: `backend/main.py`
- Launcher: `START_DAENA.bat`
- Environment setup: `setup_env.bat` or `scripts/setup_env.py`

### Protected Files
- `backend/daena_brain.py` - Core brain (read-only, use adapters)
- `backend/core/brain/store.py` - Brain store (read-only, use adapters)
- `backend/utils/sunflower_registry.py` - Registry (read-only, use adapters)
- `START_DAENA.bat` - Main launcher (modify carefully)

## Execute manual verification steps

When asked to **execute manual steps**, **run verification**, or **run all manual steps and fix errors**:

1. **Start backend** (if not running): run `scripts\start_backend_with_env.bat` in a separate terminal, or use `.\scripts\run_all_tests.ps1 -StartBackend` (PowerShell). Backend must listen at http://localhost:8000 with `EXECUTION_TOKEN` set.
2. **Wait for health**: poll `GET /health` until 200 (up to 90s).
3. **Run in order**:  
   - **One-shot:** `scripts\run_manual_steps.bat` (checks health, then smoke + manual_verification_steps).  
   - Or: `python scripts\smoke_control_plane.py --base http://localhost:8000 --token <EXECUTION_TOKEN>` then `python scripts\manual_verification_steps.py` (set `DAENA_BASE_URL`, `EXECUTION_TOKEN`).
4. **Fix errors** in scripts or APIs before proceeding; re-run until both pass.

Manual verification steps (API equivalents) are implemented in `scripts/manual_verification_steps.py` (token gating, skills run, execution run, proactive run_once, tasks create/run, runbook page, skills artifacts, lockdown).

## When in Doubt

1. **Ask the user** before making large changes
2. **Run guard scripts** to verify no truncation/duplicates
3. **Make minimal changes** - patch, don't rewrite
4. **Preserve existing code** - only modify what's necessary
5. **Test changes** - verify launcher still works after edits

---

**Last Updated**: 2026-01-30  
**Purpose**: Prevent file truncation and ensure code quality








