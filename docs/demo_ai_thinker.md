# AI Thinker Demo Script - Daena Local AI VP

## Quick Setup (Pre-Demo)

```bash
cd D:\Ideas\Daena_old_upgrade_20251213

# Option 1: Use demo launcher
.\START_DEMO.bat

# Option 2: Manual start
.\venv_daena_main_py310\Scripts\activate
set DEMO_MODE=1
python -m backend.main
```

**Wait for:** `Uvicorn running on http://0.0.0.0:8000`

---

## Demo Windows (Open These)

| Window | URL | Purpose |
|--------|-----|---------|
| **Daena Office** | http://localhost:8000/ui/daena-office | Main chat interface |
| **Brain Settings** | http://localhost:8000/ui/brain-settings | Show local models |
| **Founder Panel** | http://localhost:8000/ui/founder-panel | Show company overview |
| **Demo Page** | http://localhost:8000/demo | Router + Council demo |

---

## Demo Flow (5-6 Minutes)

### Part 1: Show the Brain (1 min)
**Open:** Brain Settings

1. Show detected models: `deepseek-r1:8b`, `qwen2.5:7b-instruct`, etc.
2. Point out: "These are LOCAL models running on Ollama - no cloud required"
3. Toggle a model on/off to show selection works

**Say:** "Daena can switch between these models based on task type - code, reasoning, fast chat."

---

### Part 2: Talk to Daena (2 min)
**Open:** Daena Office

1. Click "New Chat"
2. Ask: **"Daena, run the company today. What should I prioritize?"**
3. Wait for response (uses local model)
4. Show the streaming response with Daena avatar

**Say:** "This is all running locally. Daena routes to the best model, orchestrates agents, and responds as a VP."

5. Try: **"Search the web for AI Tinkerers Toronto"**
   - Shows web search tool execution
   - Results appear inline in chat

6. Try: **"What models do you have available?"**
   - Shows model list tool

---

### Part 3: Router + Council Demo (1 min)
**Open:** Demo Page

1. Click sample prompt "🔀 Routing"
2. Click **RUN DEMO**
3. Watch:
   - Router decision card populates (model, provider, reason)
   - Council votes animate in (Security ✓, Reliability ✓, Product ✓)
   - Trace timeline dots light up
   - Response appears

**Say:** "This shows our governance layer - every decision passes through a council that checks security, reliability, and product fit."

---

### Part 4: Founder Overview (1 min)
**Open:** Founder Panel

1. Show the 8 departments (Sunflower structure)
2. Show the 48 agents (8×6)
3. Create a snapshot: "This lets founders roll back to previous configurations"

**Say:** "The Founder sees everything - departments, agents, councils. And can snapshot the entire company state."

---

### Part 5: Voice (Optional - 30 sec)
**In Daena Office:**

1. Click the microphone icon to enable voice
2. Ask something verbally (if voice env is configured)
3. Daena responds with TTS

**Say:** "Full voice pipeline - speech-to-text, reasoning, text-to-speech with voice cloning."

---

## Backup Prompts (If Stuck)

| Prompt | What It Shows |
|--------|---------------|
| "Run diagnostics" | System health check |
| "List my files" | Workspace access |
| "Analyze the departments" | DB inspector + analysis |
| "Open https://google.com" | Browser automation |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "Brain offline" | Run `ollama serve` in separate terminal |
| "No models" | Run `ollama pull deepseek-r1:8b` |
| Port 8000 in use | Kill other Python processes |
| Voice not working | Check `venv_daena_audio_py310` |

---

## Elevator Pitch

> "Daena is an AI Vice President that runs your company locally. It orchestrates multiple LLMs, manages 8 departments with 48 agents, and passes every decision through a governance council. No cloud required - your entire AI executive team runs on your laptop."

---

## Key Differentiators

1. **Local-first** - Runs entirely on Ollama, no API keys needed
2. **Multi-LLM router** - Picks the right model for each task
3. **Council governance** - Security, Reliability, Product review
4. **Full VP capabilities** - Tools, search, browser, voice
5. **Snapshot/rollback** - Founder can revert configurations
