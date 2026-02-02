# Daena AI - Quick Start Guide

**Version**: 2.0.0  
**Status**: Production Ready

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- Python 3.9+
- pip (Python package manager)

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Set Environment Variables
```bash
# Windows PowerShell
$env:DAENA_MEMORY_AES_KEY = "your-encryption-key-here"
$env:DAENA_READ_MODE = "nbmf"
$env:DAENA_DUAL_WRITE = "false"

# Linux/Mac
export DAENA_MEMORY_AES_KEY="your-encryption-key-here"
export DAENA_READ_MODE="nbmf"
export DAENA_DUAL_WRITE="false"
```

### Step 3: Deploy System

**Windows:**
```powershell
.\scripts\deploy_production.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/deploy_production.sh
./scripts/deploy_production.sh
```

### Step 4: Access System

- **Command Center**: http://localhost:8000/command-center
- **API Documentation**: http://localhost:8000/docs
- **Monitoring**: http://localhost:8000/monitoring/memory
- **Health Check**: http://localhost:8000/health

### Step 5: Run Tests
```bash
python scripts/test_system_end_to_end.py
```

---

## 📋 Manual Setup (Alternative)

If you prefer manual setup:

### 1. Database Setup
```bash
python backend/scripts/recreate_database.py
python backend/scripts/seed_6x8_council.py
python Tools/verify_structure.py
```

### 2. Operational Checks
```bash
python Tools/daena_cutover.py --verify-only
python Tools/daena_drill.py
python Tools/generate_governance_artifacts.py
```

### 3. Start Server
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

---

## 🎯 What You Get

### Command Center
- **Metatron's Cube Visualization**: See all 48 agents in hexagonal layout
- **Animated Data Flow**: Watch real-time communication between agents
- **Project Management**: Track projects from idea to execution
- **External Integrations**: Connect to Manus, OpenAI, GitHub, etc.
- **Human Hiring**: Manage job positions and candidates
- **Analytics**: Real-time system metrics and insights

### Backend API
- **60+ Endpoints**: Complete REST API
- **Monitoring**: Real-time metrics and health checks
- **Analytics**: Agent behavior and communication patterns
- **Governance**: Complete audit trail and compliance

### Features
- **48 AI Agents**: 8 departments × 6 agents
- **NBMF Memory**: 3-tier memory system with CAS + SimHash
- **Hex-Mesh Communication**: Patent-pending communication pattern
- **Phase-Locked Rounds**: Scout → Debate → Commit
- **Cost Savings**: 60%+ on LLM calls
- **Performance**: <25ms L1 latency, <120ms L2 latency

---

## 🔧 Troubleshooting

### Server Won't Start
```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac

# Kill existing process if needed
# Then restart server
```

### Database Issues
```bash
# Recreate database
python backend/scripts/recreate_database.py
python backend/scripts/seed_6x8_council.py
```

### Missing Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### Check Logs
```bash
# View deployment logs
tail -f logs/deployment_*.log

# Check server logs
# (Logs are output to console when running uvicorn)
```

---

## 📚 Next Steps

1. **Explore Command Center**: Navigate to `/command-center` and explore the Metatron visualization
2. **Review API Docs**: Check `/docs` for all available endpoints
3. **Monitor Metrics**: Visit `/monitoring/memory` for real-time metrics
4. **Read Documentation**: See `docs/` folder for detailed guides
5. **Deploy to Production**: Follow `docs/PRODUCTION_DEPLOYMENT_GUIDE.md`

---

## 🆘 Support

- **Documentation**: `docs/`
- **API Docs**: `/docs` (when server is running)
- **Issues**: Check logs in `logs/` directory
- **Runbook**: `docs/OPERATIONAL_RUNBOOK.md`

---

**Last Updated**: 2025-01-XX  
**Status**: ✅ Production Ready  
**Version**: 2.0.0

