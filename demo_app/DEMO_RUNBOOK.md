# DEMO RUNBOOK - AI Tinkerers Toronto (Jan 29, 2026)

## Quick Start (5-minute setup)

### 1. Start Backend
```bash
cd D:\Ideas\Daena_AITinkerersDemo_20260129
.\START_DEMO.bat
```

Or manually:
```bash
set DEMO_MODE=1
set DEFAULT_LOCAL_MODEL=deepseek-r1:8b
set OLLAMA_BASE_URL=http://127.0.0.1:11434
python -m backend.main
```

### 2. Verify Server Running
Open browser to: **http://localhost:8000**

Expected: Daena dashboard loads without errors.

### 3. Open Demo Page
Navigate to: **http://localhost:8000/demo**

---

## Smoke Test (Run Before Presentation)

### Test 1: Demo Health Check
```bash
curl http://localhost:8000/api/v1/demo/health
```
Expected: `{"status": "ready", ...}`

### Test 2: Run Demo with Prompt 1
1. Go to http://localhost:8000/demo
2. Enter prompt: `"Compare AWS vs Azure for a 500-user startup"`
3. Click **RUN DEMO**
4. Verify:
   - Router shows model selection (e.g., `deepseek-r1:8b`)
   - Council votes appear (Security ✓, Reliability ✓, Product ✓)
   - Timeline dots animate left-to-right
   - Response appears in output area

### Test 3: Run Demo with Prompt 2
1. Enter prompt: `"Draft a 90-day hiring plan for an AI startup"`
2. Click **RUN DEMO**
3. Verify same flow works

### Test 4: Check Trace Display
After running demos, the timeline should show:
- **Route** → **Security** → **Reliability** → **Product** → **Merge** → **Memory**
- Each with timing in ms

---

## Key URLs for Demo

| Purpose | URL |
|---------|-----|
| Demo page (main) | http://localhost:8000/demo |
| Daena chat | http://localhost:8000/ |
| Founder panel | http://localhost:8000/founder |
| API docs | http://localhost:8000/docs |
| Demo health | http://localhost:8000/api/v1/demo/health |
| Brain status | http://localhost:8000/api/v1/brain/status |

---

## What to Show (6-Minute Script)

### 0:00 - 0:30: Open Demo
- Open http://localhost:8000/demo
- Run one prompt
- Point at timeline as it animates

### 0:30 - 2:30: Router Agent
- Open: `Core/routing/router_agent.py` (or show in VS Code)
- Show: model selection signals
- Explain: "Router picks a model based on complexity, cost, speed"

### 2:30 - 4:30: Council Scoring
- Open: `backend/services/demo_council.py`
- Show: role scoring format (security, reliability, product)
- Explain: "Each role evaluates independently, then we merge"

### 4:30 - 5:30: Traceability
- Open: `backend/services/demo_trace.py`
- Show: trace event logging
- Explain: "Every decision is logged for debugging and audit"

### 5:30 - 6:00: Hard-Won Lesson
- "Separating router vs evaluator avoids mode-flipping"
- "Makes decisions debuggable and reproducible"

---

## Backup Plan

If anything breaks during the demo:
1. Have YouTube video ready (90-sec recording)
2. Have screenshots of trace timeline
3. Switch to explaining the architecture verbally

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Backend won't start | Check if port 8000 is in use: `netstat -ano | findstr 8000` |
| Ollama not connected | Run `ollama serve` first, verify at http://127.0.0.1:11434 |
| Demo page blank | Check browser console for JS errors |
| "Not found" errors | Verify you're in the right folder with correct virtual env |
| Council returns empty | Check LLM connection in brain status |

---

## Pre-Event Checklist

- [ ] Ollama running with deepseek-r1:8b model
- [ ] Backend starts without errors
- [ ] Demo page loads at /demo
- [ ] Both test prompts run successfully
- [ ] Trace timeline animates correctly
- [ ] VS Code open with key files ready
- [ ] Backup video uploaded and URL saved

---

**Last Updated:** January 19, 2026
**Folder:** D:\Ideas\Daena_AITinkerersDemo_20260129
