# Daena Architecture Atlas

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction
**Companion docs:** `DAENA_SYSTEM_GRAPH.mmd`, `DAENA_EXECUTION_SPINE_PRD.md`, `DAENA_ARCHITECTURE_GAP_BACKLOG.md`
**Inputs:** every prior `docs/Ultraview/*` report (90+ files), `docs/ARCHITECTURE.md`, `docs/PATENT-NBMF-eDNA-TLM-DREAM-UNIFIED.md`, the entire `backend/app/` and `frontend/src/` trees, and 4 parallel Explore-agent inventories run today.
**Stance:** documentation-only. No product code modified.

> **One-liner:** Daena's intelligence stack is **rich and largely
> wired** (10 department brains, OODA-R loop, Council/Quintessence,
> 5-tier NBMF, Soul Engine, Plain-English Policy Compiler, Asset
> Shield). Daena's user-facing surface is **fragmented and partially
> dishonest** (47 settings keys but only 7 enforced; two scan
> launchers; V1+V2 connections panels coexist; Dream loop defined
> but never scheduled; eDNA + RAG advertised but absent). The fix
> is NOT to delete intelligence layers — it is to wire them into
> **one canonical Execution Spine** so the operator sees a single
> action lifecycle and the intelligence runs honestly underneath.

---

## A. Founder Vision Summary

### A.1 What Daena is supposed to become

Daena is a **governed AI operating system**: a personal-or-enterprise
runtime where the operator delegates work to a structured organisation
of AI agents, every action passes through transparent governance, and
no advertised capability is fake. The founder's locked positioning
(`CLAUDE.md`):

> *"Daena is the most intelligent AI — multiple minds, one answer.
> Power-first, governance-ready. Choose your brain, unleash the full
> system."*

Daena is NOT a single-LLM wrapper, NOT an open-loop autonomous agent,
and NOT a pure SaaS dashboard. It is the **operating console** for an
"AI Ops Control Room" service per
`DAENA_BUSINESS_MODEL_REALITY_CHECK.md`: governed orchestration over
any runtime, audit trail that never blocks, brought to security-
sensitive teams that cannot ship open-loop agents.

### A.2 Why it is more than OpenClaw

OpenClaw (and Paperclip — the AGPL fighter-brand reference; see
`CLAUDE.md` competitive table) is a **single-agent scheduler**: 1
runtime = 1 employee, heartbeat ticks, atomic checkout, approval
gates. Strong distribution (53k stars in 6 weeks) and clean
`npx ... onboard --yes` UX, but **no organisational model, no
multi-runtime synthesis, no expert-lens injection, no tiered memory
that forgets hallucinations, no patent-pending dream consolidation**.

Daena occupies a categorically different unit of computation:

| Dimension                    | OpenClaw / Paperclip           | Daena                                                             |
|------------------------------|--------------------------------|-------------------------------------------------------------------|
| Unit                         | 1 agent = 1 runtime             | 10 departments × 6 capabilities = 60 capability slots, 10 brains  |
| Reasoning                    | Single-LLM call                 | Standard / Council (3+ parallel) / Quintessence (Council + DCPs)  |
| Pipeline                     | Linear scheduler                | 10-stage governed pipeline (BehaviorGuard → Persist+Audit)        |
| Memory                       | Conversation log                | NBMF 5-tier (Working / Short / Long / Core / Immutable) + L2Q     |
| Safety                       | Approval gate per task          | 9 Hard Laws + Asset Shield + initiator-aware tier collapse        |
| Self-improvement             | None                            | Dream Engine + Skill Refinery + LearningService + Self-Repair     |
| Personality                  | Generic system prompt           | Soul Engine (10 named department personas + 7 core soul docs)     |
| Security reasoning           | Out of scope                    | Laevateinn 60+ modules + scan_workflow T1-T5 + evilbob mode       |
| Deploy                       | npm install                     | Local-first (RTX 4060) OR Cloud Run; same governance both         |

The intelligence stack is the moat. Stripping it would commoditise
Daena into "yet another agent scheduler."

### A.3 What MUST be preserved (no negotiation)

1. **Department brains + Soul Engine** (10 named personas, 6
   capabilities each). The org-chart metaphor is the user mental model.
2. **OODA-R loop** (`cognition/ooda_engine.py`) — observe, orient,
   decide, act, **reflect**. The reflect phase is what makes Daena
   self-correcting.
3. **Council / Quintessence** with DCP expert-lens injection. Even
   if downgraded by the Three-Tier Escalation Router on simple
   queries, the option must remain on hard problems.
4. **NBMF 5-tier memory + CAS dedup + L2Q quarantine + trust-gated
   promotion** (patent-pending). Hallucinations expire; only verified
   knowledge persists.
5. **Always-on Shield** (PromptInjectionScanner + BehaviorGuard +
   tenant isolation + Asset Shield egress filter). Never a toggle.
6. **9 Hard Laws** + hash-chained audit ledger (Hard Law #9). Tamper
   evidence is the trust foundation.
7. **Plain-English Policy Compiler** (founder writes English, Claude
   CLI compiles to YAML, SecurityGate hot-reloads). Operator never
   touches JSON triggers.
8. **Local-first deployment** + cloud-optional. Operator owns the
   GPU, the SQLite, the Daena-Mind vault.

Collapsing any of these = no longer Daena.

---

## B. Intelligence Layers

For each layer: source, status, inputs, outputs, downstream consumers,
frontend surface, tests, risks. Status legend: **WORKING** (hot path),
**PARTIAL** (some consumers / scheduling missing), **DOC-ONLY**
(referenced but no code), **UNKNOWN** (needs live verification).

### B.1 Department Brains — 10 departments × 6 capabilities

- **Status:** **WORKING** (DB model + router live; seeding path
  unclear).
- **Source:** `app/models/organization.py` (Department, Agent,
  BrainModel, SubCapability with `(department_id, sub_capability)`
  unique constraint), `app/services/department_router.py`
  (TASK_DEPARTMENT_MAP — 17 task types → dept × cap),
  `app/services/departments/*.py` (border_agent, marketing_agent,
  sales_agent, security_operations_agent).
- **Inputs:** `task_type` strings from SwarmPlanner / chat
  orchestrator VP stage.
- **Outputs:** `AgentAssignment(department_id, sub_capability,
  agent_id, model_preference)`.
- **Downstream:** SwarmExecutor; chat orchestrator system-prompt
  builder (via Soul Engine overlay).
- **Frontend:** `/departments` (DepartmentsPage), `/minds` +
  `/minds/:slug` (MindsPage / MindDetailPage), `/agents` API.
- **Tests:** none for routing; org seed path not test-covered.
- **Risks:** Department seeding lives in lifespan startup; if seed
  table empty in fresh DB, `department_router.route()` may fail
  silently. The router uses an in-memory cache with no health
  endpoint.

### B.2 Six-capability pattern (MIND / EYES / HANDS / VOICE / SHIELD / MEMORY)

- **Status:** **WORKING** (1 agent per capability per department;
  enforced by DB unique constraint).
- **Mapping (from `department_router.py:34-52`):**
  - HANDS — code_generation, code_editing, browser_automation, bulk_operations
  - EYES — file_operations, web_research
  - MIND — data_analysis, complex_reasoning, cost_analysis, compliance_check, skill_extraction
  - VOICE — simple_chat, content_creation, outreach_draft
  - SHIELD — security_scan
  - MEMORY — implicit (no direct task-type mapping found)
- **Risk:** MEMORY capability has no direct `TASK_DEPARTMENT_MAP`
  entry — it is implicit (memory is a substrate, not a task class).
  Document this so future contributors don't add MEMORY tasks
  expecting routing.

### B.3 OODA-R loop

- **Status:** **WORKING** (core loop implemented, used by EXE-mode
  agent loops; feature-flagged in chat orchestrator).
- **Source:** `app/services/cognition/ooda_engine.py`. Phases via
  `CognitivePhase` enum: OBSERVE / ORIENT / DECIDE / ACT / REFLECT.
- **Inputs:** task description → `CognitiveState`.
- **Outputs:** `CognitiveResult(success, strategies_tried,
  cycles_used, lessons_learned, root_causes_found)`. Max 5 cycles.
- **Downstream:** AgentLoop wraps OODA for tool execution; Tool
  Lifecycle Manager records outcomes; Council/Quintessence is
  invoked in DECIDE.
- **Integration:** OBSERVE recalls from NBMF, ORIENT picks
  frameworks via MetaReasoner, DECIDE uses Council scoring, ACT
  uses ToolUseLoop + LoopDetector, REFLECT runs 5-Whys + writes
  lessons to NBMF.
- **Frontend:** none (background reasoning).
- **Tests:** none.
- **Risks:** Max-cycle safety exists but no max-strategies-per-cycle
  cap. No timeout on phase wall-time. REFLECT writes to NBMF but
  hits the same `memory_generation` privacy gate (PR-S1) — should
  use `store_experience` with agent-experience semantics, not
  user-content semantics.

### B.4 Cognitive layer (20+ frameworks)

- **Status:** **WORKING** (frameworks live, called by MetaReasoner;
  some helpers PARTIAL).
- **Source:** `app/services/cognition/` — `meta_reasoner.py`,
  `cognitive_reasoner.py`, `knowledge_hunter.py`, `resource_finder.py`,
  `self_upgrader.py`, `mind_router.py`, `lens_router.py`,
  `apex_cognition.py`, `beyond_mythos.py`, `first_principles.py`,
  `five_whys.py`, `inversion.py`, `pre_mortem.py`,
  `constraint_analyzer.py`, `constraint_probe.py`,
  `completeness_probe.py`, `consequence_chain.py`,
  `task_prioritizer.py`, `weakness_tracker.py`, `unreplicable.py`,
  `knowledge_graph.py`.
- **Frontend:** none.
- **Risks:** Several "Apex / Beyond Mythos / KnowledgeHunter" modules
  are PARTIAL — they have callers but the inputs/outputs are not
  always observable. Suspected dead-end branches inside `apex_cognition`.

### B.5 Council + Quintessence (multi-model synthesis with DCP lenses)

- **Status:** **WORKING** (Council parallel-fan-out + synthesizer
  live; Quintessence with 25 of 55 DCPs shipped).
- **Source:** `app/services/council_engine.py`,
  `app/services/quintessence_engine.py`,
  `app/services/dcp_loader.py`, `app/config/dcps.json` (55 DCPs:
  ENGINEERING, PRODUCT, DESIGN, SECURITY, STRATEGY shipped — 5
  domains × 5 experts = 25; 6 domain placeholders empty).
- **DCP per-expert fields:** `id`, `archetype`, `prompt_directive`,
  `decision_priorities`, `blind_spots`, `evaluation_criteria`.
- **Council flow:** parallel proposers → anonymized peer review
  (Karpathy llm-council pattern, `CLAUDE.md` "MIXTURE-OF-AGENTS")
  → chairman synthesis with DISAGREEMENT ANALYSIS + VERIFICATION +
  VERDICT + SELF-CRITIQUE.
- **Three-Tier Escalation Router** (`CLAUDE.md`): trivial → single
  mind --effort low; moderate → single mind --effort medium;
  complex/risky/operator-toggled → Council/QE. Downgrades emit
  `orchestrator.council_downgraded_to_standard` audit row.
- **Frontend:** routing-mode pill in `Header.tsx` (STD / QE).
- **Tests:** none for council; tier-router downgrade not test-covered.
- **Risks:** 30 DCPs unshipped (6 empty stubs in `dcps.json`).
  Synthesis prompt is large — latency cost on every QE invocation.
  No fallback if synthesizer model errors mid-stream.

### B.6 Governance / Shield / Asset Shield / Plain-English Policy

- **Status:** **WORKING** (always-on; PR-S1 added privacy gates).
- **Source:** `app/services/security_gate.py`, 
  `app/services/security/behavior_guard.py`,
  `app/services/security/asset_shield/` (consent_token, egress_filter,
  operator_initiation, vault_adapter), `app/services/governance.py`,
  `app/services/policy_store.py`, `app/services/policy_compiler.py`,
  `app/services/permission_dispatch.py`,
  `app/services/permission_resolver.py`, `app/api/v1/policies.py`.
- **Layers:**
  - **Shield always-on:** SecurityGate `shield_scan()` (source-code,
    API-key, founder-data patterns) + BehaviorGuard (session risk
    score CURIOUS → JAILBREAK → EXTRACTION).
  - **Security mode-selectable:** SecurityGate `scan()` (injection
    patterns) only fires in BALANCED + GOVERNED modes.
  - **Asset Shield always-on:** vault adapter + egress filter +
    consent tokens + initiator-aware tier collapse (operator-
    initiated → auto-consent; background → full T0-T4 ladder).
  - **Plain-English Policy Compiler:** `POST /policies/compile`
    translates English → YAML; SecurityGate watches dir + reloads.
  - **9 Hard Laws** (immutable; any mode enforces audit + Hard Laws).
- **Frontend:** `/policies` (PoliciesPage), `/governance/approvals`,
  `/governance/audit`, `/security/*`. Header governance pill.
- **Tests:** policies test, hard-law test (limited).
- **Risks:** Audit hash chain is computed but **NOT validated on
  read** — operator can delete rows; chain breaks silently. No
  `POST /governance/audit/verify` endpoint visible. Founder's
  evilbob mode bypass uses HMAC compare on `EVILBOB_KEY` but env
  leaks would be catastrophic.

### B.7 Memory / NBMF (5 tiers + CAS + L2Q + trust)

- **Status:** **WORKING** with PR-S1 privacy enforcement.
- **Source:** `app/services/memory.py`, `app/models/memory.py`
  (`MemoryEntry`, `LearningLog`).
- **Tiers:** WORKING (T0, 30 min) → SHORT_TERM (T1, 24 hr) →
  LONG_TERM (T2) → CORE (T3) → IMMUTABLE (T4).
- **Extensions:** SHA-256 CAS dedup; L2Q quarantine
  (`is_quarantined=True` until trust ≥ 0.7); trust scoring 0.0-1.0;
  agent-experience content types (AGENT_DECISION, SKILL_OUTCOME,
  PATTERN_LEARNED, APPROACH_FAILED) auto-quarantine; user-content
  types (FACT, PREFERENCE, LEARNING, POLICY, DIRECTIVE).
- **Privacy (PR-S1):** `users.settings.memory_generation=false` →
  `store()` returns `{"blocked_by_privacy": True}` sentinel + once-
  per-process audit row. `users.settings.search_past_conversations=false`
  → orchestrator Stage 6 skips `recall_for_chat`.
- **Frontend:** Settings → Memory + Privacy tabs. Memory page partial.
- **Risks:** Promotion threshold (0.7) may trap useful learnings in
  quarantine. CORE tier has no TTL — unbounded growth. Embeddings
  field exists but is never populated; semantic search degrades to
  keyword + stopword stripping (lossy).

### B.8 Dream Engine — self-correction loop (patent-pending)

- **Status:** **PARTIAL — defined, NOT scheduled.**
- **Source:** `app/services/dream_engine.py` (~200 lines).
- **Cycle ops:** MERGE (Jaccard > 0.75), PROMOTE (quarantined →
  trust ≥ 0.7), CONTRADICT (conflicting tag/content), SYNTHESIZE
  (recurring patterns → reusable skills), DECAY (-0.05 trust per
  30d, demote at 90d, archive at 180d), SENSITIVE_REENCODE
  (PII / financial / medical / credentials regex re-encrypt).
- **Trigger:** **NONE in code today.** No cron entry. No startup
  hook. No API endpoint to invoke. The function exists but nobody
  calls it on a schedule.
- **Frontend:** none.
- **Risks:** Highest-leverage intelligence layer that is currently
  inert. Until it runs, NBMF accumulates without merging,
  contradiction-detection never fires, sensitive content sits in
  cleartext indefinitely. **Top P0 wire-up.** (See backlog.)

### B.9 eDNA — enterprise behavior layer

- **Status:** **DOC-ONLY.** No source file matches `eDNA` or
  `enterprise.dna` in the codebase.
- **Reference:** `CLAUDE.md` IDENTITY section + `docs/PATENT-NBMF-eDNA-TLM-DREAM-UNIFIED.md`.
- **Partial substitute:** `RoutingPolicy` model in
  `app/models/governance.py` covers per-tenant overrides
  (preferred_models, provider_priority, cost_ceiling,
  blocked_models). But there is no auto-extraction from audit trail,
  no cross-decision pattern learning, no "company DNA" surface.
- **Frontend:** none. (PoliciesPage handles named rules, not
  emergent behavior.)
- **Risks:** Patent application references eDNA prominently. If
  patent prosecution depends on demonstrable embodiment, eDNA needs
  at least a minimum viable wire (e.g. "extract repeated approval
  patterns from audit trail → propose policy"). Today it is a
  marketing claim.

### B.10 Skill / Tool discovery (TLM)

- **Status:** **WORKING** for the core loop; vault sync STUB; tool
  catalog hardcoded.
- **Source:** `app/services/skill_refinery/` (extraction_service,
  refinement_service, retrieval_service, skill_store, news_monitor,
  _nbmf_hook), `app/services/tool_lifecycle/` (tool_discovery,
  tool_registry, session_manager, activation_proxy, usage_tracker,
  health_monitor, phase_detector, orchestra_integration,
  auto_scanner, nbmf_bridge), `app/services/skill_scanner.py`,
  `app/services/skill_service.py`.
- **Discovery:** `tool_discovery.py` keyword match against
  `TOOL_CATALOG` (~170 tools, hardcoded). Returns ranked
  candidates.
- **Refinery (3-pass):** Gap Finder → Improver → Critic; outputs
  T2_REFINED skill with confidence. Circuit breaker: max 3
  concurrent, daily 100K-token budget, founder emergency-stop.
- **Skill maturity tiers:** T0_RAW → T1_DRAFT → T2_REFINED →
  T3_PRODUCTION → T4_COMPOUND. Maps to `D:\Ideas\Daena-Mind\T*\`.
- **Frontend:** `/skills` (SkillsPage with permission dropdown).
- **Risks:** TOOL_CATALOG static. No bidirectional sync between
  RefinedSkill DB rows and Daena-Mind vault markdown files (Phase
  E promised; STUB).

### B.11 Security reasoning — Laevateinn pipeline + scan workflow + evilbob

- **Status:** **WORKING** with founder gates.
- **Source:** `app/services/security/scan_workflow.py` (9-stage
  orchestrator), `app/services/security/evilbob_mode.py`
  (offensive-mode activation), `app/services/security/real_scanner.py`,
  `app/services/laevateinn/*` (60+ reasoning modules: debate,
  deep_think, code_verifier, causal_graph, adversarial_gate,
  outcome_simulator, episodic_memory, knowledge_graph, meta_monitor,
  speculative, tool_augmented, etc.).
- **Tier costs:** T1 SCOUT $0.50 + $0.002/file → T5 EVILBOB
  $50 + $0.05/file.
- **evilbob activation gate (ALL must hold):** `EVILBOB_KEY` env
  matches user input (HMAC constant-time compare); environment is
  LOCAL (not Cloud Run / staging / prod, detected via `K_SERVICE`
  / `GAE_ENV` / `AWS_LAMBDA_FUNCTION_NAME`); user role is
  founder/admin.
- **Frontend:** `/security` (SecurityDashboardPage with 5 sub-tabs),
  `/scan` (ScanPage), `/scan/:id/walkthrough` (ScanWalkthroughPage),
  `/engagements` (EngagementConsolePage), `/security-scope`.
- **Tests:** none for full scan_workflow; some Laevateinn module
  tests sparse.
- **Risks:** Two scan launchers (ScanPage + EngagementConsolePage) —
  see §F. `tool_augmented.py` has `web_search_stub` references —
  fake research evidence in strategic mode. `laevateinn/knowledge_graph.py`
  is local SQLite, **NOT tenant-isolated** (multi-tenant privacy
  gap if cloud ever resumes).

### B.12 Self-improvement / auto-learning

- **Status:** **PARTIAL** (audit live; learning loop in-memory only —
  patterns wiped on restart).
- **Source:** `app/services/self_improvement/self_audit.py` (read-
  only audits — pytest count, ruff lint, security scan score 0-100),
  `app/services/self_fix.py` (Tier-2 if tests pass / Tier-3 if
  fail), `app/services/self_repair.py` (max 3 attempts; Ollama only),
  `app/services/learning_service.py` (ActionOutcome → LearnedPattern
  if 3+ steps + 80% success).
- **Frontend:** `/api/v1/self-improvement` API; no dedicated page.
- **Risks:** **Rule 17 violation.** `LearningService` keeps
  `_active: dict` and `_history: list` in memory only. Restart
  wipes everything. The promised feedback loop (LearningService →
  SkillRefinery → NBMF → DreamEngine) **never closes** because
  step 1 doesn't persist.

### B.13 Department Souls (10 named personas + 7 core docs)

- **Status:** **WORKING.**
- **Source:** `app/services/soul_engine.py`,
  `app/soul/foundation.md`, `reasoning.md`, `personality.md`,
  `loyalty.md`, `shield.md`, `vp_mode.md` (added 2026-04-18),
  `emotional_awareness.md` (added 2026-04-22),
  `app/soul/departments/{engineering,product,marketing,sales,finance,
  operations,research,legal_compliance,skill_governance,security_operations}.md`,
  `app/api/v1/souls.py`.
- **Personas:** Aria (Engineering), Nova (Product), Zephyr
  (Marketing), Orion (Sales), Sterling (Finance), Atlas (Operations),
  Iris (Research), Themis (Legal & Compliance), Kira (Skill
  Governance), Rourke (Security Operations).
- **Mode overlays:** UNLEASHED (full soul + power addendum) /
  BALANCED (full soul + light guardrails) / GOVERNED (full soul +
  enterprise overlay).
- **Frontend:** `/minds` + `/minds/:slug`.
- **Risks:** Soul `.md` files are not in DB version control —
  manual edits not auditable. VP mode added late; composition
  order with other layers may surprise older invocations.

---

## C. Execution Layers

### C.1 Chat pipeline — `POST /api/v1/chat/messages/stream`

- **Status:** **WORKING** (10-stage SSE pipeline; ~26-substage form
  per ARCHITECTURE.md April 2026 note).
- **Service:** `app/services/chat_orchestrator.py` (~3600 lines).
- **Stages (canonical):** 0a BehaviorGuard → 0b SecurityGate → 1
  LoadSession → 2 QueryUnderstanding → 3 GovernanceCheck → 4
  CostPreflight → 5 ModelRouter → 6 MemoryRecall (PR-S1 gated) →
  6.1 Agent experiences (NOT user-recall; tenant-scoped) → 6.2
  CKG cross-domain insights → 7 BuildRequest (system prompt +
  Soul + skill evidence + TLM tool catalog) → 7.5 DaenaBot
  dispatch (EXE only) → 7.6 TLM record → 8 LLMStream → 9 Persist
  → 10 Audit + Cost.
- **DB writes:** ChatMessage, GoaAuditEvent, ToolExecution (EXE),
  DepartmentMessage (VP fan-out).
- **Audit:** `LLM_CALL`, `privacy.memory_recall_skipped`,
  governor-resolved action types.
- **Notification:** none from chat itself; downstream services
  emit (cost_guard → budget_alert; approval → governance_rejection).
- **Frontend:** `/chat`, `/dashboard`, `/departments/:slug/chat`.
- **Gaps:** VP stage 2.8 feature-flagged off pending Phase 12.

### C.2 Action modes (CMD vs EXE)

- **Status:** **WORKING.** CMD mode rejects tool execution outright
  (`session.mode == "CMD"` raises `ValidationError`). EXE routes
  through DaenaBot.
- **Service:** `app/services/execution_service.py`.
- **DB writes (EXE):** ToolExecution, GoaRequest if Tier ≥ 3.
- **Frontend:** ChatPage mode toggle + Header CMD/EXE pill.
- **Gaps:** None at gate; EXE depends on Stage 7.5 dispatch path.

### C.3 Runtime / model routing

- **Status:** **WORKING.**
- **Service:** `app/services/model_router.py`,
  `app/services/model_registry.py`, `app/services/runtimes/registry.py`.
- **Scoring weights:** tag_match 0.40, locality 0.25, cost 0.20,
  context_window 0.15. Locality preference: local Ollama > cloud-
  proxied > external API. Default fallback: `llama3.1:latest`.
  Think-mode model: `deepseek-r1:14b`.
- **Frontend:** ConnectionsPage > MainBrainPanel + SettingsModelsRuntimes.
- **Gaps:** `local_first_routing` and `cost_aware_routing` user
  settings are not consumed by the router (Phase 10b §2.4-2.5).

### C.4 CLI providers (adapters)

- **Status:** **MIXED.** 7 active adapters + 1 stub + 1 V2.
- **Source:** `app/services/runtimes/adapters/`:
  - `claude_code.py` (21 KB) WORKING — spawns `claude` CLI
  - `claude_session.py` (23 KB) WORKING — session-aware variant
  - `codex.py` (14 KB) WORKING
  - `gemini_cli.py` (16 KB) WORKING
  - `grok_cli.py` (10 KB) WORKING
  - `ollama_adapter.py` (5 KB) WORKING (deprecated; llama-server preferred)
  - `vllm_adapter.py` (6 KB) WORKING — talks OpenAI-compatible to llama-server
  - `mcp_bridge.py` (637 B) **STUB** — placeholder
  - `mcp_bridge_runtime_adapter.py` (21 KB) WORKING — V2 canonical
- **Gaps:** stub `mcp_bridge.py` should be deleted or merged into
  the V2 adapter to remove name collision (M2 in Ultraview report).

### C.5 MCP bridge (V1 + V2 coexisting)

- **Status:** **WORKING but DUPLICATE.** V2 canonical for EXE; V1
  legacy still active for plugin-admin UI.
- **V1:** `app/services/mcp_invoker.py`, `mcp_registry.py`,
  `mcp_sync.py`, `packages/daena-mcp/`. No persistent invocation
  log — fire-and-forget.
- **V2:** `app/services/runtimes/adapters/mcp_bridge_runtime_adapter.py`.
  Spawns stdio MCP session via Python SDK; captures stdout in
  `ExecutionReceipt`.
- **DB writes:** MCPServer (registration only, no V1 invocation
  trail; V2 captures ToolExecution rows in EXE).
- **Frontend:** ConnectionsPage > McpServersPanel (V1) +
  McpServersV2Panel (V2) coexist behind `USE_CONNECTION_REGISTRY_V2`
  flag (still false in prod).

### C.6 Skills CRUD + Refinery

- **Status:** **WORKING** (CRUD + 3-pass refinery; vault sync STUB).
- **Endpoints:** `POST /skills` (ADMIN), `GET /skills`, `GET
  /skills/{id}`, `POST /skills/seed`, `POST /skills/refinery`.
- **Audit:** `SKILL_INGESTION` when refinery promotes to Skill.
- **Frontend:** `/skills` (SkillsPage with All/Web/Local/Custom/System
  filters + per-skill permission dropdown).
- **Gaps:** RefinedSkill DB rows do not bidirectionally sync to
  Daena-Mind T0/T1/T2/T3/T4 markdown vault.

### C.7 Tasks (background queue)

- **Status:** **WORKING** (PR-S2.1 retrofit ships `task_complete`
  notification; queue restart-recovery shipped 2026-04-29).
- **Endpoints:** `POST/GET /execution/tasks`, `POST .../run`,
  `PATCH`, `DELETE`, `POST /tasks/batch-delete`.
- **DB writes:** Task, ToolExecution, BackgroundTask (Phase 10c
  persistence fix), Notification (PR-S2.1).
- **Frontend:** `/tasks`, `/workstreams`, `/pipeline`, `/projects`,
  `/files`.
- **Gaps:** create / run / batch-run / retry / cancel / batch-archive
  / batch-delete still lack audit emit (Phase 9B §4.1; PR-T1
  scheduled).

### C.8 Security scans — `POST /security/scans/start`

- **Status:** **WORKING** with U2 unsafe-gate flag (Phase 10).
- **Service:** `app/services/security/scan_workflow.py` 9-stage
  pipeline; SubAgentSpawner + Laevateinn + ConsensusGradient +
  ReportTierEngine + cost calc.
- **DB writes:** SecurityFinding, SecurityReport, Engagement,
  GoaAuditEvent, var/scan_traces/{job_id}.json,
  var/security_reports/{job_id}.json.
- **Frontend:** `/scan`, `/scan/:id/walkthrough`, `/security/scans`,
  `/engagements`, `/security-scope`.
- **Gaps:** scope-gate enforcement at REST boundary fixed Phase 10
  U2; engagement scope (U3) still relies on agent enforcement —
  potentially bypassable.

### C.9 Company Mode — `POST /company-mode/activate`

- **Status:** **WORKING** with U1 unsafe-flag fixed Phase 10.
- **Service:** `app/services/company_mode.py` + `missions.py` +
  `agent_ops.py`. Founder writes brief → SalesAgent prospects →
  MarketingAgent drafts → drafts land in approval queue (default
  `auto_send=False`).
- **DB writes:** Mission, Draft, GoaRequest + PendingApproval,
  GoaAuditEvent (`COMPANY_MODE_ACTIVATION`).
- **Frontend:** `/company-mode`.
- **Gaps:** Send providers (LinkedIn, email, SMS) STUBBED; no
  outbound POST. Phase 13 LINKEDIN-PROVIDER + EMAIL-PROVIDER
  tickets gated on OAuth + account-risk disclosure.

### C.10 Approvals + governance + audit

- **Status:** **WORKING** (full hash-chain ledger).
- **Service:** GovernanceEngine (`governance.py`), ApprovalService
  (`approval.py`), AuditService (`audit.py`).
- **Decision flow:** hard laws → risk → effective slider → tier →
  SILENT (T0) / LOG (T1) / NOTIFY (T2) / APPROVE (T3) /
  COUNCIL+APPROVE (T4).
- **DB writes:** GoaRequest, PendingApproval, GoaAuditEvent (entry_hash,
  prev_hash chain).
- **SSE:** `/governance/approvals/stream` for live updates.
- **Frontend:** `/governance/approvals`, `/governance/audit`.
- **Gaps:** Audit hash-chain validation is implemented in
  `audit.py:74-80` but no read-time verification endpoint exists
  for the operator. Operator can DELETE rows; chain breaks silently.

### C.11 Notifications (Phase 11 PR-S2 + PR-S2.1)

- **Status:** **WORKING** (just shipped: model + service + 2
  endpoints; bell hydrate; 3 of 5 backend triggers retrofitted).
- **Service:** `app/services/notification_service.py`.
- **Event types (7 total):** `task_complete` (notif_task_complete),
  `budget_alert` (notif_budget_alert), `heartbeat` (notif_heartbeat
  — no real trigger yet), `governance_rejection` (notif_gov_reject),
  `runtime_disconnect` (notif_runtime_disconnect — no real trigger
  yet), `privacy_blocked` (always-emit), `system_info` (always-emit).
- **Emit sites confirmed (PR-S2.1):** `cost_guard.py:339-341`
  (budget_alert with 60-min per-user dedup), `approval.py:192-193`
  (governance_rejection routed to requester), `execution_service.py:785-787`
  (task_complete on bg-queue completion).
- **DB writes:** Notification.
- **Frontend:** Header bell hydrates `GET /notifications` once on
  mount; `/settings/notifications` test button calls POST
  `/notifications/test`.
- **Gaps:** Heartbeat + runtime_disconnect emit paths SKIPPED in
  PR-S2.1 — need a fan-out service (provider/system event →
  affected tenants → notification subscribers). Documented as
  PR-NOTIF-FANOUT (~6h) in PR-S2.1 report §4.

### C.12 Audit events (action_type catalogue)

- **Status:** **WORKING** with 18+ canonical action_type values.
- **Catalogue (grep results):**
  - `LLM_CALL` — chat_orchestrator (every completion)
  - `privacy.memory_recall_skipped` — chat_orchestrator Stage 6 gate
  - `privacy.memory_write_blocked` — memory.py PR-S1 gate
  - `DEPLOY` — approval.py:33
  - `DELETE` — audit.py:38, governance.py:129
  - `SKILL_INGESTION` — governance.py:700 (refinery promote)
  - `SENSITIVE` — dream_engine.py:256
  - `MERGE`, `PROMOTE`, `CONTRADICT`, `SYNTHESIZE`, `DECAY` —
    dream_engine.py (NOT FIRING because Dream is unscheduled)
  - `RUNTIME_EXECUTION` — swarm/executor.py:466
  - `connector.installed`, `connector.imported`, `connector.connected`,
    `connector.configured`, `connection.probed`, `connection.enabled`,
    `connection.disabled` (per Frontend Action Design Rulebook
    lifecycle sections)
- **Hash chain:** `entry_hash = sha256(actor_id + action_type +
  result + prev_hash + timestamp)`. `audit.py:74-80` provides
  verification helper but no public endpoint.

### C.13 Heartbeat (daemon + cron)

- **Status:** **WORKING** (daemon active; CronRun ledger persists
  per-tick — Phase 10c Rule-17 fix).
- **Service:** `app/services/heartbeat/heartbeat_daemon.py` +
  `heartbeat_checks.py` + `cron_scheduler.py` + `work_queue.py`.
- **Check types:** GIT_STATUS (4s), TEST_SUITE (6s), GITHUB_ISSUES
  (6s), OLLAMA_HEALTH (5s), OLLAMA_MODEL_UPDATES (6s),
  AUTONOMOUS_WORK, DEPARTMENT_WORKFLOWS, RUNTIME_HEALTH (implicit).
- **Configuration:** stored in `users.settings.heartbeat_config`
  JSONB BUT — per Phase 10C-B — also held in daemon-process memory;
  changes via `/settings/heartbeat` revert on restart unless the
  daemon re-reads on each cycle.
- **Frontend:** Header HeartbeatIndicator pulse + `/settings/heartbeat`
  config tab.
- **Gaps:** PR-H1 (heartbeat config DB persistence) outstanding.

### C.14 Self-improvement / Dream / Learning (background)

- **Status:** **PARTIAL.** Self-Audit live (read-only). Dream
  defined-but-unscheduled. LearningService in-memory only. SelfFix
  / SelfRepair work but limited to Ollama / single primary runtime.
- **See B.8, B.12** for source files.
- **Gaps:** All three of (a) schedule Dream cycle, (b) persist
  LearningService outcomes to NBMF T0, (c) close the loop
  Learning → Refinery → Dream → SkillRefined-promotion are open.

---

## D. Data / Memory Layers

### D.1 NBMF — `memory_entries` table

- **Source-of-truth:** SQLite/Postgres `memory_entries` row, scoped
  by tenant_id + user_id + scope (USER / SESSION / TENANT).
- **Persistence:** YES (survives restart).
- **Retrieval:** `MemoryService.recall_for_chat()` Stage 6; rank =
  0.50 keyword + 0.20 tier_norm + 0.20 confidence + 0.10 recency.
- **Write:** `MemoryService.store()` post-stream; CAS dedup by
  content_hash.
- **Privacy:** PR-S1 enforced (`memory_generation` gate at write,
  `search_past_conversations` gate at recall). 2 of 47 settings
  enforced.
- **Status:** **LIVE.**
- **Gap:** Embeddings field exists, never populated. Semantic
  search degrades to keyword matching.

### D.2 Agent experiences (subset of `memory_entries`)

- **Content types:** AGENT_DECISION, SKILL_OUTCOME, PATTERN_LEARNED,
  APPROACH_FAILED. Auto-quarantine on insert (`memory.py:280-282`).
- **Source-of-truth:** same table, distinguished by content_type.
- **Status:** **STUB — no writer.** No caller invokes
  `store_experience()` despite the function being defined. The
  promised OODA-REFLECT → write-experience hook is not wired.
- **Gap:** Highest-leverage learning loop is broken because
  REFLECT writes general user-content memory (subject to PR-S1
  privacy gate) instead of agent-experience (tenant-scoped, not
  user-scoped per PR-S1 §6.1).

### D.3 RefinedSkill / Skill Refinery

- **Source-of-truth:** `refined_skills` table + `Skill` rows in
  `execution.py`.
- **Maturity tiers:** T0_RAW → T1_DRAFT → T2_REFINED → T3_PRODUCTION
  → T4_COMPOUND. Soft-delete via `archived_at`.
- **Status:** **PARTIAL.** Extraction + refinement + retrieval work.
- **Gap:** Bidirectional sync to Daena-Mind vault not implemented.

### D.4 RAG retrieval

- **Status:** **NOT IMPLEMENTED.** Per `MEMORY_RAG_OBSIDIAN_SYNC_REPORT.md`:
  `/api/v1/memory/status` reports `rag: not configured`.
- **Risk:** Highest single Rule-17 violation surface — UI implies
  retrieval works for Claude/Codex/Gemini context export, no
  service file exists.
- **Required before shipping:** test endpoint, `last_retrieval_test`
  field, honest "Not Configured" label until first real hit.

### D.5 CKG — Cross-domain Knowledge Graph

- **Source-of-truth:** `app/services/laevateinn/knowledge_graph.py`
  (local SQLite, self-contained) + `app/services/cognition/knowledge_graph.py`
  (referenced by security/cognition).
- **Status:** **LIVE for Laevateinn only.** Not coordinated with
  NBMF.
- **Risk:** **NOT TENANT-ISOLATED.** Any cross-tenant data could
  leak via shared KG if cloud multi-tenant resumes. Currently
  fine because local-first single-founder. Critical to fix before
  Cloud Run resume.

### D.6 Dream loop

- **Source-of-truth:** `dream_engine.py` operations in-memory only;
  no DreamReport / DreamAction tables exist.
- **Status:** **INACTIVE — defined-but-unscheduled.**
- **Gap:** No cron entry, no API endpoint, no startup hook.

### D.7 eDNA enterprise behavior

- **Status:** **DOC-ONLY.**
- **Partial substitute:** RoutingPolicy model. No auto-extraction
  from audit trail. No emergent-pattern surface.

### D.8 Auto-learning (LearningService)

- **Source-of-truth:** `learning_service.py` `_active: dict` +
  `_history: list` IN-MEMORY ONLY. Lost on restart.
- **Status:** **PARTIAL — Rule 17 violation.**
- **Gap:** No persistence to NBMF T0 or RefinedSkill.

### D.9 Audit ledger (`goa_audit_events`)

- **Source-of-truth:** SQLite append-only with hash chain.
- **Status:** **LIVE.**
- **Gap:** Hash-chain validation NOT exposed as endpoint.
  Operator-deletable rows break tamper-evidence claim.

### D.10 CronRun ledger (`cron_runs`)

- **Source-of-truth:** SQLite. Per-execution row.
- **Status:** **LIVE** (Phase 10c Rule 17 fix).
- **Gap:** No retry-on-failure, no operator monitor surface.

### D.11 BackgroundTask ledger (`background_tasks`)

- **Source-of-truth:** SQLite. Mirrors in-memory queue.
- **Status:** **LIVE** (Phase 10c Rule 17 fix). Restart marks
  running rows `failed_due_to_restart` so operator decides retry.
- **Gap:** No exponential backoff; no priority escalation.

### D.12 NBMF archive

- **Source-of-truth:** `memory_entries.archived_at` soft-delete +
  `archive.py` filesystem move to `.archive/{category}/{ts}/`.
- **Status:** **PARTIAL.** Soft-delete works.
- **Gap:** No bidirectional Daena-Mind vault sync. No
  scheduled cleanup.

### D.13 User settings JSONB (47 keys)

- **Source-of-truth:** `User.settings` JSONB column.
- **Backend consumers (7 of 47, post-Phase 11):**
  1. `memory_generation` (PR-S1)
  2. `search_past_conversations` (PR-S1)
  3. `notif_task_complete` (PR-S2 + PR-S2.1)
  4. `notif_budget_alert` (PR-S2 + PR-S2.1)
  5. `notif_heartbeat` (PR-S2 gate; emit pending PR-NOTIF-FANOUT)
  6. `notif_gov_reject` (PR-S2 + PR-S2.1)
  7. `notif_runtime_disconnect` (PR-S2 gate; emit pending PR-NOTIF-FANOUT)
- **Other 40 keys:** STUB / PARTIAL / DEAD per Phase 10b audit.

---

## E. Frontend Surfaces

### E.1 Cluster: Chat & Dashboard

- **/chat (ChatPage):** canonical streaming chat with session
  sidebar, message history, executor panel, peer signals feed.
  KEEP_WORKING. Add audit emit for session rename/archive.
- **/dashboard (DashboardPage):** sunflower hive — Daena center +
  10 department hexagons + governance pulse + quick links.
  KEEP_WORKING. Strategic glance.
- **/departments/:slug/chat (DepartmentChatPage):** chat scoped to
  department; reuses ChatPage layout. KEEP_WORKING. Verify
  `department_id` actually biases orchestrator routing (not just
  cosmetic).

### E.2 Cluster: Connections (V1 + V2 panels coexist)

- **/connections (ConnectionsPage):** tabbed hub.
  - **MainBrainPanel:** select primary runtime. KEEP_WORKING.
  - **ConnectionsV2Panel:** master truth-backed list. KEEP_WORKING
    (canonical V2).
  - **McpServersPanel (V1):** detected MCP servers. KEEP_WORKING
    but DUPLICATE of McpServersV2Panel.
  - **McpServersV2Panel:** truth-backed (6 booleans + per-dim
    failure_reason). KEEP_WORKING (canonical).
  - **PluginsCatalogBrowser (V1):** Codex-style catalog.
    KEEP_WORKING but DUPLICATE of PluginsV2Panel.
  - **PluginsV2Panel:** plugin + oauth_app + provider rows.
    KEEP_WORKING (canonical).
- **Recommendation:** flip `USE_CONNECTION_REGISTRY_V2=true` and
  hide V1 panels behind a Founder-gated "Show legacy" toggle.

### E.3 Cluster: Settings (13 tabs)

| Tab | Backend consumer? | Recommended action |
|---|---|---|
| General (display_name + dark_mode + autopilot) | display_name LIVE; dark_mode UI; autopilot DEAD | MERGE display_name → AccountPage |
| LLM (provider keys + routing toggles) | keys LIVE; `local_first_routing` + `cost_aware_routing` DEAD | KEEP keys; tooltip "wiring pending PR-S4" on routing toggles |
| Governance (mode + slider + policy hooks) | mode LIVE via request body; slider DEAD | KEEP; flag advanced behind disclosure |
| Models & Runtimes | LIVE | KEEP (complementary to MainBrainPanel) |
| Memory (NBMF tuning) | LIVE | KEEP |
| Voice | LIVE; Header has quick toggle | KEEP both, sync state |
| Billing (monthly_budget + threshold + over_budget_action) | PARTIAL — parallel source-of-truth (Subscription.monthly_budget_usd) | TOOLTIP "vocab unification + wire pending PR-S3" |
| Privacy (5 toggles, 2 enforced post-PR-S1) | 2 LIVE; 3 DEAD | LIVE 2 = "Enforced by backend" badge; 3 stay Coming Soon |
| Notifications (9 toggles, 5 enforced post-PR-S2) | 5 LIVE; 4 (sound/email/digest/desktop) DEAD | LIVE 5 = enforced; sound/email/digest = Coming Soon (no delivery channel); desktop = client-only master gate |
| Shortcuts | UI-only | KEEP |
| Heartbeat (interval/checks/cost guards) | DAEMON-MEMORY ONLY (resets on restart) | TOOLTIP "PR-H1 will move to DB" |
| Developer (webhooks + debug + API keys) | webhooks DEAD; debug UI; API keys → AccountPage | DELETE webhooks; MERGE API keys → AccountPage |
| About | LIVE | KEEP |

### E.4 Cluster: Governance & Audit

- **/governance/approvals (GovernanceApprovalsPage):** pending
  queue + approve/reject. KEEP_WORKING.
- **/governance/audit (GovernanceAuditPage):** hash-chain audit
  log + filter + export. KEEP_WORKING. Add chain-verify endpoint.

### E.5 Cluster: Security & Scan

- **/security (SecurityDashboardPage):** 5 sub-tabs (Overview /
  Tools / Scans / Shields / Missions). HANDS-OFF per CLAUDE.md
  v3.7.0 Security Supercharge.
- **/scan (ScanPage):** consumer-facing scan launcher with T1-T5
  selection. Phase 10 U2 fix made REST-boundary scope-gate active.
- **/scan/:id/walkthrough (ScanWalkthroughPage):** live SSE phase
  timeline + reasoning feed (T5 specifically). KEEP.
- **/engagements (EngagementConsolePage):** governed scan with
  approval-gated tier 3+. Phase 10 U3 closed scope-gate at REST.
- **/security-scope (SecurityScopePage):** authorized-target CRUD.
- **DUPLICATE PAIR:** ScanPage + EngagementConsolePage. See §F.

### E.6 Cluster: Execution (Tasks / Workstreams / Pipeline / Projects / Files)

- **/tasks:** background queue (PENDING/RUNNING/PAUSED/COMPLETED/FAILED/
  CANCELLED). PARTIAL — audit emit for create/run/batch missing.
- **/workstreams:** Council R3 lock — autonomous unit (goal/owner/
  state/blocker/next-step + governance timeline). KEEP_WORKING.
  Add pause/resume tests.
- **/pipeline:** 8-stage Kanban (DISCOVERY → … → CLOSED). KEEP.
- **/projects:** workspace CRUD. KEEP. Add edit/delete tests.
- **/files:** upload/download/delete. KEEP.

### E.7 Cluster: Intelligence (Departments / Minds / Skills / Policies / Company / Analytics)

- **/departments:** grid of 10 with capability badges. KEEP.
- **/minds + /minds/:slug:** soul gallery + detail + refine
  (founder-gated). KEEP.
- **/skills:** Claude-Desktop-style sidebar + permission
  dropdown. KEEP.
- **/policies:** Plain-English + per-department tabs. PARTIAL —
  hard-delete should soft-archive (PR-P1).
- **/company-mode:** founder brief + activation history. KEEP_WORKING
  with U1 fix (auto_send + no-approval combo blocked).
- **/analytics:** usage / cost / governance breakdown. KEEP.

### E.8 Cluster: Account

- **/account (AccountPage):** profile + API keys. KEEP. Adopt
  display_name as canonical (deduplicate with SettingsGeneral).

---

## F. Current Duplication Map

> 10 critical pairs identified by the frontend-mapping agent.
> Format: surface A | surface B | what they share | risk |
> recommended action.

### F.1 V1 vs V2 connection panels (3 pairs)

| Pair | A (V1) | B (V2) | Risk | Action |
|---|---|---|---|---|
| MCP servers | `McpServersPanel.tsx` | `McpServersV2Panel.tsx` | Mutations via V1 may not reflect V2 truth; users may see stale data | HIDE V1 when `USE_CONNECTION_REGISTRY_V2=true`; deprecate V1 endpoints |
| Plugins / OAuth | `PluginsCatalogBrowser.tsx` | `PluginsV2Panel.tsx` | Install dialog appears in both; no clear canonical | HIDE V1 when V2 enabled |
| Runtime registry | (legacy `useRuntimeRegistry` hook) | `useConnectionsV2('cli_runtime')` | Hook has zero non-self consumers (per Ultraview H3) | DELETE legacy hook; consolidate on V2 |

### F.2 Profile editing (display_name)

| A | B | Risk | Action |
|---|---|---|---|
| `SettingsGeneral.tsx` (display_name field) | `account/AccountDetails.tsx` (display_name field) | Two write surfaces for same field; user confusion | MERGE → AccountPage canonical; remove from SettingsGeneral or read-only with link |

### F.3 API keys

| A | B | Risk | Action |
|---|---|---|---|
| `SettingsDeveloper.tsx` (references API keys) | `account/AccountApiKeys.tsx` (full CRUD) | Two locations for same concept; SettingsDeveloper has no create UI | MERGE → AccountPage; REMOVE from SettingsDeveloper |

### F.4 Scan launcher

| A | B | Risk | Action |
|---|---|---|---|
| `ScanPage.tsx` (T1-T5 selection) | `EngagementConsolePage.tsx` (T1-T4 + governance gate) | Two "start a scan" surfaces; users confused which is canonical | MERGE → one launcher; route to /scan if T1-T2; route to /engagements with governance pre-set if T3+ |

### F.5 Heartbeat config vs status

| A | B | Type | Action |
|---|---|---|---|
| `SettingsHeartbeat.tsx` (config) | `Header.tsx` HeartbeatIndicator (status) | Separate concerns (config vs status) | KEEP BOTH; but PR-H1: persist config to `users.settings.heartbeat_config` so it survives restart |

### F.6 Voice config vs toggle

| A | B | Type | Action |
|---|---|---|---|
| `SettingsVoice.tsx` (provider, permissions) | `Header.tsx` VoiceToggle (on/off) | Separate concerns | KEEP BOTH; sync state |

### F.7 MainBrain vs ChatInput model dropdown

| A | B | Type | Action |
|---|---|---|---|
| ConnectionsPage MainBrainPanel | ChatInput "Model:" per-message override | Override pattern (intentional) | KEEP BOTH; surface "using X instead of primary Y" label when overridden |

### F.8 Dashboard hive vs Departments grid

| A | B | Type | Action |
|---|---|---|---|
| `DashboardPage.tsx` sunflower hive | `DepartmentsPage.tsx` capability grid | Strategic vs tactical (intentional) | KEEP BOTH; clarify navigation: hive → click → grid |

### F.9 Tasks vs Workstreams

| A | B | Type | Action |
|---|---|---|---|
| `TasksPage.tsx` (low-level operations: 6-state machine) | `WorkstreamsPage.tsx` (autonomous units: 5-state machine, Council R3 lock) | Distinct concepts (intentional) | KEEP BOTH; add taxonomy tooltip ("Tasks = jobs you queued; Workstreams = autonomous units Daena ran for you") |

### F.10 Background queues (heartbeat vs autopilot)

| A | B | Type | Action |
|---|---|---|---|
| `services/heartbeat/work_queue.py` | `services/autopilot/background_queue.py` | Two task-queue mental models per Duplicates report | DOCUMENT both; consider unification when PR-NOTIF-FANOUT lands |

---

## G. OpenClaw Comparison — what to copy and what NOT to copy

### G.1 What OpenClaw / Paperclip do simpler

- **One install command:** `npx paperclipai onboard --yes` → working
  agent in seconds. No 12-step setup.
- **One running agent metaphor:** "1 employee = 1 runtime." Easy
  mental model. No org chart to learn.
- **One queue, one heartbeat, one approval gate.** No tier matrix.
- **Open-source distribution flywheel:** AGPL/MIT means GitHub
  acquisition compounds. 53k stars in 6 weeks.
- **Linear, predictable execution:** task → runtime → result. No
  Council, no QE, no tier-router downgrade. Easy to debug because
  there is one path.

### G.2 What Daena MUST copy

1. **One-command install path.** Today Daena needs `start-daena.bat`
   + 3 terminals + WSL2 setup. Match Paperclip's bar: one command,
   one URL, working chat in 60s. Local-first makes this achievable.
2. **One canonical action lifecycle visible to the operator.** Today
   the operator sees Tasks vs Workstreams vs Pipeline vs Projects vs
   Files vs Engagements with overlapping semantics. Pick one
   primitive (the **Workstream**, per Council R3 lock) as the spine.
3. **One launcher for any "do this" intent.** Today the operator
   has Chat (CMD/EXE), CompanyMode, Scan, Engagement, Tasks-Create,
   each with different shapes. A single `+ New action` button that
   classifies intent and routes is OpenClaw-simple.
4. **One settings surface that tells the truth.** Today Daena's
   settings advertise 47 keys and enforces 7. Either wire the rest
   or DELETE the dead toggles. Coming-Soon labels are a transition
   step; deletion is the destination.
5. **Distribution playbook.** Daena OSS (AGPL-3.0 fighter brand
   per `CLAUDE.md`) is the founder's existing answer. Phase
   in `npx daena-oss init` once the Execution Spine is one path.

### G.3 What Daena must NOT copy from OpenClaw

1. **Weak trust boundaries.** OpenClaw's "approve everything"
   model breaks at scale. Daena's 5-tier governance + Hard Laws +
   Asset Shield are the moat. Keep.
2. **Unsafe skill execution.** OpenClaw runs skills with whatever
   permissions the runtime has. Daena's Plain-English Policy
   Compiler + per-skill permissions + initiator-aware Asset Shield
   prevent silent escalation. Keep.
3. **Single-agent scheduling.** OpenClaw's "1 agent = 1 runtime"
   ceiling is what makes it commodity. Daena's department brains +
   Council/QE synthesis is the moat — preserve it under the simple
   surface. The user does not need to know there are 60 capability
   slots; the engineering does.
4. **No memory governance.** OpenClaw stores everything. Daena's
   NBMF L2Q quarantine, trust gating, decay, and Dream
   consolidation differentiate signal from noise over time. Keep.
5. **No expert-lens injection.** OpenClaw uses a single system
   prompt. Daena's DCP injection (currently 25 of 55 shipped)
   is what makes hard problems land differently. Ship the
   remaining 30 DCPs; do NOT remove the layer.

### G.4 The thesis: "OpenClaw-simple but enterprise-governed"

The user-visible surface should look like OpenClaw — one launcher,
one queue, one approval gate, one bell, one settings page. The
backend should remain the multi-mind, multi-tier, governed,
self-correcting system Daena already is. Simplification is a
**presentation layer redesign**, not an intelligence-layer
amputation.

---

## H. Proposed Daena Execution Spine

### H.1 Canonical lifecycle (one path the operator sees)

```
Intent
  ↓
Brain / Council selection (auto: Three-Tier Escalation Router; manual override allowed)
  ↓
Capability registry lookup (Skill + Runtime + MCP server matching the intent)
  ↓
Governance + OODA pre-check (Shield always on; OODA Observe + Orient + DECIDE)
  ↓
Runtime / Tool execution (CMD = plan only; EXE = act with TLM + DaenaBot)
  ↓
Progress reporting (SSE: deltas, thinking, tool activity, governance notices)
  ↓
Artifact (Workstream + Task + Result + optional file/PR/draft)
  ↓
Audit (hash-chained GoaAuditEvent — one per state-changing step)
  ↓
Notification (Notification row — gated by per-event notif_* flag)
  ↓
Memory + Dream learning (NBMF write + experience to L2Q + Dream cycle later)
```

### H.2 Why this spine

- It is **what already exists** — the chat orchestrator's 10-stage
  pipeline + governance + memory + audit are 90% of the spine.
- It **preserves every intelligence layer**: Brain selection
  invokes the Three-Tier Router; Council/QE fires when needed; OODA
  runs in EXE mode; Soul Engine injects per-department; Asset Shield
  always on; NBMF + Dream complete the loop.
- It **collapses the user surface**: every action — chat send,
  scan start, company-mode activation, file process, draft email —
  becomes a Workstream artifact with the same lifecycle. The
  operator learns ONE shape.

### H.3 Capability Registry as the missing keystone

The component that ties this spine together cleanly is a unified
**Capability Registry** that today is scattered across 4 sources:

1. `connection_v2` table (runtimes, MCP, plugins, providers — V2
   canonical)
2. `Skill` table + Refinery (skills as capabilities)
3. `tool_lifecycle/tool_discovery.py` (TOOL_CATALOG hardcoded)
4. `runtimes/registry.py` (in-memory adapter table)

**Proposal:** the Execution Spine's "Capability lookup" stage
queries one logical surface (`registry.find(intent, role,
governance_mode)`) that fans out to the four physical sources and
returns a ranked list. The PRD specifies this contract.

---

## I. Recommended Simplification

### I.1 Keep (do not touch)

- The 10-stage chat pipeline. It is the spine.
- The governance gates (Shield + Security + Asset Shield + Hard Laws).
- The 9 Hard Laws + hash-chained audit ledger.
- NBMF 5-tier + L2Q + trust scoring.
- Council + Quintessence + DCP layer.
- Soul Engine + 10 named department personas.
- The Workstream primitive (Council R3 lock).
- Plain-English Policy Compiler.
- The Capability Registry V2 model (`connection_v2` + 6 booleans).
- Local-first deployment (and Cloud Run remaining as paused option).

### I.2 Merge / unify

- **Profile editing → AccountPage** (de-duplicate display_name,
  API keys).
- **Scan launcher → one** (route by tier + governance mode).
- **V1 connection panels → hide behind V2 flag** (don't delete,
  but hide).
- **`mcp_bridge.py` stub → merge into `mcp_bridge_runtime_adapter.py`**
  (kill name collision).
- **Capability lookup → one logical surface** over 4 sources
  (per H.3).
- **Two background queues (`heartbeat/work_queue.py` +
  `autopilot/background_queue.py`) → one** (PR-NOTIF-FANOUT
  candidate).

### I.3 Hide behind "Advanced"

- DCP-level controls (operator picks "QE", not 5 individual
  expert lenses).
- Per-tier audit views (default = "all decisions"; operator drills
  in if needed).
- Manual Council member selection (auto-pick by intent).
- Manual NBMF tier promotion (Dream handles).
- Webhooks tab (DEAD; remove or hide entirely).
- evilbob mode (founder-only; never surface).
- T0/T1/T2/T3/T4 governance tier internals (per
  `GOVERNANCE_SIMPLIFICATION_REPORT.md` — keep Unleashed/Balanced/
  Governed surface).

### I.4 Coming Soon (label honestly)

- `notif_sound`, `notif_email`, `notif_daily_digest` (no delivery
  channel).
- `improve_from_usage`, `location_metadata`, `storage_local` cloud
  variant (no consumer / no spec).
- `local_first_routing`, `cost_aware_routing` (router doesn't read
  yet — PR-S4).
- Email send providers in Company Mode (PR LINKEDIN-PROVIDER /
  EMAIL-PROVIDER).

### I.5 Delete or back-end-driven

- Any UI that round-trips a setting the backend never reads
  WITHOUT a Coming-Soon badge — this is the Rule 17 violation
  surface.
- Static "demo data" arrays in browse modals (per Duplicates
  report) — make every list DB-sourced.
- Old `RuntimeSwapper.DEFAULT_RUNTIMES` style stubs (already
  deleted per ADR-001 example).

### I.6 What must become backend-driven (not localStorage)

- Heartbeat config (`SettingsHeartbeat` daemon-memory only; PR-H1
  moves to `users.settings.heartbeat_config` with daemon re-read).
- Routing toggles (`local_first_routing`, `cost_aware_routing` —
  PR-S4 plumbs through ModelRouter).
- Budget vocab (`monthly_budget` / `over_budget_action` / threshold
  — PR-S3 unifies enum + wires BudgetManager to read user.settings).

---

## J. Risk Register

### J.1 Hallucination risk

- **Where it bites:** chat orchestrator Stage 8 LLM streams without
  RAG/citation grounding; LearningService extracts patterns from
  unverified outcomes; Skill Refinery's Critic pass relies on
  Ollama (Phase 2 constraint) — local model may miss subtle errors.
- **Mitigation today:** L2Q quarantine + trust scoring + 5-Whys in
  REFLECT + DCP "evaluation_criteria" per expert.
- **Gap:** RAG NOT WIRED. Critical for any company-context claim.

### J.2 Unsafe action risk

- **Where it bites:** EXE mode + DaenaBot + MCP V2 invocation +
  Company Mode draft-send.
- **Mitigation today:** SecurityGate + Hard Laws + initiator-aware
  Asset Shield + per-skill permissions + approval gate at Tier 3+ +
  CMD-mode default + Company-Mode auto_send=False default + U1
  contradiction guard (Phase 10).
- **Gap:** Audit hash chain not validated on read; operator
  deletion silently breaks Hard Law #9.

### J.3 Fake UI risk

- **Where it bites:** SettingsPage (40 of 47 toggles dead),
  RAG status badge, two scan launchers, V1 connection panels
  showing stale truth, heartbeat config that resets on restart.
- **Mitigation today:** Phase 10C-D added Coming-Soon labels for
  privacy + notification; Phase 11 enforced 5 of those toggles.
- **Gap:** 30+ Rule-17 violations remain.

### J.4 Duplicate-truth risk

- **Where it bites:** display_name (SettingsGeneral + AccountDetails),
  API keys (SettingsDeveloper + AccountApiKeys), V1+V2 connections,
  ScanPage + EngagementConsolePage, monthly_budget (user.settings vs
  Subscription.monthly_budget_usd vocab mismatch).
- **Mitigation today:** Phase 10c documented duplicates.
- **Gap:** No automated duplicate-source-of-truth detector in CI.

### J.5 Privacy risk

- **Where it bites:** RAG export to external runtimes (Claude/Codex/
  Gemini) could leak founder T3/T4 NBMF; Laevateinn KG not tenant-
  isolated; CKG silently shared across tenants if cloud resumes.
- **Mitigation today:** PR-S1 enforced 2 toggles; Asset Shield
  egress filter on Settings → Privacy → Memory toggles.
- **Gap:** RAG retrieval test endpoint missing; CKG tenant-scoping
  required before Cloud Run resume.

### J.6 Cloud / local drift risk

- **Where it bites:** Local-first features (vault override using dev
  KEK; heartbeat daemon in-process; CronRun ledger SQLite) may
  silently break under Cloud Run; Cloud Run paused so divergence
  can grow.
- **Mitigation today:** `CLOUD_DEPLOYMENT_PAUSED_DECISION.md`
  explicitly defers cloud features.
- **Gap:** No CI guard preventing local-only patterns from being
  added (e.g. Path.home() detector — see M3 in CONNECTIONS_MCP).

### J.7 Cost / runtime risk

- **Where it bites:** preflight_check fires before every LLM call;
  Council/QE multiplies cost ~3-5×; T5 EVILBOB scan = $50 + $0.05/
  file; LearningService daily 100K-token Ollama budget.
- **Mitigation today:** Cost preflight Stage 4 + per-user budget
  + Three-Tier Escalation Router downgrades QE on simple queries
  + dedup window on budget_alert (PR-S2.1).
- **Gap:** `monthly_budget` user setting not wired to BudgetManager
  (vocab mismatch — PR-S3); `cost_aware_routing` not wired (PR-S4).

### J.8 Security-tool misuse risk

- **Where it bites:** evilbob mode offensive capabilities (nmap,
  nuclei, Playwright, proxy rotation, Tor); ScanPage scope-bypass
  (Phase 10 U2 fix); EngagementConsolePage scope reliance on agent
  enforcement (U3); third-party `testssl.sh` vendored under
  `backend/`; `tool_augmented.py` web_search stubs.
- **Mitigation today:** evilbob requires founder + LOCAL + KEY
  (HMAC compare); REST-boundary scope-gate at scan workflow entry
  (Phase 10 fix).
- **Gap:** EVILBOB_KEY in plaintext env var is a single point of
  failure; cloud env-var spoofing detection limited.

---

## Appendix — Multi-Model Review (Codex / Gemini / Perplexity)

Multi-model review was kicked off in parallel during the writing of
this Atlas. Codex CLI 0.125.0 and Gemini CLI 0.35.3 are both
verified present. Each was given the System Graph + the Phase 11
reports and asked for a focused 600-word reply.

### Gemini (UX simplification angle) — full reply truncated by tail; key insight captured

> **The Brutal Observation:** *Daena's frontend currently presents
> a "Hallucination of Control." The Phase 10B audit reveals that
> 40 out of 47 settings keys are "DEAD" or "STUB" — they persist
> to the DB, but the backend consumers don't exist or ignore them.
> An operator toggles "Memory Generation: OFF" or "Privacy Mode:
> ON," and the system silently continues its default behavior.
> This isn't just a UX failure; it's a breach of the "Governed AI"
> brand promise, making the interface a placebo rather than a
> control surface.*

This framing — **Hallucination of Control** — is adopted as the
canonical name for the Atlas's largest single fake-UI risk class
(see §J.3). Phase 11 PR-S1 + PR-S2 + PR-S2.1 closed 5 of the 40
violations. The Backlog P2-07 enumerates the remaining 35 with a
"wire / label / delete" triage rule.

### Codex (architecture / regression angle) — empty output

Codex CLI exited cleanly (exit 0) but produced no captured output
to the `--output-last-message` file. Suspected cause: WSL Linux
Codex CLI auth state may be in the same expired-token state as
Claude CLI per `CLAUDE.md` "CLAUDE CLI AUTH FALLBACK" section.
Operator action: `codex login` to refresh the Linux token, OR
re-invoke Codex from the Windows binary with the founder's
preferred shell.

When Codex review is recovered, append findings here. The Backlog
PR sequencing (§"Recommended sequencing") is structured to be
robust to Codex absence — Claude leads architecture, Codex
contributes single-file algorithmic work where the
Cross-AI delegation table assigns it.

### Perplexity (public-references angle) — not invoked

Perplexity API is paid; per the brief's "Do not print or commit
secrets" rule, no API key was loaded. The Atlas + PRD + Backlog
synthesis is grounded in:
- Public docs already in the founder's
  `docs/Ultraview/` corpus (90+ files including the
  `DAENA_BUSINESS_MODEL_REALITY_CHECK.md` Deloitte / Zapier /
  Palantir references).
- The locked positioning in `CLAUDE.md`.
- Karpathy's `llm-council` pattern (already cited in `CLAUDE.md`
  "MIXTURE-OF-AGENTS + KARPATHY THREE-STAGE COUNCIL" section).
- The Together-AI MoA paper (arXiv 2406.04692, cited in
  `CLAUDE.md`).
- The "Single-Agent LLMs Outperform Multi-Agent Systems on
  Multi-Hop Reasoning Under Equal Thinking Token Budgets"
  research (arXiv 2604.02460, also cited).

These references already inform the **Three-Tier Escalation Router
must NOT fire Council on every turn** principle and the
**chairman synthesis** Council/QE design. No external public-
research call was needed to ground the Atlas.

---

## Appendix B - Blind-Spot Reconciliation (added 2026-05-02 by PR-DOC-DRIFT-FIX)

Following the Backend Blind-Spot Inventory sweep on 2026-05-01
(`DAENA_BACKEND_BLINDSPOT_INVENTORY.md` and
`DAENA_BACKEND_MODULE_GRAPH.mmd`), the following corrections apply
to the Atlas without rewriting the body. Each correction names the
section it amends.

### B.1 Atlas under-counted backend surface area

The Atlas correctly identified the brain (OODA, Council, QE, Soul,
Dream, NBMF, Asset Shield, governance) but under-counted the
periphery. The Blind-Spot Inventory enumerates the gap. Headline
counts:

| Metric | Atlas implied | Filesystem ground truth |
|---|---|---|
| Total backend Python files | not given | ~753 |
| Service `.py` files | "30+" in section C | ~318 (~125k LOC) |
| API routers | "12 endpoint categories" | 45 routers, 396 HTTP routes + 2 WebSocket = 398 endpoints |
| SQLAlchemy models | not enumerated | 54 models, 7 migrations (`001_*` through `008_*`) |
| Background jobs | OODA + cron + queue + Dream + heartbeat (named) | 8 (5 STARTED_AND_USED, 1 VISIBLE_IN_UI_BUT_NEVER_STARTED, 1 ORPHAN, 1 fire-and-forget) |
| Security service files | "60+ Laevateinn modules" | 36 in `security/` + 28-31 in `laevateinn/` + 7 founder-gated offensive (red_team_ops, exploitation_queue, zero_day_engine, osint_engine, opsec, credential_chain, mission_intelligence) |
| Env flags | not enumerated | 42 (4 critical, 1 dead) |

Subtrees not named in the Atlas body but live on disk (full list in
`DAENA_BACKEND_BLINDSPOT_INVENTORY.md` §2):

- `backend/app/services/benchmarks/` (7 modules, ~5,000 LOC) and
  the matching `/api/v1/benchmark/*` router (15 routes). Explains
  the 11 root-level `run_*.py` benchmark scripts and 14 result
  artifacts that previously looked like clutter.
- `backend/app/services/security/cognitive_scan_engine.py`
  (1,700 LOC, 24 importers - the actual nucleus of the scan workflow
  that the Atlas mentioned only as "scan_workflow").
- `backend/app/services/swarm/{executor,planner}.py` (multi-agent
  orchestration sibling to DaenaBot; not in the Atlas spine
  diagram).
- 5 specialised DaenaBot agents beyond the original 4 named:
  `vuln_scanner_agent` (12 importers), `vision_browser_agent`,
  `target_interaction_agent`, `plugin_admin_agent`,
  `web_crawler_agent`.
- The full integrations cluster: `calendar_client`, `gmail_client`,
  `notion_client`, `oauth_credentials_store`, `integration_router`.
- The 4 department service splits:
  `department_{budget,message,policy,state}_service.py`.
- 20+ analyzer modules under `cognition/` (Atlas said "20+
  frameworks" without enumeration; full names in Inventory §2.1).

### B.2 Dream Engine: scheduled, not unscheduled

**Atlas section B.10** and **`DAENA_ARCHITECTURE_GAP_BACKLOG.md`
P0-04** previously claimed Dream Engine is UNSCHEDULED. This is
incorrect.

Ground truth (verified 2026-05-01 by Phase D agent and direct read
of `backend/app/main.py` lifespan):

- `dream_engine` IS scheduled by APScheduler at a 15-minute interval
  via `_run_deferred_initialization` in `main.py.lifespan`.
- The schedule binding is real and active. Consolidation cycles run
  unattended whenever the FastAPI process is up.
- `GET /api/v1/memory/dream/status` returns
  `{last_run, total_cycles, is_running}` and works.

The actual gap is operator visibility: no frontend page renders the
last-run-time, total cycles, or per-cycle merge/promote/decay
summary. This is a P2 UI-surface gap, not a P0 safety blocker.
Backlog entry P0-04 has been reclassified accordingly (see
`DAENA_ARCHITECTURE_GAP_BACKLOG.md` 2026-05-02 reconciliation
header).

### B.3 HeartbeatDaemon: implemented but not auto-started (the real Rule 17 violation)

**Atlas section C.6** correctly named `HeartbeatDaemon` as a
background scheduler. What the Atlas did not flag is that the
daemon is implemented (~650 LOC) and the API routes
`POST /heartbeat/{start,pause,stop}` are mounted, but
`main.py.lifespan` never starts the daemon. The frontend
`SettingsHeartbeat.tsx` exposes Pause / Resume / Stop controls
that are decorative until an operator manually invokes the start
endpoint.

This violates Rule 17 (Honesty + Persistence + Visibility, locked
2026-04-29 via ADR-001): UI controls advertise daemon control but
no daemon is running.

Tracked as new Backlog entry P0-09 with two acceptable fix shapes
(start it, or remove the controls). Effort 30 minutes. The
Blind-Spot Inventory previously misattributed this to the Dream
Engine; that misattribution is corrected by B.2 + B.3.

### B.4 Vault path correction

**`DAENA_BACKEND_BLINDSPOT_INVENTORY.md` §3** flagged a documentation
drift: the `vault.py` referenced as a protected file does not exist
on disk. Ground truth (verified by direct glob):

| Claim | Ground truth |
|---|---|
| `backend/app/services/vault.py` (protected) | Does not exist. |
| `backend/app/services/vault_v2.py` (mentioned by Phase A agent) | Does not exist. |
| Real vault implementation | `backend/app/services/security/asset_shield/vault_adapter.py` (AES-GCM envelope vault adapter under Asset Shield). |
| Real vault migration helper | `backend/app/services/vault_migration.py`. |
| Real OAuth credential store | `backend/app/services/integrations/oauth_credentials_store.py`. |

CLAUDE.md (project) Rule 18 added 2026-05-02 by PR-DOC-DRIFT-FIX
codifies these three as the protected paths. The Phase A agent's
"vault.py + vault_v2.py both present" duplicate flag in the
Blind-Spot Inventory was incorrect and has been corrected in the
Inventory itself.

### B.5 PRs that landed since the Atlas was written

The Atlas (2026-05-01) recommended a sequence of follow-on PRs.
Status as of 2026-05-02:

| PR | Status | Commit |
|---|---|---|
| PR-NOTIF-MIG-008 (notifications table migration) | LANDED | `fe57ff7` |
| PR-AUDIT-VERIFY PR #1 (GET `/audit/verify?deep=true` + recall descriptor) | LANDED | `2492b82` |
| PR-AUDIT-VERIFY PR #2 (POST `/audit/verify` rich diagnostic + memory retrieval-test) | LANDED | `07aaede` |
| PR-DOC-DRIFT-FIX (this PR) | LANDING | (this commit) |
| PR-LEARN-01 + PR-DREAM-01 (LearningService persistence + DreamReport persistence) | OPEN | - |
| PR-HB-DAEMON-WIRE (start the heartbeat daemon or remove the controls) | OPEN | - |
| PR-AUDIT-VERIFY-CRON (nightly auto-verify) | OPEN (carved out of P0-01 close) | - |
| PR-NOTIF-FANOUT (per-tenant heartbeat + runtime_disconnect notifications) | OPEN (P1-03) | - |

### B.6 What this appendix does NOT change

- The Atlas body (sections A through J) is preserved unchanged. The
  reconciliation here corrects facts but does not rewrite the
  conceptual model.
- The Multi-Model Review appendix (Codex / Gemini / Perplexity)
  above is preserved unchanged.
- The "Hallucination of Control" framing remains canonical for the
  fake-UI risk class. PR-AUDIT-VERIFY PR #2 closed the Obsidian
  face of it (gating "available" badge to a real glob probe pass);
  the remaining surfaces are still tracked in Backlog P2-07.

End of Atlas.
