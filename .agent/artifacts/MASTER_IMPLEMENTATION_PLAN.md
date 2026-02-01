# DAENA MASTER IMPLEMENTATION PLAN
## Unified Strategy Combining All Innovation Frameworks (NBMF, Sunflower-Honeycomb, ClawBot/MoltBot, MiniMax)

**Created:** 2026-02-01  
**Purpose:** Single source of truth for completing Daena's development  
**Hackathon:** Consensus Hong Kong 2026

---

## 🎯 CORE INNOVATIONS TO INTEGRATE

### 1. **NBMF — Neural Bytecode Memory Format** (Daena's Brain)
From docs: Replace image compression with learned latent vectors
- **L1 HOT:** Vector DB, recent context, p95 < 25ms recall
- **L2 WARM:** NBMF encoded knowledge (256-2048 dims + Zstd compression)
- **L3 COLD:** Summarized + compressed archives
- **Policy-based fidelity:** Lossless (legal/finance/PII) vs Semantic (chat/ops)
- **Progressive aging:** Fresh = detailed, old = summarized

### 2. **Sunflower-Honeycomb Architecture** (8×6 Agent Grid)
From docs: 48+ agents across 8 departments with shared memory
- All agents share a unified knowledge base (no silos)
- Cross-department communication via handshakes
- Reflexive learning: system learns from agent experiences

### 3. **ClawBot/MoltBot/MiniMax Power Core**
From user vision: Autopilot capabilities with governance
- **ClawBot:** Install software, scan vulnerabilities, execute tasks autonomously
- **MoltBot:** Research, talent testing, knowledge gathering
- **MiniMax:** Cost optimization, resource allocation

### 4. **ENDA — Enterprise Neuromorphic Data Architecture**
From docs: Hierarchical memory with blockchain audit
- Append-only ledger for all data operations
- Federated learning: raw data stays on-device
- SHA-256 integrity hashing + AES-256 encryption

---

## 📋 PHASES

### PHASE 0: IMMEDIATE CLEANUP ✅ (TODAY)
**Goal:** Clean repository, remove duplicates, organize structure

**Tasks:**
1. Move all test files to `/tests` directory
2. Delete duplicate/outdated files from root
3. Ensure `docs/` and `daena doc/` excluded from git
4. Clean up backup files (*.backup, *.bak)
5. Organize log files to `/logs` (gitignored)

**Files to delete/move:**
- `test_*.py` (25 files) → move to `/tests/`
- `backend_*.log` → delete (gitignored)
- `*.backup` files → delete
- Junk txt files → delete

---

### PHASE 1: COMPLETE CURRENT IMPLEMENTATIONS ✅ (TODAY - DONE)
**Goal:** Finish services we just built

**Completed:**
- [x] `backend/services/skill_registry.py` — 6 built-in skills
- [x] `backend/services/package_auditor.py` — Typosquat detection working
- [x] `backend/services/unified_memory.py` — CAS deduplication
- [x] `backend/services/memory_consolidation.py` — Learning loop
- [x] `backend/routes/skills.py` — API routes
- [x] `backend/routes/packages.py` — API routes
- [x] MCP tools wired: fact_check, defi_scan, council_consult

---

### PHASE 2: NBMF MEMORY TIER SYSTEM ✅ (DONE - 2026-02-01)
**Goal:** Implement 3-tier hierarchical memory per NBMF spec

**Completed Services:**
1. ✅ `backend/services/memory/hot_memory.py` — L1 Vector DB cache
2. ✅ `backend/services/memory/warm_memory.py` — L2 NBMF encoder/decoder
3. ✅ `backend/services/memory/cold_memory.py` — L3 Archive with summarization
4. ✅ `backend/services/memory/memory_router.py` — Policy-based routing
5. ✅ `config/memory_policy.yaml` — Policy configuration

**API Routes Added:**
- `/api/v1/memory/store` — Store with policy-based routing
- `/api/v1/memory/recall` — Recall from any tier
- `/api/v1/memory/search` — HOT tier semantic search
- `/api/v1/memory/stats` — Tier statistics
- `/api/v1/memory/age` — Run aging process

---

### PHASE 3: SYSTEM-WIDE GOVERNANCE LOOP ✅ (DONE - 2026-02-01)
**Goal:** Extend security/governance across ALL decisions (not just DeFi)

**Completed Services:**
1. ✅ `backend/services/governance_loop.py` — Full implementation

**API Routes Added:**
- `/api/v1/governance/evaluate` — Evaluate action risk
- `/api/v1/governance/approve` — Approve pending action
- `/api/v1/governance/reject` — Reject pending action
- `/api/v1/governance/pending` — List pending approvals
- `/api/v1/governance/stats` — Governance statistics
- `/api/v1/governance/toggle-autopilot` — Enable/disable autopilot

---

### PHASE 4: SHADOW DEPARTMENT ✅ (DONE - 2026-02-01)
**Goal:** Build the defensive deception layer per HTML blueprint

**Completed Services:**
1. ✅ `backend/services/shadow/shadow_agent.py` — Invisible monitoring
2. ✅ `backend/services/shadow/honeypot.py` — Decoy routes + canary tokens
3. ✅ `backend/services/shadow/threat_intel.py` — TTP logging + attacker profiling

**API Routes Added:**
- `/api/v1/shadow/admin/keys` — Honeypot (fake keys that alert)
- `/api/v1/shadow/internal/vault` — Honeypot (fake data)
- `/api/v1/shadow/config/secrets` — Honeypot (fake config)
- `/api/v1/shadow/dashboard` — Threat dashboard data
- `/api/v1/shadow/alerts` — Recent alerts
- `/api/v1/shadow/honeypots` — Honeypot configurations
- `/api/v1/shadow/threats` — Threat intel report
- `/api/v1/shadow/scan` — Scan input for threats

**Frontend Updates:**
- ✅ `control_plane_v2.html` wired to Shadow API
- ✅ Shadow Dept tab loads real backend stats

---

### PHASE 5: RESEARCH AGENT INTEGRATION ✅ (DONE - 2026-02-01)
**Goal:** Wire `daena_research` MCP tool to real research capabilities

**Completed Services:**
1. ✅ `backend/agents/research_agent.py` — Multi-source research with trust verification (Web, Local KB, MCP)

**API Routes Added:**
- `/api/v1/research/query` — Full research query
- `/api/v1/research/quick-search` — Single source search
- `/api/v1/research/history` — Search history
- `/api/v1/research/sources` — List available sources

**Integrations:**
- Wired `daena_research` MCP tool to `ResearchAgent`
- Integrated Integrity Shield for fact checking

---

### PHASE 6: FRONTEND CONTROL PLANE UPDATE ✅ (DONE - 2026-02-01)
**Goal:** Apply control_plane.html from docs with real-time WebSocket updates

**Updates:**
- ✅ `control_plane_v2.html` is now the main interface
- ✅ Wired to all new APIs: Shadow, Governance, Memory, Skills, Packages
- ✅ Real-time WebSocket feed for Agent, Council, and Threat events
- ✅ Removed 10+ stub templates and duplicate backend routes

---

### PHASE 7: TOKEN & NFT LAYER (POST-HACKATHON)
**Goal:** Deploy $DAENA token and Agent NFTs per HTML blueprint

**Contracts:**
- `blockchain/DaenaToken.sol` — ERC-20
- `blockchain/DaenaAgentNFT.sol` — ERC-721 (agent slot licensing)
- `blockchain/DaenaTreasury.sol` — Multi-sig, Council-gated

**API Routes:**
- `/api/v1/token/balance`
- `/api/v1/treasury/status`
- `/api/v1/nft/slots`

---

### PHASE 8: PWA + DESKTOP (1 DAY)
**Goal:** Mobile and desktop packaging

**PWA:**
```
frontend/pwa/
  manifest.json
  sw.js
  index.html
  app.js
```

**Desktop (Tauri):**
```
desktop/
  tauri.conf.json
  src/
```

---

### PHASE 9: DEMO VIDEO PREPARATION ✅ (READY - 2026-02-01)
**Goal:** Create a "killer demo" video showing the system resisting manipulation

**Assets Prepared:**
- ✅ `docs/2026-01-31/DEMO_STORYBOARD.md` — 9-scene storyboard
- ✅ `scripts/killer_demo.py` — Automated event driver script
- ✅ `scripts/demo_preflight.py` — System validation script
- ✅ `frontend/templates/control_plane_v2.html` — Updated for visual flair

**How to Run:**
1. Start Backend: `python -m backend.main`
2. Open UI: `http://localhost:8000/ui/control-plane`
3. Check Stats: `python scripts/demo_preflight.py`
4. Run Demo: `python scripts/killer_demo.py`

**Demo Flow (per DEMO_STORYBOARD.md):**
1. Chat with Daena → triggers research
2. Show agent activity in Control Plane
3. Council debate visible
4. Package install attempt → Auditor catches typosquat
5. DeFi scan → finds vulnerabilities
6. Threat detection → Shadow dept alert
7. Memory consolidation → show learning

**Video:**
- 2 minutes max
- Voiceover explaining each section
- Screen recording of Control Plane

---

## 📊 PRIORITY ORDER (NEXT 9 DAYS)

| Day | Phase | Deliverable |
|-----|-------|-------------|
| 1 | Cleanup + Phase 1 | Clean repo, verify services |
| 2-3 | Phase 2 | NBMF memory tiers |
| 4 | Phase 3 | System-wide governance loop |
| 5-6 | Phase 4 | Shadow Department |
| 7 | Phase 5 + 6 | Research agent + Frontend update |
| 8-9 | Phase 9 | Demo video + submission |

---

## 🔐 SECURITY CHECKLIST (MUST DO)

- [ ] `.env_azure_openai` removed from git history
- [ ] All API keys rotated
- [ ] AES-256 encryption at rest enabled
- [ ] SHA-256 integrity hashing for all data
- [ ] Ledger audit logging active
- [ ] Honeypots deployed
- [ ] Canary tokens scattered

---

## 🧠 INTEGRATION POINTS

### How ClawBot/MoltBot/MiniMax Maps to Services:

| Bot Capability | Daena Service |
|----------------|---------------|
| ClawBot: Install software | Package Auditor → Governance Loop |
| ClawBot: Scan vulnerabilities | DeFi Scanner + Shadow Agent |
| ClawBot: Execute tasks | Skill Registry → Sandbox |
| MoltBot: Research | Research Agent → Memory |
| MoltBot: Test talent | Skill approval workflow |
| MoltBot: Gather knowledge | NBMF Memory Store |
| MiniMax: Cost optimization | Treasury tracking |
| MiniMax: Resource allocation | Agent department routing |

### Memory Flow:
```
User Request
    ↓
Daena VP (Orchestrator)
    ↓
Governance Loop (assess risk)
    ↓
[Low Risk: execute + report]
[Medium Risk: Council → execute/defer]
[High Risk: Founder approval required]
    ↓
Execute via Agent
    ↓
Store outcome in NBMF Memory
    ↓
Learning Loop extracts insights
    ↓
Insights injected into future prompts
```

---

## 📁 FILE STRUCTURE AFTER CLEANUP

```
Daena_old_upgrade_20251213/
├── backend/
│   ├── services/
│   │   ├── skill_registry.py ✅
│   │   ├── package_auditor.py ✅
│   │   ├── unified_memory.py ✅
│   │   ├── memory_consolidation.py ✅
│   │   ├── outcome_tracker.py ✅
│   │   ├── integrity_shield.py ✅
│   │   ├── governance_loop.py (NEW)
│   │   ├── memory/
│   │   │   ├── hot_memory.py (NEW)
│   │   │   ├── warm_memory.py (NEW)
│   │   │   ├── cold_memory.py (NEW)
│   │   │   └── memory_router.py (NEW)
│   │   ├── shadow/
│   │   │   ├── shadow_agent.py (NEW)
│   │   │   ├── honeypot.py (NEW)
│   │   │   └── threat_intel.py (NEW)
│   │   └── mcp/
│   │       ├── mcp_server.py ✅
│   │       └── mcp_registry.py
│   ├── routes/
│   │   ├── skills.py ✅
│   │   ├── packages.py ✅
│   │   ├── defi.py ✅
│   │   ├── integrity.py ✅
│   │   ├── outcomes.py ✅
│   │   ├── honeypot_routes.py (NEW)
│   │   └── threat_dashboard.py (NEW)
│   └── agents/
│       └── research_agent.py (NEW)
├── frontend/
│   ├── templates/
│   │   └── control_plane.html (UPDATE with new blueprint)
│   └── pwa/ (NEW)
├── desktop/ (NEW)
├── tests/ (CONSOLIDATE HERE)
├── config/
│   └── memory_policy.yaml (NEW)
├── .agent/
│   └── artifacts/
│       └── MASTER_IMPLEMENTATION_PLAN.md (THIS FILE)
├── docs/ (gitignored — local only)
└── daena doc/ (gitignored — local only)
```

---

## ✅ SUCCESS CRITERIA

1. **Memory:** All data flows through NBMF 3-tier system
2. **Governance:** Every agent action assessed + tracked
3. **Learning:** Outcomes → Lessons → Insights → Better decisions
4. **Security:** Encryption + Audit + Honeypots active
5. **Demo:** 2-min video showing full loop
6. **Hackathon:** Submitted with compelling pitch

---

**IMPORTANT:** If token limits reached, any agent can resume by reading this plan.
All files, paths, and responsibilities are documented above.

*Plan version: 1.0 | Created: 2026-02-01T10:30:00-05:00*
