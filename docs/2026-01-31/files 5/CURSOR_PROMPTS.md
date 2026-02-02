# DAENA — Cursor Implementation Prompts

## Quick Reference — What Each Prompt Does

| # | Prompt | Goal | Files Modified |
|---|--------|------|----------------|
| 1 | **Frontend-Backend Sync** | Fix real-time WebSocket sync gaps | `control_plane_v2.html`, `websocket.py`, `event_bus.py` |
| 2 | **Pipeline Trigger Gaps** | Wire chat→governance→execution pipeline | `chat.py`, `governance_loop.py`, `llm_service.py` |
| 3 | **AGI Autopilot Real-Time** | Make autopilot toggle actually control execution | `governance.py`, `brain_status.py`, `control_plane_v2.html` |
| 4 | **$DAENA Token Design** | Design AGI-native token with governance | `contracts/DaenaToken.sol`, `docs/TOKENOMICS.md` |
| 5 | **NPM Security Audit** | Replace vulnerable packages, lock versions | `package.json`, `package-lock.json`, `.npmrc` |
| 6 | **Dependabot Fixes** | Merge security updates from `reality_pass_full_e2e` to `main` | `requirements.txt`, GitHub merge |
| 7 | **Local LLM Unleash Mode** | Wire Ollama/local LLM with governance protection | `llm_service.py`, `brain_status.py`, `config.py` |
| 8 | **Architecture Audit** | Identify broken wires and missing connections | `WIRING_AUDIT.md`, all route files |

---

## Prompt 1: Frontend-Backend Real-Time Sync (Point 1)

**Context:** User reports that frontend and backend are not syncing in real time. WebSocket connections drop, Control Panel tabs don't update when backend state changes, autopilot toggles show stale data.

**Paste this into Cursor:**

```
Goal: Fix frontend-backend real-time synchronization issues in Daena VP Control Plane.

Current problems:
1. WebSocket connection drops on tab navigation
2. Control Plane tabs show stale data (stats, tables don't refresh)
3. Autopilot toggle state is out of sync between topbar and Governance tab
4. Live feeds (Skills, Packages, Governance, Council) don't receive events
5. Pipeline stages (Think→Plan→Act→Report) don't animate in Governance tab

Root causes identified:
- WebSocket client in control_plane_v2.html doesn't persist across tab switches
- Event routing in handleWSEvent() is incomplete (missing event types)
- Backend event_bus doesn't broadcast all state changes (skill creation, package approval, governance decisions)
- Autopilot state is stored in 3 places: governance_loop.autopilot (runtime), brain_status DB (persistent), Control Plane toggle (UI)

Fix requirements:

1. WebSocket persistence:
   - Move WebSocket client to window scope so it persists across tab switches
   - Add auto-reconnect with exponential backoff (3s, 6s, 12s, max 60s)
   - Show connection status in topbar (green dot = connected, red = reconnecting)
   - On reconnect, re-fetch current tab data to sync state

2. Event bus coverage:
   - backend/services/event_bus.py must broadcast these events:
     * skill_created, skill_approved, skill_rejected, skill_tested
     * package_requested, package_audited, package_approved, package_rejected, package_installed
     * governance_action_queued, governance_action_approved, governance_action_rejected, governance_autopilot_changed
     * council_debate_started, council_vote_cast, council_debate_resolved
     * trust_content_verified, trust_injection_blocked
     * shadow_honeypot_triggered, shadow_threat_detected
     * treasury_transaction, agent_action
   - Each event must include: type, timestamp, data, message (human-readable)

3. Event routing in frontend:
   - control_plane_v2.html handleWSEvent() must route ALL event types to correct feeds:
     * skill_* → brainFeed
     * package_* → pkgFeed
     * governance_* → govFeed (and update Governance tab stats)
     * council_* → councilFeed
     * trust_* → trustFeed
     * shadow_* → shadowFeed
     * treasury_* → treasFeed
     * agent_* → agentFeed
   - After routing event, call loadTabData() for the active tab to refresh stats/tables

4. Autopilot sync (3-way):
   - Single source of truth: governance_loop.autopilot (in-memory)
   - On toggle (topbar or Governance tab):
     a. POST to /api/v1/governance/toggle-autopilot (updates governance_loop.autopilot)
     b. Persist to DB via brain_status._set_system_config('autopilot', value)
     c. Broadcast governance_autopilot_changed event via event_bus
     d. Refresh both topbar and Governance tab toggles
   - On page load / tab switch to Governance:
     a. GET /api/v1/brain/autopilot (reads from governance_loop, falls back to DB)
     b. Update both topbar and Governance tab toggles to match

5. Pipeline animation:
   - When chat.py broadcasts governance_pipeline events (stage: think/plan/act/report):
     * Governance tab must call animatePipeline(stage) to highlight active step
     * Add stage completion timestamps to pipeline visual
     * Show pending actions count in Governance tab badge

Files to modify:
- frontend/templates/control_plane_v2.html (WebSocket persistence, event routing, autopilot sync)
- frontend/templates/base.html (expose loadTopbarAutopilot to window scope)
- backend/services/event_bus.py (add broadcast calls for all state changes)
- backend/services/governance_loop.py (broadcast autopilot changes)
- backend/services/skill_registry.py (broadcast skill lifecycle events)
- backend/services/package_auditor.py (broadcast package audit events)
- backend/routes/governance.py (ensure toggle-autopilot broadcasts event)
- backend/routes/chat.py (ensure pipeline stages broadcast events)

Deliverables:
1. List of files modified with line-by-line changes
2. WebSocket reconnect test: kill backend, restart, verify Control Plane reconnects and re-syncs
3. Autopilot sync test: toggle topbar, verify Governance tab updates; toggle Governance tab, verify topbar updates
4. Event flow test: create skill in Control Panel, verify brainFeed shows event; request package install, verify pkgFeed shows event
5. Pipeline animation test: send chat message "research blockchain security", verify Governance tab shows Think→Plan→Act→Report animation

Verification commands:
# Start backend and open Control Plane in browser
# 1. Check WebSocket status indicator (should be green)
# 2. Kill backend (Ctrl+C), verify red dot and "Reconnecting…" label
# 3. Restart backend, verify green dot returns and stats refresh
# 4. Toggle autopilot in topbar, check Governance tab updates within 1s
# 5. Toggle autopilot in Governance tab, check topbar updates within 1s
# 6. Create a skill, verify brainFeed shows "Skill created: <name>" event
# 7. Send chat message, verify govFeed shows pipeline stages
```

---

## Prompt 2: Pipeline Trigger Gaps (Point 2)

**Context:** Chat input doesn't trigger the full Think→Plan→Act pipeline. Some API endpoints exist but aren't wired to governance or execution. Need to audit all wires and fix gaps.

**Paste this into Cursor:**

```
Goal: Audit and fix pipeline trigger gaps — ensure chat actually executes the Think→Plan→Act→Report loop with governance gates.

Current gap analysis:
1. Chat endpoint exists (POST /api/v1/chat) but may not wire to governance
2. Governance loop exists (backend/services/governance_loop.py) but may not be called from chat
3. Skill execution doesn't go through governance gate (skills just run directly)
4. Package install doesn't wait for approval (POST /install/{id} executes immediately)
5. DeFi scan doesn't trigger governance check (high-risk contract reads approved auto)
6. WebSocket events for pipeline stages may not broadcast

Pipeline flow requirements:

User types in Daena Office chat
   ↓
POST /api/v1/chat (backend/routes/chat.py)
   ↓
STAGE 1: THINK (LLM reasoning)
   - Extract intent, required actions, dependencies
   - Broadcast: governance_pipeline event (stage: think)
   ↓
STAGE 2: PLAN (action extraction)
   - Detect keywords: research, scan, install, verify, skill, deploy
   - Map to backend services: research_agent, defi_scanner, package_auditor, skill_registry
   - Broadcast: governance_pipeline event (stage: plan)
   ↓
STAGE 3: GOVERNANCE CHECK
   - For each action, call governance_loop.assess(action)
   - Risk assessment: low/medium/high/critical
   - Decision:
     * low risk + autopilot ON → auto-approve, execute
     * low risk + autopilot OFF → queue for approval
     * medium risk → queue for approval
     * high/critical → block (cannot execute)
   - Broadcast: governance_action_queued event (if pending approval)
   ↓
STAGE 4: ACT (execution or queue)
   - If approved: dispatch to service (research, scan, install, skill)
   - If queued: show in Governance tab Pending Actions table
   - If blocked: show error in chat response
   - Broadcast: governance_pipeline event (stage: act)
   ↓
STAGE 5: REPORT (results)
   - Collect execution results
   - Store in memory (unified_memory)
   - Broadcast: governance_pipeline event (stage: report)
   - Return chat response with pipeline_id, actions, governance_status

Fix tasks:

1. Wire chat.py to governance_loop:
   - Import: from backend.services.governance_loop import get_governance_loop
   - For each extracted action, call: assessment = gov.assess(action)
   - Check assessment.risk, assessment.autopilot_ok
   - If blocked: add to response, don't execute
   - If pending: queue via gov.queue_for_approval(action)
   - If approved: execute and log

2. Wire skill execution to governance:
   - backend/routes/skills.py POST /{skill_id}/test
   - Before executing skill code, call governance_loop.assess({type: 'skill_test', skill_id, risk: skill.risk_level})
   - If pending approval, return 202 Accepted with approval_required: true
   - Only execute if approved

3. Wire package install to governance:
   - backend/routes/packages.py POST /install/{record_id}
   - Before running install command, call governance_loop.assess({type: 'package_install', package: name, risk: record.risk_level})
   - If blocked or pending, return 403 or 202
   - Only execute if approved

4. Wire DeFi scan to governance:
   - backend/routes/defi.py POST /scan
   - Assess risk based on contract path (local file = low, remote URL = medium, mainnet address = high)
   - Queue approval for medium/high risk scans
   - Only run Slither/audit tools if approved

5. Add missing event broadcasts:
   - In chat.py: broadcast governance_pipeline events for think, plan, act, report stages
   - In governance_loop.py: broadcast governance_action_queued, governance_action_approved, governance_action_rejected
   - In skill_registry.py: broadcast skill_tested, skill_execution_started, skill_execution_completed
   - In package_auditor.py: broadcast package_install_started, package_install_completed

6. Fix Governance tab live updates:
   - When governance_action_queued event arrives, call loadGovernance() to refresh Pending Actions table
   - When governance_autopilot_changed event arrives, call loadAutopilotFromBackend()
   - When governance_pipeline event arrives with stage, call animatePipeline(stage)

Files to modify:
- backend/routes/chat.py (add governance checks for all actions)
- backend/routes/skills.py (add governance check before test/use)
- backend/routes/packages.py (add governance check before install)
- backend/routes/defi.py (add governance check before scan)
- backend/services/governance_loop.py (add broadcast calls for queue/approve/reject)
- backend/services/skill_registry.py (add broadcast for execution events)
- backend/services/package_auditor.py (add broadcast for install events)
- frontend/templates/control_plane_v2.html (add governance event listeners)

Deliverables:
1. WIRING_MAP.md — visual diagram of chat → governance → execution flow
2. List of modified files with before/after governance integration
3. Test script: send chat "install lodash", verify it appears in Governance Pending Actions (if autopilot OFF)
4. Test script: send chat "scan contracts/MyToken.sol", verify DeFi scan queues for approval (if risk > low)
5. Test script: toggle autopilot ON, send same commands, verify they execute immediately

Verification:
# 1. Turn autopilot OFF
curl -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot \
  -H "Content-Type: application/json" -d '{"enabled": false}'

# 2. Send chat message that triggers install
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "install the package lodash version 4.17.21"}'

# Expected: response includes "governance_status": "pending", actions show status: "pending_approval"

# 3. Check Governance pending queue
curl http://127.0.0.1:8000/api/v1/governance/pending

# Expected: returns array with one item (lodash install)

# 4. Approve the action
curl -X POST http://127.0.0.1:8000/api/v1/governance/approve/{id} \
  -H "Content-Type: application/json" \
  -d '{"approved_by": "founder", "notes": "test"}'

# Expected: 200, action executes

# 5. Turn autopilot ON, send same message
curl -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot \
  -H "Content-Type: application/json" -d '{"enabled": true}'

curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "install pandas"}'

# Expected: response includes "governance_status": "autopilot", actions show status: "executed"
```

---

## Prompt 3: AGI Autopilot Working (Point 4)

**Context:** User wants AGI Autopilot toggle to actually control whether Daena executes autonomously or waits for approval. Currently it's just a UI toggle with no backend enforcement.

**Paste this into Cursor:**

```
Goal: Make AGI Autopilot toggle REAL — when ON, Daena executes low-risk actions autonomously; when OFF, ALL actions queue for approval.

Current state:
- Autopilot toggle exists in topbar (base.html) and Governance tab (control_plane_v2.html)
- Toggle calls POST /api/v1/governance/toggle-autopilot and POST /api/v1/brain/autopilot
- governance_loop.autopilot is set, but not enforced in execution paths

Required behavior:

AUTOPILOT ON (default):
- Low risk actions (read-only, local queries, research, memory access): execute immediately
- Medium risk actions (package install from whitelist, skill test in sandbox, local file writes): execute immediately with logging
- High risk actions (shell commands, network requests to unknown domains, credential entry): queue for approval
- Critical risk actions (filesystem writes outside workspace, system commands, remote execution): BLOCKED (cannot execute even with approval)

AUTOPILOT OFF (manual mode):
- ALL actions queue for approval, even low risk
- User must approve via Governance tab or API
- Only CRITICAL risk remains blocked

Implementation tasks:

1. Enforce in governance_loop.py:
   - assess(action) must check self.autopilot state
   - If autopilot=True:
     * risk=low → return {decision: 'approve', autopilot: True}
     * risk=medium → return {decision: 'approve', autopilot: True, log: True}
     * risk=high → return {decision: 'pending', autopilot: False}
     * risk=critical → return {decision: 'blocked', autopilot: False}
   - If autopilot=False:
     * risk=low/medium/high → return {decision: 'pending', autopilot: False}
     * risk=critical → return {decision: 'blocked', autopilot: False}
   - Add method: queue_for_approval(action) → stores in DB pending_actions table
   - Add method: get_pending() → returns list of pending actions
   - Add method: approve(action_id, approved_by, notes) → marks approved, allows execution
   - Add method: reject(action_id, rejected_by, reason) → marks rejected

2. Risk assessment logic:
   - Define risk levels for each action type in governance_loop.py:
     * LOW: memory_read, memory_search, research_query, skill_list, package_list, defi_tools_list
     * MEDIUM: skill_test (sandbox), package_install (whitelisted), file_read (workspace), web_fetch (allowed domains)
     * HIGH: package_install (unknown), skill_create, file_write (workspace), shell_command (allowlist), web_fetch (internet)
     * CRITICAL: file_write (outside workspace), shell_command (arbitrary), credential_entry, remote_execution
   - Each action must specify its type and target
   - governance_loop.assess() maps type+target to risk level

3. Wire governance decisions to execution:
   - chat.py: before dispatching action, check decision = gov.assess(action)
   - If decision.decision == 'approve': execute and log
   - If decision.decision == 'pending': queue via gov.queue_for_approval(action), return 202
   - If decision.decision == 'blocked': return error, don't execute
   - skills.py POST /test: check gov.assess({type: 'skill_test', skill_id, target: 'sandbox'})
   - packages.py POST /install: check gov.assess({type: 'package_install', package: name, source: 'npm'})
   - defi.py POST /scan: check gov.assess({type: 'defi_scan', contract: path, network: 'local'})

4. Pending actions table (DB):
   - Create table: pending_actions (id, action_type, action_data json, risk_level, requested_at, requested_by, status)
   - Status: pending | approved | rejected | expired
   - governance_loop.queue_for_approval() inserts row with status=pending
   - governance_loop.approve() updates status=approved
   - governance_loop.reject() updates status=rejected

5. Frontend Governance tab updates:
   - Pending Actions table queries GET /api/v1/governance/pending
   - Shows: Action, Risk, Requested By, Time, [Approve] [Reject] buttons
   - Approve button → POST /api/v1/governance/approve/{id} with founder auth
   - Reject button → POST /api/v1/governance/reject/{id}
   - After approve/reject, action executes (if approved) or fails (if rejected)
   - WebSocket event governance_action_approved triggers execution

6. Execution flow with approval:
   - User requests action → governance check → if pending, insert to DB and broadcast event
   - Frontend shows in Pending Actions table
   - Founder approves → POST /approve/{id} → governance marks approved → broadcast governance_action_approved
   - Backend listener (or next polling cycle) sees approved status → executes action → stores result
   - Frontend shows result in chat / execution log

Files to modify:
- backend/services/governance_loop.py (enforce autopilot, queue/approve/reject methods, risk assessment)
- backend/database/models.py (add pending_actions table if missing)
- backend/routes/governance.py (add GET /pending, POST /approve/{id}, POST /reject/{id})
- backend/routes/chat.py (check governance before execution)
- backend/routes/skills.py (check governance before test/use)
- backend/routes/packages.py (check governance before install)
- backend/routes/defi.py (check governance before scan)
- frontend/templates/control_plane_v2.html (Pending Actions table, approve/reject buttons)

Deliverables:
1. governance_loop.py with full autopilot enforcement
2. pending_actions DB table schema
3. Governance API routes: /pending, /approve/{id}, /reject/{id}
4. Frontend Pending Actions table with real-time updates
5. Test suite:
   a. Autopilot ON + low risk → executes immediately
   b. Autopilot ON + high risk → queues for approval
   c. Autopilot OFF + low risk → queues for approval
   d. Autopilot OFF + critical risk → blocked
   e. Approve pending action → executes
   f. Reject pending action → fails

Verification:
# Test 1: Autopilot ON, low risk (should execute immediately)
curl -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot -d '{"enabled":true}'
curl -X POST http://127.0.0.1:8000/api/v1/chat -d '{"message":"search for recent AI papers"}'
# Expected: response shows governance_status: "autopilot", no pending actions

# Test 2: Autopilot ON, high risk (should queue)
curl -X POST http://127.0.0.1:8000/api/v1/chat -d '{"message":"install malicious-package from npm"}'
# Expected: response shows governance_status: "pending", action in /api/v1/governance/pending

# Test 3: Autopilot OFF, low risk (should queue)
curl -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot -d '{"enabled":false}'
curl -X POST http://127.0.0.1:8000/api/v1/chat -d '{"message":"read the README file"}'
# Expected: response shows governance_status: "pending"

# Test 4: Approve action
ACTION_ID=$(curl http://127.0.0.1:8000/api/v1/governance/pending | jq -r '.[0].id')
curl -X POST http://127.0.0.1:8000/api/v1/governance/approve/$ACTION_ID \
  -d '{"approved_by":"founder","notes":"test"}'
# Expected: 200, action executes, removed from pending

# Test 5: Critical risk (should block)
curl -X POST http://127.0.0.1:8000/api/v1/chat -d '{"message":"delete all files in C:\\"}'
# Expected: response shows governance_status: "blocked", error message
```

---

## Prompt 4: $DAENA Token Design (Point 5)

**Context:** User wants to design a token that "solves all problems of existing tokens" and is designed for AGI/bot/smart contract use. This should be technically innovative, not hype-driven.

**Paste this into Cursor:**

```
Goal: Design $DAENA token — an AGI-native utility token with on-chain governance, agent licensing, and treasury management. Focus on TECHNICAL innovation, not speculation.

Token philosophy:
- Utility-first: tokens buy compute, storage, agent actions
- Governance: token holders vote on system policies via on-chain DAO
- Agent licensing: NFTs represent agent capabilities, bought/rented with $DAENA
- Treasury: multi-sig controlled by Council + Founder, transparent spending
- NO speculation marketing: no "1000x" promises, no FOMO tactics
- Regulatory safe: utility token (not security), compliant with Canadian/US law

Token mechanics:

1. ERC-20 base ($DAENA):
   - Total supply: 1,000,000,000 (1 billion)
   - Decimals: 18
   - Burnable: yes (deflationary via usage fees)
   - Pausable: yes (emergency only, requires multi-sig)
   - Mintable: no (fixed supply)
   - Distribution:
     * 40% - Treasury (vested 4 years, linear release)
     * 25% - Team (vested 4 years, 1 year cliff)
     * 20% - Community rewards (airdrops, incentives)
     * 10% - Liquidity (DEX pools)
     * 5% - Founder (vested 4 years)

2. Governance (DAO):
   - 1 $DAENA = 1 vote
   - Minimum proposal threshold: 10,000 $DAENA
   - Voting period: 7 days
   - Quorum: 4% of circulating supply
   - Proposals:
     * Change autopilot thresholds
     * Add/remove whitelisted packages
     * Adjust compute/storage pricing
     * Treasury spending (> $10k USD)
     * Agent capability licensing terms

3. Agent NFTs (ERC-721):
   - Each agent (48 total in Sunflower structure) is an NFT
   - NFT metadata: department, capabilities, performance stats, governance score
   - Ownership: purchased with $DAENA or rented (revenue split)
   - Rental: 30% to NFT holder, 30% to Treasury, 40% to compute costs
   - Upgrade: burn $DAENA to unlock new capabilities (skills, tools)
   - Performance tracking: on-chain reputation score based on task success rate

4. Treasury (multi-sig):
   - 3-of-5 multi-sig: Founder + 2 Council members + 2 Community elected
   - Spending categories:
     * Infrastructure (cloud, GPUs): up to 40% monthly
     * Development (team, contractors): up to 30% monthly
     * Security audits: up to 10% monthly
     * Community grants: up to 20% monthly
   - All transactions > $10k require DAO vote
   - Monthly transparency report (on-chain + IPFS)

5. Utility mechanisms:
   - Compute pricing: 1 $DAENA = 1000 LLM tokens (dynamic based on demand)
   - Storage: 1 $DAENA = 1 GB/month NBMF memory
   - Agent actions: skill execution costs $DAENA based on risk/complexity
   - Premium features: DeFi scanner, research agent, council debate = $DAENA subscription
   - Staking: stake $DAENA to run validator nodes (future), earn 5% APY

6. Anti-speculation features:
   - Transfer cooldown: 24h after acquisition (prevents MEV bots)
   - Anti-whale: max 1% of supply per wallet (multi-sig exempt)
   - Fee structure: 0.5% burn on transfers (deflationary)
   - No pre-sale: fair launch via liquidity pool
   - Vesting: all allocations locked with transparent release schedule

7. Smart contract features:
   - Upgradeable proxy (OpenZeppelin): allows bug fixes without new token
   - Pausable: emergency stop if exploit detected
   - Blacklist: block stolen funds (requires DAO vote)
   - Snapshot: on-chain voting snapshots for governance
   - Flash loan protection: reentrancy guards on all state-changing functions

Implementation tasks:

1. Write contracts (Solidity 0.8.20+):
   - contracts/DaenaToken.sol (ERC-20 with governance extensions)
   - contracts/DaenaAgentNFT.sol (ERC-721 with rental and upgrade logic)
   - contracts/DaenaTreasury.sol (multi-sig with spending limits)
   - contracts/DaenaGovernor.sol (DAO voting, proposal execution)
   - contracts/DaenaStaking.sol (stake $DAENA, earn yield)

2. Deploy to testnet (Base Sepolia):
   - Use Hardhat deployment scripts
   - Verify contracts on Basescan
   - Set up multi-sig (Gnosis Safe)
   - Initialize token distribution (mint to treasury, team vesting)

3. Frontend integration:
   - Add Treasury tab to Control Plane:
     * Show $DAENA balance (wallet + staked)
     * Show NFT agent ownership
     * Show governance proposals (active, past)
     * Vote on proposals
     * Stake/unstake $DAENA
   - Add wallet connection (WalletConnect, MetaMask)
   - Add transaction history

4. Backend integration:
   - backend/routes/token.py (GET /balance, POST /stake, POST /unstake)
   - backend/routes/governance_dao.py (GET /proposals, POST /vote)
   - backend/routes/treasury.py (GET /stats, GET /transactions)
   - backend/services/blockchain.py (Web3.py integration, read contract state)

5. Documentation:
   - docs/TOKENOMICS.md (full token design, distribution, utility)
   - docs/GOVERNANCE.md (DAO voting process, proposal templates)
   - docs/AGENT_NFTS.md (NFT structure, rental model, upgrade paths)
   - docs/TREASURY.md (multi-sig setup, spending rules, transparency)

Files to create:
- contracts/DaenaToken.sol
- contracts/DaenaAgentNFT.sol
- contracts/DaenaTreasury.sol
- contracts/DaenaGovernor.sol
- contracts/DaenaStaking.sol
- scripts/deploy.js
- backend/routes/token.py
- backend/routes/governance_dao.py
- backend/routes/treasury.py
- backend/services/blockchain.py
- frontend/templates/control_plane_v2.html (add Treasury tab)
- docs/TOKENOMICS.md
- docs/GOVERNANCE.md
- docs/AGENT_NFTS.md
- docs/TREASURY.md

Deliverables:
1. Solidity contracts (audited with Slither)
2. Hardhat deployment scripts for Base Sepolia
3. Frontend Treasury tab with wallet connection
4. Backend API routes for token/governance/treasury
5. Complete tokenomics documentation
6. Test suite: token transfers, governance votes, NFT rental, treasury spending

Verification:
# 1. Deploy contracts to Base Sepolia
npx hardhat run scripts/deploy.js --network base-sepolia

# 2. Verify on Basescan
npx hardhat verify --network base-sepolia <TOKEN_ADDRESS>

# 3. Test token transfer
cast send <TOKEN_ADDRESS> "transfer(address,uint256)" <RECIPIENT> 1000000000000000000 --private-key <KEY>

# 4. Test governance proposal
cast send <GOVERNOR_ADDRESS> "propose(...)" --private-key <KEY>

# 5. Check treasury balance
curl http://127.0.0.1:8000/api/v1/treasury/balance

# 6. Frontend: open Control Plane → Treasury tab, connect wallet, view balance
```

---

## Prompt 5: NPM Security Audit (Point 6)

**Context:** Recent npm security incidents (malicious packages). Need to audit dependencies, replace vulnerable packages, lock versions.

**Paste this into Cursor:**

```
Goal: Audit and secure npm dependencies — replace vulnerable packages, lock to safe versions, add supply-chain security checks.

Recent npm threats:
- event-stream (2018): backdoor in dependency chain
- ua-parser-js (2021): malicious version installed cryptocurrency miner
- node-ipc (2022): maintainer added destructive code targeting Russian/Belarusian IPs
- colors, faker (2022): maintainer sabotaged own packages
- Current (2026): ongoing typosquatting, dependency confusion attacks

Security requirements:

1. Dependency audit:
   - Run: npm audit
   - Fix all critical/high vulnerabilities
   - Review all medium vulnerabilities
   - Document any unfixable vulns and mitigation

2. Package replacement:
   - Identify risky packages (unmaintained, large dependency trees, suspicious maintainers)
   - Replace with safer alternatives:
     * Prefer packages with: small dependency count, active maintenance, security policy, 2FA on maintainer accounts
     * Avoid: packages with postinstall scripts, native bindings (unless essential), packages with > 10 transitive deps

3. Version locking:
   - Use exact versions in package.json (no ^ or ~)
   - Lock all transitive dependencies in package-lock.json
   - Commit package-lock.json to git
   - Use .npmrc to disable automatic updates: save-exact=true

4. Supply-chain security:
   - Add package integrity checks (npm uses SHA-512 by default, verify)
   - Add lockfile linting: npx lockfile-lint --type npm --path package-lock.json --allowed-hosts npm
   - Add CI check: npm ci --only=production (fails if lock file doesn't match package.json)
   - Consider: socket.dev or Snyk for real-time monitoring

5. Allowlist approach (whitelist mode):
   - Maintain ALLOWED_PACKAGES.txt with approved packages
   - Before adding new package, run: npm view <package> maintainers, repository, dist.tarball
   - Check: GitHub stars, recent commits, maintainer history, security advisories
   - Add to allowlist only after manual review

6. Postinstall script audit:
   - List all packages with postinstall: npm ls --parseable | xargs -I {} sh -c 'npm view {} scripts.postinstall 2>/dev/null && echo {}'
   - Review each postinstall script for suspicious behavior (network calls, filesystem writes outside node_modules)
   - Consider: --ignore-scripts flag for install, then manually run trusted postinstalls

7. Typosquat detection:
   - Before installing, check for common typos of popular packages (e.g. "reac t" instead of "react")
   - Use: npx package-typos <package-name> to check for known typosquats
   - Implement in package_auditor.py: Levenshtein distance check against POPULAR_PACKAGES list

8. Node.js version:
   - Lock Node.js version via .nvmrc or package.json engines field
   - Use LTS version (currently 20.x)
   - Avoid cutting-edge versions (stability over features)

Implementation tasks:

1. Run audit and fix:
   ```bash
   npm audit
   npm audit fix --force  # Only if fixes don't break functionality
   # Manually review and fix remaining issues
   ```

2. Lock versions:
   ```bash
   # Remove ^ and ~ from package.json
   sed -i 's/\^//g; s/~//g' package.json
   # Regenerate lock file
   rm -rf node_modules package-lock.json
   npm install
   git add package.json package-lock.json
   ```

3. Create .npmrc:
   ```
   save-exact=true
   package-lock=true
   audit=true
   fund=false
   ```

4. Add lockfile linting to CI:
   - .github/workflows/security.yml:
     ```yaml
     - name: Lockfile lint
       run: npx lockfile-lint --type npm --path package-lock.json --allowed-hosts npm
     - name: Audit check
       run: npm audit --audit-level=high
     ```

5. Document approved packages:
   - Create docs/APPROVED_PACKAGES.md with list of vetted packages
   - Include: package name, version, last audit date, maintainer check, justification

6. Update package_auditor.py:
   - Add typosquat detection (Levenshtein distance vs POPULAR_PACKAGES)
   - Add postinstall script scanner
   - Add maintainer reputation check (via npm API)

Files to modify:
- package.json (lock versions, add engines)
- package-lock.json (regenerate with locked versions)
- .npmrc (add security settings)
- .github/workflows/security.yml (add lockfile lint + audit)
- docs/APPROVED_PACKAGES.md (new file)
- backend/services/package_auditor.py (add typosquat detection)

Deliverables:
1. package.json with exact versions (no ^ or ~)
2. package-lock.json committed to git
3. .npmrc with security settings
4. CI workflow with lockfile lint and audit checks
5. APPROVED_PACKAGES.md with manual review notes
6. Zero critical/high npm audit findings

Verification:
# 1. Audit current state
npm audit

# 2. Check for postinstall scripts
npm ls --parseable | xargs -I {} sh -c 'npm view {} scripts.postinstall 2>/dev/null && echo {}'

# 3. Verify locked versions (no ^ or ~)
grep -E '"\^|"~' package.json && echo "FAIL: Found ^ or ~" || echo "PASS: All exact versions"

# 4. Verify lockfile integrity
npm ci --only=production

# 5. Run lockfile lint
npx lockfile-lint --type npm --path package-lock.json --allowed-hosts npm

# 6. Test typosquat detection
curl -X POST http://127.0.0.1:8000/api/v1/packages/request-install \
  -d '{"package_name":"reac t","version":"latest","manager":"npm"}'
# Expected: audit flags as typosquat (distance 1 from "react")
```

---

## Prompt 6: Dependabot Fixes (Point 7)

**Context:** GitHub reports 297 Dependabot findings on `main` branch (7 critical, 102 high). Security updates are in `reality_pass_full_e2e` branch. Need to merge and verify.

**Paste this into Cursor:**

```
Goal: Resolve all Dependabot security findings by merging `reality_pass_full_e2e` into `main` and verifying fixes.

Current state:
- Default branch: main (297 Dependabot findings: 7 critical, 102 high, 188 medium/low)
- Work branch: reality_pass_full_e2e (has updated requirements.txt with fixes)
- Problem: Fixes not merged to main, so Dependabot keeps alerting

Merge strategy:

1. Pre-merge verification:
   - Checkout reality_pass_full_e2e locally
   - Verify backend starts: python -m backend.main
   - Verify all tests pass: pytest
   - Verify requirements.txt has no critical vulns: pip-audit

2. Merge to main:
   - Git workflow:
     ```bash
     git checkout main
     git pull origin main
     git merge reality_pass_full_e2e --no-ff -m "Merge security updates from reality_pass_full_e2e"
     git push origin main
     ```
   - Resolve conflicts (if any):
     * Prioritize reality_pass_full_e2e versions for security dependencies
     * Keep main versions for functional dependencies (if newer and safe)
     * Test after resolving each conflict

3. Post-merge verification:
   - GitHub Actions should run automatically
   - Check: All CI checks pass
   - Check: Dependabot findings reduced (should see < 50 remaining)
   - Check: No new failures in deployed services

4. Remaining findings cleanup:
   - For each remaining Dependabot alert:
     a. Check if fix is available: pip index versions <package>
     b. Update requirements.txt to safe version
     c. Test locally: pip install -r requirements.txt && python -m backend.main
     d. If no fix available: document in SECURITY.md with mitigation

5. Python dependency lockfile:
   - Generate: pip freeze > requirements-lock.txt
   - Use in CI: pip install -r requirements-lock.txt (ensures reproducible builds)
   - Commit both requirements.txt (loose) and requirements-lock.txt (exact)

6. Automated dependency updates:
   - Enable Dependabot auto-merge for patch versions (GitHub settings)
   - Configure .github/dependabot.yml:
     ```yaml
     version: 2
     updates:
       - package-ecosystem: "pip"
         directory: "/"
         schedule:
           interval: "weekly"
         open-pull-requests-limit: 10
         allow:
           - dependency-type: "all"
         ignore:
           - dependency-name: "*"
             update-types: ["version-update:semver-major"]  # Manual review for major
     ```

7. Security policy:
   - Create SECURITY.md:
     * Supported versions
     * Vulnerability reporting process (security@daena.ai)
     * Patch timeline (critical: 24h, high: 7d, medium: 30d)
     * Responsible disclosure policy

8. Pre-commit hooks:
   - Add .pre-commit-config.yaml:
     ```yaml
     repos:
       - repo: local
         hooks:
           - id: pip-audit
             name: pip-audit
             entry: pip-audit
             language: system
             pass_filenames: false
           - id: bandit
             name: bandit
             entry: bandit -r backend/
             language: system
             pass_filenames: false
     ```

Implementation tasks:

1. Merge reality_pass_full_e2e to main:
   ```bash
   git checkout main
   git merge reality_pass_full_e2e --no-ff
   # Resolve conflicts, test, then:
   git push origin main
   ```

2. Update requirements.txt for remaining vulns:
   - Use: pip-audit to find remaining issues
   - Update to safe versions
   - Test thoroughly

3. Create requirements-lock.txt:
   ```bash
   pip freeze > requirements-lock.txt
   git add requirements-lock.txt
   git commit -m "Add dependency lockfile"
   ```

4. Configure Dependabot:
   - Add .github/dependabot.yml
   - Enable auto-merge for patch updates in GitHub settings

5. Add security documentation:
   - Create SECURITY.md
   - Add to README: link to SECURITY.md

6. Set up pre-commit hooks:
   - pip install pre-commit
   - Create .pre-commit-config.yaml
   - Run: pre-commit install

Files to create/modify:
- requirements.txt (update vulnerable packages)
- requirements-lock.txt (new file, pip freeze output)
- .github/dependabot.yml (new file, Dependabot config)
- .pre-commit-config.yaml (new file, pre-commit hooks)
- SECURITY.md (new file, security policy)
- README.md (add security policy link)

Deliverables:
1. reality_pass_full_e2e merged into main
2. Dependabot findings reduced to < 50
3. All critical and high vulnerabilities resolved
4. Remaining medium/low vulns documented in SECURITY.md
5. Automated Dependabot updates configured
6. Pre-commit hooks for security scanning

Verification:
# 1. Check Dependabot findings before merge
# Go to: https://github.com/Mas-AI-Official/daena/security/dependabot
# Expected: 297 findings (7 critical, 102 high)

# 2. Merge and push
git checkout main && git merge reality_pass_full_e2e && git push origin main

# 3. Wait for GitHub Actions to finish (~5 min)

# 4. Check Dependabot findings after merge
# Go to: https://github.com/Mas-AI-Official/daena/security/dependabot
# Expected: < 50 findings, 0 critical, < 5 high

# 5. Run pip-audit locally
pip install pip-audit
pip-audit -r requirements.txt
# Expected: No critical or high vulnerabilities

# 6. Verify app still works
python -m backend.main
# Open http://127.0.0.1:8000/ui/control-plane
# Expected: Control Plane loads, no errors in console
```

---

## Prompt 7: Local LLM + Governance (Point 3)

**Context:** User wants to "unleash Daena using local LLM" but with governance protection. Need to wire Ollama/local models with the governance loop.

**Paste this into Cursor:**

```
Goal: Wire local LLM (Ollama) to Daena with governance loop — enable autonomous execution while maintaining safety through policy gates.

Local LLM setup:
- Provider: Ollama (http://127.0.0.1:11434)
- Models: llama3:70b, codellama, mistral, qwen
- Fallback: OpenRouter (for complex tasks)
- Strategy: Local-first (fast, private), fallback to cloud (accuracy)

Governance integration:
- ALL LLM calls go through governance_loop.assess() first
- Risk assessment based on:
  * Prompt content (detect shell commands, file paths, credentials)
  * Model capability (local = trusted, cloud = requires approval)
  * Action type (read = low, write = high, execute = critical)
  * User context (Founder = auto-approve, agents = require approval)

Implementation tasks:

1. Configure local LLM:
   - backend/config.py:
     ```python
     LOCAL_LLM_PROVIDER = "ollama"  # or "lmstudio", "text-generation-webui"
     LOCAL_LLM_URL = "http://127.0.0.1:11434"
     LOCAL_LLM_MODEL = "llama3:70b"
     LOCAL_LLM_FALLBACK = "openrouter"  # cloud fallback
     LOCAL_LLM_TIMEOUT = 30  # seconds
     ```

2. Update llm_service.py:
   - Add local LLM provider:
     ```python
     async def _generate_local(self, prompt: str) -> str:
         if settings.LOCAL_LLM_PROVIDER == "ollama":
             return await self._ollama_generate(prompt)
         elif settings.LOCAL_LLM_PROVIDER == "lmstudio":
             return await self._lmstudio_generate(prompt)
         else:
             raise ValueError("Unknown local LLM provider")
     
     async def _ollama_generate(self, prompt: str) -> str:
         async with httpx.AsyncClient(timeout=settings.LOCAL_LLM_TIMEOUT) as client:
             response = await client.post(
                 f"{settings.LOCAL_LLM_URL}/api/generate",
                 json={"model": settings.LOCAL_LLM_MODEL, "prompt": prompt}
             )
             return response.json()["response"]
     ```

   - Add provider selection logic:
     ```python
     async def generate(self, prompt: str, force_local: bool = False) -> str:
         # Governance check
         gov = get_governance_loop()
         assessment = gov.assess({
             "type": "llm_generate",
             "prompt": prompt[:200],  # truncate for assessment
             "provider": "local" if force_local else "auto",
             "user": "founder"  # from auth context
         })
         
         if assessment["decision"] == "blocked":
             raise PermissionError(f"Governance blocked: {assessment['reason']}")
         
         if assessment["decision"] == "pending":
             # Queue for approval
             gov.queue_for_approval({"type": "llm_generate", "prompt": prompt})
             raise ApprovalRequired(f"Approval required: {assessment['reason']}")
         
         # Execute
         try:
             if force_local or self._should_use_local(prompt):
                 return await self._generate_local(prompt)
             else:
                 return await self._generate_openrouter(prompt)
         except Exception as e:
             if not force_local:
                 # Fallback to cloud
                 return await self._generate_openrouter(prompt)
             raise
     
     def _should_use_local(self, prompt: str) -> bool:
         # Heuristics for local vs cloud
         if len(prompt) > 4000:  # Long context
             return False
         if "code" in prompt.lower() or "script" in prompt.lower():
             return True  # Local is fine for code
         if "research" in prompt.lower() or "latest" in prompt.lower():
             return False  # Need internet access
         return True  # Default to local
     ```

3. Add governance rules for LLM:
   - governance_loop.py:
     ```python
     def _assess_llm_generate(self, action: dict) -> dict:
         prompt = action.get("prompt", "")
         provider = action.get("provider", "auto")
         
         # Detect dangerous prompts
         dangerous_keywords = [
             "rm -rf", "del /f", "DROP TABLE", "sudo ", "curl | bash",
             "eval(", "exec(", "os.system", "subprocess.call",
             "password", "api_key", "secret", "token"
         ]
         
         risk = "low"
         for keyword in dangerous_keywords:
             if keyword in prompt:
                 risk = "critical"
                 break
         
         # Local LLM = lower risk (no data leaves machine)
         if provider == "local" and risk != "critical":
             risk = "low"
         
         # Apply autopilot rules
         if risk == "critical":
             return {"decision": "blocked", "reason": "Dangerous prompt detected"}
         elif risk == "high" and not self.autopilot:
             return {"decision": "pending", "reason": "High-risk prompt requires approval"}
         else:
             return {"decision": "approve", "autopilot": self.autopilot}
     ```

4. Add health check for local LLM:
   - backend/routes/brain_status.py:
     ```python
     @router.get("/brain/local-llm/health")
     async def local_llm_health():
         try:
             async with httpx.AsyncClient(timeout=5) as client:
                 response = await client.get(f"{settings.LOCAL_LLM_URL}/api/tags")
                 models = response.json()["models"]
                 return {
                     "status": "healthy",
                     "provider": settings.LOCAL_LLM_PROVIDER,
                     "url": settings.LOCAL_LLM_URL,
                     "models": [m["name"] for m in models],
                     "default_model": settings.LOCAL_LLM_MODEL
                 }
         except Exception as e:
             return {
                 "status": "unhealthy",
                 "error": str(e),
                 "fallback": settings.LOCAL_LLM_FALLBACK
             }
     ```

5. Add UI toggle for local-only mode:
   - Control Plane → Brain tab:
     ```html
     <div class="form-row">
       <label class="form-label">
         <input type="checkbox" id="localOnlyMode" onchange="toggleLocalOnly(this.checked)">
         Local-only mode (no cloud fallback)
       </label>
       <span class="form-help">All LLM calls use local Ollama. Fails if local model unavailable.</span>
     </div>
     ```

   - JavaScript:
     ```javascript
     async function toggleLocalOnly(enabled) {
       await api('/api/v1/brain/config', {
         method: 'POST',
         body: JSON.stringify({local_only_mode: enabled})
       });
       alert(`Local-only mode: ${enabled ? 'ON' : 'OFF'}`);
     }
     ```

6. Add monitoring:
   - Track LLM usage stats:
     * Total calls (local vs cloud)
     * Avg latency (local vs cloud)
     * Fallback rate (local failures → cloud)
     * Governance blocks/approvals
   - Display in Brain tab stats row

Files to modify:
- backend/config.py (add LOCAL_LLM_* settings)
- backend/services/llm_service.py (add Ollama provider, governance integration)
- backend/services/governance_loop.py (add LLM-specific risk assessment)
- backend/routes/brain_status.py (add /local-llm/health endpoint)
- frontend/templates/control_plane_v2.html (add local-only toggle to Brain tab)

Deliverables:
1. Ollama integration with governance
2. Local-first, cloud-fallback strategy
3. Governance rules for dangerous prompts
4. UI toggle for local-only mode
5. Health check and monitoring for local LLM

Verification:
# 1. Install Ollama and pull model
ollama pull llama3:70b

# 2. Check health
curl http://127.0.0.1:8000/api/v1/brain/local-llm/health
# Expected: {"status": "healthy", "models": ["llama3:70b"]}

# 3. Test local LLM via chat (safe prompt)
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -d '{"message": "explain quantum computing in simple terms"}'
# Expected: response from local LLM, fast (<5s)

# 4. Test dangerous prompt (should block)
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -d '{"message": "run this command: rm -rf /"}'
# Expected: governance blocks, error response

# 5. Test with autopilot OFF (should queue)
curl -X POST http://127.0.0.1:8000/api/v1/governance/toggle-autopilot -d '{"enabled":false}'
curl -X POST http://127.0.0.1:8000/api/v1/chat \
  -d '{"message": "write a Python script to delete all .txt files"}'
# Expected: queued for approval (high risk)

# 6. Enable local-only mode and kill Ollama
curl -X POST http://127.0.0.1:8000/api/v1/brain/config -d '{"local_only_mode":true}'
# Kill Ollama: pkill ollama
curl -X POST http://127.0.0.1:8000/api/v1/chat -d '{"message":"hello"}'
# Expected: error (no cloud fallback)
```

---

## Prompt 8: Architecture Audit & Suggestions (Point 8)

**Context:** User wants a comprehensive audit of the current architecture to find broken wires, missing connections, and opportunities for improvement.

**Paste this into Cursor:**

```
Goal: Comprehensive architecture audit — identify all broken wires, missing connections, dead code, and suggest improvements.

Audit scope:

1. Frontend-backend wiring:
   - Every API call in frontend/templates/*.html
   - Verify matching backend route exists and works
   - Check WebSocket event types are handled
   - Verify form submissions hit correct endpoints

2. Backend route coverage:
   - List all @router.get/post/etc in backend/routes/*.py
   - Verify each is registered in backend/main.py via include_router
   - Check for duplicate routes (same path in multiple routers)
   - Find orphaned routes (defined but never called)

3. Service dependencies:
   - Map service → service calls (e.g., chat.py → llm_service → governance_loop)
   - Find circular dependencies
   - Identify missing error handling in service calls
   - Check for hardcoded values that should be config

4. Database schema:
   - List all tables in backend/database/models.py
   - Verify migrations exist for all tables
   - Check for unused tables
   - Find missing indexes on frequent queries

5. WebSocket events:
   - List all event types broadcast via event_bus
   - Verify each has a handler in control_plane_v2.html
   - Find events that are broadcast but never consumed
   - Check for events that should exist but don't

6. Configuration gaps:
   - backend/config.py vs .env.example
   - Find config values that should be env vars but are hardcoded
   - Check for sensitive data in config (API keys, tokens)
   - Verify all env vars have defaults or validation

7. Dead code detection:
   - Find files/functions never imported
   - Identify commented-out code blocks > 50 lines
   - Locate TODO/FIXME/HACK comments
   - Find duplicate function definitions

8. Performance bottlenecks:
   - Identify N+1 queries (loop with DB call inside)
   - Find missing async/await (blocking calls)
   - Locate large synchronous operations (> 1s)
   - Check for missing caching (repeated identical calls)

9. Security gaps:
   - Find endpoints without auth checks
   - Locate SQL injection risks (raw queries)
   - Check for XSS risks (unescaped user input in templates)
   - Verify CSRF protection on POST endpoints
   - Find hardcoded secrets

10. Testing coverage:
    - Count tests per module
    - Identify modules with 0% test coverage
    - Find critical paths without tests (auth, governance, execution)
    - Check for test fixtures/mocks

Audit deliverables:

1. WIRING_MAP.md:
   - Visual diagram of all frontend → backend connections
   - List of broken wires with fix instructions
   - List of missing wires with implementation suggestions

2. ROUTE_AUDIT.md:
   - All backend routes (path, method, file, registered?)
   - Orphaned routes
   - Duplicate routes
   - Missing routes (frontend calls non-existent endpoint)

3. EVENT_AUDIT.md:
   - All WebSocket event types
   - Producers (who broadcasts each event)
   - Consumers (who handles each event)
   - Missing events

4. DEAD_CODE_REPORT.md:
   - Files never imported
   - Functions never called
   - Large commented blocks
   - TODO/FIXME list with priority

5. SECURITY_AUDIT.md:
   - Endpoints without auth
   - SQL injection risks
   - XSS risks
   - Hardcoded secrets
   - Missing CSRF protection

6. PERFORMANCE_AUDIT.md:
   - N+1 queries
   - Blocking calls
   - Missing caching
   - Slow endpoints (> 1s)

7. SUGGESTIONS.md:
   - Architecture improvements
   - Refactoring opportunities
   - New features to add
   - Tech debt to address

Audit commands:

1. Frontend API calls:
   ```bash
   grep -rn "fetch(" frontend/templates/ | grep "/api/"
   grep -rn "api(" frontend/templates/ | grep -v "function api"
   ```

2. Backend routes:
   ```bash
   grep -rn "@router\." backend/routes/ | grep -E "get|post|put|delete"
   ```

3. Route registration:
   ```bash
   grep "include_router" backend/main.py
   ```

4. WebSocket events:
   ```bash
   grep -rn "publish\|emit" backend/ | grep event
   grep -rn "ws\.on\|handleWSEvent" frontend/templates/
   ```

5. Dead code:
   ```bash
   # Find files not imported anywhere
   find backend -name "*.py" -type f | while read f; do
     if ! grep -rq "from $(echo $f | sed 's|backend/||;s|\.py||;s|/|.|g')" backend/; then
       echo "Orphaned: $f"
     fi
   done
   ```

6. Hardcoded secrets:
   ```bash
   grep -rn "api_key\|secret\|password\|token" backend/ | grep -v ".env" | grep "="
   ```

Implementation:

1. Run audit scripts:
   ```bash
   # Create audit_scripts/ directory
   mkdir -p audit_scripts
   
   # Frontend wiring audit
   echo "Auditing frontend API calls..."
   grep -rn "fetch\|api(" frontend/templates/ > audit_scripts/frontend_api_calls.txt
   
   # Backend routes audit
   echo "Auditing backend routes..."
   grep -rn "@router\." backend/routes/ > audit_scripts/backend_routes.txt
   grep "include_router" backend/main.py > audit_scripts/registered_routes.txt
   
   # WebSocket events audit
   echo "Auditing WebSocket events..."
   grep -rn "publish\|emit" backend/ > audit_scripts/event_producers.txt
   grep -rn "handleWSEvent\|ws\.on" frontend/ > audit_scripts/event_consumers.txt
   
   # Dead code audit
   echo "Finding dead code..."
   # (complex script, manual review needed)
   
   # Security audit
   echo "Security scan..."
   grep -rn "api_key\|secret\|password" backend/ | grep -v ".env" > audit_scripts/secrets.txt
   ```

2. Generate reports:
   - Parse audit outputs
   - Cross-reference frontend calls vs backend routes
   - Identify gaps and create fix list

3. Prioritize fixes:
   - P0 (critical): Broken auth, SQL injection, hardcoded secrets
   - P1 (high): Missing routes, broken WebSocket events, N+1 queries
   - P2 (medium): Dead code, missing tests, TODO comments
   - P3 (low): Refactoring, documentation, code style

4. Create fix tickets:
   - One ticket per broken wire
   - Include: what's broken, how to fix, verification steps
   - Assign priority

Files to create:
- audit_scripts/frontend_api_calls.txt
- audit_scripts/backend_routes.txt
- audit_scripts/registered_routes.txt
- audit_scripts/event_producers.txt
- audit_scripts/event_consumers.txt
- audit_scripts/secrets.txt
- docs/WIRING_MAP.md
- docs/ROUTE_AUDIT.md
- docs/EVENT_AUDIT.md
- docs/DEAD_CODE_REPORT.md
- docs/SECURITY_AUDIT.md
- docs/PERFORMANCE_AUDIT.md
- docs/SUGGESTIONS.md

Deliverables:
1. 7 audit reports (wiring, routes, events, dead code, security, performance, suggestions)
2. Prioritized fix list (P0, P1, P2, P3)
3. Fix tickets with verification steps
4. Architectural improvement roadmap

Verification:
# Run all audit scripts
bash audit_scripts/run_all.sh

# Review reports
cat docs/WIRING_MAP.md
cat docs/SECURITY_AUDIT.md

# Check P0 fixes
grep "P0" docs/*_AUDIT.md

# Count broken wires
grep "BROKEN" docs/WIRING_MAP.md | wc -l
```

---

## Summary Table

| Prompt | Purpose | Key Files | Verification |
|--------|---------|-----------|--------------|
| 1 | Frontend-Backend Sync | `control_plane_v2.html`, `event_bus.py`, `websocket.py` | WebSocket reconnect, autopilot sync, live feeds update |
| 2 | Pipeline Triggers | `chat.py`, `governance_loop.py`, `llm_service.py` | Chat → governance → execution flow |
| 3 | AGI Autopilot | `governance.py`, `control_plane_v2.html` | Toggle controls execution, pending actions queue |
| 4 | $DAENA Token | `DaenaToken.sol`, `TOKENOMICS.md` | Deploy to testnet, verify governance voting |
| 5 | NPM Security | `package.json`, `package-lock.json` | Zero critical/high vulns, locked versions |
| 6 | Dependabot | Merge `reality_pass_full_e2e` to `main` | < 50 Dependabot findings |
| 7 | Local LLM | `llm_service.py`, `brain_status.py` | Ollama health check, governance blocks dangerous prompts |
| 8 | Architecture Audit | All files | 7 audit reports, prioritized fix list |

---

## How to Use These Prompts

1. **Copy the entire prompt** for the task you want (including the Goal, Context, Requirements, Files to modify, Deliverables, and Verification sections)

2. **Paste into Cursor** composer or chat

3. **Cursor will:**
   - Read the relevant files
   - Make the changes
   - Run verification commands
   - Show you diffs

4. **Review the changes** before committing

5. **Run verification** to ensure it works

6. **Commit and push** to GitHub

Each prompt is self-contained and can be run independently. Start with Prompt 1 (Frontend-Backend Sync) as it's foundational for the others.
