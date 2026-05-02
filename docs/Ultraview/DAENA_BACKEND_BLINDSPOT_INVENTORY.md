# DAENA Backend Blind-Spot Inventory

**Date:** 2026-05-01
**Branch:** rebuild-connections-mcp-runtime @ f71892c
**Method:** Read-only static sweep, 6 parallel Explore agents (Phases A–H), spot-verified by main thread on 8 high-impact claims
**Source-of-truth:** Filesystem, NOT documentation. Atlas docs treated as "claims under audit"
**Scope of write:** This doc + `DAENA_BACKEND_MODULE_GRAPH.mmd` only. Zero code changes.

---

## How to read this doc

The four Atlas/PRD/Backlog/Graph docs (collectively "Atlas") are **largely correct** about the intelligence stack but **systematically under-count** the breadth of the backend. This inventory does NOT contradict the Atlas; it **completes** it. Where the Atlas says "Daena ships X", the filesystem usually shows X plus 2–3 unmentioned siblings. The blind-spots are mostly *quantitative* (more modules than documented), with one *qualitative* P0 (Notification table has no migration) and a small set of orphan/duplicate cleanups.

Hard rule kept: **no code modified, no scans run, no offensive tools triggered, no secrets printed.** All findings are static-analysis-only.

---

## 1. Files / modules Atlas already covered

The Atlas explicitly named or represented (via cluster reference) these subtrees and was correct:

| Subtree | Atlas section | Status |
|---|---|---|
| `backend/app/services/chat_orchestrator.py` | C.1 / Execution | Covered |
| `backend/app/services/execution_service.py` | C.2 | Covered |
| `backend/app/services/governance.py` + security_gate | B.6 / Governance | Covered |
| `backend/app/services/notification_service.py` (Phase 11 PR-S2) | C.13 | Covered |
| `backend/app/services/cost_guard.py` | C.5 / Cost | Covered |
| `backend/app/services/audit.py` (hash-chain) | D.10 / Audit | Covered |
| `backend/app/services/dream_engine.py` | B.10 / Memory | Covered (flagged as UNSCHEDULED — incorrect, see §7) |
| `backend/app/services/learning_service.py` | B.11 | Covered (flagged as in-memory — confirmed) |
| `backend/app/services/heartbeat/heartbeat_daemon.py` | C.6 | Covered (flagged as DAEMON — but **never started in lifespan**, see §7) |
| `backend/app/services/heartbeat/cron_scheduler.py` | C.6 | Covered (DB-backed real-exec confirmed) |
| `backend/app/services/autopilot/background_queue.py` | C.7 | Covered (DB-backed restart-recovery confirmed) |
| `backend/app/services/runtimes/registry.py` + adapters | C.8 | Covered |
| `backend/app/services/mcp_registry.py` + `mcp_invoker.py` | C.9 | Covered |
| `backend/app/services/connection_v2/*` | C.10 | Covered |
| `backend/app/services/security/security_gate.py` + `behavior_guard.py` | B.5 | Covered |
| `backend/app/services/security/asset_shield/*` | B.5 / Asset Shield | Covered (vault_adapter, egress_filter, consent_token, operator_initiation — all four present) |
| `backend/app/services/security/evilbob_mode.py` | H / evilbob | Covered (3-gate fail-closed verified) |
| `backend/app/services/cognition/ooda_engine.py` | B.3 / OODA-R | Covered |
| `backend/app/services/council_engine.py` + `quintessence_engine.py` | B.4 | Covered |
| `backend/app/services/skill_refinery/*` | B.12 | Covered (5 sub-services) |
| `backend/app/services/tool_lifecycle/*` (TLM) | B.12 / Tools | Covered |
| `backend/app/services/soul_engine.py` + `soul_maker/*` | B.13 / Souls | Covered |
| `backend/app/api/v1/{notifications,connections,chat,agents,governance,memory,execution,skills,connections_v2,runtimes,settings,billing,heartbeat,prompts,dynamic-models,health,auth}.py` | C.14 / API | Covered |

Atlas got the *core spine* right.

---

## 2. Files / modules MISSING from Atlas

These exist on disk and are wired into the backend but the four Atlas docs do not name them. Counts come from the parallel Phase A/B/C agents and were reasonableness-checked by the orchestrator.

### 2.1 Backend subtrees / clusters not named in Atlas

| Subtree | LOC est. | What it is | Why it matters |
|---|---|---|---|
| `backend/app/services/security/laevateinn/` (~28–31 reasoning modules) | ~2,300 | Failure-memory, debate, deep-think, cognitive-forcing, counterfactual, calibration, etc. | T5 EVILBOB tier extension; Atlas mentioned "Laevateinn" but did not enumerate sub-modules |
| `backend/app/services/security/red_team_ops.py` | 1,046 | LiveTargetMonitor + SocialEngineeringCrafter + ExfiltrationProver + ImplantSimulator + RedTeamReportGenerator | BACKGROUND PATH ONLY (verified). Powerful authorized red-team capability; not in Atlas spine diagram. |
| `backend/app/services/security/zero_day_engine.py` | — | SupplyChainAttackPlanner | Not in Atlas |
| `backend/app/services/security/exploitation_queue.py` | 540 | OWASP-class queues (L1/L2/L3 levels), PoC artifact tracking | Not in Atlas |
| `backend/app/services/security/cognitive_scan_engine.py` | 1,700+ | Most-imported security service (24 importers). 9-phase scan workflow nucleus | Atlas mentioned scan_workflow but not this engine |
| `backend/app/services/security/osint_engine.py` (Apollo) | — | OSINT/intel collection | Not in Atlas |
| `backend/app/services/security/credential_chain.py` | — | Credential parsing / lateral-movement-aware | Not in Atlas |
| `backend/app/services/security/opsec.py` | — | Request fingerprinting, profile rotation, TLS mimicry, evidence encryption | Not in Atlas (used by EVILBOB tier scans) |
| `backend/app/services/security/network_intelligence.py` | — | ProtocolKnowledgeBase | Not in Atlas |
| `backend/app/services/security/mission_intelligence.py` | — | Mission-level intel | Not in Atlas |
| `backend/app/services/cognition/` 20+ analyzer modules | — | first_principles, five_whys, inversion, pre_mortem, consequence_chain, constraint_analyzer/probe, completeness_probe, task_prioritizer, weakness_tracker, knowledge_hunter, self_upgrader, resource_finder, apex_cognition, beyond_mythos, knowledge_graph, mind_router, lens_router, meta_reasoner, unreplicable | Atlas listed "20+ frameworks" but did not enumerate or distinguish lens_router vs mind_router |
| `backend/app/services/swarm/` (executor + planner) | — | Multi-agent orchestration | Not in Atlas |
| `backend/app/services/daenabot/{vuln_scanner_agent,vision_browser_agent,target_interaction_agent,plugin_admin_agent,web_crawler_agent}.py` | — | Specialised DaenaBot agents beyond the 4 named (File/Terminal/Browser/MCP) | Atlas named only the 4 originals |
| `backend/app/services/departments/` (5 dept-agent files + border_agent + dynamic_departments) | — | DepartmentAgent base + SecurityOps/Sales/Marketing/Border + dynamic | Atlas names departments; doesn't enumerate per-dept agent files |
| `backend/app/services/department_{budget,message,policy,state}_service.py` | — | Per-department concerns (4 services) | Not in Atlas |
| `backend/app/services/department_workflows.py`, `department_router.py`, `department_prompts.py` | — | Departmental orchestration | Not in Atlas |
| `backend/app/services/voice/{stt_pipeline,tts_pipeline,realtime_voice_llm,outbound,conversation_session}.py` | — | Voice pipelines (with stub guards — see §G) | Atlas mentioned voice broadly |
| `backend/app/services/vision_loop.py`, `web_eyes.py` | — | Vision / web-eyes (web_eyes ORPHAN) | Not in Atlas |
| `backend/app/services/integrations/{calendar,gmail,notion}_client.py` + `oauth_credentials_store.py` + `integration_router.py` + `oauth_service.py` | — | SaaS connector + OAuth | Atlas mentioned OAuth; doesn't enumerate |
| `backend/app/services/benchmarks/` (7 modules, ~5,000 LOC) | 5,000 | CLI/Cost/Intelligence/Hallucination/Real benchmark suite + dataset_loader + suite | **Entirely unnamed in Atlas** — explains 11 root-level `run_*.py` benchmark scripts |
| `backend/app/services/agent_core/{agent_loop,daemon,prompt_governance,smart_resolver,interactive_prompts,system_access}.py` | — | Agent core loop layer | Not in Atlas |
| `backend/app/services/self_critique.py`, `self_fix.py`, `self_repair.py`, `self_improvement/self_audit.py` | — | Self-improvement mini-cluster | Atlas mentioned self-improvement once |
| `backend/app/services/{permission_dispatch,permission_resolver,policy_compiler,policy_store,pii_guard}.py` | — | Permissions + plain-English policy compiler + PII guard | Atlas mentioned policy compiler in CLAUDE.md but doc didn't enumerate files |
| `backend/app/services/mcp_bootstrap.py`, `mcp_sync/detector.py`, `mcp/server.py` | — | MCP bootstrap + sync detector + server (in addition to mcp_registry/invoker) | Atlas mentioned MCP client/server broadly |
| `backend/app/services/{drift_detector,plugin_catalog,extension_scanner,sub_agent_spawner,runtime_truth_registry}.py` | — | Misc support | Not in Atlas |
| `backend/app/services/{remote/gateway,session/session_sync}.py` | — | Remote / session sync | Not in Atlas |
| `backend/app/services/company_{context,mode,mode_providers,mode_replies}.py` + `pipeline_service.py` + `workstream_service.py` + `workstream_redirect_parser.py` | — | Company/Mission mode + Pipeline/CRM + Workstream | Atlas mentioned Workstream; mission/pipeline broader than named |
| `backend/app/services/cost_router.py` (in addition to cost_guard) | — | Cost-aware routing | Atlas named only cost_guard |
| `backend/app/services/billing/{budget_manager,cost_tracker}.py` | — | Billing cluster (budget_manager ORPHAN) | Not in Atlas |
| `backend/app/services/dcp_loader.py`, `demo_mode.py`, `daena_vp.py`, `subscription_service.py`, `project_service.py`, `dynamic_model_service.py`, `intent_amplifier.py`, `archive.py`, `chat.py` (separate from chat_orchestrator), `agents.py`, `oauth.py` | — | Misc | Not in Atlas |

### 2.2 Top-level loose files in `backend/` root (not in `app/` or `tests/`) — Atlas didn't mention any

| File | Risk |
|---|---|
| `tmp_endpoint_analysis.json` + `tmp_endpoint_analysis2.json` | Stale work products from a prior endpoint audit — should move to `.tmp/` or delete |
| `daena.db` + `daena_dev.db` + `daena_dev2.db` | 3 SQLite DBs side-by-side — only one is canonical for dev |
| `run_aime_pilot.py`, `run_aime_full.py`, `run_aime_rerun.py`, `run_aime_majority_vote.py`, `run_aime_cognitive.py`, `run_aime_session11.py` | 6 AIME benchmark runners loose at root |
| `run_truthfulqa.py`, `run_gsm_symbolic.py`, `run_council_test.py`, `run_full_power_benchmark.py` | 4 more benchmark runners |
| `aime_*.txt`, `aime_*.json`, `truthfulqa_results.json`, `gsm_symbolic_results.json`, `council_test_*.{txt,json}`, `intelligence_benchmark_results.json`, `aime_session11_*.json`, `aime_full_log.txt`, `aime_rerun_log.txt`, `aime_majority_vote_log.txt`, `benchmark_live_log.txt` | ~14 benchmark output artifacts |
| `bandit_self_audit.json`, `bandit_post_fix.json`, `bandit_final.json` | 3 bandit security audit outputs |
| `repair-db.sh`, `repair-db-v2.sh` | **Destructive:** drops/wipes tables |
| `wait-for-backend.sh`, `start-detached.sh`, `start-linux.sh`, `run-benchmark-linux.sh`, `start-llama-server.ps1` | Operational scripts |
| `backend.log` | Stale runtime log |
| `.daena-port` | Port discovery file (legitimate, written by main.py) |
| `run.py` | Entry shim |

**Decision needed:** Move `run_*.py` + result artifacts into `backend/scripts/benchmarks/` and add a README. Move `repair-db*.sh` into `backend/scripts/maintenance/` with a top-of-file warning banner.

### 2.3 `backend/backend/` — confirmed nested duplicate path

```
backend/backend/.archive/agent_core_browser_agent.py
```

A single archived file living one directory level deeper than it should. Almost certainly the residue of a prior `mv`/`cp` mistake. **Safe to remove after founder OK** (only one orphan file inside, already archived).

---

## 3. Backend services not mentioned by name in Atlas

Counted by the Phase C agent: **318 service Python files across 28 layers.** Atlas explicitly named ~60 of them. The 250+ not-named services include:

- The whole `benchmarks/` cluster (7 modules) and the entire benchmark API surface
- The 28-module `laevateinn/` reasoning pipeline
- 9 of the 13 `voice/` + `vision*` modules
- 4 of the 5 SaaS integrations (only `oauth_service` was named)
- 4 dept service splits (`department_{budget,message,policy,state}_service.py`)
- 5 specialised DaenaBot agents (only the 4 originals named)
- 20+ analyzer modules under `cognition/` (Atlas said "20+ frameworks" without enumeration)
- The `swarm/` mini-package
- 3 self-improvement files

### Services flagged as ORPHAN (importer_count == 0)

| File | Likely status |
|---|---|
| `backend/app/services/cognition/completeness_probe.py` | Module exists, never imported. **Investigate**: was it intended for QueryUnderstanding? |
| `backend/app/services/memory_import.py` | MemoryImporter never called. Probably superseded by `memory.py` |
| `backend/app/services/security/source_correlator.py` | Whitebox/blackbox correlator — Atlas mentioned it; importer set may have been removed. **Verify** |
| `backend/app/services/security/async_approval_manager.py` | Not used; approval flow lives in `approval.py` |
| `backend/app/services/user_config.py` | Superseded by `core/config.py` settings |
| `backend/app/services/voice/realtime_voice_llm.py` | Stub: NotImplementedError. ORPHAN |
| `backend/app/services/web_eyes.py` | Vision side-experiment, never wired |
| `backend/app/services/billing/budget_manager.py` | BudgetManager — superseded by `cost_guard.py` |
| `backend/app/services/agent_core/daemon.py` | DaenaDaemon — only invokable via `python -m ...`, never called from FastAPI lifespan |

### Services flagged as DUPLICATE (same purpose, multiple files)

| Pair | Recommended action |
|---|---|
| `security/cve_intelligence.py` ↔ `security/cve_intel.py` | Pick one canonical, delete the other (both verified to exist) |
| `connection_service.py` (V1) ↔ `connection_v2/*` (V2) | V1 has 3 importers still; V2 is gated behind `USE_CONNECTION_REGISTRY_V2` (default off). **Keep both** until flag flip; document who calls V1 |
| `cognition/lens_router.py` ↔ `cognition/mind_router.py` | Likely conceptually overlap; needs founder decision on canonical name |
| `chat.py` (service) ↔ `chat_orchestrator.py` | `chat.py` is the persistence/CRUD service; `chat_orchestrator.py` is the pipeline runner. Probably NOT a true duplicate — naming is just confusing |

### CLAUDE.md "do not delete" rule check

> **Corrected 2026-05-02 by PR-DOC-DRIFT-FIX.** The original entry
> below quoted CLAUDE.md as containing the literal hard rule
> *"Do not delete vault.py or oauth_credentials_store.py."* Direct
> grep of both `D:\Ideas\Daena\CLAUDE.md` (project) and
> `C:\Users\masou\.claude\CLAUDE.md` (global) on 2026-05-02 found
> NO such literal text. The protection rule was being carried only
> by per-session briefs, not by CLAUDE.md itself. PR-DOC-DRIFT-FIX
> closed that gap by adding **Rule 18** to the project CLAUDE.md
> with the three correct paths. The original ground-truth findings
> below are still valid and continue to apply.

| File | Exists at expected path? | Actual location |
|---|---|---|
| `vault.py` | NO -- not at `backend/app/services/vault.py` | The vault implementation lives at `backend/app/services/security/asset_shield/vault_adapter.py`. There is also `backend/app/services/vault_migration.py` but that's a migration helper, not the vault. |
| `oauth_credentials_store.py` | YES | `backend/app/services/integrations/oauth_credentials_store.py` |

**Documentation drift (resolved 2026-05-02):** the prior versions of
this Inventory said the CLAUDE.md hard rule was written as if
`vault.py` is a file. In fact CLAUDE.md never named `vault.py` at
all. The Phase A agent's claim that "vault.py and vault_v2.py both
present" is **incorrect** (verified: glob finds only
`vault_migration.py` outside of `asset_shield/`). The corrected
hard rule was added to project CLAUDE.md as **Rule 18** by
PR-DOC-DRIFT-FIX (commit landing 2026-05-02), referencing the three
real paths:

- `backend/app/services/security/asset_shield/vault_adapter.py`
- `backend/app/services/vault_migration.py`
- `backend/app/services/integrations/oauth_credentials_store.py`

---

## 4. Routers not mapped to frontend

Phase B counted **396 HTTP routes + 2 WebSocket = 398 endpoints across 45 routers.** The frontend's `lib/api.ts` SILENT_PREFIXES + `frontend/src/api/*.ts` consumers cover ~25 endpoint families. The remainder are likely-unused or operator-only.

### Suspected UNUSED routers (no frontend caller found)

| Router | Routes | Notes |
|---|---|---|
| `benchmark.py` | 15 | Intelligence/cost/real benchmarks. **No frontend** — used only by root-level `run_*.py` scripts |
| `laevateinn.py` | 4 | Text comprehension/processing engine. No UI — verify if any internal service calls it |
| `daenabot.py` | 2 | `/execute` endpoint — verify frontend usage |
| `security_authorized_scope.py` | 3 | Recent (Phase X-3 ticket landed); UI may be in-flight |
| `waitlist.py` | 2 | Marketing waitlist — uncertain UI binding |
| `mcp_sync.py` | 2 | Backend-only? Check if used by `mcp_bootstrap.py` |
| `tts.py` | 3 | TTS rest endpoints — voice pipeline uses voice_ws WebSocket; tts.py rest may be redundant |
| `souls.py` | 8 | Personas refinement — internal department overlay; UI surface unclear |
| Department sub-routers (`/department-budget`, `/department-messages`, `/department-policies`, `/department-states`) | several each | Internal; may not yet have UI |
| `runtime` (singular) | 7 | Truth registry, import, health-check, test-call. Operator-level — UI is `RuntimeSwapper` which uses `/runtimes` plural. Risk: V1/V2 confusion |
| `missions.py` | 16 | Mission graphs, proximity, weakness — possibly autonomous-sales orchestration; UI uncertain |
| `pipeline.py` | 12 | Sales pipeline CRUD — UI may be Phase G work |
| `company_mode.py` | 9 | Activate/briefs/drafts/outbound-send — UI fragment exists but coverage uncertain |

### Phase 11 notification routes

| Method | Path | Status |
|---|---|---|
| GET `/api/v1/notifications` | List user notifications | USED (Header.tsx hydrates on mount) |
| POST `/api/v1/notifications/test` | Emit test (always system_info) | USED (SettingsNotifications.handleSendTest) |

### Duplicate-purpose routes

- `/api/v1/connections/*` (V1, 25 routes) vs `/api/v1/connections/v2/*` (V2, 11 routes — feature-flag gated)
- `/api/v1/runtime/*` (singular, truth registry) vs `/api/v1/runtimes/*` (plural, legacy compat)
- `POST /api/v1/chat/sessions/{id}/messages/stream` vs `POST /api/v1/chat/messages/stream` (both fold into one orchestrator internally)

### Dangerous/admin-only routes (mounted but require strong gate)

- `PATCH /api/v1/skills/{skill_id}` — ADMIN
- `PUT /api/v1/billing/user-quotas/{target_user_id}` — ADMIN
- `DELETE /api/v1/org/members/{member_id}` — Org admin
- All `evilbob`/`founder` debug routes — gated behind founder role

No router was found that's mounted but completely unauthorised on a destructive verb.

---

## 5. Models without migrations

### 5.1 P0 BLOCKER — Notification table

**Verified facts:**
- `backend/app/models/notification.py` exists (Phase 11 PR-S2, 2026-05-01)
- `backend/app/models/__init__.py` includes it in `__all__`
- `backend/migrations/versions/` contains migrations 001 through 007 (verified by Glob)
- **Grep `notification` across `backend/migrations/` returns zero results**

**Implication:** When this branch is deployed against PostgreSQL, the `notifications` table will not exist. Every call to `NotificationService.emit(...)` from `chat_orchestrator`, `cost_guard`, `execution_service`, or `approval` will fail at the `session.add(Notification(...))` step with a `sqlalchemy.exc.ProgrammingError: relation "notifications" does not exist`. SQLite dev still works because `Base.metadata.create_all()` is called in dev startup (main.py).

**Required fix before any prod-touching work:** create `backend/migrations/versions/008_add_notifications.py` mirroring the `Notification` columns + the composite index `ix_notifications_user_id_created_at`.

### 5.2 Models that rely on `Base.metadata.create_all()` (dev) or pre-existing migrations (prod)

Roughly **46 of 54 models** do not have an explicit migration in the 001–007 version chain. They are presumably covered by an earlier migration not in this branch's history (the project predates this branch's slice). Worth a one-time audit by reading the production DB schema and writing a "baseline" migration `000_baseline.py` that asserts the existing schema.

### 5.3 Migrations without a current model (orphan tables)

A scan of `CREATE TABLE` statements in the 7 versions vs. the `__tablename__` set across `backend/app/models/` did not find an orphan table — every CREATE has a corresponding model. ✅

---

## 6. Migrations without models

(See §5.3 — none found.)

---

## 7. Startup jobs NOT surfaced in UI

Phase D agent classification (re-checked by main thread):

| Job | Started by | Classification | Notes |
|---|---|---|---|
| `_warmup_ollama` | main.py:477 (fire-and-forget) | STARTED_BUT_NO_UI | OK — silent best-effort |
| `_periodic_runtime_rescan` | main.py:689 (60s loop) | STARTED_BUT_NO_UI | Surfaces via `/runtimes` listing freshness |
| Background queue worker | main.py deferred init | STARTED_AND_USED | `/heartbeat/queue` + autopilot UI |
| Cron scheduler | main.py deferred init | STARTED_AND_USED | `/heartbeat/cron-runs` UI |
| Dream Engine (15-min APScheduler) | main.py deferred init | STARTED_BUT_NO_UI | **UI claims Dream is UNSCHEDULED** but it actually IS scheduled. Atlas needs correction. |
| Runtime registry init | main.py deferred init | STARTED_AND_USED | `/runtimes` listing |
| MCP registry init | main.py deferred init | STARTED_AND_USED | `/mcp` listing |
| Founder accounts seeding | deferred init | STARTED_BUT_NO_UI | Idempotent seed; OK |
| Departments + agents seeding | deferred init | STARTED_BUT_NO_UI | Idempotent seed; visible via departments UI |
| Connector catalog seed | deferred init | STARTED_AND_USED | `/connections` UI |
| Demo mode seed | deferred init (env-gated) | STARTED_BUT_NO_UI | Only when `DEMO_MODE=true` |
| Company context soul vault hydration | deferred init | STARTED_BUT_NO_UI | OK |
| Provider V2 seeding | deferred init (gated on `USE_CONNECTION_REGISTRY_V2`) | STARTED_BUT_NO_UI | Default off |
| EvilBob auto-activation | deferred init (gated on `EVILBOB_AUTO_ACTIVATE` + `EVILBOB_KEY` + LOCAL env) | STARTED_BUT_NO_UI | **Founder-only**; correct |
| Heartbeat daemon (`HeartbeatDaemon`) | **NEVER STARTED** in main.py | VISIBLE_IN_UI_BUT_NEVER_STARTED | **Rule 17 violation candidate** — UI has Pause/Resume/Stop controls but the daemon never auto-starts. Operator must call `/heartbeat/start` manually. |
| `agent_core/daemon.py` (`DaenaDaemon`) | **NEVER STARTED** from FastAPI | ORPHAN_BACKGROUND_SERVICE | CLI-only entry point (`python -m ... start`). Bypassed by FastAPI runtime. |

### Dream-Engine reclassification

The Atlas + Backlog (`DAENA_ARCHITECTURE_GAP_BACKLOG.md` P0 #4) marked Dream Engine as "UNSCHEDULED — no APScheduler binding." **This is wrong.** The 15-min APScheduler binding is live. What may be missing is the *user-visible* surface (a "last dream consolidation: 2 hours ago" badge somewhere). The P0 status should be downgraded to P1 (UI-only).

### Heartbeat-daemon reclassification

`HeartbeatDaemon` IS implemented (650 LOC). It IS callable. UI HAS controls. But `main.py` lifespan does NOT invoke `daemon.start()`. So the controls are decorative until an operator manually POSTs to start it. **This IS the Rule 17 violation** the Atlas warned about — but mislabelled (it's the daemon, not the cron, that's the placebo).

---

## 8. UI surfaces with NO backend consumer

### "Hallucination of Control" — partial confirmation

Phase F+G agent set the Atlas claim under audit and returned a softer verdict:

| Claimed Atlas (Settings dead-toggle thesis) | Actual filesystem |
|---|---|
| "40 of 47 settings keys are DEAD/STUB" | True for *some* per-user dict keys. 5 notification toggles ARE backed (post Phase 11 PR-S2). |
| `governance_mode` is a real toggle | Backend honors it inconsistently — many call sites default to BALANCED regardless of user's setting |
| Sound/Email/Daily-Digest notification toggles | Disabled on purpose (no backend) — labelled as such, NOT placebo |
| `OLLAMA_ENABLED` | DEAD flag — kept for backward compat after llama.cpp swap. No-op. |

### UI-visible-but-no-backend list (highest impact)

1. `developer_mode` — UI does not expose toggle anywhere. Set only via env. Is this intentional? (Per CLAUDE.md it's the only flag allowing real deletion vs. archive.)
2. `LLAMA_SERVER_MANAGED` value — no UI surface; operator must edit env. Probably intentional, but undocumented in /settings.
3. Many per-user `settings.notif_*` flags work, but per-user `settings.routing.*` does not appear to feed the model router.
4. Several `Settings → Privacy` toggles (memory_generation_off, privacy_mode_on) — Phase G agent confirmed these don't gate anything in `chat_orchestrator`.

### Routes the UI doesn't call (re-listed from §4 for emphasis)

`benchmark/*`, `laevateinn/*`, `souls/*`, several department sub-routers, `missions/*`, `pipeline/*`, `runtime` (singular).

---

## 9. Backend capabilities with NO UI surface

These are real, working backend features with no operator-facing surface:

| Capability | File(s) | Why it matters |
|---|---|---|
| Dream Engine consolidation reports | `dream_engine.py` | Real, 15-min cadence, but "last run at" is not on any page |
| Skill Refinery proposals queue | `skill_refinery/refinement_service.py` + `/api/v1/skill_refinery/*` (15 routes) | Full pipeline — needs a queue page |
| Cron history | `/heartbeat/cron-runs` | Backend writes `cron_runs` table; UI may underuse it |
| Background queue restart-recovery (`failed_due_to_restart`) | `background_queue.py` | New status code never surfaced in queue UI |
| Knowledge Graph (`cognitive/knowledge_graph.py`) | DB writes + file writes | Not on any UI page |
| Vision loop (`vision_loop.py`) | 9 importers | Service is real but no UI runs it interactively |
| Self-improvement loop (`self_audit`, `self_critique`, `self_fix`, `self_repair`) | 4 files | Backend has these but they're not on operator dashboard |
| Drift detector (`drift_detector.py`) | Real | Not on dashboard |
| Recovery monitor (`runtimes/recovery_monitor.py`) | Real | Not on dashboard |
| Sub-agent spawner (`sub_agent_spawner.py`) | Real | Not on dashboard |
| Pre-ingestion filter (`security/pre_ingestion_filter.py`) | Real, used | Operator can't see what was filtered |
| Apex cognition / hypothesis tester (`apex_cognition.py`) | Real | No "ran with hypothesis testing" indicator in chat UI |
| Beyond Mythos enricher | Real, used in Phase 3b of scan_workflow | Not labelled in scan UI cards |
| Knowledge hunter (`knowledge_hunter.py`) | 3 importers | Not labelled in UI |
| Forgotten Infra Scanner (`unreplicable.py` ForgottenInfraScanner) | 5 importers | Not on dashboard |
| Plugin admin agent (`plugin_admin_agent.py`) | 4 importers | Internal-only |

---

## 10. Dangerous / local-only modules

### 10.1 EVILBOB activation chain (verified fail-closed)

`backend/app/services/security/evilbob_mode.py` (lines 70–106 spot-checked):

```
detect_environment() reads env vars in this order:
  cloud_vars = [K_SERVICE, GAE_ENV, AWS_LAMBDA_FUNCTION_NAME,
                AZURE_FUNCTIONS_ENVIRONMENT, RENDER, RAILWAY_ENVIRONMENT, FLY_APP_NAME]
  if any cloud var is present → return "cloud"
  fallback: settings.app_env in (production, staging) → return "cloud"
  else → "local"
```

Activation requires ALL THREE:
1. `EVILBOB_KEY` env var matches user input (constant-time compare)
2. Environment == "local"
3. Founder/admin role (when auth active)

Auto-activation (`EVILBOB_AUTO_ACTIVATE=true`) on startup also requires KEY + LOCAL. Cloud or staging env causes activation to be **denied with `evilbob.activation_denied` audit event**.

**Verdict:** No bypass found. Gate is fail-closed. Founder trust assumption: only the operator's machine runs `LOCAL` env.

### 10.2 Local-only / cloud-blocked modules (depend on EVILBOB activation)

All under `backend/app/services/security/`, only callable when EVILBOB is active:

- `red_team_ops.py` (1,046 LOC) — explicit `BACKGROUND PATH ONLY -- never import in hot path` comment **verified**
- `exploitation_queue.py`
- `zero_day_engine.py` (SupplyChainAttackPlanner)
- `osint_engine.py` (Apollo)
- `opsec.py`
- `credential_chain.py`
- `mission_intelligence.py`
- The whole T5 EVILBOB tier of `report_tiers.py` (extra OODA-R + opsec stages)

### 10.3 Always-on defensive modules

- `security_gate.py` (PromptInjectionScanner + shield_scan)
- `security/behavior_guard.py` (anti-RE honeypot, jailbreak detection — designed deception)
- `security/asset_shield/{vault_adapter,egress_filter,consent_token,operator_initiation}.py` (Asset Shield)
- `security/zero_fp_gate.py` (no unverified findings in OPERATOR+ reports)
- `security/real_scanner.py` (deterministic, no-LLM scanning)

### 10.4 Destructive scripts on disk

- `backend/repair-db.sh` and `backend/repair-db-v2.sh` — drop/wipe DB tables. Loose at root, no warning banner. **Move to `backend/scripts/maintenance/`** with a header line forbidding execution against production DSN.

---

## 11. Archive / duplicate folders requiring founder decision

### 11.1 Confirmed nested archive

```
D:\Ideas\Daena\backend\backend\.archive\agent_core_browser_agent.py
```

A single file in a **doubled** path (`backend/backend/`). Almost certainly created by a stray `mkdir backend && mv ...` or an export script. **Founder decision:** keep, or `rm -r backend/backend/`?

### 11.2 `.archive/` at repo root

Phase A reported 4 files. Treat as historic — leave alone.

### 11.3 `backend/.archive/`

Phase A noted `vault.py` and `connections.py` as archived/superseded — verify that they truly are under `.archive/` (not at services/ root, where they don't exist per spot-check).

### 11.4 The 11 root-level benchmark runners

`backend/run_aime_*.py` (6 files), `backend/run_truthfulqa.py`, `backend/run_gsm_symbolic.py`, `backend/run_council_test.py`, `backend/run_full_power_benchmark.py`, plus result JSONs/TXTs. **Founder decision:** keep them at root (operator habit) or move to `backend/scripts/benchmarks/`?

---

## 12. Delete candidates (do NOT delete yet — pending founder OK)

| File | Reason | Risk if deleted |
|---|---|---|
| `backend/backend/.archive/agent_core_browser_agent.py` (and the empty parent dir) | Nested-path orphan | None |
| `backend/app/services/billing/budget_manager.py` | 0 importers; superseded by `cost_guard.py` | None unless reactivated |
| `backend/app/services/cognition/completeness_probe.py` | 0 importers | Investigate intent first |
| `backend/app/services/memory_import.py` | 0 importers; superseded by `memory.py` | Low |
| `backend/app/services/security/source_correlator.py` | 0 importers; **was used in scan_workflow earlier** | Re-check before delete |
| `backend/app/services/security/async_approval_manager.py` | 0 importers; approval flow lives in `approval.py` | Low |
| `backend/app/services/user_config.py` | 0 importers; superseded by `core/config.py` Settings | Low |
| `backend/app/services/voice/realtime_voice_llm.py` | NotImplementedError on every method | Stub — keep until voice is built or remove claim from UI |
| `backend/app/services/web_eyes.py` | 0 importers | Side-experiment |
| `backend/app/services/security/cve_intelligence.py` OR `security/cve_intel.py` | One of these is canonical | Founder decision |
| `backend/tmp_endpoint_analysis.json` + `tmp_endpoint_analysis2.json` | Stale work artifacts | None |
| `backend/{aime_*,truthfulqa_results,gsm_symbolic_results,council_test_*,benchmark_live_log,intelligence_benchmark_results,aime_session11_*}.{json,txt}` | Benchmark output artifacts at repo root | None — but archive them |
| `backend/bandit_*.json` (3 files) | Bandit scan outputs | Move to `.tmp/security-audits/` |

**No file is recommended for deletion in this report.** Founder must approve each, individually or by batch.

---

## 13. Top 20 blind-spots ranked by risk

Risk = `production_blast_radius × likelihood_of_hitting_in_normal_use × difficulty_to_detect_at_runtime`.

| # | Blind-spot | Risk | Why |
|---|---|---|---|
| 1 | **Notification table missing migration** (Phase 11) | **P0** | Production deploy → every emit raises `ProgrammingError`. SQLite dev hides it. Affects 5 retrofitted services. |
| 2 | Heartbeat daemon UI controls but daemon never auto-starts in lifespan | **P0** | Rule 17: visible-but-not-running. Operator clicks Pause expecting effect; gets nothing. |
| 3 | EVILBOB tier capabilities present + auto-activation supported | **P0 governance**, **safe-as-built** | Verified fail-closed across 3 gates. But **a single misconfigured env (EVILBOB_KEY committed to env file shipped to cloud) bypasses all defence.** Treat the secret like a master key. |
| 4 | `red_team_ops.py` and 6 sibling offensive modules wired to scan workflow tier T5 | **P0 governance**, **safe-as-built** | Only callable when EVILBOB active + LOCAL env. Cannot accidentally call from a chat. |
| 5 | Connection V1 + V2 coexist; `USE_CONNECTION_REGISTRY_V2` default off; UI may show V1 panels mixed with V2 | **P1** | Founder asked us not to flip the flag. Migration tail is sustained tech debt; consolidate before next major UI work. |
| 6 | Dream Engine actually runs every 15 min but Atlas/Backlog says UNSCHEDULED | **P1** | Documentation drift. P0 entry in BACKLOG is wrong; downgrade to "no UI surface for last-run-time" P2. |
| 7 | Voice subsystem `NotImplementedError` raised on real user interaction (`outbound.send_*`, `realtime_voice_llm.request_*`, `stt_pipeline.transcribe`, `tts_pipeline.synthesize`) | **P1** | Reachable from `/voice/ws/*`. Should return graceful "voice provider not configured" error, not stack trace. |
| 8 | Phase 11 retrofit-emitter test environment (UserQuota seed) — must remain stable | **P1 fragile** | Tests were sensitive to UserQuota's `period_start` daily-rollover logic; document fixture requirement. |
| 9 | `cve_intelligence.py` ↔ `cve_intel.py` duplicate | **P2** | Pick canonical, archive the other |
| 10 | `lens_router.py` ↔ `mind_router.py` likely-duplicate | **P2** | Founder decision on canonical name |
| 11 | `connection_v2/probe.py:59` raises `NotImplementedError` | **P2** | Probe fallback unimplemented; V2 registry can't validate misbehaving connections — but V2 is gated off by default |
| 12 | `cognitive_scan_engine.py:2805` `scan_custom_operation` returns hardcoded "not implemented yet" string | **P2** | User submits custom op, gets fake-success. Add real fallback or refuse. |
| 13 | Multiple `security_dashboard.py` endpoints return `{}`/`[]` on error; operator sees no error | **P2** | Rule 17 violation: failure invisible. Replace with explicit error channel. |
| 14 | `runtimes.py:177,183,191` returns `[]` on internal exception | **P2** | Frontend shows "no runtimes" instead of "error fetching runtimes" |
| 15 | DaenaDaemon (`agent_core/daemon.py`) is CLI-only and never invoked by FastAPI | **P2** | Probably an old experiment — confirm and archive |
| 16 | `backend/backend/.archive/` nested duplicate path | **P2 housekeeping** | Single-file orphan — delete after founder OK |
| 17 | 11 benchmark runners + 14 result artifacts loose at `backend/` root | **P2 housekeeping** | Move to `backend/scripts/benchmarks/` |
| 18 | `repair-db*.sh` destructive scripts loose at `backend/` root with no banner | **P2 hygiene** | Move + add header warning |
| 19 | 3 separate SQLite DB files at root (`daena.db`, `daena_dev.db`, `daena_dev2.db`) | **P3** | Pick one canonical for dev; document the others |
| 20 | `bandit_self_audit.json` + `bandit_post_fix.json` + `bandit_final.json` at repo root | **P3** | Move to `.tmp/security-audits/` |

---

## Cross-cutting findings

### A. Atlas got the *quality* of intelligence right; under-counted the *surface area*

The Atlas correctly identified the brain (OODA, Council, QE, Soul, Dream, NBMF, Asset Shield, governance). The blind spots are almost entirely in the **periphery**: more cognition analyzers, more security sub-modules, more department services, the entire benchmark suite, more DaenaBot agents, integrations cluster. None of these *replace* the brain — they *augment* it. The architectural mental model in the Atlas remains sound.

### B. The "Hallucination of Control" claim is partially true, partially overstated

True for: legacy per-user dict settings (routing/privacy), `OLLAMA_ENABLED`. Overstated for: notification toggles (real after Phase 11 PR-S2), governance_mode (inconsistently honored, not entirely dead). The accurate framing: **the scope of the placebo is shrinking** as PRs land. Phase 11 cut it from 47 → ~38 dead keys. Continue the trend; don't generalize.

### C. The offensive surface is correctly scoped and gated, but secret hygiene is the load-bearing assumption

EVILBOB activation requires ALL of (KEY + LOCAL + role). Founder threat model: if `EVILBOB_KEY` is ever shipped in an `.env` to cloud, the whole gate collapses. The `gitleaks` regex set in `real_scanner.py` will catch most key patterns, but **add an explicit pre-commit hook that rejects any commit touching `.env` if `EVILBOB_KEY` is set to a non-empty string.**

### D. The Notification migration gap is the only true production blocker discovered

Everything else is housekeeping, documentation drift, or feature stubs that don't break code. The 5 retrofitted emitters land notifications via `session.add(Notification(...))` in production code paths. On PostgreSQL with no migration, those calls fail. Test suite doesn't catch it because tests use SQLite + `Base.metadata.create_all()`. **Highest-priority single fix.**

---

## Appendix: Numbers at a glance

| Metric | Count |
|---|---|
| Total backend files inventoried (Phase A) | ~753 |
| Backend `app/` Python files | ~443 |
| Tests | ~220 |
| Backend root loose executables | 18 |
| Backend root loose data/db artifacts | 16 |
| Migrations | 7 (`001_…` through `007_…`) |
| MCP packages | 9 |
| Archived files (.archive/) | 4 |
| HTTP routes (Phase B) | 396 |
| WebSocket endpoints | 2 |
| Routers | 45 |
| Service files (Phase C) | ~318 |
| Service LOC | ~125,000 |
| SQLAlchemy models (Phase E) | 54 |
| Models without explicit migration in 001–007 | 46 (most rely on pre-existing baseline) |
| Models with **NO** migration anywhere (Phase 11 gap) | **1 (Notification)** |
| Background jobs (Phase D) | 8 |
| Started + used | 5 |
| Started + no UI | 3 |
| Visible-in-UI but never started | 1 (HeartbeatDaemon) |
| Orphan service modules (importer == 0) | 9 |
| Duplicate-purpose service pairs | 3–4 |
| Stub modules (NotImplementedError or hardcoded fake-success) | 7+ (mostly voice, conn_v2/probe, scan_custom_operation) |
| Env flags total (Phase F) | 42 |
| Critical env flags | 4 (EVILBOB_KEY, DAENA_KEK/VAULT_ENCRYPTION_KEY, DISABLE_AUTH, developer_mode) |
| Dead env flags | 1 (OLLAMA_ENABLED) |
| Security service files (Phase H) | 36 |
| Laevateinn reasoning modules | ~28–31 |
| EVILBOB activation gates | 3 (KEY + LOCAL + ROLE) |
| Cloud-blocked enforcement source-of-truth file | 1 (`evilbob_mode.py::detect_environment`) |

---

**End of inventory.**

Companion artifact: `DAENA_BACKEND_MODULE_GRAPH.mmd` — Mermaid layered graph of the same data.
