# DEMO RUNBOOK - AI Tinkerers Toronto

**Event**: AI Tinkerers Toronto · January 29, 2026  
**Venue**: Google Toronto  
**Duration**: 6 minutes live demo

---

## 🚀 Quick Start (Local)

```bash
cd D:\Ideas\Daena_old_upgrade_20251213

# 1. Activate environment
.\venv_daena_main_py310\Scripts\activate

# 2. Start backend
python -m backend.main

# 3. Open demo page
# Navigate to: http://localhost:8000/demo
```

---

## ✅ Pre-Flight Checklist (2 hours before)

### Backend
- [ ] `/api/v1/health/` returns `{"status": "healthy"}`
- [ ] `/api/v1/demo/health` returns `{"status": "ready"}`
- [ ] Ollama running with at least one model

### Demo Flow
- [ ] Run smoke test: `python scripts\demo_smoke_test.py`
- [ ] All 5 tests pass
- [ ] Demo page loads in < 3 seconds

### Offline Fallback
- [ ] Disconnect WiFi temporarily
- [ ] Demo still completes (local model)
- [ ] Cached responses work

### Stage Kit
- [ ] Laptop charger + adapter
- [ ] Backup video on desktop (`demo_assets\backup_demo.mp4`)
- [ ] ID + confirmation email ready for building entry

---

## 📋 Demo Script (6 minutes)

### Minute 0-1: Introduction
> "I'm demoing Daena, an AI VP that routes, reviews, and governs LLM responses in real-time."

### Minute 1-3: Live Demo
1. Enter prompt: *"Explain how Daena routes requests to different AI models"*
2. Click **RUN**
3. Point out:
   - **Router Decision**: Shows which model was selected and why
   - **Council Votes**: Security, Reliability, Product each vote
   - **Trace Timeline**: Real-time execution flow

### Minute 3-5: Technical Deep Dive
- "The router uses Sunflower scoring to pick optimal model"
- "Council is prompt-based, not fine-tuned — runs on any LLM"
- "Full trace enables debugging and compliance audits"

### Minute 5-6: Lessons Learned
- "Hard-won lesson: Always have offline fallback"
- "Governance layer adds ~500ms but catches 12% of edge cases"
- "Built with Antigravity IDE + Gemini 3 Flash"

---

## 🔧 Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start | Check port 8000 is free: `netstat -an | findstr 8000` |
| Ollama not responding | Restart: `ollama serve` |
| Demo hangs | Fallback kicks in after 5s - wait or use cached |
| UI blank | Hard refresh (Ctrl+Shift+R) |
| Total failure | Switch to backup video |

---

## 📞 Emergency Contacts

- **Venue WiFi**: (Check Google badge for credentials)
- **Backup hotspot**: Personal phone tethering
- **Video fallback**: `demo_assets\backup_demo.mp4`

---

## 🎯 Success Criteria

- [ ] Demo completes without errors
- [ ] All 3 council votes visible
- [ ] Trace timeline populated
- [ ] Audience understands router + council + trace flow
