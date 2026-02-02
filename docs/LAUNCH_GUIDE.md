# 🚀 Daena AI VP - Launch Guide

**Version**: 2.0.0  
**Status**: ✅ Production Ready

---

## Quick Launch (3 Steps)

### Step 1: Start Server

**Option A: Quick Start Script**
```bash
python scripts/quick_start_server.py
```

**Option B: Manual Start**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Option C: Full Deployment**
```bash
# Windows
.\scripts\deploy_production.ps1

# Linux/Mac
./scripts/deploy_production.sh
```

### Step 2: Verify Server

Open in browser:
- **Health**: http://localhost:8000/health
- **Command Center**: http://localhost:8000/command-center
- **API Docs**: http://localhost:8000/docs

Or test via command line:
```bash
curl http://localhost:8000/health
```

### Step 3: Access Command Center

Navigate to: **http://localhost:8000/command-center**

You'll see:
- **Metatron's Cube** visualization with all 48 agents
- **Animated data flow** lines between agents
- **System stats** dashboard
- **Control panel** for projects, hiring, integrations

---

## First-Time Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables (Optional)
```bash
# Windows PowerShell
$env:DAENA_MEMORY_AES_KEY = "your-secure-key-here"
$env:DAENA_READ_MODE = "nbmf"

# Linux/Mac
export DAENA_MEMORY_AES_KEY="your-secure-key-here"
export DAENA_READ_MODE="nbmf"
```

### 3. Setup Database
```bash
python backend/scripts/recreate_database.py
python backend/scripts/seed_6x8_council.py
```

### 4. Start Server
```bash
python scripts/quick_start_server.py
```

---

## What You'll See

### Command Center Features

1. **Metatron's Cube Visualization**
   - Central Daena node (gold/cyan hexagon)
   - 8 department nodes (gold hexagons)
   - 48 agent nodes (cyan hexagons)
   - Animated data flow lines (shiny light)

2. **System Stats Dashboard**
   - Total Agents: 48
   - Active Agents: 48
   - CAS Hit Rate: >60%
   - Projects: Tracked in real-time

3. **Control Panel**
   - New Project button
   - Hire Human button
   - Connect Platform button
   - Full Analytics button
   - Quick Command input

4. **Interactive Features**
   - Click agents to see details
   - Click departments to view overview
   - Watch data flow in real-time
   - Create projects and track workflow

---

## Quick Commands

### Create a Project
Type in Quick Command: `"build a mobile app"` or `"create marketing campaign"`

### Hire Human
Click "Hire Human" button → Create position → Track candidates

### Connect Platform
Click "Connect Platform" → Select platform (Manus, OpenAI, etc.) → Enter API key

### View Analytics
Click "Full Analytics" → See agent efficiency, communication patterns, anomalies

---

## Troubleshooting

### Server Won't Start
```bash
# Check port availability
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# Check dependencies
pip install -r requirements.txt --upgrade

# Check database
python backend/scripts/recreate_database.py
```

### Command Center Not Loading
- Check browser console for errors
- Verify server is running: http://localhost:8000/health
- Check API endpoints: http://localhost:8000/api/v1/departments/

### No Agents Showing
```bash
# Re-seed database
python backend/scripts/seed_6x8_council.py
python Tools/verify_structure.py
```

---

## Next Steps After Launch

1. **Explore Command Center**
   - Click around the Metatron visualization
   - Create a test project
   - Try connecting an external platform

2. **Review Analytics**
   - Check agent efficiency metrics
   - View communication patterns
   - Monitor CAS hit rate

3. **Test Features**
   - Create a project workflow
   - Test external integrations
   - Try human hiring interface

4. **Monitor System**
   - Check monitoring endpoints
   - Review governance artifacts
   - Monitor cost savings

---

## Production Deployment

For production deployment, see:
- `docs/PRODUCTION_DEPLOYMENT_GUIDE.md` - Full deployment guide
- `docs/PRODUCTION_LAUNCH_CHECKLIST.md` - Launch checklist
- `docs/NEXT_STEPS_PRODUCTION.md` - Next steps guide

---

## Support

- **Documentation**: `docs/` folder
- **Quick Start**: `QUICK_START.md`
- **API Docs**: http://localhost:8000/docs (when server running)
- **Troubleshooting**: `docs/OPERATIONAL_RUNBOOK.md`

---

**Ready to Launch!** 🚀

Start the server and explore the world's most advanced AI agent system!

