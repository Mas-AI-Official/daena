# Launch Scripts Fixed - MAS-AI Ecosystem
**Date:** 2025-12-07  
**Status:** ✅ Complete

---

## Summary

Fixed launch scripts to ensure they work with the current project structure.

---

## Scripts Fixed

### 1. `START_DAENA_FRONTEND.bat` ✅

**Changes:**
- Added backend API URL info to output
- Script already uses correct `pnpm dev:daena` command

**Status:** ✅ Fixed

---

### 2. `LAUNCH_COMPLETE_SYSTEM.bat` ✅

**Changes:**
- Added check for virtual environment existence
- Added fallback if venv not found
- Added check for frontend directory
- Changed `npm run dev` to `pnpm dev:daena` for Daena frontend
- Added error handling for missing directories

**Status:** ✅ Fixed

---

## Canonical Launch Scripts

### For Daena Backend Only
```batch
START_SYSTEM.bat
```
- Activates virtual environment
- Runs system verification
- Seeds database
- Starts backend server on port 8000

### For Daena Frontend Only
```batch
START_DAENA_FRONTEND.bat
```
- Checks Node.js and pnpm
- Installs dependencies if needed
- Starts Daena internal UI on port 3000

### For VibeAgent Frontend Only
```batch
START_VIBEAGENT_FRONTEND.bat
```
- Checks Node.js
- Checks Daena backend connection
- Navigates to VibeAgent directory
- Starts VibeAgent UI on port 3001

### For Complete System (All Services)
```batch
START_COMPLETE_SYSTEM.bat
```
- Starts Daena backend
- Starts Daena frontend
- Starts VibeAgent frontend
- All in separate windows

**Alternative:**
```batch
LAUNCH_COMPLETE_SYSTEM.bat
```
- Same as above but with additional checks
- Includes voice service (if available)

---

## How to Run

### Option 1: Complete System (Recommended)
```batch
START_COMPLETE_SYSTEM.bat
```

### Option 2: Individual Services
```batch
REM Terminal 1: Backend
START_SYSTEM.bat

REM Terminal 2: Daena Frontend
START_DAENA_FRONTEND.bat

REM Terminal 3: VibeAgent Frontend
START_VIBEAGENT_FRONTEND.bat
```

### Option 3: Alternative Launcher
```batch
LAUNCH_COMPLETE_SYSTEM.bat
```

---

## Access Points

After launching:

- **Daena Backend API:** http://localhost:8000
- **Daena API Docs:** http://localhost:8000/docs
- **Daena Internal UI:** http://localhost:3000
- **VibeAgent Platform:** http://localhost:3001

---

## Prerequisites

1. **Python 3.10+** with virtual environment
2. **Node.js 18+** installed
3. **pnpm** installed (or will be auto-installed)
4. **Backend dependencies** installed in venv
5. **Frontend dependencies** installed (`pnpm install` in `frontend/`)

---

## Troubleshooting

### Backend Won't Start
- Check virtual environment exists: `venv_daena_main_py310`
- Check Python version: `python --version`
- Check dependencies: `pip list` in venv

### Frontend Won't Start
- Check Node.js: `node --version`
- Check pnpm: `pnpm --version`
- Install dependencies: `cd frontend && pnpm install`

### Port Already in Use
- Backend (8000): Stop other services on port 8000
- Daena Frontend (3000): Stop other services on port 3000
- VibeAgent (3001): Stop other services on port 3001

---

**Last Updated:** 2025-12-07






