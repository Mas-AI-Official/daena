# DAENA -- Project Context (Claude Code Extension)
# This file extends DAENA.md with Claude Code-specific instructions.
# DAENA.md contains the runtime-agnostic identity that works with ANY AI tool.
# If switching to Cursor, Codex, or another tool: read DAENA.md instead.

## SESSION STARTUP: LOAD KNOWLEDGE GRAPH
At session start, run these MCP calls to load codebase context:
```
mcp__codebase-memory__index_status(project="D-Ideas-Daena")
mcp__codebase-memory__get_architecture(project="D-Ideas-Daena")
```
Graph location: `D:\Ideas\Daena\.axon\kuzu` (9617 nodes, 37853 edges)
Use `mcp__codebase-memory__search_code` and `mcp__codebase-memory__query_graph` for fast lookups.
Use `mcp__codebase-memory__detect_changes` to see what changed since last session.

## HANDS OFF REFERENCE (2026-04-20)
Read `D:\Claude-Coworker\inbox.md` HANDS OFF section at the top before
touching any security / governance / scan / asset-shield code. The
v3.7.0 Security Supercharge stack is shipped and stable; do not
refactor without an explicit ticket + GitNexus impact analysis.

## LOCAL LLM RUNTIME (2026-04-20)
Daena's local runtime is llama.cpp `llama-server.exe` on
`127.0.0.1:8080`, NOT Ollama. Ollama is deprecated:
- `OLLAMA_ENABLED=false` in `.env` silences the 11434 probe + no-models warnings.
- `VLLM_BASE_URL=http://127.0.0.1:8080/v1` (the vLLM adapter speaks
  to any OpenAI-compatible server, including llama-server).
- Manual launcher: `backend/start-llama-server.ps1 -Model {qwen3-8b|coder|gemma}`.
- Models under `D:\Ideas\MODELS_ROOT\gguf\`.
- The separate MCP bridge at `D:\Ideas\MODELS_ROOT\local-llm-bridge\` is for Claude Code orchestration (Opus delegating to the local worker). Daena's backend does NOT use MCP for local LLM; it hits HTTP directly.

### Auto-swap manager (Package 9, 2026-04-20)
llama-server only loads one GGUF at a time, but Daena's router
wants to pick per-task (coder for code, gemma for summarization,
qwen3-8b for everything else). **`LlamaServerManager`** owns the
lifecycle and hot-swaps when requested.

`LLAMA_SERVER_MANAGED` three-valued env:
- `off` -- Daena consumes whatever you manually launched (passive)
- `respect_external` (DEFAULT) -- Daena swaps its own process on demand, but refuses to kill a server it did not start. Safe alongside Claude Code's MCP bridge.
- `force` -- Daena always owns the process. Will kill any external llama-server. Use only when the MCP bridge is NOT in use.

Manager guarantees:
- Mutex lock serializes concurrent `ensure_loaded` calls (no duplicate spawn).
- Cooldown (30s default) suppresses rapid re-swap thrash.
- Local in-memory state cached so subsequent calls to the same model skip the `/v1/models` probe.
- PID file at `backend/.llama-server.pid` tracks the managed process; external servers identified by mismatch.
- Fail-safe: any manager error in the request pre-hook is logged but never raises into the HTTP call.

## IDENTITY
Daena is a governed multi-agent LLM orchestration platform by MAS-AI Technologies Inc.
An AI operating system where 10 department-agents (each with 6 sub-capabilities) collaborate like a company, governed by internal policies, expert councils, and auditable decision trails.

Positioning: "Perplexity Computer, but governed." Speed of autonomous execution + intelligence of multi-model synthesis + invisible internal governance + cost of local-first.

## PRODUCT IDENTITY (LOCKED, do not change)
Daena is GOVERNED-FIRST AI, not local-first.
- Governance and smart orchestration is the CORE identity
- Local, cloud, hybrid are deployment OPTIONS, not the identity
- The Primary Mind setting determines which runtime orchestrates all others
- When Primary Mind = Claude Code: Claude orchestrates Codex, Gemini, Ollama
- When Primary Mind = Ollama: everything runs locally and free
- The governance pipeline applies identically regardless of which mind is primary
- "Local-first" is a pricing tier (FREE), not the product category

One-line positioning:
"Daena is the most intelligent AI -- multiple minds, one answer.
Power-first, governance-ready. Choose your brain, unleash the full system."

Do not position Daena as "Ollama wrapper" or "local AI tool."
Position Daena as "power-first intelligence with governance when you need it."

### Go-to-market positioning (added 2026-04-19)

Daena + MAS-AI sells **three things**, layered:

1. **Product (self-serve SaaS)** at `daena.mas-ai.co`
   - Governed multi-agent orchestration platform with FREE / PRO / ENT tiers.
   - Offensive security via elevated mode (founder-only activation).
   - Hosted, tenant-isolated, audit-logged.

2. **Automation service (done-with-you)** at `mas-ai.co`
   - Integrate a customer's existing job/workflow/department with Daena agents + external LLMs.
   - Examples: auto-triage support tickets, auto-run weekly revenue review, auto-scan staging before release, auto-research competitors, auto-generate customer-facing reports.
   - Deliverable: running Daena instance wired into their stack, plus playbook + SOP for their team.

3. **Consultation (done-for-you strategic)** at `mas-ai.co/consulting`
   - AI-readiness audits, governance design, agent architecture for regulated industries.
   - Positions Masoud as the governed-AI specialist, leveraging the patent filings (PhiLattice + NBMF).
   - Retainer model for ongoing advisory after initial engagement.

Website copy lives at:
- `daena.mas-ai.co` -> product pages, pricing, docs, sign-up.
- `mas-ai.co` -> services pages (automation + consulting), case studies, contact.

Do not conflate the two domains. `daena.mas-ai.co` is the product; `mas-ai.co` is the company + services surface.

### Primary Mind verification
- The Primary Mind setting (in Connections or Settings) must persist on reload
- When changed, the chat model selector should reflect the new primary
- In Auto mode, the Primary Mind handles complex tasks, Ollama handles cheap tasks
- The fallback chain must be visible: Primary Mind -> next available -> Ollama -> API keys
- Test: set Primary Mind to Claude Code, send a message in Auto mode, verify the audit log shows Claude Code was selected for complex reasoning

## OWNER
Masoud Masoori, solo founder, MAS-AI Technologies Inc., Ontario Canada.
2 USPTO provisionals filed: PhiLattice Architecture (sunflower-honeycomb), NBMF.

## IP NAMING
- PhiLattice Architecture = external brand name for the Fibonacci-derived hexagonal topology
  - Internal codebase codename: sunflower-honeycomb (NEVER rename in code)
- NBMF = Neural-Backed Memory Fabric
  - Internal codebase name: nbmf (consistent, no conflict)

## TECH STACK
- Backend: Python 3.12, FastAPI (async), SQLAlchemy 2.0 (async), Pydantic v2
- Frontend: React 18 + TypeScript + Vite + Tailwind CSS + Zustand + Framer Motion
- Database: SQLite + aiosqlite (dev), PostgreSQL + asyncpg (production)
- Cache: Redis (optional, graceful fallback)
- Queue: Celery (planned, not active)
- Streaming: Server-Sent Events (SSE) for real-time chat
- WebSocket: FastAPI WebSocket for notifications
- Auth: JWT (access + refresh tokens), OAuth2 (Google, GitHub)

## DIRECTORIES
- Canonical codebase (WRITE HERE): D:\Ideas\Daena
  - Backend: D:\Ideas\Daena\backend\
  - Frontend: D:\Ideas\Daena\frontend\
  - Docs: D:\Ideas\Daena\Doc\
  - Archive: D:\Ideas\Daena\.archive\
- Legacy (READ-ONLY): D:\Ideas\Daena_old_upgrade_20251213
- Models root: D:\Ideas\MODELS_ROOT

## RUNTIME CONTROL MODEL (3 Independent Layers)

### Layer 1: Reasoning Mode (how Daena thinks)
- **Standard** -- Fast, cheap, local-first. Single best model via router.
- **Council** -- Multi-model synthesis. 3 models independently in parallel, meta-synthesis by primary model, governance trace. Active when 2+ selectable models available. Graceful fallback to Standard with governance notice if insufficient models.
- **Quintessence** -- Council + DCP expert lens injection. Each parallel model gets a different expert perspective (from 15 DCPs across 3 domains: Engineering, Product, Design). Synthesis includes expert attribution. Same 2-model minimum as Council.

### Layer 2: Action Mode (what Daena does)
- **CMD** -- Chat/plan/simulate/preview. No external side effects.
- **EXE** -- Real execution using DaenaBot tools. Goes through security gate + governance.

### Layer 3: Continuation Mode (does Daena keep working?)
- **Autopilot OFF** -- Handle current request only, then stop.
- **Autopilot ON** -- Continue in background. Monitor, retry, escalate.

## 10-STAGE PIPELINE
All modes share this pipeline:
```
1. SecurityGate       -- Prompt injection scanning
2. LoadSession        -- Fetch session + last 20 messages
3. QueryUnderstanding -- Intent, complexity, risk classification
4. GovernanceCheck    -- Policy evaluation (tier 0-4)
5. CostPreflight     -- Budget validation
6. ModelRouter        -- Model selection (scoring or preferred_model override)
7. MemoryRecall       -- Context enrichment from NBMF tiers
8. BuildRequest       -- Format messages + system prompt
9. LLMStream          -- Yield chunks via SSE
10. Persist + Audit   -- Save response, record cost, governance log
```
EXE mode adds DaenaBot dispatch between steps 8 and 9.

## MODEL ROUTING
- Scoring weights: tag_match 0.40, locality 0.25, cost 0.20, context_window 0.15
- Locality preference: local Ollama > cloud-proxied > external API
- Default fallback: llama3.1:latest (Ollama, always available)
- Think mode model: deepseek-r1:14b
- Fallback chain: top 3 alternatives if primary fails

### 9 Providers Integrated
Ollama (local), Anthropic (Claude), OpenAI (GPT/o1/o3), Google Gemini, Groq, OpenRouter, Together.ai, Perplexity

## AGENT MODEL
10 departments, each with 6 sub-capabilities (MIND, EYES, HANDS, VOICE, SHIELD, MEMORY).
NOT 60 independent agents -- 10 unified agents with specialized limbs.
Departments: Engineering, Product, Marketing, Sales, Finance, Operations, Research, Legal & Compliance, Skill Governance, Security Operations.
All share knowledge via NBMF tiers. New departments follow golden angle spiral.

## DAENABOT (Always ON in EXE mode)
Tool execution agents wired to EXE mode pipeline:
- **FileAgent** -- File system operations (read/write/search)
- **TerminalAgent** -- Shell command execution (sandboxed)
- **BrowserAgent** -- Web automation (Playwright)
- **MCPAgent** -- MCP tool execution via HTTP with governance tier classification
- **IntentParser** -- Natural language to tool dispatcher
- **ActionPlanner** -- LLM-based multi-step decomposition with deterministic fallback
- **Workspace** -- Persistent action context chaining within a session
- **Router** -- Matches user intent to tool patterns, executes with governance

## GOVERNANCE (Power-First, Governance-Ready)

### Governance Modes (GovernanceMode enum)
- **UNLEASHED**: No governance pipeline. Shield only (IP/data protection). Raw power.
  Only Hard Laws 5 (data exfiltration) + 7 (tenant isolation) enforced.
  Audit logging still runs. Everything else: Daena finds a way.
- **BALANCED**: Light governance. SecurityGate + auto-proceed for most actions.
  Approval only for truly dangerous operations.
- **GOVERNED**: Full 10-stage pipeline (enterprise mode). All 9 Hard Laws enforced.
  Approval queues for tier 3+ actions.

### Shield (ALWAYS ON in all modes)
- SecurityGate.shield_scan() protects source code, API keys, founder info
- BehaviorGuard protects against reverse-engineering attempts
- Tenant isolation enforced at DB middleware level
- Audit logging records every decision (tamper-evident chain)

### External (user-controlled, only for connections)
- App connection permissions: Allow / Ask each time / Block (per tool)
- Critical actions (~2-5%): irreversible, high-cost, security -- ask user
- Everything else: handled by current governance mode

### Soul Engine
- Soul vault at D:\Ideas\Daena-Mind\soul\ (6 files: foundation, reasoning, personality, loyalty, shield, evolution)
- Loaded by SoulEngine (backend/app/services/soul_engine.py), cached at process startup
- Injected FIRST in system prompt (highest LLM attention priority)
- Mode-aware: UNLEASHED gets power addendum, GOVERNED gets enterprise overlay

### Governance Tiers
- Tier 0-1: "Logged" (gray badge) -- routine, no user interaction
- Tier 2: "Notified" (yellow badge) -- user informed post-hoc
- Tier 3+: "Approval Required" (red badge) -- explicit user consent needed

## MEMORY (NBMF -- Patent-Pending)
T0 Ephemeral (1hr) -> T1 Working (7d) -> T2 Project (1yr) -> T3 Institutional (permanent, founder approval) -> T4 Founder-Private (permanent, founder only).
Hallucinations auto-expire. Only verified knowledge persists.

## FRONTEND ARCHITECTURE
- 26 pages, code-split with React.lazy() (except auth + ChatPage)
- 5 Zustand stores: authStore, chatStore, modelRegistryStore, uiStore, toastStore
- Toast notification system (Zustand-based, callable from non-React code)
- Skeleton loading placeholders on all pages
- Optimistic UI for chat messages
- Auto-scroll with near-bottom detection during streaming
- Session list with 30-second TTL cache

## BACKEND ARCHITECTURE
- Multi-tenant: all data scoped to Tenant via tenant_id FK
- 10 database models: Tenant, User, Department, Agent, SubCapability, ChatSession, ChatMessage, Task, Execution, ToolCall, ApprovalQueue, GovernancePolicy, Memory, Connection, CostRecord, TokenUsage
- Startup sequence: logging -> dev tables -> seed departments -> Redis check -> ModelRegistry init -> Ollama warm-up
- Ollama keep_alive: 30m (model stays in GPU memory)

## DATABASE MODELS (backend/app/models/)
- base.py -- GUID, TimestampMixin, TenantMixin, JSONBCompat
- identity.py -- Tenant, User
- organization.py -- Department, Agent, SubCapability
- chat.py -- ChatSession, ChatMessage, ChatCategory
- execution.py -- Task, Execution, ToolCall
- governance.py -- ApprovalQueue, GovernancePolicy
- memory.py -- Memory (tiered)
- connections.py -- Connection (OAuth)
- financial.py -- CostRecord, TokenUsage

## API ENDPOINTS (backend/app/api/v1/) -- all verified 2026-03-25
- /auth -- Login, register, refresh, OAuth callbacks
- /health -- Basic + /health/detailed (uptime, Ollama, Redis, DB counts)
- /chat -- Sessions CRUD, /stream SSE, /model-registry
- /agents -- Departments + capabilities (10 depts, 60 agents)
- /governance -- Audit log + approval queue + /approvals/{id}/decide
- /memory -- Memory tiers CRUD
- /execution -- Task management (create, list, update status, retry)
- /skills -- Skill registration + catalog
- /connections -- Connectors, instances, per-tool permissions
- /runtimes -- Runtime detection, auth status, subscription info
- /settings -- User preferences (display_name, preferred_model, UI prefs in JSONB)
- /billing -- Overview, by-provider, by-task-type, history
- /heartbeat -- Status, configure, run-once, start/pause/stop
- /prompts -- Interactive agent-to-user prompts (pending, respond, history)
- /dynamic-models -- Runtime provider provisioning (hot-add API keys)
- /ws -- WebSocket connections (skeletal, polling used as interim)

## TESTING
- Backend: pytest (3086/3086 passed, 60+ test files in backend/tests/) -- verified 2026-04-18
- Frontend: tsc --noEmit for type checking (0 errors)
- Frontend build: Vite production build clean (23s)
- Main bundle: 103KB (26KB gzip), all pages lazy-loaded
- E2E: Playwright (6/6 passing)
- Linting: ruff clean, zero warnings

## CURRENT VERSION: v3.7.0-security-supercharge (2026-04-19)

Tag: v3.7.0-security-supercharge
Tests: 2956 passed, 16 skipped, 0 failed (full fast-subset regression, 2026-04-19)
Package-focused: 214/214 across the 8 new/modified test files for the Security Supercharge plan
TS errors: 0
Build: clean
8 packages landed in the Security Supercharge plan (see SESSION-LOG 2026-04-19).

### What v3.7.0 adds over v3.6.0

**Three always-on governance layers (asymmetric, initiator-aware, system-wide):**
1. Shield (existing, always on): PromptInjectionScanner + BehaviorGuard + tenant isolation.
2. Security (existing, mode-selectable): SecurityGate + ToolCallClassifier + LoopDetector + AsyncApprovalManager.
3. **Asset Shield (NEW, always on)**: vault adapter + egress filter + consent tokens + initiator-aware tier collapse. Protects api_keys / finance / identity / legal / founder_memory from egress. Operator-initiated = auto-consent; background/heartbeat/delegated = full T0-T4 ladder; asset crossings always gated regardless of initiator.

**New shipped security primitives (2026-04-19):**
- Hidden activation command: founder-only, silent keystroke interceptor, never surfaces in menus / docs / help / UI. Neutral REST path `/api/v1/security/mode/{state,activate,deactivate}`.
- `SECURITY_SCAN` intent + 8-kind target detection in `query_understanding.py`: URL, bare domain, IP, CIDR, host:port, APK/IPA/AAB, Android package, git repo.
- Chat -> ScanWorkflow bridge: Stage 2.78 SecurityScanDispatcher + event emitter with fan-out subscribers + inline `ScanProgressCard` SSE consumer.
- BeyondMythos enrichment applied to every aggregated finding (ErrorOracle, AdversarialSimulator, CompositionalPlanner wired in `scan_workflow.py` Phase 3b).
- External intelligence fan-out (`intel_fanout.py`): 6-channel parallel query across web search + NVD + GitHub Advisories + codebase-memory + NBMF T3 + knowledge graph + knowledge hunter. This is the "think outside the LLM" surface.
- CVE intel client (`cve_intel.py`) with 1hr TTL cache.
- Whitebox/blackbox source correlator (`source_correlator.py`) Shannon-style.
- Zero-FP gate (`zero_fp_gate.py`): OPERATOR+ findings without EvidenceChain are rejected before report generation. Founder override path audit-logged.
- DANGEROUS fail-safe override in intent classifier: destructive verbs (rm -rf, DROP TABLE, sudo, money transfer) always beat SECURITY_SCAN or TOOL_USE regardless of score.

**HANDS OFF list**: see `D:\Claude-Coworker\inbox.md` for the 11 backend src files + 2 frontend src files + 5 modified files + 7 test files that are stable and must not be refactored without explicit instruction.

### v3.6.0-production baseline (2026-03-28)
Tag: v3.0.0-production-ready
Tests: 3086/3086 passing (verified 2026-04-18)
25 issues fixed across P0 (6), P1 (6), P2 (5), verification (8)

### What is live and verified (browser-tested 2026-03-25)
- Chat: 7 Ollama models in selector (from live backend registry), SSE streaming, governance pipeline
- Runtimes: Claude Code + Codex + Ollama online and authenticated
- Connections: 14 connectors with Claude Desktop two-panel layout, per-tool Allow/Ask/Block permissions
- Extensions: Desktop Commander, Browser Agent, Screen Capture with permission persistence
- Settings: 12 tabs, UI preferences persist to backend JSONB (dark_mode, chat_mode, routing, etc.)
- Voice: browser-native TTS/STT, conversational mode (auto-send + auto-speak), navbar toggle
- Billing: cost_tracker.log_usage() wired into chat pipeline Stage 10, billing API endpoints live
- Governance: SSE notices explain WHY decisions were made (YOLO+AGI auto-approved, PARANOID+AGI requires approval)
- Audit: 32+ entries with model names, latency, cost. Select/archive/delete/export JSON actions.
- Departments: 10 departments, 60 agents. Dashboard shows correct count.
- Tasks: retry failed tasks, batch archive/delete, status filtering
- NBMF Archive: exports to Daena-Mind vault (D:\Ideas\Daena-Mind\) in T0-T4 tiers, Obsidian-compatible

### Ollama models loaded
deepseek-r1:14b, llama3.1:8b, mistral:7b, nomic-embed-text:latest, qwen2.5-coder:14b, qwen3-coder:30b, qwen3.5:27b

## Audit Status (2026-03-25)

Codex deep audit completed 2026-03-19. Repo B confirmed canonical.
Deep audit v2 completed 2026-03-23. 8 contract mismatches found and fixed.
Full verification completed 2026-03-25. All 12 API endpoints verified, all pages browser-tested.

Post-audit workstreams ALL DONE:
- Config hardening, founder telemetry, env precedence, memory scoping, lazy-loading
- Council/Quintessence restored as live modes (with 2-model minimum gate)
- DaenaBot always ON (EXE mode), controls removed from settings
- Skill Refinery Phase 1+2 complete (extraction, refinement, retrieval, skill store)
- AES-256 vault for secret management
- Founder policy editor with routing telemetry
- Performance optimized (40x improvement via batch SQL + Redis cache)
- Production Docker config ready (Dockerfile, docker-compose.yml, deploy scripts)
- Landing page at landing/index.html
- 55 DCPs loaded from dcps.json and wired to runtime
- Heartbeat/approval/billing contract mismatches fixed
- Settings persistence across reload (backend JSONB)
- Voice integration (TTS + STT + conversational mode)

## Ship-Ready Features (2026-03-21)

New capabilities added in ship-ready session:
- **EXE Mode**: ActionPlanner (LLM multi-step decomposition), Workspace (session action chaining), auto-detect in query_understanding
- **Skill Refinery Circuit Breaker**: timeout, concurrency limit, emergency stop, daily cost tracking
- **Dynamic Model Hot-Add**: runtime API key provisioning, model discovery without restart, per-user preferred model
- **MCP Tool Registry**: discover/register/unregister tools, governance tier auto-classification, MCPAgent for execution
- **Department 10**: Security Operations added at sunflower_index 9 (continuous monitoring, threat detection, prompt injection scanning)
- **GCP Production Deployment**: Cloud Run at https://daena-596551989073.us-central1.run.app

## Skill Refinery (Phase 1+2 complete, Phase 3 pending)

Department 9 inside Daena. NOT a separate system.

Architecture: Quintessence DCPs remain the engine. Extracted skills become fuel.
When skills exist for a domain, chat_orchestrator.py retrieves top 3-5 relevant skills and injects as evidence into DCP prompts. Pure DCP prompts still work when no skills exist.

Completed infrastructure:
- backend/app/services/skill_refinery/extraction_service.py (extract skills from content)
- backend/app/services/skill_refinery/refinement_service.py (3-pass: gap finder, improver, critic)
- backend/app/services/skill_refinery/retrieval_service.py (semantic retrieval for orchestrator)
- backend/app/services/skill_refinery/skill_store.py (CRUD + tier management)
- backend/app/api/v1/skill_refinery.py (REST endpoints)
- backend/app/models/skill.py (database model)

External tools handle ingestion (Skill_Seekers, youtube-skills). Daena IP is the refinement pipeline: gap finder, improver, critic.

Skills map to Daena-Mind vault tiers: T0=raw, T1=draft, T2=refined, T3=production, T4=compound.

Phase 3 pending: governance integration for skill trust tiers, usage tracking, news monitor for stale skills.

Circuit breaker added: asyncio.Semaphore (MAX_CONCURRENT=3), asyncio.wait_for timeout (60s),
emergency stop (FOUNDER-only), daily token cost tracking (100K limit).
Endpoints: POST /emergency-stop, POST /emergency-resume, GET /daily-cost.

## PHASE COMPLETION STATUS (as of v3.0.0)

- [x] Phase A: Wire V2 components into live UI
- [x] Phase B: Backend/frontend contract alignment (8 audit issues)
- [x] Phase C: Settings persistence + billing wiring
- [x] Phase D: Voice integration + governance visibility
- [x] Phase E: Audit log actions + task retry + NBMF archive
- [x] Phase F: Full frontend-backend sync verification (12/12 endpoints, all pages browser-tested)
- [ ] Phase G: AI Company Operations (next)

### Phase G: AI Company Operations

Activate Daena as a functioning AI company where departments execute real work:

1. **Department Activation**: Each of the 10 departments should have at least one active workflow:
   - Engineering: auto-review PRs, generate tests, fix lint errors
   - Product: track feature requests from chat, prioritize backlog
   - Marketing: generate content drafts, SEO analysis
   - Sales: lead research, outreach drafts
   - Finance: cost tracking dashboard, budget alerts
   - Operations: project status reports, scheduling
   - Research: competitive analysis, tech scouting
   - Legal & Compliance: contract review, IP tracking
   - Skill Governance: extract skills from conversations, quality scoring
   - Security Operations: prompt injection scanning, access audit

2. **Project Pipeline**: Projects page should track active work with milestones, assigned departments, and progress. Each project scopes context for agents.

3. **Client Billing**: Monthly usage reports per tenant. Token counts, API costs, runtime hours. Export as invoice PDF.

4. **24/7 Heartbeat Automation**: Heartbeat daemon runs continuously, checking inbox, tasks, runtime health, project state, git status. Failed tasks auto-retry. Critical alerts escalate to founder.

5. **Skill Refinery Phase 3**: Governance integration for skill trust tiers, usage tracking, news monitor for stale skills.

## NemoClaw Reference (study, don't adopt)

NVIDIA NemoClaw (March 2026) is an enterprise security wrapper for OpenClaw, not a competitor.

Three patterns worth studying for future Daena features:
1. OpenShell YAML hot-swap policy: governance rules that reload without restart
2. Privacy Router: PII detection and stripping before cloud API calls (natural fit for security_gate.py)
3. Single-command install UX: target for Daena deployment

## RULES
1. Never modify legacy repo.
2. NEVER delete -- archive to .archive/. Developer mode toggle for hard delete (ADMIN+ only).
3. All work in D:\Ideas\Daena\.
4. Stop at phase gates.
5. Flag unique IP for patent documentation.
6. Production-ready (no TODOs, no demo data, no hardcoded secrets).
7. Every module: docstring + type hints + async + smoke test.
8. Governance is TOGGLEABLE (UNLEASHED/BALANCED/GOVERNED). Shield (IP/data protection) always enforced.
9. Multi-user ready from day one (multi-tenant).
10. Run pytest + npm run build after every change batch. Zero tolerance for broken builds.
11. Never rename sunflower-honeycomb in code.
12. Never use em dash in any output or file content.
13. Council/Quintessence are active with minimum 2 selectable models required. If fewer than 2 models are available, graceful fallback to STANDARD with governance notice. Council: parallel 3-model synthesis. Quintessence: Council + DCP expert lens injection (3 domains, 15 experts in Phase 1).
14. When modifying chat_orchestrator.py memory enrichment, keep the pattern extendable. Future skill retrieval will hook in at the same point.
15. Soul vault lives at backend/app/soul/ (inside codebase, gitignored). Memory tiers (T0-T4) stay at D:\Ideas\Daena-Mind\ (outside codebase). Soul deploys with Docker. Memory is runtime data.
16. Always Parallel, Serial Fallback: All multi-model calls (Council, Quintessence) MUST use asyncio.gather() for parallel execution. Sequential await is fallback only when gather fails. Code never breaks -- always shoot for highest performance.

## SESSION MANAGEMENT

After completing each PHASE, write a summary to docs/SESSION-LOG.md with:
- what was done
- what was verified
- current test count
- next task

Then tell Masoud: "Phase X complete. Context is getting heavy. Consider starting a fresh session for Phase Y."

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Daena** (15301 symbols, 47874 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/Daena/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Daena/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Daena/clusters` | All functional areas |
| `gitnexus://repo/Daena/processes` | All execution flows |
| `gitnexus://repo/Daena/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
