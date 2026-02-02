# Daena Complete System Launch Instructions

## 🚀 Quick Start

### Main Launcher (Recommended)
```batch
LAUNCH_DAENA_COMPLETE.bat
```

This script will:
1. ✅ Check all prerequisites (Python, Node.js, npm)
2. ✅ Set up backend environment (create/activate venv)
3. ✅ Set up frontend environment (install npm packages)
4. ✅ Check backend health and start if needed
5. ✅ Check frontend health and start if needed
6. ✅ Verify all system components
7. ✅ Display system status
8. ✅ **Automatically open browser** to http://localhost:3000

### Alternative: Test First, Then Launch
```batch
TEST_AND_LAUNCH.bat
```

This script does the same but with more verbose testing output.

## 📋 What Gets Checked

### Prerequisites
- ✅ Python 3.8+ installed
- ✅ Node.js 18+ installed
- ✅ npm installed

### Backend Environment
- ✅ Virtual environment (venv) exists or creates it
- ✅ Backend dependencies installed from `requirements.txt`
- ✅ Backend server running on port 8000
- ✅ Backend API responding at `/api/v1/health`

### Frontend Environment
- ✅ Frontend dependencies installed (`node_modules`)
- ✅ Frontend server running on port 3000
- ✅ Frontend responding (may take 30-60 seconds on first compile)

### System Components
- ✅ Database file exists (or will be created)
- ✅ All routes registered
- ✅ Both environments active

## 🔐 Login Credentials

- **Username:** `masoud`
- **Password:** `masoudtnt2@`

## 🌐 URLs

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **Backend Health:** http://localhost:8000/api/v1/health

## ⚙️ How It Works

1. **Environment Activation:**
   - Backend: Activates `venv\Scripts\activate.bat`
   - Frontend: Uses npm from system PATH

2. **Server Startup:**
   - Backend: Starts in separate window (`Daena Backend Server`)
   - Frontend: Starts in separate window (`Daena Frontend Server`)

3. **Health Checks:**
   - Uses `curl` to test HTTP responses
   - Waits with timeouts for servers to start
   - Retries multiple times if needed

4. **Browser Launch:**
   - Automatically opens default browser
   - Navigates to http://localhost:3000

## ⏱️ Timing

- **First Run:** 60-90 seconds (installs dependencies, compiles)
- **Subsequent Runs:** 20-30 seconds (servers start faster)

## 🛑 Stopping Servers

Close the separate windows:
- `Daena Backend Server` window
- `Daena Frontend Server` window

Or use Ctrl+C in each window.

## 🔧 Troubleshooting

### Backend Not Starting
- Check if port 8000 is already in use
- Verify Python and dependencies are installed
- Check `backend\requirements.txt` exists

### Frontend Not Starting
- Check if port 3000 is already in use
- Verify Node.js and npm are installed
- Check `frontend\apps\daena\package.json` exists
- First compile can take 60+ seconds

### Browser Not Opening
- Manually navigate to http://localhost:3000
- Check if frontend is still compiling (wait 30-60 seconds)

### Dependencies Issues
- Backend: Run `pip install -r backend\requirements.txt`
- Frontend: Run `npm install` in `frontend\apps\daena`

## 📝 Notes

- Both servers run in **separate windows** for easy monitoring
- Frontend compilation happens on first run (can be slow)
- Backend auto-reloads on code changes
- Frontend auto-reloads on code changes (Next.js hot reload)

## ✅ Success Indicators

When everything is working:
- ✅ Backend window shows: `Uvicorn running on http://0.0.0.0:8000`
- ✅ Frontend window shows: `Ready on http://localhost:3000`
- ✅ Browser opens to login page
- ✅ Can login with credentials above

## 🎯 Next Steps After Launch

1. Login with credentials
2. Navigate through dashboard
3. Check departments (8 total)
4. Check agents (48 total)
5. Explore Council governance
6. Test VibeAgent connections
7. Review analytics and monitoring

---

**Ready to launch? Run `LAUNCH_DAENA_COMPLETE.bat`!**






