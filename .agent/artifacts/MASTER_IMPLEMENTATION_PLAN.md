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

### PHASE 2: NBMF MEMORY TIER SYSTEM (PRIORITY - 2 DAYS)
**Goal:** Implement 3-tier hierarchical memory per NBMF spec

**New Services:**
1. `backend/services/memory/hot_memory.py` — L1 Vector DB cache
2. `backend/services/memory/warm_memory.py` — L2 NBMF encoder/decoder
3. `backend/services/memory/cold_memory.py` — L3 Archive with summarization
4. `backend/services/memory/memory_router.py` — Policy-based routing

**Memory Config:**
```yaml
# config/memory_policy.yaml
memory_policy:
  classes:
    legal:         { fidelity: lossless, retention: 7y, encrypt: true }
    finance:       { fidelity: lossless, retention: 7y, encrypt: true }
    pii:           { fidelity: lossless_edge, on_device: true }
    chat:          { fidelity: semantic, retention: 180d, hot_cache_days: 14 }
    ops_log:       { fidelity: semantic, retention: 90d }
    research_note: { fidelity: semantic, retention: 365d }
    training_chunk:
      fidelity_global: semantic
      fidelity_edge: lossless
      federated: true
  aging:
    - after_days: 14
      action: tighten_compression
      apply_to: [chat, ops_log]
    - after_days: 90
      action: summarize_pack
      apply_to: [chat, ops_log]
  security:
    encrypt_at_rest: AES-256
    integrity_hash: SHA-256
    ledger: local_append_only
```

**Integration Points:**
- Connect `unified_memory.py` to NBMF tiers
- Route skill/package/outcome data through memory tiers
- Enable hot → warm → cold aging pipeline

---

### PHASE 3: SYSTEM-WIDE GOVERNANCE LOOP (1 DAY)
**Goal:** Extend security/governance across ALL decisions (not just DeFi)

**Current Gap:** Package auditor and skill registry only work for specific domains
**Fix:** Create unified governance pipeline for all agent actions

**New Service:**
`backend/services/governance_loop.py`
```python
class GovernanceLoop:
    """System-wide decision governance with autopilot + approval modes"""
    
    def evaluate_action(self, action: Dict) -> Decision:
        """Every agent action goes through this loop"""
        risk_level = self.assess_risk(action)
        
        if risk_level == "low" and self.autopilot_enabled:
            # ClawBot mode: execute + report
            return Decision(action="execute", report_to="founder")
        elif risk_level == "medium":
            # Council consult + execute if approved
            council = self.consult_council(action)
            if council.recommendation == "APPROVE":
                return Decision(action="execute", report_to="founder")
            else:
                return Decision(action="defer", escalate_to="founder")
        else:  # high/critical
            # Always require founder approval
            return Decision(action="pending", requires="founder_approval")
```

**Action Types to Cover:**
- File operations (read/write/delete)
- Package installs
- Skill creation
- External API calls
- Research queries
- DeFi scanning
- Model training updates
- Treasury operations

---

### PHASE 4: SHADOW DEPARTMENT (2 DAYS)
**Goal:** Build the defensive deception layer per HTML blueprint

**New Services:**
1. `backend/services/shadow/shadow_agent.py` — Invisible monitoring
2. `backend/services/shadow/honeypot.py` — Decoy routes + canary tokens
3. `backend/services/shadow/threat_intel.py` — TTP logging + attacker profiling

**Routes:**
- `/api/v1/admin/keys` — Honeypot (fake keys that alert)
- `/api/v1/internal/vault` — Honeypot (fake data)
- `/api/v1/threats/live` — WebSocket threat feed

**Dashboard Tab:**
- Shadow Dept panel (founder-only visibility)
- Honeypots active / Canary tokens deployed / Alerts 24h

---

### PHASE 5: RESEARCH AGENT INTEGRATION (1 DAY)
**Goal:** Wire `daena_research` MCP tool to real research capabilities

**Expected Behavior:**
- Query → Search web/knowledge base → Verify via Integrity Shield → Return
- Track outcomes in learning loop
- Store findings in NBMF memory

**Service:**
`backend/agents/research_agent.py`
- Multi-source search (web, local knowledge, MCP tools)
- Trust scoring for sources
- Deduplication of findings

---

### PHASE 6: FRONTEND CONTROL PLANE UPDATE (2 DAYS)
**Goal:** Apply control_plane.html from docs with real-time WebSocket updates

**From HTML Blueprint:**
- Live agent activity feed
- Council debates visible
- Treasury dashboard
- Trust & Safety tab
- Shadow Dept tab (founder only)
- Skill Registry management
- Package Audit management

**Key Fix:**
- Make it SPA (single-page app) with persistent WebSocket
- Event bus routes: `agent_activity`, `council_debate`, `treasury`, `threat`
- Tabs show/hide without page reload

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

### PHASE 9: DEMO VIDEO + HACKATHON SUBMISSION
**Goal:** Record compelling demo showing full loop

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
