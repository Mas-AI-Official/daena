# DAENA MASTER EXECUTION PLAN
## Making Daena Smarter Than Any AGI — Learning, Remembering, Governing

**Created:** 2026-02-01  
**Objective:** Implement all remaining features from DAENA_FULL_POWER.md to make Daena:
- **Learn** from every decision outcome (Learning Loop)
- **Remember** across sessions (Unified Memory + CAS)
- **Process outside sandbox** through MCP integration
- **Identify threats/vulnerabilities** through Integrity Shield + DeFi Scanner
- **Self-create skills** under governance (Skill Registry)
- **Govern package installs** (Package Auditor)

---

## ✅ COMPLETED (Jan 31 Session)

| Feature | Status | Location |
|---------|--------|----------|
| Data Integrity Shield | ✅ DONE | `backend/services/integrity_shield.py` |
| Prompt Injection Detection | ✅ DONE | Part of integrity_shield.py |
| Trust Ledger | ✅ DONE | `.ledger/trust_ledger.json` |
| Integrity API Routes | ✅ DONE | `backend/routes/integrity.py` |
| Trust & Safety UI Tab | ✅ DONE | `frontend/templates/control_plane.html` |
| Outcome Tracker | ✅ DONE | `backend/services/outcome_tracker.py` |
| Outcome API Routes | ✅ DONE | `backend/routes/outcomes.py` |
| DeFi Scanner API | ✅ DONE | `backend/routes/defi.py` |
| Demo Vulnerable Contract | ✅ DONE | `contracts/DemoVault.sol` |
| MCP Server (Daena exposes tools) | ✅ DONE | `backend/services/mcp/mcp_server.py` |
| MCP Server Routes | ✅ DONE | `backend/routes/mcp.py` |
| Slither Installed | ✅ DONE | `slither --version` works |
| Demo Storyboard | ✅ DONE | `docs/2026-01-31/DEMO_STORYBOARD.md` |
| MCP fact_check → Integrity Shield | ✅ WIRED | Real verification, not placeholder |

---

## 🔴 PRIORITY 1: EXECUTE IMMEDIATELY (Today)

### 1.1 Install New Components from `docs/2026-01-31/new files/`

These files are ready to deploy — just need to copy to correct locations:

| Source File | Target Location | Purpose |
|-------------|-----------------|---------|
| `skill_registry.py` | `backend/services/skill_registry.py` | Dynamic skill creation with governance |
| `package_auditor.py` | `backend/services/package_auditor.py` | Supply-chain security for npm/pip |
| `SYSTEM_PROMPT_UPDATE.py` | Review & integrate into llm_service.py | Enhanced system prompt |
| `control_plane.html` | Compare & merge with existing | UI enhancements |

### 1.2 Create API Routes for New Services

- [ ] `backend/routes/skills.py` — Skill Registry endpoints
- [ ] `backend/routes/packages.py` — Package Auditor endpoints

### 1.3 Unified Memory System (Learning Loop Core)

From DAENA_FULL_POWER.md Part 3:
- [ ] `backend/services/unified_memory.py` — Single API for all memory access
- [ ] `backend/services/memory_consolidation.py` — Daily insight extraction
- [ ] Expert calibration integration with Outcome Tracker
- [ ] CAS deduplication tracking

---

## 🟠 PRIORITY 2: WIRE REMAINING MCP TOOLS (Today/Tomorrow)

Currently in `mcp_server.py`:
- [x] `daena_fact_check` → Real Integrity Shield ✅
- [ ] `daena_research` → Wire to Research Agent
- [ ] `daena_defi_scan` → Wire to DeFi Scanner routes
- [ ] `daena_council_consult` → Wire to Council system

---

## 🟡 PRIORITY 3: MOBILE + DESKTOP APPS (Feb 2-3)

### PWA Mobile App
From DAENA_FULL_POWER.md Part 4A:
- [ ] Create `frontend/pwa/` directory
- [ ] `manifest.json` with Daena branding
- [ ] `sw.js` service worker (offline, push notifications)
- [ ] `index.html` single-file PWA
- [ ] Route in FastAPI to serve PWA

### Desktop App (Tauri)
From DAENA_FULL_POWER.md Part 4B:
- [ ] Create `desktop/` directory
- [ ] `tauri.conf.json`
- [ ] `src/main.rs` entry point
- [ ] Build scripts for .msi/.dmg

---

## 🟢 PRIORITY 4: POLISH FOR HACKATHON (Feb 3-7)

### Demo Flow Improvements
- [ ] Agent activity visible in real-time (loading states)
- [ ] Sub-90-second demo timing
- [ ] Sample contracts for multiple chains (Aptos, Solana, Polkadot)

### Repository Cleanup
- [ ] Update README with new architecture
- [ ] Move irrelevant files to /archive
- [ ] Professional documentation

### Final Testing
- [ ] Full E2E test on fresh browser
- [ ] Offline fallback demo recording
- [ ] Pre-recorded backup video

---

## 📋 TASK EXECUTION ORDER (Follow Exactly)

```
STEP 1: Copy skill_registry.py → backend/services/
STEP 2: Copy package_auditor.py → backend/services/
STEP 3: Create backend/routes/skills.py (API for skill registry)
STEP 4: Create backend/routes/packages.py (API for package auditor)
STEP 5: Register new routes in backend/main.py
STEP 6: Create backend/services/unified_memory.py
STEP 7: Create backend/services/memory_consolidation.py
STEP 8: Wire remaining MCP tools (research, defi_scan, council_consult)
STEP 9: Test all new endpoints
STEP 10: Commit + push to GitHub
STEP 11: Create PWA structure (frontend/pwa/)
STEP 12: Create Tauri desktop structure (desktop/)
STEP 13: Final demo polish
STEP 14: Record demo video
STEP 15: Update README
```

---

## 🔒 GOVERNANCE PRINCIPLES (Why Daena is Different)

From the unified system prompt, Daena differs from other AI by:

1. **Hierarchical Permission Control**
   - User → Daena (VP) → Sub-Agents → Tools
   - Every action traces back to permission chain

2. **Self-Created Skills Under Governance**
   - Daena can propose new skills
   - Council reviews, Founder approves
   - Sandbox testing before activation

3. **Package Supply-Chain Security**
   - Every npm/pip install goes through audit
   - CVE check, typosquat detection, behavioral analysis
   - Auto-reject critical risks, pending approval for medium

4. **Learning from Outcomes**
   - Every decision tracked
   - Outcome recorded (success/failure)
   - Expert calibration updated
   - Consolidated into insights

5. **Data Integrity Shield**
   - No single-source claims trusted
   - Prompt injection detection
   - Manipulation pattern recognition
   - Trust scores for all sources

---

## 🎯 SUCCESS METRICS

By end of Feb 7 (Hackathon submission):

| Metric | Target |
|--------|--------|
| Demo duration | < 90 seconds |
| All new endpoints tested | ✅ |
| Skill Registry active | 6+ built-in skills |
| Package Auditor active | Catches typosquats |
| MCP tools wired | All 4 functional |
| PWA installable | Works on iOS + Android |
| GitHub repo clean | Professional README |
| Video recorded | 2-minute max |

---

## 📁 FILES TO CREATE/MODIFY

### New Files:
1. `backend/services/skill_registry.py` ← from new files
2. `backend/services/package_auditor.py` ← from new files
3. `backend/services/unified_memory.py`
4. `backend/services/memory_consolidation.py`
5. `backend/routes/skills.py`
6. `backend/routes/packages.py`
7. `frontend/pwa/manifest.json`
8. `frontend/pwa/sw.js`
9. `frontend/pwa/index.html`
10. `desktop/tauri.conf.json`
11. `desktop/src/main.rs`

### Modify:
1. `backend/main.py` — Register new routes
2. `backend/services/mcp/mcp_server.py` — Wire remaining tools
3. `backend/services/llm_service.py` — Enhanced system prompt
4. `frontend/templates/control_plane.html` — Skills + Packages tabs
5. `README.md` — Professional update

---

*Plan created: 2026-02-01 09:34*
*Execute in order. Commit after each major step.*
