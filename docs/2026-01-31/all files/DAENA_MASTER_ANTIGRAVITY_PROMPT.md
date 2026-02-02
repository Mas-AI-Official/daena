# DAENA — Master Antigravity Prompt & Security Hardening Document
## Autonomous Company OS · VP-Layer Orchestration · DeFi / Web3 · Council Governance
### Build Date: 2026-01-31 | Version: 2.0

---

> **DATA PRIVACY NOTICE**: All code, keys, and secrets in this document are for your private local build only. Nothing here should be committed to any public repo. Your `.env`, keys, and model paths stay local. Antigravity runs on YOUR GPU — no cloud telemetry, no training pipeline, no data leaving your machine unless YOU explicitly configure an outbound integration.

---

# PART 1 — SECURITY HARDENING (Critical Fixes from Codebase Audit)

Before you run a single prompt through Antigravity, these issues must be fixed in your repo. Every one of these was found in the current codebase.

---

## 1.1 Exposed Secrets — ROTATE IMMEDIATELY

Your `.env_azure_openai` has live keys in the repo. These are already burned:

| What | Action |
|------|--------|
| Azure OpenAI API Key (`4caImQ91An…`) | Rotate NOW in Azure Portal → Keys & Endpoint |
| HuggingFace Token (`hf_WmLaYU…`) | Rotate NOW at huggingface.co/settings/tokens |
| Azure Endpoint URL | Change or lock to VNet-only after rotation |

After rotating, create your `.env` with the new values and NEVER commit it.

## 1.2 `.gitignore` Hardening

Add this to your repo root `.gitignore` immediately:

```
# Secrets & Environment
.env
.env_azure_openai
.env.*
!.env.example

# Models & Brain (can be 50GB+)
MODELS_ROOT/
local_brain/
DaenaBrain/
hf_cache/
*.bin
*.safetensors
*.gguf

# Logs & Audit
logs/
*.log
audit_*.json

# OS
Thumbs.db
.DS_Store
```

## 1.3 WebSocket Security — Missing Origin Check

**File**: `static/js/websocket-client.js`

**Problem**: The WebSocket connects to `ws://` with zero origin validation. Anyone on your network can inject messages.

**Fix to apply in your repo**:

```javascript
// In websocket-client.js, REPLACE the connect() method's URL construction:

connect(endpoint, connectionId = null) {
    const id = connectionId || endpoint;

    if (this.connections.has(id)) {
        const ws = this.connections.get(id);
        if (ws.readyState === WebSocket.OPEN) return ws;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${endpoint}`;

    // ✅ SECURITY: Verify we're connecting to ourselves only
    const allowedHosts = [window.location.host, '127.0.0.1:8000', 'localhost:8000'];
    const parsedHost = new URL(wsUrl).host;
    if (!allowedHosts.includes(parsedHost)) {
        console.error(`🚨 BLOCKED WebSocket to unauthorized host: ${parsedHost}`);
        return null;
    }

    // ✅ SECURITY: Add origin header for backend to verify
    const ws = new WebSocket(wsUrl, [], { 
        // Subprotocol used as a lightweight auth signal
    });
    // ... rest of method unchanged
}
```

## 1.4 API Client — Execution Token Stored in sessionStorage

**File**: `static/js/api-client.js`

**Problem**: `sessionStorage` is readable by ANY JavaScript on the page (XSS vector). The execution token is the most sensitive credential in the system.

**Fix**: Move token handling to an HttpOnly cookie set by the backend, OR at minimum scope it to a single-use per-request flow:

```javascript
// REPLACE setExecutionToken / getExecutionToken with:
setExecutionToken(token) {
    // Store in memory only — never sessionStorage in production
    this._execToken = token;
    // Expire after 15 minutes of inactivity
    clearTimeout(this._execTokenTimer);
    this._execTokenTimer = setTimeout(() => { this._execToken = null; }, 900000);
}
getExecutionToken() {
    return this._execToken || null;
}
```

## 1.5 Browser Automation — Credential Exposure

**File**: `static/js/api-client.js` → `browserLogin()`

**Problem**: Username and password are sent in plaintext JSON to `/daena/tools/browser/login`. If this endpoint is ever logged, credentials are captured.

**Fix**: This endpoint must enforce HTTPS-only and the backend must never log the `password` field. Add to your backend route:

```python
@router.post("/browser/login")
async def browser_login(req: BrowserLoginRequest):
    # NEVER log req.password
    logger.info(f"Browser login initiated for URL: {req.url}, user: {req.username}")
    # ... execute login ...
```

## 1.6 CORS — Lock Down for Production

Your backend currently uses `CORS(app, allow_origins=["*"])`. This means ANY website can make authenticated requests to your Daena backend.

**Fix in your `main.py`**:

```python
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",  # Only if you run a separate frontend dev server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["X-Execution-Token", "Content-Type", "Authorization"],
)
```

## 1.7 Auth Disabled Flag

Your `.env` has `DISABLE_AUTH=1`. This is fine for local-only dev. But add a guard:

```python
# In main.py startup
import os
if os.getenv("DISABLE_AUTH") == "1" and not os.getenv("ENV", "dev") == "dev":
    raise RuntimeError("🚨 DISABLE_AUTH=1 is NOT allowed outside dev environment!")
```

---

# PART 2 — ARCHITECTURE OVERVIEW (What Daena IS)

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FOUNDER (You)                                 │
│              Ultimate Authority · Override Everything                 │
└─────────────────────────┬────────────────────────────────────────────┘
                          │  grants permissions
                          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DAENA — VP Interface                               │
│    Orchestrator · Permission Gateway · Governance Layer               │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │  Council    │  │  Sub-Agent  │  │  DeFi /     │  │  Device    │  │
│  │  System     │  │  Swarm      │  │  Web3       │  │  Control   │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┬──────────────┐
          ▼               ▼               ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────┐
│   COUNCIL    │  │  SUB-AGENTS  │  │  DEFI    │  │  PHONE /     │
│              │  │              │  │  ENGINE  │  │  REMOTE      │
│ 5 experts    │  │ Code, Research│ │          │  │  CONTROL     │
│ per domain   │  │ File, Browser│  │ Scan     │  │              │
│ trained on   │  │ Voice, DeFi  │  │ Audit    │  │ See/hear/    │
│ real people  │  │              │  │ Deploy   │  │ control from │
│              │  │              │  │          │  │ mobile       │
└──────────────┘  └──────────────┘  └──────────┘  └──────────────┘
```

### Permission Flow (enforced at every step)

```
User Request
    → Daena analyzes intent + risk
    → Permission check (has it? auto-approve? or ask user?)
    → Task decomposition
    → Sub-agent assigned with SCOPED permissions (time-limited)
    → Execution monitored by SafetyMonitor
    → Result validated
    → Permissions auto-revoked
    → Audit log written
    → Report to user
```

---

# PART 3 — COUNCIL SYSTEM ARCHITECTURE

The Council is Daena's advisory board. Each domain has 5 "expert agents" trained on the thinking patterns, knowledge, and communication style of real people you bring on board.

```
┌─────────────────────────────────────────────────────┐
│                   COUNCIL ROUTER                     │
│   Receives question → Routes to relevant council(s) │
│   Collects votes → Synthesizes single recommendation│
└───────────┬─────────────────────────────────────────┘
            │ dispatches to
    ┌───────┴───────┬───────────┬──────────┐
    ▼               ▼           ▼          ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ FINANCE │  │  TECH   │  │ LEGAL   │  │  ...    │
│ COUNCIL │  │ COUNCIL │  │ COUNCIL │  │         │
│         │  │         │  │         │  │         │
│ Expert1 │  │ Expert1 │  │ Expert1 │  │         │
│ Expert2 │  │ Expert2 │  │ Expert2 │  │         │
│ Expert3 │  │ Expert3 │  │ Expert3 │  │         │
│ Expert4 │  │ Expert4 │  │ Expert4 │  │         │
│ Expert5 │  │ Expert5 │  │ Expert5 │  │         │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
    │               │           │
    └───────┬───────┘───────────┘
            ▼
    ┌─────────────┐
    │  SYNTHESIS  │ → Single clear recommendation
    │   ENGINE    │ → Confidence score
    └─────────────┘
            │
            ▼
        DAENA (aware of full council output)
            │
            ▼
     Acts or escalates to Founder
```

### How Council Experts Are Created

Each expert slot is populated by:
1. You bring in a person (interview, documents, writing samples, past decisions)
2. A dedicated fine-tune or RAG pipeline builds their "thinking model"
3. The expert agent responds in that person's style and reasoning pattern
4. The 5 experts in each council debate internally before reaching consensus
5. The Council Router merges outputs from multiple councils when a question spans domains

### Council → Daena → Agents Flow

```
Founder asks: "Should we enter the NFT marketplace space?"
    ↓
Daena routes to: [FINANCE COUNCIL, LEGAL COUNCIL, TECH COUNCIL]
    ↓
Each council's 5 experts debate internally
    ↓
Each council outputs: {recommendation, confidence, risks, dissent_notes}
    ↓
Council Router synthesizes: "PROCEED with reservations — see risk_id_7"
    ↓
Daena receives synthesis + is aware of all underlying debate
    ↓
Daena assigns sub-agents to execute approved actions
    ↓
Sub-agents report back → Daena updates council on outcomes → Learning loop
```

---

# PART 4 — DeFi / SMART CONTRACT ENGINE

Daena's DeFi module is NOT just a scanner. It's the company's treasury and execution arm for on-chain operations.

## 4.1 Security Layers (Defense in Depth)

```
Layer 1: STATIC ANALYSIS     → Slither (pattern matching)
Layer 2: SYMBOLIC EXECUTION  → Mythril (formal verification paths)
Layer 3: FUZZ TESTING        → Echidna (property-based, finds edge cases)
Layer 4: INTEGRATION TESTS   → Foundry (fork mainnet, test real state)
Layer 5: AI AUDIT            → Daena synthesizes all tool outputs
Layer 6: HUMAN GATE          → You approve before any on-chain action
```

## 4.2 Token Security Requirements

Any token Daena creates or interacts with must pass:

1. **No single point of failure** — multi-sig required for treasury moves
2. **Upgradeable with timelock** — 48h minimum delay on any contract upgrade
3. **Oracle manipulation resistance** — TWAP oracles, not spot price
4. **Reentrancy guards** — OpenZeppelin ReentrancyGuard on all external calls
5. **Access control** — Role-based (Owner, Admin, Operator) with separation
6. **Emergency pause** — Circuit breaker pattern with auto-pause on anomaly
7. **Audit trail** — Every state change emits events, indexed and queryable

## 4.3 Approval Gate Architecture

```
AI suggests action (e.g., "deploy contract to mainnet")
    ↓
Risk assessment: CRITICAL
    ↓
Daena shows you: contract code, diff, gas estimate, risk score
    ↓
You approve (biometric/PIN on mobile, or click on desktop)
    ↓
Multi-sig wallet signs (requires M-of-N threshold)
    ↓
Transaction broadcast
    ↓
Confirmation monitoring + automatic rollback trigger if anomaly detected
```

---

# PART 5 — PHONE / REMOTE CONTROL LAYER

Daena runs on your local machine (GPU + RAM). But you need to see and control everything from your phone.

## Architecture

```
┌─────────────┐     secure tunnel     ┌─────────────────┐
│  YOUR PHONE │ ←─── WSS + HTTPS ───→ │  LOCAL MACHINE  │
│             │                        │                 │
│  Daena App  │                        │  Daena Core     │
│  (mobile)   │                        │  (Python/GPU)   │
│             │                        │                 │
│  • See live │                        │  • All LLMs     │
│    agent    │                        │  • All agents   │
│    status   │                        │  • All councils │
│  • Voice    │                        │  • DeFi engine  │
│    chat     │                        │  • File system  │
│  • Approve  │                        │  • Browser auto │
│    actions  │                        │                 │
│  • Control  │                        │                 │
│    devices  │                        │                 │
└─────────────┘                        └─────────────────┘
```

### Connection Options (pick one based on your setup)

| Method | Best For | Security | Setup Complexity |
|--------|----------|----------|-----------------|
| Tailscale / WireGuard | Home network, always-on | ⭐⭐⭐⭐⭐ | Low |
| Cloudflare Tunnel | Public access needed | ⭐⭐⭐⭐⭐ | Medium |
| SSH Tunnel | Quick test | ⭐⭐⭐⭐ | Low |
| Ngrok | Temporary demo | ⭐⭐⭐ | Lowest |

### What the Phone App Shows (Real-Time)

- **Agent Activity Feed**: Which agents are running, what they're doing, live streaming output
- **Council Debates**: Watch expert agents discuss in real-time
- **Approval Queue**: One-tap approve/deny for pending actions
- **Voice Chat**: Talk to Daena with voice, hear responses (TTS streamed)
- **System Health**: CPU/GPU/RAM/VRAM usage, model loading status
- **Emergency Stop**: Big red button, instant halt of all operations

---

# PART 6 — ANTIGRAVITY INTEGRATION PROMPTS

Use these prompts with Antigravity to build each component. They are ordered by dependency — build in this sequence.

---

## PROMPT 1: Security Hardening & Environment Setup

```
You are building the Daena autonomous company platform. First priority is security hardening.

CONTEXT: This is a local-first AI platform. It runs on the user's machine with local LLMs. No data should leave the machine unless explicitly configured. The platform controls files, runs code, interacts with blockchain, and will eventually control physical devices.

TASKS:
1. Create a hardened .env.example with ALL required variables (no real values, only PLACEHOLDER_ROTATE_ME style markers)
2. Create a secrets_audit.py script that scans the entire repo for:
   - Hardcoded API keys (regex patterns for Azure, HF, OpenAI, Anthropic)
   - Passwords in config files
   - Private keys (.pem, .key files)
   - Connection strings with credentials
   Output: JSON report with file, line, severity, masked value
3. Create a pre-commit hook (pre-commit-config.yaml) that:
   - Runs secrets_audit.py on staged files
   - Blocks commit if any HIGH severity finding
   - Runs gitleaks if available
4. Harden CORS: Replace allow_origins=["*"] with explicit localhost-only list
5. Move execution token from sessionStorage to in-memory-only with 15-min auto-expiry
6. Add WebSocket origin validation on both client and server side
7. Create SECURITY.md documenting: what runs locally, what CAN reach network, approval requirements for any outbound

OUTPUT: All files ready to drop into the repo. No placeholders in actual code — every security check must be real and functional.
```

---

## PROMPT 2: Council System Core

```
You are building the Council governance system for Daena (an autonomous AI company OS).

CONTEXT: The Council is an advisory board of AI agents. Each business domain (Finance, Tech, Legal, Marketing, HR, Strategy, Product, Security) has a council of 5 expert agents. Each expert is trained on (or RAG-loaded with) the knowledge and thinking patterns of a real person. When Daena needs advice on a decision, she routes the question to the relevant council(s). The 5 experts debate, reach consensus, and return a single recommendation with confidence score.

ARCHITECTURE REQUIREMENTS:
- Council Router: receives a question + domain tags, dispatches to councils, collects responses, runs synthesis
- Expert Agent: has a persona profile (name, expertise, communication style, known biases), receives a question, responds in character
- Debate Engine: experts exchange 2-3 rounds of arguments before voting
- Synthesis Engine: takes all 5 expert outputs + vote counts + dissent notes → produces single recommendation JSON
- Daena Awareness: Daena receives the FULL debate transcript (not just the summary) so she can learn from disagreements

DATA STRUCTURES:
- CouncilDomain: { name, experts: [ExpertProfile], active: bool }
- ExpertProfile: { name, domain, persona_prompt, rag_index_path, communication_style, known_biases }
- DebateRound: { round_number, speaker, argument, references }
- CouncilDecision: { recommendation, confidence: 0-1, risks: [], dissent: [], full_transcript }

API ENDPOINTS (FastAPI):
- POST /api/v1/council/consult — { question, domains: [], urgency: "low|medium|high" }
- GET /api/v1/council/decision/{decision_id}
- GET /api/v1/council/domains — list all domains and their experts
- POST /api/v1/council/domains/{domain}/experts — add/update expert profile
- WebSocket /ws/council/debate/{decision_id} — stream live debate for UI

INTEGRATION:
- Council must call the local LLM (via Ollama or the configured brain) for each expert response
- Each expert response must be generated with their persona injected as system prompt
- The debate rounds happen sequentially (expert1 speaks, expert2 responds to expert1, etc.)

OUTPUT: Complete Python implementation of all components. Include a demo script that simulates a full council consultation.
```

---

## PROMPT 3: DeFi Engine — Scanner + Audit + Deploy Guard

```
You are building the DeFi/Web3 engine for Daena.

CONTEXT: Daena's company needs to interact with blockchain. This includes: auditing smart contracts before deployment, scanning for vulnerabilities, generating audit reports, and eventually executing on-chain transactions with multi-sig approval gates.

SECURITY REQUIREMENTS (non-negotiable):
- ALL contract scanning runs in sandboxed subprocess with timeout (max 10 min)
- NO network access during static analysis
- Path traversal prevention: canonicalize all paths, reject anything outside workspace
- Output size limit: 10MB per tool
- Secret redaction: scan all tool outputs for key patterns before returning to UI
- Approval gate: ANY write operation (deploy, upgrade, fund) requires explicit user approval
- Multi-sig: treasury operations require M-of-N signatures

IMPLEMENTATION:

1. Scanner Service (backend/services/defi_scanner.py):
   - Wraps: Slither, Mythril, Foundry, Echidna
   - Each tool runs in subprocess with: timeout, output capture, resource limits
   - Results normalized to unified Finding format: { severity, title, location, tool, description, recommendation, code_snippet }
   - Dependency checker: verify tools are installed before attempting scan

2. Audit Report Generator:
   - Takes scan findings → generates structured report
   - Sections: Executive Summary, Critical Findings, Medium Findings, Recommendations
   - Includes risk scoring per finding
   - Output: JSON + Markdown

3. Deploy Guard (backend/services/defi_deploy_guard.py):
   - Intercepts any deploy/upgrade request
   - Runs FULL scan suite automatically
   - If any CRITICAL finding: BLOCK deployment
   - If HIGH findings: require explicit user override with reason
   - Generates pre-deploy checklist: tests passed? audit clean? timelock set? multi-sig configured?

4. Frontend Integration:
   - Real-time scan progress via WebSocket
   - Findings displayed with color-coded severity
   - One-click "Generate Report"
   - Approval modal for deploy/fix actions showing full diff

API ENDPOINTS:
- POST /api/v1/defi/scan — { contract_path, tools: ["slither", "mythril"] }
- GET /api/v1/defi/scan/{scan_id} — poll for results
- POST /api/v1/defi/report/{scan_id} — generate audit report
- POST /api/v1/defi/deploy-guard/check — pre-deploy validation
- POST /api/v1/defi/approve — approve a pending action (requires execution token)

OUTPUT: Full implementation. Include test contracts (both vulnerable and fixed) for demo purposes.
```

---

## PROMPT 4: Frontend — Daena Command Center (The Main UI)

```
You are building the main command center UI for Daena — an autonomous AI company OS.

DESIGN DIRECTION: Retro-futuristic control room. Think: mission control at a space agency meets a Bloomberg terminal. Dark background (#0a0e1a), amber/gold accents (#d4a843), subtle grid lines, data flowing in real-time. NOT generic dark mode SaaS. This should feel like you're commanding something powerful.

TYPOGRAPHY: 
- Headings: "Orbitron" (Google Fonts) — gives the sci-fi command feel
- Body: "Share Tech Mono" — monospace but refined, data-dense
- Accent labels: "Rajdhani" — clean, technical

LAYOUT (single page, tabbed sections):

TAB 1 — COMMAND CENTER (default view):
- Top bar: Daena status indicator (animated pulse when active), current time, system health (CPU/GPU/RAM as circular gauges)
- Left panel: Agent Activity Feed (real-time, WebSocket-driven). Each agent shown as a card with: name, type, current action (streaming text), status light (green/amber/red)
- Center: Main chat with Daena (full-featured: voice toggle, search modes, streaming responses, citation pills)
- Right panel: Council Status. Shows active consultations, expert debate snippets streaming in, decision confidence meters

TAB 2 — COUNCIL CHAMBER:
- Full-screen debate view. Pick a domain, ask a question, watch 5 experts argue in real-time
- Each expert has a distinct color and avatar initial
- Debate rounds shown as a conversation thread
- Final recommendation displayed prominently with confidence bar
- History of past decisions searchable

TAB 3 — DEFI OPERATIONS:
- Contract scanner interface (file picker, tool selection, scan progress)
- Findings dashboard with severity breakdown (donut chart)
- Approval queue: pending actions shown as cards with full context
- Deploy guard checklist visualization

TAB 4 — CONTROL PLANE:
- Agent management: create, configure, enable/disable sub-agents
- Permission management: active permissions, templates, grant/revoke
- Integrations: connected services status
- System settings

TAB 5 — FOUNDER PANEL:
- Emergency stop (prominent red button)
- Full audit log (filterable, searchable)
- System backup/rollback controls
- Permission override (grant/revoke any permission instantly)
- Incident room access

REAL-TIME REQUIREMENTS:
- WebSocket connection for: agent activity, council debates, chat streaming, system metrics
- All data updates WITHOUT page refresh
- Connection status indicator (reconnecting state shown)
- Graceful degradation if WebSocket drops (poll fallback)

INTERACTIONS:
- All buttons have loading states
- Approval actions show confirmation modal with full context before executing
- Voice chat: mic button animates when listening, waveform visualization during recording
- Keyboard shortcuts: Ctrl+K for command palette (search agents, actions, files)

OUTPUT: Complete HTML/CSS/JS. Single-file templates that integrate with the existing Jinja2 backend ({% extends "base.html" %}). Include ALL JavaScript inline or in separate files that match the existing static/js/ structure. Wire EVERY button to the correct /api/v1/ endpoint using the existing DaenaAPI client pattern.
```

---

## PROMPT 5: Mobile Remote Control App

```
You are building a mobile-optimized remote control interface for Daena.

CONTEXT: Daena runs on a desktop/laptop with a powerful GPU. The user needs to monitor and control everything from their phone. This is NOT a full rebuild — it's a responsive overlay that activates on small screens, or a standalone PWA (Progressive Web App) that connects to the local Daena instance via secure tunnel.

REQUIREMENTS:

1. PWA Setup:
   - manifest.json with proper icons, standalone display
   - Service worker for offline-capable notification handling
   - Install prompt for "Add to Home Screen"

2. Mobile Layout (triggered at ≤768px or as standalone PWA):
   - Bottom navigation bar: Home | Chat | Agents | Approvals | More
   - Full-screen chat with Daena (voice-first: big mic button, waveform animation)
   - Agent cards in scrollable grid (compact: name, status light, current action in 1 line)
   - Approval queue: swipe-gesture approve/deny (or tap buttons)
   - Pull-to-refresh on agent list and approval queue

3. Connection Management:
   - Auto-detect connection method (direct LAN, tunnel, etc.)
   - Show connection status prominently (green dot = connected, red = trying to reconnect)
   - Graceful offline mode: queue approvals locally, sync when reconnected

4. Voice Integration:
   - Voice-to-text for chat input (Web Speech API or whisper if available)
   - Text-to-speech for Daena responses (streaming audio)
   - Push notifications for: approval requests, emergency alerts, agent errors

5. Security:
   - Connection uses WSS (encrypted WebSocket) only
   - Session token stored in memory, auto-expired
   - Biometric auth prompt before any approval action
   - Remote wipe capability (founder can revoke mobile session)

OUTPUT: Complete PWA implementation. manifest.json, service-worker.js, and mobile-optimized CSS that layers on top of the existing frontend (media queries + standalone mode detection). All JavaScript wired to the same /api/v1/ endpoints.
```

---

## PROMPT 6: Local LLM Integration & Model Router

```
You are building the local LLM integration layer for Daena.

CONTEXT: The user has LLMs stored at D:\Ideas\MODELS_ROOT (on Windows). Models include: DeepSeek R1 variants, Qwen, Llama, Mistral, and others via Ollama. Daena needs to route different types of requests to the best model based on the task.

REQUIREMENTS:

1. Model Discovery Service:
   - Scan MODELS_ROOT on startup, detect all available models
   - Query Ollama API for running models and their status
   - Cache model metadata (size, capabilities, speed benchmarks)

2. Router Logic (backend/services/model_router.py):
   - Route by task type:
     * "reasoning" (complex analysis, council debates) → R1 or largest available reasoning model
     * "code" (coding, debugging) → Code-specific model if available, else general
     * "fast" (quick answers, UI responses) → Smallest fast model (e.g., Qwen 0.5B or similar)
     * "council_expert" → Model assigned to that specific expert (can be different models per expert)
     * "defi_audit" → Code model with extra context about Solidity
   - Fallback chain: if preferred model is busy/unavailable, route to next best
   - Load balancing: track which models are currently processing, avoid overloading single GPU

3. Context Window Management:
   - Track token usage per session
   - Auto-summarize conversation when approaching context limit
   - Inject capability summaries at session start (what tools Daena has access to)

4. Model Health Monitoring:
   - Periodic ping to each model
   - Track response latency, error rates
   - Auto-restart stuck models via Ollama API
   - Alert if GPU memory is critically low

5. Cross-Platform Path Handling:
   - Works on Windows (D:\Ideas\MODELS_ROOT), Linux (/models), macOS
   - Environment variable override: MODELS_ROOT can point anywhere
   - Symlink support for model directories

API ENDPOINTS:
- GET /api/v1/brain/models — list all discovered models with status
- POST /api/v1/brain/models/{model}/select — set as active for a task type
- GET /api/v1/brain/status — current routing table, active models, GPU stats
- POST /api/v1/brain/route — { task_type, prompt } → routed response (internal use)

OUTPUT: Full implementation. Include a model benchmarking script that tests all available models on standard prompts and generates a performance report.
```

---

## PROMPT 7: Sub-Agent Swarm & Task Orchestration

```
You are building the sub-agent swarm system for Daena.

CONTEXT: Daena orchestrates multiple specialist sub-agents. Each sub-agent has a specific capability (code, research, file management, browser automation, voice, DeFi). Daena decomposes user requests into subtasks, assigns them to the right agents, monitors execution, and synthesizes results.

REQUIREMENTS:

1. Agent Registry (backend/services/agent_registry.py):
   - Register available agent types with their capabilities
   - Track agent instances: idle, active, busy, error, terminated
   - Agent health checks (periodic status ping)
   - Max concurrent agents configurable (default: 5)

2. Task Decomposition Engine:
   - Takes a user request → breaks into subtasks
   - Each subtask tagged with: required_agent_type, required_permissions, dependencies, priority
   - Dependency graph: subtask B cannot start until subtask A completes
   - Parallel execution where no dependencies exist

3. Permission Delegation:
   - Each sub-agent gets ONLY the permissions needed for its subtask
   - Permissions are TIME-LIMITED (expire when task completes or after max duration)
   - If agent needs permission it doesn't have → escalates to Daena → may escalate to user
   - Auto-revoke on task completion or error

4. Execution Monitor:
   - Real-time streaming of each agent's output
   - Timeout detection: if agent hasn't produced output in X minutes, alert
   - Error recovery: retry logic with exponential backoff
   - Kill switch: Daena can terminate any agent instantly

5. Result Synthesis:
   - Collect outputs from all subtasks
   - Merge into coherent response
   - Identify conflicts between subtask results
   - Present to user with attribution (which agent did what)

6. Agent Types to Implement:
   - CodeAgent: writes/edits code, runs tests, suggests fixes
   - ResearchAgent: web search, page scraping, summarization
   - FileAgent: reads/writes/organizes files in workspace
   - BrowserAgent: navigates websites, fills forms, extracts data
   - DeFiAgent: smart contract scanning, audit report generation
   - VoiceAgent: handles speech input/output pipeline

INTEGRATION:
- Each agent calls the local LLM via the Model Router (Prompt 6)
- Agent outputs stream back to Daena in real-time via WebSocket
- Daena's UI shows agent activity cards updating live

OUTPUT: Complete implementation of all agent types (stub implementations are fine for Browser and Voice — focus on the orchestration layer). Include integration tests that verify permission scoping, timeout handling, and result synthesis.
```

---

# PART 7 — IMPLEMENTATION ORDER & DEPENDENCIES

```
Phase 1: SECURITY (Prompt 1)
    ↓ must complete before anything else
Phase 2: LOCAL LLM LAYER (Prompt 6)
    ↓ everything else needs this
Phase 3: SUB-AGENT SWARM (Prompt 7)
    ↓ depends on LLM layer
Phase 4: COUNCIL SYSTEM (Prompt 2)
    ↓ depends on sub-agent swarm + LLM layer
Phase 5: DEFI ENGINE (Prompt 3)
    ↓ depends on sub-agent swarm
Phase 6: FRONTEND (Prompt 4)
    ↓ depends on all backend being in place
Phase 7: MOBILE (Prompt 5)
    ↓ depends on frontend + WebSocket layer
```

---

# PART 8 — WHAT MAKES DAENA DIFFERENT (Hype Points)

1. **Truly autonomous** — finds contracts, analyzes them, makes money, plans execution. Not a chatbot. An operating company.
2. **Council governance** — decisions aren't made by one model. 5 experts per domain debate, vote, and advise. Disagreements are tracked and learned from.
3. **Zero-trust DeFi** — every on-chain action goes through 6 layers of security scanning before you even see the approval button.
4. **You're always in control** — emergency stop, permission revocation, full audit trail. The AI works FOR you, not around you.
5. **Local-first, cloud-ready** — runs on YOUR GPU today. When you're ready to scale, the architecture supports cloud deployment without rewriting.
6. **Real-time everywhere** — watch your agents work from your phone. See council debates happen live. Approve actions with one tap.
7. **Jarvis-level interaction** — voice chat, streaming responses, command palette, the whole experience feels like talking to an intelligence that actually has access to everything.

---

# PART 9 — QUICK START CHECKLIST

- [ ] Rotate Azure + HuggingFace keys (Part 1, Section 1.1)
- [ ] Update `.gitignore` (Part 1, Section 1.2)
- [ ] Run Prompt 1 through Antigravity → apply security fixes
- [ ] Verify MODELS_ROOT has your models (D:\Ideas\MODELS_ROOT)
- [ ] Run Prompt 6 → local LLM layer
- [ ] Test: can Daena chat using local model?
- [ ] Run Prompt 7 → sub-agent swarm
- [ ] Run Prompt 2 → council system
- [ ] Run Prompt 3 → DeFi engine
- [ ] Run Prompt 4 → new frontend
- [ ] Run Prompt 5 → mobile app
- [ ] Set up secure tunnel (Tailscale recommended) for phone access
- [ ] First full test: ask Daena to research something, watch agents work, see council advise

---

*Built for the Daena Autonomous Company OS — 2026-01-31*
*All prompts designed for Antigravity code generation*
*Security hardening based on live codebase audit*
