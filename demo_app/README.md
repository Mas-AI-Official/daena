# Daena Live Demo

🏛️ **AI Tinkerers Toronto - January 2026**

A public demonstration of Daena AI VP capabilities - your company's AI-native executive.

## What's Included

| Component | Description |
|-----------|-------------|
| **Demo UI** | Interactive router + council governance demo |
| **Sample Queries** | Pre-built scenarios showing AI decision-making |
| **Trace Timeline** | Visual request lifecycle from routing to response |
| **Demo Auth** | Simple PIN-based access for live demos |
| **Cloudflare Tunnel** | Scripts to expose demo to internet |

## NOT Included (Private)

- Full production backend
- Founder panel / admin features  
- Database write operations
- Voice cloning files
- File system access

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Ollama running locally with `deepseek-r1:8b` model
- Backend server running on `localhost:8000`

### Step 1: Start the Backend
```bash
cd D:\Ideas\Daena_old_upgrade_20251213
.\START_DEMO.bat
```

### Step 2: Access Demo
Open http://localhost:8000/demo

### Step 3 (Optional): Share via Tunnel
```bash
# Windows
.\demo_app\START_TUNNEL.bat

# macOS/Linux
./demo_app/start_tunnel.sh
```

Share the Cloudflare URL with demo attendees.

---

## 🔐 Demo Authentication (Optional)

Enable PIN protection for public demos:

```bash
# Set environment variables before starting
set DEMO_AUTH_ENABLED=true
set DEMO_PIN=AITINKER2026
```

Default PIN: `AI2026`

---

## 📝 Demo Flow

1. Open http://localhost:8000/demo (or tunnel URL)
2. Select a sample prompt OR type your own:
   - "Should we deploy to production tonight?"
   - "Scan the codebase for security issues"
   - "Run a full diagnostics check"
3. Click **RUN DEMO**
4. Watch the magic:
   - 🧠 **Router Decision** - Which LLM tier handles this?
   - ⚖️ **Council Votes** - Security, Reliability, Product perspectives
   - ⏱️ **Trace Timeline** - Full request lifecycle
   - 💬 **Final Response** - Synthesized answer

---

## 🔌 API Endpoints (Demo Only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/demo/health` | GET | Check demo status |
| `/api/v1/demo/run` | POST | Run demo scenario |
| `/api/v1/demo/trace/{id}` | GET | Get trace timeline |
| `/demo/login` | GET/POST | Demo PIN login |
| `/demo/logout` | GET | End demo session |

---

## 🎙️ Demo Script

### Opening (30 sec)
> "Daena is an AI-native VP that runs your company. She's not just a chatbot - she has a full governance system with councils, routing intelligence, and tool execution."

### Demo 1: Smart Router (1 min)
> "Watch how Daena routes requests to different AI tiers based on complexity..."
- Type: "What's 2+2?"
- Type: "Should we pivot our product strategy?"

### Demo 2: Council Governance (2 min)
> "For important decisions, Daena convenes a council..."
- Type: "Deploy the new payment system to production"
- Show: Security concerns, Reliability checks, Product alignment

### Demo 3: Tool Execution (1 min)
> "Daena can also execute tools..."
- Type: "Open browser and go to google.com"
- Type: "Search the web for AI Tinkerers Toronto"

### Closing
> "This is just the demo. The full system has 400+ API endpoints, 48 department councils, voice cloning, and autonomous task execution."

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Brain offline" | Start Ollama: `ollama serve` |
| Slow responses | Pull model: `ollama pull deepseek-r1:8b` |
| WebSocket errors | Refresh page, check backend is running |
| Tunnel won't start | Install cloudflared: `winget install Cloudflare.cloudflared` |

---

## 📁 Files

```
demo_app/
├── README.md           # This file
├── .env.example        # Environment template
├── START_DEMO.bat      # Windows launcher (copied)
├── START_TUNNEL.bat    # Cloudflare tunnel (Windows)
├── start_tunnel.sh     # Cloudflare tunnel (Unix)
├── demo_auth.py        # PIN authentication
├── demo_mode.py        # Demo configuration
├── demo.py             # API routes
├── demo_council.py     # Lightweight council
├── demo_trace.py       # Trace logger
├── demo_ai_thinker.md  # Demo script
├── DEMO_RUNBOOK.md     # Stage-day guide
├── templates/
│   └── demo.html       # Demo UI
├── static/
│   └── demo.js         # Frontend logic
└── scripts/
    └── demo_smoke_test.py  # Validation
```

---

## 📜 License

Proprietary - Mas-AI Official  
**Do NOT share the full backend source code publicly.**

---

Made with ❤️ for AI Tinkerers Toronto
