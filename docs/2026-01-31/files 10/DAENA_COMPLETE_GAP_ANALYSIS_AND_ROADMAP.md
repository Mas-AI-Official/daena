# DAENA PROJECT: COMPLETE GAP ANALYSIS & ROADMAP
## Executive Summary - The Truth About Your Current State

**Date**: February 3, 2026  
**Hardware**: XPS 16, 32GB RAM, RTX 4060  
**Vision**: Governed AGI with Sunflower-Honeycomb + NBMF + E-DNA + DaenaBot Hands  
**Reality**: **MAJOR GAPS** - Frontend-Backend desync, security holes, no actual automation, missing integrations

---

## 🚨 CRITICAL FINDINGS

### 1. **YOU DON'T HAVE A GOVERNED AGI YET**

Your `.env` shows:
```env
DISABLE_AUTH=1                          # ❌ ANYONE CAN ACCESS
EXECUTION_TOKEN_REQUIRED=false          # ❌ NO APPROVAL ENFORCEMENT
ALLOWED_SHELL_COMMANDS=npm,pip,python   # ❌ ARBITRARY CODE EXECUTION
GOVERNANCE_AUTO_APPROVE_MEDIUM_RISK=true # ❌ AUTO-APPROVING RISKY ACTIONS
CORS_ORIGINS=http://localhost:8000      # ❌ FRONTEND ON :3000 WON'T WORK
```

**What this means**: You have the UI for governance, but **the backend ignores it**. Anyone with network access can execute commands without approval.

---

### 2. **FRONTEND ≠ BACKEND**

#### Frontend Claims:
- Skill Registry with operator filters (Founder/Daena/Agents)
- Approval policies (Auto/Needs Approval/Always)
- Risk levels (Low/Med/High/Critical)
- 900+ API integrations planned

#### Backend Reality:
- Skills exist but **don't enforce executors**
- Tool dispatch goes through `tool_broker.py` but **approval is bypassed** when `EXECUTION_TOKEN_REQUIRED=false`
- DaenaBot Hands **not running** (you get "Not configured" error)
- No actual connection to external automation (browser/desktop/shell)

#### The Problem:
Your frontend looks professional, but clicking "Test Action" either:
1. Throws "Dispatch failed" (fixed partially in recent commits)
2. Shows "Not connected to OpenClaw Gateway" (because DaenaBot Hands service isn't running)
3. Even if it executes, there's **no real audit/governance** because auth is disabled

---

### 3. **NO ACTUAL "HANDS" SERVICE**

The `claw_bot.txt` document explains:
- You need `DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws`
- You need `DAENABOT_HANDS_TOKEN=<strong secret>`
- You need a **separate WebSocket service** listening on that port
- **You don't have this running**

Without it, Daena **cannot** control your desktop, browser, or shell. She's stuck inside the backend-only sandbox.

---

### 4. **297 DEPENDABOT FINDINGS (7 CRITICAL)**

Your GitHub repo has **297 security vulnerabilities**, including:
- Outdated npm/pip packages with known CVEs
- Critical authentication bypass risks
- Potential RCE (Remote Code Execution) vectors

**This must be fixed BEFORE unleashing automation.**

---

### 5. **MISSING INTEGRATIONS**

Your frontend has placeholders for:
- Sunflower-Honeycomb (hex-mesh communication)
- NBMF Memory (3-tier L1/L2/L3)
- E-DNA Learning Engine
- DaenaBot Automation Layer
- Consulate Councils (two-tier deliberation)

Backend shows:
- ✅ NBMF files exist (`nbmf_memory.py`, `unified_memory.py`)
- ✅ E-DNA files exist (`edna_learning.py`)
- ✅ DaenaBot files exist (`daenabot_automation.py`)
- ❌ **NOT FULLY WIRED** - Startup sequence incomplete
- ❌ **NOT SYNCING** - Frontend doesn't receive real status

---

### 6. **DUPLICATE & OUTDATED FILES**

Your repo structure shows:
```
/backend          (main backend)
/backend_external (duplicate? or external tools?)
/Governance       (internal governance)
/Governance_external (duplicate?)
/Tools            (internal tools)
/Tools_external   (external tools?)
/memory_service   (main memory)
/memory_service_external (duplicate?)
/monitoring       (main monitoring)
/monitoring_external (duplicate?)
/docs             (current docs)
/docs-Previous version (outdated docs)
```

**This creates confusion:**
- Are `_external` folders for separate services or duplicates?
- Multiple `_start_backend.bat` files
- Multiple `.env` files (`.env`, `.env_azure_openai`, `_env.example`)
- Old documentation mixed with new

---

## 💡 VISION vs REALITY GAP ANALYSIS

| Component | Vision | Reality | Gap |
|-----------|--------|---------|-----|
| **Governance** | "OpenClaw freedom but controlled" | Auth disabled, no token enforcement | **90% gap** |
| **Automation** | Desktop + Browser + Shell via DaenaBot Hands | No running Hands service | **100% gap** |
| **Memory** | NBMF L1/L2/L3 with CAS+SimHash | Files exist, not fully wired | **40% gap** |
| **E-DNA** | Self-learning pattern optimization | Files exist, not active | **60% gap** |
| **Councils** | Two-tier LLM + Persona consensus | Partial implementation | **50% gap** |
| **Security** | Founder-only rule changes, encrypted vault | Auth off, no vault | **95% gap** |
| **Frontend** | Synced with backend, real-time updates | Static UI, fake data | **70% gap** |
| **Skills** | Operator-based ACLs with risk levels | No enforcement | **80% gap** |

---

## 🔧 TECHNICAL ARCHITECTURE ISSUES

### Issue 1: Startup Sequence Chaos

`backend/main.py` has:
- Multiple `_run_startup()` functions (duplicates from fixing bugs)
- Routes registered multiple times
- Services initialized but not started
- No clear dependency order

**Fix**: Clean up `main.py`, create proper startup orchestration.

---

### Issue 2: Tool Execution Pipeline Broken

Current flow:
```
Frontend Button → /api/v1/tools/submit → tool_broker.py → ???
```

Expected flow:
```
Frontend → tool_broker → risk_assessment → approval_queue 
  → (if approved) → unified_tool_executor 
  → (if hands needed) → daenabot_automation 
  → (if external) → openclaw_gateway_client → WebSocket to Hands service
```

**Problem**: Approval queue is bypassed, Hands service doesn't exist.

---

### Issue 3: Frontend Data Mocking

Your frontend shows:
- 48 agents (hardcoded)
- 8 departments (hardcoded)
- Projects (fake demo data)
- Tool actions (not synced with real backend state)

**Fix**: Create real endpoints that return actual agent/department/project state from backend.

---

### Issue 4: No Hands Service Implementation

You need:
1. A separate Python service that:
   - Listens on WebSocket at `ws://127.0.0.1:18789/ws`
   - Accepts commands: `click at x y`, `type <text>`, `run command <cmd>`, `go to <url>`
   - Executes using `pyautogui`, `playwright`, `subprocess`
   - Returns results back to Daena backend
2. Strong authentication (`DAENABOT_HANDS_TOKEN`)
3. Approval enforcement (only execute if backend says "approved")

**Current State**: You have `daenabot_automation.py` in backend, but it's meant to be called BY the Hands service, not BE the Hands service.

---

## 🖥️ OPTIMAL MODEL SETUP FOR YOUR HARDWARE

### Your Hardware:
- CPU: Intel (XPS 16)
- RAM: 32GB
- GPU: RTX 4060 (8GB VRAM)

### Recommended Ollama Models:

#### **Tier 1: Fast Local Models (Run on GPU)**
```bash
# Main reasoning model (fits in 8GB VRAM)
ollama pull qwen2.5-coder:14b-instruct  # Better than 32b for your VRAM

# Fast general model
ollama pull gemma2:9b                   # Fast, efficient

# Multimodal (vision)
ollama pull llava:13b                   # Vision + reasoning
```

#### **Tier 2: Larger Models (CPU offload, slower but smarter)**
```bash
# For complex reasoning when time permits
ollama pull llama3.3:70b-q4_K_M        # Quantized to fit, CPU-heavy

# Fallback coding model
ollama pull deepseek-coder:33b-instruct
```

#### **Tier 3: Tiny Models (Blazing fast, less smart)**
```bash
# For simple tasks
ollama pull qwen2.5:3b
ollama pull phi3:3.8b
```

---

### Hybrid Cloud Strategy

#### Free Cloud (with rate limits):
- **Google Gemini 2.0 Flash**: Free tier, very fast
- **Groq**: Free Llama 3.3 70B (limited to 20 requests/min)
- **Hugging Face Inference API**: Free for some models

#### Paid Cloud (for critical tasks):
- **Claude 3.5 Sonnet**: Your current config ($10/day budget)
- **GPT-4o**: Vision + reasoning
- **Gemini 2.0 Flash Thinking**: Complex reasoning

---

### Routing Strategy

```python
# .env configuration
LOCAL_FIRST=true
CLOUD_FALLBACK_ENABLED=true
MAX_RETRIES_BEFORE_CLOUD=2

# Priority cascade
LLM_ROUTER_STRATEGY=smart_cascade

# Model tier assignment
TIER1_LOCAL=qwen2.5-coder:14b-instruct,gemma2:9b    # GPU-fast
TIER2_LOCAL=llama3.3:70b-q4_K_M                     # CPU-slow but smart
TIER3_CLOUD_FREE=gemini-2.0-flash                   # Free cloud
TIER4_CLOUD_PAID=claude-3-5-sonnet-latest           # Paid when needed

# Task routing rules
SIMPLE_TASKS=TIER1_LOCAL           # <500 tokens, factual
CODING_TASKS=TIER1_LOCAL,TIER4_CLOUD_PAID
REASONING_TASKS=TIER2_LOCAL,TIER4_CLOUD_PAID
VISION_TASKS=llava:13b,gpt-4o
CONSENSUS_TASKS=TIER1_LOCAL,TIER2_LOCAL,TIER3_CLOUD_FREE  # 3 models vote
```

**Expected Performance**:
- 90% tasks handled locally (free)
- 7% tasks use free cloud tier (Gemini Flash)
- 3% tasks use paid cloud (Claude/GPT for critical decisions)
- Total cost: **~$2-5/day** instead of $10/day

---

## 💰 DAENA CRYPTOCURRENCY ROADMAP

### Phase 1: Research - Identify All Crypto Weaknesses

#### Common Cryptocurrency Problems:
1. **Scalability**: Bitcoin (7 TPS), Ethereum (15-30 TPS)
2. **Energy Waste**: PoW mining consumes massive power
3. **Centralization**: Mining pools control >51% hash
4. **Volatility**: Price swings 10-50% in days
5. **Security**: Smart contract bugs, reentrancy attacks
6. **Privacy**: Transactions are public (except Monero)
7. **Usability**: Complex wallets, seed phrases lost = funds gone
8. **Finality**: Bitcoin takes 60 minutes for 6 confirmations
9. **Interoperability**: Can't easily swap between chains
10. **Governance**: Hard forks split communities (BTC vs BCH)
11. **Fees**: Ethereum gas can be $50-200 per transaction
12. **MEV (Maximal Extractable Value)**: Bots front-run transactions
13. **Custody**: "Not your keys, not your coins" = user responsibility
14. **Regulation**: Uncertain legal status in many countries
15. **Environmental Impact**: E-waste from ASIC miners

---

### Phase 2: Daena Coin Design - Solutions

#### 1. **Hybrid Consensus: PoS + PoAI**
- Proof of Stake (energy efficient) + Proof of AI (Daena validates via governance)
- Daena agents act as validator nodes
- No mining waste, <0.01% of Bitcoin's energy

#### 2. **Instant Finality**
- Transactions confirm in <3 seconds using Byzantine Fault Tolerant consensus
- No waiting for blocks

#### 3. **AI-Stabilized Price**
- Daena's council monitors market, adjusts supply/demand algorithmically
- Target: <5% volatility (vs 30%+ for BTC/ETH)

#### 4. **Smart Contract Verification**
- Daena agents audit code before deployment
- Automatically detect reentrancy, overflow, access control bugs
- 99%+ vulnerability detection vs human audits

#### 5. **Universal Interoperability**
- Built-in bridges to BTC, ETH, SOL, etc.
- Atomic swaps without wrapped tokens

#### 6. **Zero-Knowledge Privacy**
- zkSNARKs for private transactions
- Optional transparency for compliance

#### 7. **AI-Powered Wallet Recovery**
- Multi-factor identity verification via Daena
- Social recovery without seed phrases
- Biometric + behavior pattern recognition

#### 8. **Dynamic Fee Adjustment**
- AI predicts network congestion, adjusts fees in real-time
- Target: <$0.01 per transaction average

#### 9. **Anti-MEV Protection**
- Encrypted mempool until block finalization
- Fair ordering enforced by Daena validators

#### 10. **DAO Governance**
- Token holders vote via Daena's council system
- Proposals must pass quorum + AI risk assessment
- No contentious hard forks

#### 11. **Regulatory Compliance Layer**
- Optional KYC/AML integration for exchanges
- Compliance mode vs privacy mode
- Geographic restrictions enforceable

#### 12. **Carbon Offset Integration**
- Automatic carbon credit purchase from transaction fees
- Net carbon-neutral blockchain

#### 13. **Sharding for Scalability**
- 100,000+ TPS via parallel shard chains
- Daena agents coordinate cross-shard transactions

#### 14. **Self-Healing Network**
- Daena's E-DNA detects anomalies, patches vulnerabilities
- Auto-upgrade smart contracts with bug fixes

#### 15. **Decentralized AI Training Rewards**
- Users contribute compute for Daena training → earn tokens
- Proof of Intelligence instead of Proof of Work

---

### Phase 3: Implementation Plan

#### Step 1: White Paper (Week 1-2)
```markdown
# Daena Coin: The First AI-Governed Cryptocurrency

## Abstract
Daena Coin solves the 15 major problems of existing cryptocurrencies by combining:
- AI-powered governance
- Hybrid PoS+PoAI consensus
- zkSNARK privacy
- Universal interoperability
- Carbon-neutral operation

## Technical Specifications
- Block time: 2 seconds
- Finality: 3 seconds
- TPS: 100,000+ (sharded)
- Energy per tx: 0.001 kWh (vs Bitcoin's 700 kWh)
- Transaction fee: $0.01 average
```

#### Step 2: Token Economics (Week 2-3)
```python
# Supply model
TOTAL_SUPPLY = 1_000_000_000  # 1 billion DAENA tokens
INITIAL_DISTRIBUTION = {
    "founders": 0.15,           # 15% vested over 4 years
    "team": 0.10,               # 10% vested over 3 years
    "ecosystem": 0.30,          # 30% for grants, partnerships
    "public_sale": 0.20,        # 20% via fair launch
    "liquidity": 0.15,          # 15% for DEX pools
    "treasury": 0.10,           # 10% for governance
}

# Inflation model
ANNUAL_INFLATION = 0.02  # 2% per year for staking rewards
MAX_SUPPLY = 2_000_000_000  # Hard cap at 2 billion

# Burn mechanism
BURN_RATE = 0.001  # 0.1% of transaction fees burned
```

#### Step 3: Smart Contract Development (Week 3-6)
```solidity
// DaenaCoin.sol - ERC-20 compatible with AI governance
contract DaenaCoin {
    // AI oracle integration
    address public daenaOracleAddress;
    
    // Governance functions
    function proposeChange(bytes memory proposal) public {
        require(balanceOf(msg.sender) >= PROPOSAL_THRESHOLD);
        // Submit to Daena AI council for risk assessment
        DaenaOracle(daenaOracleAddress).assessProposal(proposal);
    }
    
    // Dynamic fee adjustment
    function calculateFee() public view returns (uint256) {
        // AI predicts congestion, adjusts fee
        return DaenaOracle(daenaOracleAddress).getFeeRecommendation();
    }
    
    // Smart contract audit before deployment
    modifier audited() {
        require(DaenaOracle(daenaOracleAddress).auditPassed(address(this)));
        _;
    }
}
```

#### Step 4: Validator Node Setup (Week 6-8)
```python
# daena_validator.py
class DaenaValidator:
    def __init__(self):
        self.ai_council = DaenaCouncil()
        self.blockchain_client = Web3Provider()
        
    async def validate_block(self, block):
        # AI-powered validation
        risk_score = await self.ai_council.assess_risk(block)
        if risk_score > THRESHOLD:
            return self.reject_block(block, reason="AI risk assessment failed")
        
        # Verify transactions
        for tx in block.transactions:
            if not self.verify_signature(tx):
                return self.reject_block(block, reason="Invalid signature")
            
            # Check smart contract safety
            if tx.to in self.smart_contract_addresses:
                audit_result = await self.ai_council.audit_contract(tx.to)
                if not audit_result.safe:
                    return self.reject_block(block, reason=f"Unsafe contract: {audit_result.issues}")
        
        return self.accept_block(block)
```

#### Step 5: Testnet Launch (Week 9-12)
- Deploy on Ethereum Sepolia testnet
- Run Daena validator nodes
- Invite beta testers
- Stress test with 100K+ TPS

#### Step 6: Security Audit (Week 13-16)
- Third-party audit by Trail of Bits or Certik
- Bug bounty program
- Formal verification of critical contracts

#### Step 7: Mainnet Launch (Week 17-20)
- Fair launch - no pre-mine
- Initial DEX offering (IDO) on Uniswap
- CEX listings (Binance, Coinbase)

---

### Phase 4: Bot Trading Integration

#### Daena Sells to Bots
```python
# daena_market_maker.py
class DaenaMarketMaker:
    """
    Daena creates liquidity and sells tokens to trading bots
    """
    async def provide_liquidity(self):
        # Add DAENA/ETH, DAENA/USDC pools
        await self.add_liquidity_pool("DAENA/ETH", initial_eth=100)
        await self.add_liquidity_pool("DAENA/USDC", initial_usdc=10000)
    
    async def sell_to_bots(self):
        # Monitor bot activity
        bots = await self.detect_trading_bots()
        
        for bot in bots:
            # Offer tokens at optimal price
            optimal_price = await self.ai_council.calculate_optimal_price(bot)
            await self.create_limit_order(bot_address=bot, price=optimal_price)
    
    async def arbitrage_protection(self):
        # Prevent bots from profiting unfairly
        price_feeds = await self.get_multi_exchange_prices()
        if price_discrepancy > 0.05:  # 5%
            await self.rebalance_liquidity()
```

---

## 🛠️ CURSOR PROMPTS TO FIX EVERYTHING

### Prompt 1: Security Hardening

```
You are working in the Mas-AI-Official/daena repository. Fix the critical security issues:

GOAL:
1. Enable authentication properly
2. Enforce execution token requirement
3. Restrict shell commands to safe operations only
4. Update CORS to include frontend origin
5. Add JWT_SECRET and FOUNDER_APPROVAL_TOKEN to .env
6. Create a secure key vault (Windows Credential Manager integration)

ACTIONS:
A) Update .env:
   - Set DISABLE_AUTH=0
   - Set EXECUTION_TOKEN_REQUIRED=true
   - Add JWT_SECRET=<generate strong secret>
   - Add FOUNDER_APPROVAL_TOKEN=<generate strong secret>
   - Update ALLOWED_SHELL_COMMANDS=dir,ls,cat,type,echo,git
   - Update CORS_ORIGINS to include http://localhost:3000,http://127.0.0.1:3000

B) Update backend/main.py:
   - Add authentication middleware to ALL routes
   - Verify JWT token on protected endpoints
   - Enforce FOUNDER_APPROVAL_TOKEN for critical actions

C) Update backend/services/tool_broker.py:
   - Check if execution token is present before running tools
   - Block CRITICAL risk tasks always
   - Require approval for MEDIUM and HIGH risk tasks
   - Auto-approve only LOW risk tasks when GOVERNANCE_AUTO_APPROVE_LOW_RISK=true

D) Create backend/security/credential_vault.py:
   - Integrate with Windows Credential Manager for secrets
   - Never store passwords in plain text
   - Encrypt sensitive data at rest

CONSTRAINTS:
- Do not break existing functionality
- Add proper error messages when auth fails
- Log all security events to audit trail

DELIVERABLE:
- List changed files with diffs
- Verify no plain-text secrets remain in code
```

---

### Prompt 2: Implement DaenaBot Hands Service

```
You are working in the Mas-AI-Official/daena repository. Create the missing DaenaBot Hands service:

GOAL:
Create a WebSocket service that listens on ws://127.0.0.1:18789/ws and executes automation commands.

ACTIONS:
A) Create backend/services/daenabot_hands_server.py:
   - WebSocket server using `websockets` library
   - Accept commands: {"action": "click", "x": 100, "y": 200}
   - Execute using pyautogui for desktop, playwright for browser, subprocess for shell
   - Return {"status": "success", "result": ...} or {"status": "error", "error": ...}
   - Authenticate using DAENABOT_HANDS_TOKEN

B) Update backend/integrations/openclaw_gateway_client.py:
   - Connect to ws://127.0.0.1:18789/ws
   - Send commands when backend needs automation
   - Handle reconnection on disconnection
   - Timeout after 30 seconds if no response

C) Create scripts/start_daenabot_hands.py:
   - Startup script for the Hands service
   - Run in separate process
   - Log all actions to daenabot_hands.log
   - Graceful shutdown on SIGTERM

D) Update .env:
   - Add DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws
   - Add DAENABOT_HANDS_TOKEN=<strong random secret>

E) Create backend/services/hands_approval_queue.py:
   - Queue for actions awaiting founder approval
   - Frontend can poll this to show pending approvals
   - Founder approves → action executes
   - Founder rejects → action is cancelled

CONSTRAINTS:
- All desktop automation must be SANDBOXED (no destructive actions without approval)
- Browser automation must run in a separate profile
- Shell commands must be whitelisted
- Log every action with timestamp and result

TESTING:
- Create tests/test_daenabot_hands.py to verify all actions work
- Test WebSocket connection, authentication, command execution, error handling

DELIVERABLE:
- New files created
- Integration with existing backend
- Startup instructions in README
```

---

### Prompt 3: Sync Frontend with Backend

```
You are working in the Mas-AI-Official/daena repository. Sync the frontend with real backend data:

GOAL:
Replace hardcoded frontend data with real API calls to backend.

ACTIONS:
A) Update backend/routes/agents.py:
   - Add GET /api/v1/agents endpoint that returns all 48 agents from database
   - Add GET /api/v1/agents/{agent_id} for individual agent
   - Add GET /api/v1/agents/{agent_id}/status for real-time status

B) Update backend/routes/departments.py:
   - Add GET /api/v1/departments endpoint for all 8 departments
   - Add GET /api/v1/departments/{dept_id}/agents for department's agents

C) Update backend/routes/projects.py:
   - Add GET /api/v1/projects endpoint for all projects
   - Add POST /api/v1/projects to create new project
   - Add GET /api/v1/projects/{project_id}/tasks

D) Update frontend/templates/command_center.html:
   - Replace hardcoded agent data with fetch('/api/v1/agents')
   - Replace hardcoded project data with fetch('/api/v1/projects')
   - Add real-time WebSocket connection for agent status updates

E) Update frontend/templates/control_pannel.html:
   - Fetch real tools from GET /api/v1/tools
   - Show real approval queue from GET /api/v1/approvals/pending
   - Update tool status from WebSocket events

F) Add backend/services/websocket_server.py:
   - WebSocket server for real-time frontend updates
   - Broadcast agent status changes
   - Broadcast tool execution results
   - Broadcast approval requests

CONSTRAINTS:
- Use async/await for all API calls
- Show loading spinners while fetching
- Handle errors gracefully (show error toast, don't crash)
- Update frontend every 5 seconds OR on WebSocket event

DELIVERABLE:
- Updated backend routes with real data
- Updated frontend to consume real APIs
- WebSocket integration for real-time updates
- No more hardcoded data in frontend
```

---

### Prompt 4: Clean Up Duplicates and Outdated Files

```
You are working in the Mas-AI-Official/daena repository. Clean up the repo structure:

GOAL:
Remove duplicate folders, outdated files, and organize the codebase.

ANALYSIS FIRST:
1. Compare /backend vs /backend_external - are they duplicates or do they serve different purposes?
2. Compare /Governance vs /Governance_external
3. Compare /Tools vs /Tools_external
4. Compare /memory_service vs /memory_service_external
5. Compare /monitoring vs /monitoring_external
6. Identify which .env file is the canonical one
7. Identify which documentation folder is current

ACTIONS:
A) If _external folders are duplicates:
   - Delete them
   - Update any imports that referenced them

B) If _external folders serve a purpose:
   - Add README.md in each explaining the difference
   - Rename to be clearer (e.g., /backend_public_api)

C) Consolidate .env files:
   - Merge all settings into one .env
   - Create .env.example for documentation
   - Delete other .env variants

D) Move /docs-Previous version to /archive or delete if not needed

E) Clean up root directory:
   - Move all .bat scripts to /scripts
   - Move all .ps1 scripts to /scripts
   - Move all .py scripts to /tools or /scripts
   - Keep only essential files in root (README, LICENSE, .gitignore)

F) Fix startup scripts:
   - Keep only ONE backend startup script
   - Make it cross-platform (detect OS, run appropriate command)

CONSTRAINTS:
- Do NOT delete anything until you understand its purpose
- Create a DELETION_REPORT.md listing what was removed and why
- Update all imports/references to moved files

DELIVERABLE:
- Clean repo structure
- README updated with new structure
- DELETION_REPORT.md
- All tests still passing
```

---

### Prompt 5: Implement Two-Council System

```
You are working in the Mas-AI-Official/daena repository. Implement the two-tier council system:

GOAL:
Create a council system where:
- Tier 1: LLM Consensus Council (3+ models vote on same prompt)
- Tier 2: Persona Expert Council (Jobs, Dalio, Munger personas each consult their own LLM stack)

ACTIONS:
A) Create backend/services/llm_consensus_council.py:
   ```python
   class LLMConsensusCouncil:
       def __init__(self, models: List[str]):
           self.models = models  # e.g., ["qwen2.5-coder:14b", "llama3.3:70b", "claude-3-5-sonnet"]
       
       async def vote(self, prompt: str) -> dict:
           # Query all models in parallel
           responses = await asyncio.gather(*[
               self.query_model(model, prompt) for model in self.models
           ])
           
           # Vote
           consensus = self.calculate_consensus(responses)
           return {
               "individual_responses": responses,
               "consensus": consensus,
               "confidence": self.calculate_confidence(responses)
           }
   ```

B) Create backend/services/persona_expert_council.py:
   ```python
   class PersonaExpertCouncil:
       def __init__(self):
           self.experts = {
               "steve_jobs": SteveJobsPersona(),  # Focus: UX, innovation
               "ray_dalio": RayDalioPersona(),    # Focus: strategy, risk
               "charlie_munger": CharlieMungerPersona()  # Focus: first principles
           }
       
       async def consult(self, question: str, context: dict) -> dict:
           # Each expert uses their own LLM stack and methodology
           expert_opinions = {}
           for name, expert in self.experts.items():
               opinion = await expert.analyze(question, context)
               expert_opinions[name] = opinion
           
           # Daena merges expert conclusions
           final_decision = self.merge_expert_opinions(expert_opinions)
           return {
               "expert_opinions": expert_opinions,
               "final_decision": final_decision
           }
   ```

C) Create backend/routes/council.py:
   - POST /api/v1/council/llm-vote - Submit to LLM council
   - POST /api/v1/council/expert-consult - Submit to expert council
   - GET /api/v1/council/history - Get council decision history

D) Update backend/main.py to initialize councils on startup

E) Create frontend/templates/councils.html to visualize council decisions

CONSTRAINTS:
- Councils should be async for parallel querying
- Cache responses using NBMF CAS (if same prompt asked again, reuse)
- Log all council decisions to audit trail
- Allow founder to override council decisions

DELIVERABLE:
- Working two-tier council system
- Frontend visualization
- Unit tests for voting logic
- Integration with existing Daena decision pipeline
```

---

## 📋 PRIORITIZED ACTION PLAN

### PHASE 1: SECURITY (CRITICAL - DO THIS FIRST)
**Timeline**: Week 1
1. ✅ Run Cursor Prompt 1 (Security Hardening)
2. ✅ Fix 297 Dependabot vulnerabilities
3. ✅ Enable authentication + token enforcement
4. ✅ Create credential vault
5. ✅ Test: Verify unauthorized access is blocked

---

### PHASE 2: CORE FUNCTIONALITY
**Timeline**: Week 2-3
1. ✅ Run Cursor Prompt 2 (DaenaBot Hands Service)
2. ✅ Run Cursor Prompt 3 (Frontend-Backend Sync)
3. ✅ Test: Verify "Test Action" buttons work end-to-end
4. ✅ Test: Verify frontend shows real agent/project data

---

### PHASE 3: CLEANUP & OPTIMIZATION
**Timeline**: Week 4
1. ✅ Run Cursor Prompt 4 (Clean Up Duplicates)
2. ✅ Set up Ollama with recommended models
3. ✅ Configure hybrid routing (local-first, cloud fallback)
4. ✅ Test: Verify 90%+ tasks run locally
5. ✅ Monitor: Daily cost should drop from $10 to $2-5

---

### PHASE 4: ADVANCED FEATURES
**Timeline**: Week 5-6
1. ✅ Run Cursor Prompt 5 (Two-Council System)
2. ✅ Wire NBMF Memory properly (L1/L2/L3)
3. ✅ Wire E-DNA Learning Engine
4. ✅ Enable Agent Onboarding auto-sync
5. ✅ Test: Verify councils make decisions, memory persists

---

### PHASE 5: CRYPTOCURRENCY
**Timeline**: Week 7-20 (parallel to other work)
1. ✅ Week 7-8: Write white paper
2. ✅ Week 9-10: Design tokenomics
3. ✅ Week 11-14: Develop smart contracts
4. ✅ Week 15-16: Set up validator nodes
5. ✅ Week 17-18: Launch testnet
6. ✅ Week 19-20: Security audit + mainnet launch

---

## 🎯 SUCCESS CRITERIA

### You'll Know You're Done When:

1. ✅ **Security**:
   - Auth enabled, no unauthorized access possible
   - All secrets in encrypted vault
   - Zero critical vulnerabilities

2. ✅ **Functionality**:
   - Click "Test Screenshot" → Daena takes screenshot of your screen
   - Click "Test Browser" → Daena opens browser, navigates to URL
   - Frontend shows real agent data, not hardcoded
   - Approvals work: Medium/High risk tasks wait for your approval

3. ✅ **Performance**:
   - 90%+ tasks run on local Ollama models
   - Daily cost <$5 (down from $10)
   - Response time <2s for most queries

4. ✅ **Advanced**:
   - Councils make decisions and log them
   - NBMF memory persists across restarts
   - E-DNA learns from patterns
   - Agents coordinate via Hex-Mesh

5. ✅ **Crypto** (if you pursue it):
   - White paper published
   - Testnet running with 100K+ TPS
   - Daena validators operating
   - Bots can trade DAENA tokens

---

## 🚀 FINAL RECOMMENDATIONS

### 1. **Don't Try to Do Everything At Once**
Focus on Phase 1 (Security) and Phase 2 (Core Functionality) first. Get the basics rock solid before adding advanced features.

### 2. **Test Every Single Step**
After each Cursor prompt:
- ✅ Run the backend: `python backend/main.py`
- ✅ Open frontend: `http://localhost:3000`
- ✅ Click buttons, verify they work
- ✅ Check logs for errors

### 3. **Use Version Control**
Before running any Cursor prompt:
```bash
git add .
git commit -m "Pre-prompt checkpoint: About to run Prompt X"
```
This way you can rollback if something breaks.

### 4. **Frontend vs Backend**
Your current frontend is beautiful but fake. After Phase 2, it will be beautiful AND real. Don't get discouraged if it looks broken during the transition.

### 5. **Model Recommendations Summary**
```bash
# Install these Ollama models (total ~50GB disk):
ollama pull qwen2.5-coder:14b-instruct  # Main model
ollama pull gemma2:9b                   # Fast model
ollama pull llava:13b                   # Vision model
ollama pull llama3.3:70b-q4_K_M         # Fallback (quantized)

# Update .env:
DEFAULT_LOCAL_MODEL=qwen2.5-coder:14b-instruct
OLLAMA_REASONING_MODEL=llama3.3:70b-q4_K_M
OLLAMA_VISION_MODEL=llava:13b
OLLAMA_FAST_MODEL=gemma2:9b
LOCAL_FIRST=true
CLOUD_FALLBACK_ENABLED=true
CLOUD_REASONING_MODEL=claude-3-5-sonnet-latest  # Only for complex tasks
MAX_DAILY_COST_USD=5.00  # Reduced from $10
```

### 6. **Crypto: Be Realistic**
Building a cryptocurrency is a **massive** undertaking. The plan above is technically sound, but requires:
- Blockchain engineering expertise
- Smart contract security expertise
- Marketing + community building
- Legal compliance
- Significant capital (audits alone cost $50K-200K)

**Recommendation**: Focus on making Daena amazing FIRST. Then, if you want to tokenize her capabilities (e.g., "stake DAENA tokens to get priority access to her services"), that's a much simpler path than building a whole new blockchain.

---

## 📁 DELIVERABLES

This analysis provides:
1. ✅ Gap analysis (Vision vs Reality)
2. ✅ Technical architecture breakdown
3. ✅ Model recommendations for your hardware
4. ✅ 5 Cursor prompts to fix everything
5. ✅ Cryptocurrency roadmap
6. ✅ Prioritized action plan with timelines

**Next Steps**:
1. Review this document
2. Decide which phases to tackle first
3. Run Cursor Prompt 1 (Security) immediately
4. Test, test, test
5. Report back on progress

---

**GOOD LUCK! 🚀**

You're building something truly ambitious. The vision is solid, the foundation exists, but there's real work to be done to bridge the gap. Stay focused, tackle one phase at a time, and don't try to boil the ocean. Make Daena work reliably FIRST, then make her smarter, then make her a crypto titan.

Questions? Issues? Let me know!
