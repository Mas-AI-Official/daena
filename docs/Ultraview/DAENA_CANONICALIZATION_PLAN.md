# DAENA Canonicalization Plan

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime` @ `35c522b`
**Author:** Claude Code (Opus 4.7) under founder-direction
**Status:** **Planning only.** Zero product code modified. Zero tests run.
Zero migrations, no flag flips, no vault `--apply`, no deletions, no
external scans, no external messages, no secrets read.
**Companion docs:** `DAENA_BACKEND_BLINDSPOT_INVENTORY.md`,
`DAENA_ARCHITECTURE_GAP_BACKLOG.md`, `DAENA_ARCHITECTURE_ATLAS.md`
(sections F, G, H, I, plus Appendix B reconciliation),
`DAENA_EXECUTION_SPINE_PRD.md`, `PR_DOC_DRIFT_FIX_REPORT.md`,
`FRONTEND_CONTROL_NECESSITY_AUDIT.md`,
`DAENA_FRONTEND_ACTION_DESIGN_RULEBOOK.md`.

> **Thesis.** Daena's intelligence layer is rich and largely correct.
> Daena's surface area is bloated, partially placebo, and lacks one
> canonical action lifecycle. This plan classifies every backend
> module, frontend route, and settings key into a small fixed set of
> actions (KEEP / MERGE / HIDE / DISABLE / ARCHIVE / DELETE / DOC) and
> sequences five small PRs that close the trust gap before any spine
> rebuild starts. No file is touched in this PR. Nothing ships from
> this document; PRs ship from it.

---

## 0. Intent and constraints

### 0.1 Founder's product decision (anchor)

Keep these ten primary surfaces. They are the product's identity and
the marketing surface. Everything else is either a sub-view of one of
these, an Advanced/Developer panel, or scheduled for archive.

1. **Chat** with CMD/EXE
2. **Dashboard** (sunflower hive)
3. **Departments** (10 named department brains)
4. **Mind** (company/department intelligence + memory)
5. **Security / Scan** (Manus-style live work window)
6. **Connections** (MCP / Plugins / Brain selector)
7. **Tasks / Workstreams** (one canonical "what is running" surface)
8. **Files**
9. **Governance / Audit** (mostly internal; surface only when needed)
10. **Settings** (heavily reduced)
11. **Skills** (added 2026-05-02 by founder amendment) - the operator-
    facing surface for the Skill Refinery (extraction, refinement,
    retrieval, skill store). Stays first-class because Skills are how
    Daena's institutional knowledge accrues; the Refinery feeds DCP
    prompts via the chat orchestrator memory enrichment hook
    (CLAUDE.md project rule 14). Do NOT collapse into Settings or
    Advanced.

### 0.2 Founder's intent reframed

- **Departments are identity.** Do not collapse, do not de-emphasize.
- **Mind represents company + department intelligence + memory.**
  This is the public face of NBMF + DCP + Dream + Council.
- **Security needs a Manus-style live window.** One launcher, one
  live execution view, then reports plus remediation tasks.
- **Connections must tell the truth.** Brain choice + model +
  provider + MCP + plugin are all one truth surface. V1 panels
  collapse behind "Legacy / Advanced".
- **Governance is mostly internal.** In Unleashed mode, Shield + Hard
  Laws still run, but the UI does not overwhelm the user with tier
  badges. Approval queue and Audit page stay reachable on demand.
- **Settings has too many duplicated and useless controls.** Hide
  first. Wire later. Delete last. Never ship a control with no
  consumer just to look complete.

### 0.3 Hard rules honored by this plan

| Rule | Status |
|---|---|
| No production deploy | Yes (planning only) |
| No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes (only documents the flip) |
| No `vault --apply` | Yes (vault not invoked) |
| No deletion of `vault_adapter.py` / `vault_migration.py` / `oauth_credentials_store.py` (Rule 18) | Yes (these are listed as KEEP_HOT_PATH) |
| No file deletions in this PR | Yes (deletes scheduled, not executed) |
| No secrets printed or committed | Yes (no secret material involved) |
| No external scans | Yes |
| No external messages (email / DM / SMS / webhook) | Yes |
| Em dashes in new content (project CLAUDE.md Rule 12) | None introduced |

### 0.4 Naming conventions (used throughout)

- **KEEP_HOT_PATH** - belongs in the live request path; do not touch.
- **KEEP_SUPPORTING** - useful background or operator surface; keep.
- **MERGE_DUPLICATE** - collapse to a canonical sibling; preserve
  history but stop producing the duplicate.
- **HIDE_ADVANCED** - keep functionality; hide the surface behind an
  Advanced / Developer toggle.
- **DISABLE_COMING_SOON** - keep schema or stub; render disabled with
  honest "Coming soon - PR-X wires this" badge.
- **ARCHIVE_LEGACY** - move to `.archive/`; do not delete.
- **DELETE_CANDIDATE** - propose deletion via separate DELETE-PR with
  founder approval and rollback path. Not deleted by this plan.
- **DANGEROUS_LOCAL_ONLY** - real, gated, must never accidentally fire
  in cloud or in non-founder context.
- **STUB_REPLACE_OR_REFUSE** - currently returns fake-success; either
  implement or fail-closed with honest error.
- **DOC_DRIFT** - reality and documentation disagree; fix the doc.

---

## 1. Backend classification table

Source: `DAENA_BACKEND_BLINDSPOT_INVENTORY.md` sections 1, 2, 3, 7,
9, 10, 12 + ground-truth filesystem at `35c522b`. "Importers" was
captured by the Phase A/C agents during the Blind-Spot sweep; numbers
are best-known-as-of 2026-05-02 and may shift if a service is moved.

> Convention: file paths are repo-relative. "Frontend caller" lists
> the most specific consumer (route or component) when known.
> "Founder OK?" tags the recommended action's required gate.

### 1.1 KEEP_HOT_PATH (the spine - never touch without ticket)

| File | Importers | Frontend caller | Tests | Risk if removed | Founder OK? |
|---|---:|---|---|---|---|
| `backend/app/services/chat_orchestrator.py` | 12+ | `/chat` SSE | 35+ | Chat dies | Required |
| `backend/app/services/governance.py` | 18+ | every action path | 25+ | Governance pipeline collapses | Required |
| `backend/app/services/security/security_gate.py` | 22+ | every chat + scan | 18+ | Prompt-injection guard gone | Required |
| `backend/app/services/security/behavior_guard.py` | 9 | every chat | 8 | Anti-RE shield gone | Required |
| `backend/app/services/security/asset_shield/vault_adapter.py` | 14 | secrets read path | 6 | Vault unreadable; OAuth dies | Required (Rule 18) |
| `backend/app/services/security/asset_shield/egress_filter.py` | 7 | external send | 4 | Asset egress gate gone | Required |
| `backend/app/services/security/asset_shield/consent_token.py` | 5 | initiator-aware paths | 3 | Initiator consent gate gone | Required |
| `backend/app/services/security/asset_shield/operator_initiation.py` | 5 | initiator detection | 3 | T0-T4 collapse rules break | Required |
| `backend/app/services/integrations/oauth_credentials_store.py` | 6 | OAuth callbacks | 4 | Connector connections die | Required (Rule 18) |
| `backend/app/services/vault_migration.py` | 1 (one-shot) | n/a | 1 | Future re-encryption pass impossible | Required (Rule 18) |
| `backend/app/services/audit.py` | 30+ | `/governance/audit` | 12+ | Hard Law #9 collapse | Required |
| `backend/app/services/notification_service.py` | 6 | bell / Header | 9 | In-app fan-out dies | Required |
| `backend/app/services/cost_guard.py` | 8 | preflight Stage 5 | 6 | Cost preflight gone | Required |
| `backend/app/services/model_router.py` | 7 | every chat | 8 | Routing collapses | Required |
| `backend/app/services/connection_service.py` (V1) | 3 | `/connections` legacy | 4 | V1 panels die before V2 cutover | Required (until V2 flip) |
| `backend/app/services/connection_v2/*` | 6 | `/connections` V2 panels | 9 | V2 panel data dies | Required (gated) |
| `backend/app/services/runtimes/registry.py` + adapters | 9 | `RuntimeSwapper`, MainBrainPanel | 7 | Runtime listing dies | Required |
| `backend/app/services/mcp_registry.py`, `mcp_invoker.py` | 7 | MCP V2 panel | 6 | MCP listing dies | Required |
| `backend/app/services/cognition/ooda_engine.py` | 5 | EXE path + REFLECT | 4 | OODA loop dies | Required |
| `backend/app/services/council_engine.py`, `quintessence_engine.py` | 4 | Council/QE chat mode | 6 | Council/QE dies | Required |
| `backend/app/services/soul_engine.py` + `soul_maker/*` | 8 | every chat (system prompt) | 5 | Soul layer dies | Required |
| `backend/app/services/dream_engine.py` | 3 (lifespan + cron) | Mind page (TODO) | 2 | Self-correction loop stops | Required |
| `backend/app/services/heartbeat/cron_scheduler.py` | 1 (lifespan) | `/heartbeat/cron-runs` | 4 | DB-backed cron history dies | Required |
| `backend/app/services/heartbeat/heartbeat_daemon.py` | 1 (lifespan, NOT WIRED) | `SettingsHeartbeat.tsx` | 5 | See P0-09; daemon never auto-started today | Required (PR-HB-DAEMON-WIRE) |
| `backend/app/services/autopilot/background_queue.py` | 4 | TasksPage, autopilot | 7 | Queue + restart-recovery dies | Required |
| `backend/app/services/security/cognitive_scan_engine.py` | 24 | scan flow nucleus | 8 | All scans die | Required |
| `backend/app/services/security/scan_workflow.py` | 7 | `/scan` SSE | 6 | Scan walkthrough dies | Required |
| `backend/app/services/security/zero_fp_gate.py` | 3 | scan reports | 3 | OPERATOR+ unverified findings reach UI | Required |
| `backend/app/services/security/real_scanner.py` | 5 | scan workflow | 4 | Deterministic baseline gone | Required |

### 1.2 KEEP_SUPPORTING (real, used, keep but lower priority)

| File | Importers | Frontend caller | Tests | Risk if removed | Founder OK? |
|---|---:|---|---|---|---|
| `backend/app/services/skill_refinery/*` (5 files) | 8 | `/skills` page | 12+ | Skills extraction + Refinery dies | Required |
| `backend/app/services/tool_lifecycle/*` (TLM) | 7 | EXE / DaenaBot | 6 | Tool catalog dies | Required |
| `backend/app/services/execution_service.py` | 9 | `/tasks` / EXE | 11 | Task execution dies | Required |
| `backend/app/services/approval.py` | 6 | `/governance/approvals` | 7 | Approval queue dies | Required |
| `backend/app/services/security/evilbob_mode.py` | 4 | hidden activation only | 5 | EVILBOB tier dies (founder-only) | Required (Rule 18-adjacent) |
| `backend/app/services/security/laevateinn/*` (~28-31 files) | various | scan workflow Phase 3b+ | varies | Reasoning depth on T3+ scans drops | Required (gated) |
| `backend/app/services/security/intel_fanout.py` + `cve_intel.py` | 4 | scan reports | 3 | Cross-channel intel dies | Required (see §2 for cve_intel vs cve_intelligence) |
| `backend/app/services/security/source_correlator.py` | 0 (was used) | scan workflow | 1 | Whitebox/blackbox correlation degraded | Verify before delete |
| `backend/app/services/cognition/{first_principles,inversion,pre_mortem,consequence_chain,...}.py` | varies | OODA Orient | varies | Reasoning frameworks unavailable to Council | Required |
| `backend/app/services/cognition/lens_router.py`, `mind_router.py` | 3+3 | Council prompts | 2 | See §2 (likely duplicate; needs founder pick) | Decision required |
| `backend/app/services/swarm/{executor,planner}.py` | 2 | autopilot multi-agent | 3 | Swarm dies | Keep (low traffic) |
| `backend/app/services/daenabot/{file,terminal,browser,mcp}_agent.py` | 8 | EXE | 9 | DaenaBot dies | Required |
| `backend/app/services/daenabot/{vuln_scanner,vision_browser,target_interaction,plugin_admin,web_crawler}_agent.py` | varies | scan workflow | varies | Specialized scan tooling weaker | Required (gated) |
| `backend/app/services/departments/*` (5 dept-agent files + border + dynamic) | 6 | DepartmentChatPage | 7 | Departments page collapses | Required |
| `backend/app/services/department_{budget,message,policy,state}_service.py` | 4 each | dept sub-routers | 5 | Per-dept concerns die | KEEP (Departments are identity) |
| `backend/app/services/department_workflows.py`, `department_router.py`, `department_prompts.py` | 5 | DepartmentChatPage | 6 | Department orchestration weak | Required |
| `backend/app/services/voice/{stt,tts,outbound,conversation_session}.py` | 4 | Voice toggle, Header STT | 5 | Voice dies; some endpoints raise NotImplementedError today (see §1.7) | Keep + harden |
| `backend/app/services/integrations/{calendar,gmail,notion}_client.py` + `integration_router.py` + `oauth_service.py` | 6 | Connections OAuth | 7 | Connector OAuth dies | Required |
| `backend/app/services/agent_core/{agent_loop,prompt_governance,smart_resolver,interactive_prompts,system_access}.py` | 5 | EXE inner loop | 4 | Agent loop weaker | Required |
| `backend/app/services/{permission_dispatch,permission_resolver,policy_compiler,policy_store,pii_guard}.py` | 7 | `/policies` page + PII guard | 8 | Plain-English Policy Compiler dies | Required |
| `backend/app/services/mcp_bootstrap.py`, `mcp_sync/detector.py`, `mcp/server.py` | 5 | MCP V2 panel + outbound MCP | 6 | MCP discovery dies | Required |
| `backend/app/services/{drift_detector,plugin_catalog,extension_scanner,sub_agent_spawner,runtime_truth_registry}.py` | varies | misc | varies | Misc support; required for full picture | Keep |
| `backend/app/services/company_{context,mode,mode_providers,mode_replies}.py` + `pipeline_service.py` + `workstream_service.py` + `workstream_redirect_parser.py` | 9 | CompanyMode + Pipeline + Workstreams | 11 | Company / Pipeline / Workstream dies | Required (Phase 12 spine builds on these) |
| `backend/app/services/cost_router.py` | 3 | router | 2 | Cost-aware fallback weak | Keep |
| `backend/app/services/billing/cost_tracker.py` | 4 | `/billing` | 4 | Cost telemetry dies | Required |
| `backend/app/services/learning_service.py` | 3 | OODA REFLECT | 2 | Self-improvement claim collapses (currently in-memory only - see Backlog P0-03) | Keep + persist (PR-LEARN-01) |
| `backend/app/services/dcp_loader.py` | 2 | Quintessence | 2 | DCP injection dies | Required |
| `backend/app/services/subscription_service.py` | 4 | `/billing` + cost-guard | 5 | Subscription tier checks die | Required |
| `backend/app/services/project_service.py` | 5 | `/projects` | 6 | Projects die | Required |
| `backend/app/services/dynamic_model_service.py` | 3 | Settings > LLM hot-add | 3 | Hot-add API key dies | Required |
| `backend/app/services/intent_amplifier.py` | 2 | EXE planner | 2 | Intent classification weaker | Keep |
| `backend/app/services/archive.py` | 6 | every soft-archive surface | 5 | Soft-archive dies | Required |

### 1.3 MERGE_DUPLICATE (canonical pick required - resolved in §2)

| File pair | Recommended canonical | Founder OK? |
|---|---|---|
| `services/security/cve_intelligence.py` vs `services/security/cve_intel.py` | `cve_intel.py` (newer, used by `intel_fanout.py`) | Yes, choose canonical |
| `services/cognition/lens_router.py` vs `services/cognition/mind_router.py` | Founder pick (semantics overlap) | Yes |
| `services/connection_service.py` (V1) vs `services/connection_v2/*` (V2) | V2 canonical when flag flipped; V1 read-only behind Legacy until then | Yes (no flag flip in this PR) |
| `services/chat.py` vs `services/chat_orchestrator.py` | Both kept; rename `chat.py` to `chat_session_service.py` to remove confusion | Yes |
| `services/runtimes/adapters/mcp_bridge.py` (637 B stub) vs `mcp_bridge_runtime_adapter.py` | Adapter file canonical; delete stub | Yes |
| `api/v1/runtime` (singular) vs `api/v1/runtimes` (plural) | `runtimes` plural canonical; deprecate singular with 301 redirect | Yes |
| `services/heartbeat/work_queue.py` vs `services/autopilot/background_queue.py` | Defer unification until PR-NOTIF-FANOUT lands; document distinct purposes | Yes |
| `users.settings.developer_mode` vs system `Settings.developer_mode` | Rename user key to `developer_ui_mode`; system key canonical (PR-S6) | Yes |

### 1.4 HIDE_ADVANCED (keep functionality, hide surface)

| Capability | Surface today | Recommended action | Why hide |
|---|---|---|---|
| DCP-level controls (per-expert lens picks) | Chat mode picker (Quintessence) | Operator picks "QE", not 5 individual lenses; fold lens selection into auto-pick | Reduces 5-button picker to 1 |
| T0-T4 governance tier badges in chat UI | Per-message badges | Show only when tier >= 2; UNLEASHED hides all | Founder said "do not overwhelm in Unleashed" |
| Manual Council member selection | Chat mode QE | Auto-pick by intent; expose under Advanced toggle | Operator does not need to know |
| Manual NBMF tier promotion | Mind page | Dream handles; expose under Advanced | Tier promotion is rare |
| Webhooks tab | Settings (DEAD per Atlas I.3) | Hide behind Developer toggle until consumer wired | No backend |
| `evilbob` mode | Hidden activation only | Keep hidden; no menu surface | Founder-only |
| `/laevateinn/*` API surface | No UI | Keep API; no UI | Internal |
| `/missions/*` API surface | No UI today | Keep API; no UI until autonomous-sales surfaces | Internal |
| `/benchmark/*` API surface | No UI; only `run_*.py` scripts | Move scripts to `backend/scripts/benchmarks/`; keep API | Operator-only |
| `/souls/*` API surface | No UI | Keep API; no UI | Internal personas |
| `/department-{budget,message,policy,state}` sub-routers | No UI | Keep; no UI until DepartmentDetailPage ships | Internal |

### 1.5 DISABLE_COMING_SOON (render disabled with honest badge)

Per `FRONTEND_CONTROL_NECESSITY_AUDIT.md` and Backlog P2-07.

| Surface | Files | PR that wires |
|---|---|---|
| 8 of 9 `notif_*` toggles (sound, daily-digest, master, etc.) | `SettingsNotifications.tsx` | PR-NOTIF-FANOUT (heartbeat + runtime_disconnect emit) + future provider PRs (sound / email / digest) |
| 4 privacy toggles (memory_generation, search_past_conversations, improve_from_usage, location_metadata) | `SettingsPrivacy.tsx` | PR-S1 (privacy enforcement at MemoryService.write_memory + MemoryRecall) |
| 5 routing/billing toggles (local_first_routing, cost_aware_routing, monthly_budget, budget_alert_threshold, over_budget_action) | `SettingsLLM.tsx`, `SettingsBilling.tsx` | PR-S3 (budget vocab) + PR-S4 (routing wire) |
| `experimental_override` for non-callable runtimes | `MainBrainPanel.tsx` | Keep enabled; gate behind FOUNDER role; audit-traced |
| Plugins V2 Seed Providers (FOUNDER+) | `PluginsV2Panel.tsx` | Endpoint missing; disable button until Phase 6.5 |

### 1.6 ARCHIVE_LEGACY (move to .archive/, do not delete)

| File / dir | Reason |
|---|---|
| `backend/backend/.archive/agent_core_browser_agent.py` (and the empty parent) | Single-file orphan in nested duplicate path |
| `backend/app/services/billing/budget_manager.py` | Superseded by `cost_guard.py`; 0 importers |
| `backend/app/services/memory_import.py` | Superseded by `memory.py`; 0 importers |
| `backend/app/services/web_eyes.py` | Side-experiment; 0 importers |
| `backend/app/services/user_config.py` | Superseded by `core/config.py`; 0 importers |
| `backend/app/services/security/async_approval_manager.py` | Superseded by `approval.py`; 0 importers |
| `backend/app/services/agent_core/daemon.py` (`DaenaDaemon`) | CLI-only entry point; FastAPI bypass; 0 importers in lifespan |
| `backend/app/services/cognition/completeness_probe.py` | 0 importers; investigate intent first; if not adopted, archive |
| `backend/app/services/voice/realtime_voice_llm.py` | NotImplementedError on every method; archive until voice rebuild ships |
| `backend/run_*.py` (11 files) + `aime_*.{json,txt}` + result artifacts | Move to `backend/scripts/benchmarks/` (this is "archive in place" rather than `.archive/`) |
| `backend/repair-db*.sh` (2 files) | Move to `backend/scripts/maintenance/` with header banner |
| `backend/{tmp_endpoint_analysis,tmp_endpoint_analysis2}.json` | Move to `.tmp/` |
| `backend/bandit_*.json` (3 files) | Move to `.tmp/security-audits/` |
| `backend/{daena_dev2.db}` (the one not used) | Identify which is canonical; archive the other |

### 1.7 DELETE_CANDIDATE (proposed - separate DELETE-PR per item)

No file is deleted by this plan. Each entry below is the proposal that
will be executed via a separate `DELETE-PR-<name>` with founder
approval, archive-first protocol (§7), and a documented rollback.

| File | Reason | Risk if deleted | Required for delete |
|---|---|---|---|
| `backend/app/services/security/cve_intelligence.py` (assuming `cve_intel.py` chosen as canonical) | Duplicate | Verify no caller; remove imports first | Founder pick (§2) |
| `backend/app/services/runtimes/adapters/mcp_bridge.py` (637 B stub) | Stub; `mcp_bridge_runtime_adapter.py` is canonical | None (stub raises) | Founder OK |
| One of `cognition/lens_router.py` / `mind_router.py` | Likely duplicate | Verify no caller for non-canonical | Founder pick + grep |

### 1.8 DANGEROUS_LOCAL_ONLY (real, gated, never accidentally fire)

All under `backend/app/services/security/`. Only callable when EVILBOB
is active (3-gate fail-closed: KEY + LOCAL + role per
`evilbob_mode.detect_environment()`).

| File | Tier |
|---|---|
| `red_team_ops.py` (1,046 LOC; explicit `BACKGROUND PATH ONLY` comment) | T5 EVILBOB |
| `exploitation_queue.py` | T5 |
| `zero_day_engine.py` (SupplyChainAttackPlanner) | T5 |
| `osint_engine.py` (Apollo) | T5 |
| `opsec.py` | T5 |
| `credential_chain.py` | T5 |
| `mission_intelligence.py` | T5 |
| `report_tiers.py` T5 path | T5 |

**Action:** None this PR. The 3-gate is verified fail-closed in
Blindspot Inventory section 10.1. Add the pre-commit `EVILBOB_KEY`
guard from Blindspot cross-cutting C as a separate hardening PR.

### 1.9 STUB_REPLACE_OR_REFUSE (currently fakes success)

| File | Symptom | Action |
|---|---|---|
| `backend/app/services/voice/stt_pipeline.py:transcribe` | NotImplementedError on real call | Wrap caller with try/except returning honest "Voice provider not configured"; or implement |
| `backend/app/services/voice/tts_pipeline.py:synthesize` | NotImplementedError | Same |
| `backend/app/services/voice/outbound.send_*` | NotImplementedError | Same |
| `backend/app/services/voice/realtime_voice_llm.py` | NotImplementedError | Archive (1.6) |
| `backend/app/services/connection_v2/probe.py:59` | NotImplementedError | Implement probe fallback OR refuse the V2 flag flip until done |
| `backend/app/services/security/cognitive_scan_engine.py:2805` `scan_custom_operation` | Returns hardcoded "not implemented yet" | Refuse caller with explicit error; do NOT fake-success |
| Multiple `backend/app/api/v1/security_dashboard.py` endpoints | Return `{}` / `[]` on internal exception | Replace with explicit error channel (Rule 17) |
| `backend/app/api/v1/runtimes.py:177,183,191` | Return `[]` on exception | Same |

### 1.10 DOC_DRIFT (reality and docs disagree)

| Drift | Resolution |
|---|---|
| Atlas P0-04 said Dream Engine UNSCHEDULED | Closed by PR-DOC-DRIFT-FIX (commit `35c522b`); see Backlog P0-04 -> P2-DREAM-UI |
| Blindspot Inventory §3 quoted CLAUDE.md as containing literal "do not delete vault.py" rule | Closed by PR-DOC-DRIFT-FIX; project CLAUDE.md Rule 18 added with three real paths |
| Atlas headline counts under-counted backend (~318 services, 45 routers, 54 models, 42 env flags) | Closed by Atlas Appendix B.1 in PR-DOC-DRIFT-FIX |
| HeartbeatDaemon misclassified | Closed by PR-DOC-DRIFT-FIX; new Backlog P0-09 |

### 1.11 Dangerous local-only operator scripts (housekeeping)

| File | Recommended |
|---|---|
| `backend/repair-db.sh`, `backend/repair-db-v2.sh` | Move to `backend/scripts/maintenance/`; add header forbidding execution against production DSN |
| Three SQLite DBs at root (`daena.db`, `daena_dev.db`, `daena_dev2.db`) | Pick one canonical for dev; archive the others |

---

## 2. Duplicate resolution table

### 2.1 cve_intelligence.py vs cve_intel.py

| Field | Value |
|---|---|
| Canonical | `backend/app/services/security/cve_intel.py` |
| Duplicate | `backend/app/services/security/cve_intelligence.py` |
| Action | MERGE - port any unique helpers from `cve_intelligence.py` into `cve_intel.py`; ARCHIVE the older file |
| Migration path | (1) grep for `cve_intelligence` importers; (2) port any logic; (3) update imports; (4) ARCHIVE original to `backend/app/services/security/.archive/` |
| Tests needed | `tests/test_cve_intel_unit.py` covers both class APIs after merge |
| Founder approval | Yes (file delete) |

### 2.2 lens_router.py vs mind_router.py

| Field | Value |
|---|---|
| Canonical | **Founder pick required.** Mind page UX implies `mind_router` is the public name; `lens_router` reads as internal cognition-layer plumbing |
| Duplicate | The other |
| Action | RENAME the non-canonical to a clear sub-role (e.g. internal `_lens_selection.py`) OR ARCHIVE if truly redundant |
| Migration path | (1) Compare class APIs side-by-side; (2) document the intended split if both stay; (3) update imports if one is removed |
| Tests needed | New `test_router_routing_split.py` pinning canonical responsibilities |
| Founder approval | Yes (semantic decision) |

### 2.3 connection_service.py V1 vs connection_v2

| Field | Value |
|---|---|
| Canonical | `connection_v2/*` once `USE_CONNECTION_REGISTRY_V2=true` is flipped (NOT this PR) |
| Duplicate | `connection_service.py` |
| Action | Keep both. Hide V1 panels behind "Advanced / Legacy" tab; do NOT flip the flag until V2 probe stub (`connection_v2/probe.py:59`) is implemented |
| Migration path | (1) Wire honest status badges across V2; (2) ship probe fallback; (3) flip flag in dev only first; (4) deprecate V1 endpoints with 410 Gone after one cycle |
| Tests needed | `test_v1_v2_truth_consistency.py` to assert V2 returns matching truth for any V1-callable runtime |
| Founder approval | Yes (flag flip is staged) |

### 2.4 chat.py vs chat_orchestrator.py naming confusion

| Field | Value |
|---|---|
| Canonical | Both stay. `chat.py` is the persistence/CRUD service; `chat_orchestrator.py` runs the 10-stage pipeline. Naming is the only problem |
| Duplicate | None functionally |
| Action | RENAME `chat.py` to `chat_session_service.py` to remove the implication that it competes with the orchestrator |
| Migration path | (1) Rename file; (2) update imports (`grep -r "from app.services.chat import"`); (3) one commit with rename + import sweep |
| Tests needed | Existing tests pass after import rewrite |
| Founder approval | No (rename only, no behavior change) |

### 2.5 /scan vs /engagements scan launchers

| Field | Value |
|---|---|
| Canonical | One launcher (PR-4 in §8). T1-T2 routes to `/scan` quick flow; T3+ routes to `/engagements` governance-gated flow |
| Duplicate | `frontend/src/pages/ScanPage.tsx` and `frontend/src/pages/EngagementConsolePage.tsx` both have "start scan" UIs today |
| Action | REDESIGN_FLOW. Replace both launcher headers with a single `<ScanLauncher>` component already exists at `frontend/src/pages/scan/ScanLauncher.tsx`; route by tier |
| Migration path | (1) Move tier picker into `ScanLauncher` if not already; (2) `EngagementConsolePage` becomes T3+ continuation page (no launcher); (3) `ScanPage` becomes T1-T2 launcher; (4) Backend already routes uniformly through `scan_workflow.py` |
| Tests needed | `test_scan_launcher_tier_routing.py` (Playwright e2e: T1 -> /scan, T3 -> /engagements) |
| Founder approval | Yes (UX flow change) |

### 2.6 runtime singular vs runtimes plural

| Field | Value |
|---|---|
| Canonical | `/api/v1/runtimes/*` (plural) |
| Duplicate | `/api/v1/runtime/*` (singular, 7 routes) |
| Action | DEPRECATE singular. Add 308 Permanent Redirect from `/runtime/*` to `/runtimes/*` for 1 cycle; remove after frontend audit confirms no consumers |
| Migration path | (1) Audit `frontend/src/api/*.ts` for `/runtime/` (no `s`); (2) Add 308 redirects; (3) Schedule removal in next cycle |
| Tests needed | `test_runtime_singular_redirects.py` |
| Founder approval | Yes (API surface change) |

### 2.7 profile / display_name settings duplication

| Field | Value |
|---|---|
| Canonical | `account/AccountDetails.tsx` (full account surface) |
| Duplicate | `settings/SettingsGeneral.tsx` (display_name field) |
| Action | REMOVE display_name editor from SettingsGeneral; replace with read-only field plus link to `/account` |
| Migration path | (1) Delete the form section; (2) Add `<Link to="/account">Edit account details</Link>`; (3) Verify no other Settings-side consumer |
| Tests needed | Manual smoke test |
| Founder approval | No (cosmetic relocation) |

### 2.8 API keys in multiple settings surfaces

| Field | Value |
|---|---|
| Canonical | `account/AccountApiKeys.tsx` (full CRUD) |
| Duplicate | `settings/SettingsDeveloper.tsx` (references API keys) |
| Action | REMOVE API-key references from SettingsDeveloper; AccountApiKeys is canonical |
| Migration path | Same as 2.7 |
| Tests needed | Manual smoke test |
| Founder approval | No (cosmetic relocation) |

### 2.9 monthly_budget vocabulary mismatch

| Field | Value |
|---|---|
| Canonical | Single enum across API + BudgetManager (PR-S3) |
| Duplicate | `cost_guard.py:129` reads `Subscription.monthly_budget_usd`; UI writes `users.settings.monthly_budget`; over_budget_action enum mismatch (`warn|fallback|block` vs `warn_only|pause_tasks|free_models_only`) |
| Action | UNIFY enum (PR-S3). Cost-guard reads from `user.settings.monthly_budget` after a coalesce against `Subscription.monthly_budget_usd` for legacy rows |
| Migration path | (1) Define `OverBudgetAction` enum in `app/schemas/billing.py`; (2) Migrate existing rows in a one-shot script; (3) Update `cost_guard` reader; (4) Update UI option set |
| Tests needed | `test_budget_vocab_unification.py` (5 preflight calls with vs without budget cap) |
| Founder approval | Yes (schema migration) |

### 2.10 heartbeat daemon vs cron scheduler

| Field | Value |
|---|---|
| Canonical | Both stay. `cron_scheduler.py` runs scheduled jobs (DB-backed cron_runs); `heartbeat_daemon.py` runs the 24/7 health loop with operator-tunable interval |
| Duplicate | None functionally; both are real with distinct purposes |
| Action | DOCUMENT the split in `services/heartbeat/README.md` (new). Wire `heartbeat_daemon.start()` in lifespan (PR-HB-DAEMON-WIRE) so the controls in `SettingsHeartbeat.tsx` are honest |
| Migration path | PR-HB-DAEMON-WIRE (PR1 in §8) - (1) Add `await heartbeat_daemon.start()` to deferred init; (2) Persist daemon state to new `heartbeat_runs` table mirroring `cron_runs`; (3) Surface last-run-time on SettingsHeartbeat |
| Tests needed | `test_heartbeat_daemon_lifespan_start.py`, `test_heartbeat_runs_table_persistence.py` |
| Founder approval | Yes (lifespan change) |

---

## 3. Frontend route decision map

Per founder's 10-surface anchor (§0.1). For each route: keep / merge /
hide / remove later / redesign; backend dependency; current confidence
that the page is honest.

> Confidence scale: HIGH = page advertises only what the backend
> delivers; MED = some controls advertise capability the backend
> partially delivers (PARTIAL or STUB); LOW = page advertises
> capability the backend does not deliver (DEAD or fake).

### 3.1 Primary surfaces (founder's 10)

| Route | Decision | Backend deps | Confidence | Notes |
|---|---|---|---|---|
| `/chat` (`ChatPage.tsx`) | KEEP | `chat_orchestrator`, governance, model_router, audit, notification | HIGH | Spine; CMD/EXE shipped; voice integrated |
| `/dashboard` (`DashboardPage.tsx`) | KEEP | departments, agents, billing, audit | HIGH | Sunflower hive renders 10 depts; click-through to grid (Atlas F.8 intentional) |
| `/departments` (`DepartmentsPage.tsx`) + `/departments/:id` (`DepartmentChatPage.tsx`) | KEEP | departments, soul_engine, chat_orchestrator (with department_id bias) | MED | P3-06: verify `department_id` actually biases routing (not just cosmetic) |
| `/minds` (`MindsPage.tsx`) + `/minds/:id` (`MindDetailPage.tsx`) | KEEP + REDESIGN | NBMF memory, dream_engine, dcp_loader, soul_engine | MED | Should grow to be the "company / department intelligence + memory" surface; add Dream Engine status card (P2-DREAM-UI), DCP catalogue browser, NBMF tier visualization |
| `/security` (`SecurityDashboardPage.tsx` + `SecurityOverview` + `SecurityScans` + `SecurityShields` + `SecurityMissions` + `SecurityTools` + `SecurityScopePage`) | KEEP + REDESIGN (Manus-style live work window) | scan_workflow, cognitive_scan_engine, intel_fanout, asset_shield | MED | HANDS-OFF on `SecurityTools/Shields/Missions` per v3.7.0 lock; live work window is the new shape |
| `/scan` (`ScanPage.tsx`) + `/scan/launch` (`scan/ScanLauncher.tsx`) + `/scan/:id` (`ScanWalkthroughPage.tsx` + `scan/ScanReport.tsx` + `scan/ScanArtifacts.tsx`) | MERGE with /engagements per §2.5 | scan_workflow + zero_fp_gate + real_scanner | HIGH | One launcher routed by tier (PR-4 in §8) |
| `/engagements` (`EngagementConsolePage.tsx`) | REDESIGN (becomes T3+ continuation, NOT a launcher) | scan_workflow + governance + Asset Shield | MED | Today has its own launcher; merges into /scan in §2.5 |
| `/connections` (`ConnectionsPage.tsx` + `ConnectionsV2Panel.tsx` + `MainBrainPanel.tsx` + `McpServersPanel.tsx` (V1) + `McpServersV2Panel.tsx` + `PluginsCatalogBrowser.tsx` (V1) + `PluginsV2Panel.tsx`) | KEEP + COLLAPSE V1 to "Advanced / Legacy" | connection_v2, mcp_registry, runtimes/registry, oauth_service | MED | PR-3 in §8: hide V1 panels behind "Show legacy" toggle; V2 stays default |
| `/tasks` (`TasksPage.tsx`) | KEEP (sub-view of `/workstreams`) | execution_service, autopilot/background_queue | MED | After Workstream skeleton ships (PR-5 in §8), Tasks becomes a filter view |
| `/workstreams` (`WorkstreamsPage.tsx`) | KEEP + EXPAND (becomes the canonical "what is running") | workstream_service + execution_service + spine | LOW today | Page exists but skeletal; PR-5 in §8 fills it out per Execution Spine PRD §11.3 |
| `/files` (`FilesPage.tsx`) | KEEP | files endpoints, audit | HIGH | Phase 10b shipped; honest empty + meta |
| `/governance/audit` (`GovernanceAuditPage.tsx`) | KEEP (mostly internal; reachable on demand) | audit, hash chain verify endpoint | HIGH | PR-AUDIT-VERIFY shipped; deep verify + corrupt detection landed |
| `/governance/approvals` (`GovernanceApprovalsPage.tsx`) | KEEP (surface only when an approval pending) | approval, governance | HIGH | Surface in Header bell when approval queued |
| `/settings` (`SettingsPage.tsx` + 13 sub-tabs) | REDUCE (PR-2 in §8) | Many partial / dead consumers per §4 | LOW | The single largest credibility leak; see §4 |
| `/skills` (`SkillsPage.tsx`) | KEEP (first-class; founder amendment 2026-05-02) | skill_refinery (5 sub-services), `/api/v1/skill_refinery/*` (15 routes), tool_lifecycle | HIGH | Skill Refinery Phase 1+2 shipped; Phase 3 (governance integration for skill trust tiers + usage tracking + news monitor) is roadmap. Page must surface: skill list (T0 raw / T1 draft / T2 refined / T3 production / T4 compound), proposals queue (Backlog P0/P2 visibility gap), per-skill permission (Allow/Ask/Block), trust score, last-used time |

### 3.2 Sub-surfaces (intentional sub-views)

| Route | Decision | Backend deps | Confidence |
|---|---|---|---|
| `/account` (`AccountPage.tsx` + `AccountDetails.tsx` + `AccountApiKeys.tsx`) | KEEP (canonical for profile + API keys) | settings, dynamic_model_service | HIGH |
| `/projects` (`ProjectsPage.tsx`) + `/projects/:id` (`ProjectDetailPage.tsx`) | KEEP | project_service | HIGH (Phase 10b shipped honest empty) |
| `/policies` (`PoliciesPage.tsx`) | KEEP (mostly internal) | policy_compiler, policy_store | MED (P3-03 wants soft-archive on delete) |
| `/pipeline` (`PipelinePage.tsx`) | HIDE_ADVANCED (until autonomous-sales surfaces) | pipeline_service | MED |
| `/analytics` (`AnalyticsPage.tsx`) | KEEP_SUPPORTING | billing/cost_tracker, audit aggregations | MED |
| `/company-mode` (`CompanyModePage.tsx`) | KEEP | company_mode + missions + drafts | HIGH (Phase 10b closed last gap) |

### 3.3 Auth + legal (unchanged)

| Route | Decision |
|---|---|
| `/login`, `/register`, `/forgot-password`, `/reset-password`, `/auth/callback`, `/complete-profile`, `/terms`, `/privacy` | KEEP unchanged |

### 3.4 Hidden / removed surfaces

| Surface | Decision |
|---|---|
| `/heartbeat` standalone route | NONE EXISTS today; controls live in `SettingsHeartbeat.tsx`; KEEP location |
| Stand-alone Mind/Brain switcher | Folded into Connections > MainBrainPanel; do NOT add a separate route |

---

## 4. Settings reduction plan

Per founder: "Normal Settings should show only the controls a user can
trust. Advanced Settings can expose deeper founder/developer controls."

Source: `FRONTEND_CONTROL_NECESSITY_AUDIT.md` §3.1 (47 keys, 7 enforced
post-Phase-11). The plan is to ship the cleanup **before** wiring
remaining consumers, so the surface stops over-promising while real
work happens behind it.

### 4.1 Two-mode settings shape (target)

```
Settings  (default - "Normal")
+- General        small: name, theme, language
+- Models / Brain link to Connections (no controls here)
+- Memory         RAG status (honest), Dream status (honest)
+- Voice          on/off + provider
+- Notifications  in-app only (master + 2 enforced types)
+- Privacy        2 enforced toggles (PR-S1 wires the rest)
+- Billing        spend overview + 1 working budget control
+- About          version + support

Settings > Advanced  (toggle "Show advanced")
+- LLM            full provider matrix + routing toggles (Coming Soon)
+- Heartbeat      daemon controls (post-PR-HB-DAEMON-WIRE)
+- Governance     mode picker (Unleashed/Balanced/Governed) + tier visibility
+- Developer      developer_ui_mode + diagnostics
+- Shortcuts      keyboard map
```

### 4.2 Per-key triage

| Key | Real and consumed? | Action | Tab placement |
|---|---|---|---|
| `display_name` | Yes (account surface) | REMOVE from Settings; AccountDetails canonical | n/a (removed) |
| `theme`, `language`, `timezone` | Yes (UI store hydrates) | KEEP | General |
| `dark_mode` | Yes | KEEP | General |
| `chat_mode` (Standard/Council/Quintessence) | Yes (chat_orchestrator) | KEEP | General (or Chat) |
| `routing` (object) | Partial | KEEP behind Advanced > LLM | Advanced > LLM |
| `local_first_routing` | DEAD (PR-S4) | DISABLE_COMING_SOON badge | Advanced > LLM |
| `cost_aware_routing` | DEAD (PR-S4) | DISABLE_COMING_SOON badge | Advanced > LLM |
| `preferred_model` | Yes | KEEP | General |
| `heartbeat_config.*` (7 sub-keys) | DAEMON_MEMORY_ONLY (PR-H1 + PR-HB-DAEMON-WIRE) | Show with "daemon-memory only - Phase 11 PR-H1 persists" badge until wired | Advanced > Heartbeat |
| `monthly_budget` | PARTIAL (PR-S3) | Show with vocab-mismatch tooltip until wired | Billing |
| `over_budget_action` | PARTIAL (PR-S3) | Same | Billing |
| `budget_alert_threshold` | DEAD (PR-S3 + PR-NOTIF-FANOUT) | DISABLE_COMING_SOON | Billing |
| `notif_master` | Real | KEEP | Notifications |
| `notif_task_complete` | Real (PR-S2) | KEEP | Notifications |
| `notif_governance_rejection` | Real (PR-S2) | KEEP | Notifications |
| `notif_budget_alert` | Real (PR-S2.1) | KEEP | Notifications |
| `notif_privacy_blocked` | Real (PR-S2.1) | KEEP | Notifications |
| `notif_system_info` | Real (PR-S2.1) | KEEP | Notifications |
| `notif_heartbeat` | DEAD (PR-NOTIF-FANOUT) | DISABLE_COMING_SOON | Notifications |
| `notif_runtime_disconnect` | DEAD (PR-NOTIF-FANOUT) | DISABLE_COMING_SOON | Notifications |
| `notif_sound`, `notif_email`, `notif_daily_digest` | DEAD (no provider) | DISABLE_COMING_SOON or DELETE if no provider planned | Notifications |
| `memory_generation` | DEAD (PR-S1) | DISABLE_COMING_SOON | Privacy |
| `search_past_conversations` | DEAD (PR-S1) | DISABLE_COMING_SOON | Privacy |
| `improve_from_usage` | DEAD (no spec) | DISABLE_COMING_SOON or DELETE | Privacy |
| `location_metadata` | DEAD (no spec) | DISABLE_COMING_SOON or DELETE | Privacy |
| `storage_local` | DEAD (cloud disabled, default already local) | LEAVE AS-IS (correct shape) | Privacy |
| `voice_*` (provider, perms) | Real | KEEP | Voice |
| `developer_mode` (user) | NAMING COLLISION with system | RENAME to `developer_ui_mode` (PR-S6) + tooltip | Advanced > Developer |
| `governance_mode` | PARTIAL (inconsistently honored) | KEEP + add note that Unleashed still runs Shield | Advanced > Governance (or top of General) |
| `mcp_*` (5+ keys) | Real (V2 truth) | KEEP | Connections (not Settings) |
| Per-shortcut keymaps | Real | KEEP | Advanced > Shortcuts |

### 4.3 Settings cleanup order (PR-2 in §8)

1. Disable + Coming-Soon Badge on the 4 privacy toggles. (1 file, ~30 lines.)
2. Disable + Coming-Soon Badge on the 8 dead notification toggles. (1 file, ~40 lines.)
3. Tooltip on the 5 routing/billing toggles. (2 files, ~10 lines.)
4. Rename label "Developer Mode" -> "Developer UI mode" + tooltip.
5. Tooltip on 5 Heartbeat config controls clarifying daemon-memory-only.
6. Verify Plugins V2 Seed Providers button - if currently clickable, disable.
7. Move display_name editor + API keys from Settings to Account.
8. Introduce "Show advanced" toggle and re-bucket tabs per §4.1.

### 4.4 What NOT to do in PR-2

- Do NOT wire the dead toggles in PR-2. That is PR-S1 / PR-S3 / PR-S4 /
  PR-NOTIF-FANOUT / PR-H1. The wire-up shape is documented in
  `DAENA_FRONTEND_ACTION_DESIGN_RULEBOOK.md` §2.14.
- Do NOT delete the schema fields. The fields exist in
  `UserPreferencesUpdate`; preserving the schema is the only path that
  lets a future PR ship the consumer without a re-migration.

---

## 5. Governance simplification

Per founder: "Governance should mostly be internal. In Unleashed mode,
Shield/Hard Laws still run internally, but the UI should not overwhelm
the user."

### 5.1 User-facing labels (target)

Three modes only. The internal complexity (T0-T4 tiers, BehaviorGuard,
Asset Shield, Hard Laws, audit hash chain) stays load-bearing but
invisible by default.

| User label | Internal mapping | When this fires |
|---|---|---|
| **Fast / Unleashed** | `GovernanceMode.UNLEASHED` | Shield + Hard Law 5 (data exfiltration) + Hard Law 7 (tenant isolation) only. Audit always logs. Everything else allowed. |
| **Balanced** (default) | `GovernanceMode.BALANCED` | Shield + SecurityGate + auto-proceed for most actions. Approval only for truly dangerous operations (Tier >= 3 today). |
| **Governed** | `GovernanceMode.GOVERNED` | Full 10-stage pipeline. All 9 Hard Laws enforced. Approval queues for Tier >= 3. Suitable for enterprise/multi-tenant. |

### 5.2 What stays always-on (do not surface)

- **Shield** - PromptInjectionScanner + BehaviorGuard + Asset Shield
  (vault_adapter + egress_filter + consent_token). Cannot be disabled.
- **Hard Law 5** (data exfiltration block) - always.
- **Hard Law 7** (tenant isolation) - always.
- **Audit logging** - always; hash chain integrity verifiable on demand
  via `POST /governance/audit/verify` (shipped 2026-05-02 PR-AUDIT-VERIFY).
- **Asset Shield egress filter** on `api_keys / finance / identity /
  legal / founder_memory` - always.
- **EVILBOB three-gate** (KEY + LOCAL + role) - always (founder-only).

### 5.3 What stays surfaced (only when relevant)

| Surface | Visibility rule |
|---|---|
| Per-message governance tier badge | Visible only when tier >= 2 |
| Approval card | Visible only when an approval is pending |
| Audit page | Reachable from sidebar + Header (not on every page) |
| Council/QE downgrade notice | Toast only (not persistent) |
| Asset Shield "egress denied" toast | Always visible (rare; matters when it fires) |

### 5.4 What disappears from the chat surface in Unleashed

- T0-T4 tier internals.
- Per-message Hard Law check icons.
- Multi-step approval breadcrumbs (still emit audit; do not render).
- Plain-English Policy "rule that controlled this action" inline copy
  (move to Audit page expand).

### 5.5 Settings > Governance tab (Advanced)

| Control | Action |
|---|---|
| Mode picker (Fast / Balanced / Governed) | KEEP |
| "Always-on" descriptions of Shield + Hard Laws | KEEP (transparency) |
| Per-tier matrix display | HIDE behind "Show internal tier matrix" Advanced toggle |
| Per-Hard-Law toggle | DELETE if exists - Hard Laws are immutable |
| Audit chain verify button | KEEP - links to `/governance/audit?verify=true` |

---

## 6. Execution Spine alignment

Per `DAENA_EXECUTION_SPINE_PRD.md` §6: every user-initiated action
flows through 9 stages and produces one Workstream artifact. This
section maps each existing surface to the future spine without
breaking current flows.

### 6.1 The 9-stage spine (recap)

```
Intent -> Brain/Council -> Capability -> Governance/OODA ->
Execution -> Progress -> Artifact -> Audit -> Notification ->
Memory/Dream
```

### 6.2 How current surfaces map to Workstream

| Current surface | Today | After spine alignment | Workstream intent_type |
|---|---|---|---|
| Chat CMD message | Streams from `chat_orchestrator` | Spawns Workstream(intent_type=`chat_response_cmd`); orchestrator runs S0-S9 | `chat_response_cmd` |
| Chat EXE message | Same plus DaenaBot dispatch | Spawns Workstream(intent_type=`chat_response_exe`); EXE-side tools run inside S4 | `chat_response_exe` |
| Security scan from `/scan` launcher | `scan_workflow` runs outside Workstream | Spawns Workstream(intent_type=`scan_target`); scan_workflow runs as the S4 capability | `scan_target` |
| Security T3+ engagement from `/engagements` | Governance-gated `scan_workflow` | Spawns Workstream(intent_type=`engagement`) with Tier >= 3 in S3; same S4 | `engagement` |
| Department task from `/departments/:id` | DepartmentChatPage routes to `chat_orchestrator` | Spawns Workstream(intent_type=`department_task`) with `department_id` set in IntentRecord | `department_task` |
| Company Mode mission send | `company_mode` routes to drafts then send | Each send spawns Workstream(intent_type=`external_send`) with Asset Shield egress check in S3 | `external_send` |
| File process / extract | `files` endpoints call `chat_orchestrator` for extract | Spawns Workstream(intent_type=`process_file`) | `process_file` |
| Connection action (probe / enable / disable) | `connection_v2` API direct | Stays direct (lightweight; no Workstream needed) | n/a |
| Manual Task from `/tasks` | Direct `execution_service.create_task` | Spawns Workstream(intent_type=`task`); existing `/tasks` becomes a filter view of Workstream list | `task` |
| Autopilot continuation | `autopilot/background_queue` worker | Each enqueued continuation IS a Workstream with `parent_workstream_id` set | `continuation` |

### 6.3 Workstream as the canonical artifact

Per Council R3 lock and PRD §7. The Workstream model + state machine
ships in PR-SPINE-01; every existing artifact (Task, ScanReport, Draft,
File, ApprovalRequest) links via `artifact_refs` JSONB. Existing
`/tasks` and `/engagements` and `/missions` routes stay live as filter
views of `/workstreams` until the founder is ready to hide them.

### 6.4 Capability Registry as the missing keystone

Per PRD §8. Single `find(intent, role, governance_mode, tenant_id,
user_id)` over four sources (connection_v2 + skills + tool_lifecycle +
runtimes/registry). Cached 5-min TTL. Invalidated on V2 row change /
skill perm change / user setting change.

### 6.5 What the spine does NOT change

- The 10-stage chat pipeline stays internal to S4 for chat actions.
- Council / QE / DCP injection stays internal to S1 (Brain pick).
- Soul Engine stays internal to S4 prompt build.
- NBMF stays internal to S0 (recall) + S9 (write).
- Asset Shield stays internal to S3 (governance) + S4 egress checks.

---

## 7. Deletion policy

**No file is deleted by this plan or the first 5 PRs.** Each delete
goes through its own DELETE-PR with the protocol below. Per CLAUDE.md
Rule 2 ("NEVER delete - archive to .archive/. Developer mode toggle
for hard delete (ADMIN+ only).") and Rule 18 (three protected files).

### 7.1 Per-delete protocol (mandatory for every DELETE_CANDIDATE)

| Step | Action |
|---|---|
| 1. Backup / archive path | `git mv <path> <path>.archive/<YYYY-MM-DD>/` (path-preserving move under `.archive/`) |
| 2. Operation | `git mv` (preferred) or `git rm` only if the file already lives in `.archive/` after a prior step |
| 3. Tests to run | Full pytest sweep against the affected module's neighborhood + grep `from app.services.<name> import` to assert zero importers |
| 4. Rollback command | `git revert <commit>` (always) plus `git mv .archive/<...>/<file> <original_path>` for in-tree restore |
| 5. Founder approval | Required for every DELETE-PR - one-line OK in inbox.md or PR comment |

### 7.2 Per-archive protocol (lighter; for 1.6 entries)

| Step | Action |
|---|---|
| 1. Move to `.archive/` | `git mv backend/app/services/<X>.py backend/app/services/.archive/<X>.py` |
| 2. Update one importer | If any importer remains, update it to either inline the dependency or remove the import; do NOT leave dangling |
| 3. Smoke test | Run `pytest backend/tests/test_<X>_*.py` if any exists |
| 4. Founder approval | Required (archive is reversible but moves the file) |
| 5. Rollback | `git mv backend/app/services/.archive/<X>.py backend/app/services/<X>.py` |

### 7.3 Protected files (NEVER delete - Rule 18)

These are repeated here because they are the load-bearing files most
likely to be mistaken for cleanup candidates:

- `backend/app/services/security/asset_shield/vault_adapter.py`
- `backend/app/services/vault_migration.py`
- `backend/app/services/integrations/oauth_credentials_store.py`

Removing any breaks asset-shield egress filtering, vault rotation, or
OAuth-backed connections respectively. If consolidation is genuinely
needed, do it via DELETE-PR with explicit founder approval AND a
paired migration that preserves the encrypted blobs.

### 7.4 What this plan defers

The full ARCHIVE_LEGACY list in §1.6 (about 14 files plus the
benchmark scripts cluster) is NOT executed by this plan or by the
first 5 PRs. Each archive is its own small ticket scheduled after
PR-1 through PR-5 land.

---

## 8. First implementation PRs

Founder requested the first 5 PRs. Adopting the founder's preferred
order and shape verbatim, with effort and risk per Backlog estimates.

### PR 1 - PR-HB-DAEMON-WIRE (Heartbeat truth)

| Field | Value |
|---|---|
| Goal | Either start the HeartbeatDaemon properly OR remove the daemon-control UI. No fake heartbeat UI. |
| Files (start option) | `backend/app/main.py` (lifespan deferred init), `backend/app/services/heartbeat/heartbeat_daemon.py` (no logic change), `backend/migrations/versions/009_add_heartbeat_runs.py` (new), `backend/app/models/heartbeat_run.py` (new, mirror `cron_run.py`), `frontend/src/pages/settings/SettingsHeartbeat.tsx` (last-run-time card) |
| Files (remove-controls option) | `frontend/src/pages/settings/SettingsHeartbeat.tsx` (gate Pause/Resume/Stop behind "Daemon: stopped (start manually)" status banner) |
| Founder picks | Start option recommended (Backlog P0-09 fix shape #1). Remove-controls option acceptable if cost concerns. |
| Effort | 30 minutes (either option) |
| Risk | LOW. Lifespan change is local; tests cover both lifespan and SettingsHeartbeat |
| Tests | `test_heartbeat_daemon_lifespan_start.py` (asserts daemon.is_running after lifespan), `test_heartbeat_runs_table_persistence.py`, `test_settings_heartbeat_last_run_card.tsx` (Playwright) |
| Closes | Backlog P0-09, Atlas Appendix B.3, Rule 17 violation |
| Blast radius | Local to startup + SettingsHeartbeat page; no cross-cutting refactor |
| Dependencies | None |

### PR 2 - Settings cleanup (do not wire everything)

| Field | Value |
|---|---|
| Goal | First hide / disable / merge. Make Settings simple. Do NOT wire dead toggles in this PR. |
| Files | `frontend/src/pages/settings/SettingsPrivacy.tsx`, `SettingsNotifications.tsx`, `SettingsLLM.tsx`, `SettingsBilling.tsx`, `SettingsHeartbeat.tsx`, `SettingsDeveloper.tsx`, `SettingsGeneral.tsx`, `SettingsPage.tsx` (Show advanced toggle) |
| Effort | 2-3 hours (all UI-only) |
| Risk | LOW. Schema unchanged. UI badges + tooltips + relocations only. |
| Tests | Playwright: `test_settings_coming_soon_labels.tsx` (4 privacy + 8 notification + 5 routing/billing render as disabled with badge), `test_settings_account_redirects.tsx` (display_name + API key links navigate to /account), `test_settings_show_advanced_toggle.tsx` |
| Closes | Phase 10C-D Plan items 1-7, Atlas I.4 (Coming Soon labels), Atlas J.3 (Fake UI risk reduction) |
| Blast radius | Frontend only |
| Dependencies | None (PR 1 not required first) |

### PR 3 - Connections truth cleanup (V1 -> Legacy / Advanced)

| Field | Value |
|---|---|
| Goal | Keep V1 only behind "Legacy/Advanced" toggle. Make V2 the canonical truth in local/dev when safe. Do NOT flip the production flag. |
| Files | `frontend/src/pages/ConnectionsPage.tsx` (Advanced > Legacy toggle), `frontend/src/pages/connections/McpServersPanel.tsx` + `McpServersV2Panel.tsx` (V2 default; V1 behind toggle), `PluginsCatalogBrowser.tsx` + `PluginsV2Panel.tsx` (same), `frontend/src/api/connections.ts` (default V2 when env supports), `backend/app/core/config.py` (no change to default; document the dev override) |
| Effort | 3-4 hours |
| Risk | MED. Need V2 probe stub (`connection_v2/probe.py:59`) implemented OR honest "probe unavailable" status before this lands. Otherwise V2 panels show stale truth. |
| Tests | `test_v1_v2_consistency.py` (V2 truth matches V1 for any V1-callable runtime), `test_connections_legacy_toggle.tsx` (Playwright), `test_connection_v2_probe_fallback.py` |
| Closes | Backlog P2-01, Atlas F.1, Atlas I.2 |
| Blast radius | UI + backend probe handler; production flag NOT flipped |
| Dependencies | Implement `connection_v2/probe.py:59` first (small ticket, ~1h) OR ship probe-fallback to "probe unavailable" honest status |

### PR 4 - Security scan UX consolidation (Manus-style live window)

| Field | Value |
|---|---|
| Goal | One scan launcher (route by tier: T1-T2 quick, T3+ governance-gated). Manus-style live work window. Reports + remediation tasks reachable without leaving. |
| Files | `frontend/src/pages/scan/ScanLauncher.tsx` (canonical launcher; tier picker + governance preview), `frontend/src/pages/ScanPage.tsx` (replaces old launcher header with `<ScanLauncher>`), `frontend/src/pages/EngagementConsolePage.tsx` (becomes T3+ continuation page; no launcher), `frontend/src/pages/ScanWalkthroughPage.tsx` (live work window; SSE consumer), `frontend/src/pages/scan/ScanReport.tsx` (remediation tasks linked to /tasks creation), `backend/app/api/v1/scan.py` (no behavior change; route handler stays uniform) |
| Effort | 4 hours |
| Risk | MED. Two pages collapse into one flow; need careful redirect for any external links to `/engagements/launch`. |
| Tests | `test_scan_launcher_tier_routing.tsx` (Playwright: T1 -> ScanPage live window, T3 -> /engagements with governance-pre-set), `test_scan_walkthrough_live_window.tsx`, `test_scan_report_remediation_tasks.tsx` |
| Closes | Backlog P1-05, Atlas F.4 |
| Blast radius | UX flow change visible on demo; API path unchanged |
| Dependencies | None (HANDS-OFF respected for SecurityTools/Shields/Missions per v3.7.0 lock) |

### PR 5 - Workstream skeleton (Execution Spine without breaking Chat/Tasks/Scan)

| Field | Value |
|---|---|
| Goal | Start the Execution Spine. Workstream model + state machine + draft endpoint + minimal `/workstreams/:id` page. Do NOT migrate Chat/Tasks/Scan into the spine yet. |
| Files | `backend/migrations/versions/010_add_workstreams.py` (new), `backend/app/models/workstream.py` (new), `backend/app/services/workstream_service.py` (new; create / get / list / update_status / link_artifact), `backend/app/api/v1/workstreams.py` (new; POST /workstreams/draft, GET /workstreams/{id}, GET /workstreams, GET /workstreams/{id}/stream SSE), `frontend/src/pages/WorkstreamsPage.tsx` (existing skeletal -> proper list view), `frontend/src/pages/WorkstreamDetailPage.tsx` (new), `frontend/src/api/workstreams.ts` (new) |
| Effort | 4-5 hours |
| Risk | MED. New table + new SSE channel; need restart-recovery semantics from day one. |
| Tests | `test_workstream_model_migration.py`, `test_workstream_state_machine.py`, `test_workstream_restart_recovery.py` (Rule 17: in-flight workstreams marked `failed_due_to_restart` on lifespan boot), `test_workstream_draft_endpoint.py`, `test_workstreams_page.tsx` (Playwright) |
| Closes | PRD §13 TS-01 + TS-02, founds the work for PR-SPINE-02 through PR-SPINE-06 |
| Blast radius | New table + new endpoints + new pages. Existing Chat/Tasks/Scan unaffected. |
| Dependencies | None (Spine PRD already drafted; this is the first concrete PR from it) |

### PR sequencing rationale

1. PR 1 first because it is 30 min and closes the loudest current Rule 17 violation. Trust shipping cheaply.
2. PR 2 second because it is the largest credibility leak (founder explicitly said Settings has too many duplicated/useless controls). Hide before wire.
3. PR 3 third because Connections truth is the next-largest source of "two pages disagree about reality." Stage the V2 cutover cleanly.
4. PR 4 fourth because security scan duplication is high-visibility for any demo and touches the Manus-style work window founder asked for.
5. PR 5 last because the Workstream skeleton requires the previous four to have removed the worst contradictions. Spine on top of fake controls = prettier lies.

After PR 1 through 5 land, the next wave (PR-SPINE-02 through PR-SPINE-06,
PR-NOTIF-FANOUT, PR-S1, PR-S3, PR-S4, PR-LEARN-01, PR-DREAM-UI-CARD)
can run in parallel because the foundation is in place.

---

## 9. Stop and report

### 9.1 Top 10 things to KEEP (do not touch without ticket)

1. **`chat_orchestrator.py`** + the 10-stage chat pipeline.
2. **Shield + Hard Laws + Asset Shield** (always-on, do not surface in
   Unleashed).
3. **Hash-chained audit ledger** + `POST /governance/audit/verify`
   (shipped 2026-05-02).
4. **Council + Quintessence + DCP layer** (the moat over OpenClaw).
5. **NBMF 5-tier memory** + L2Q + trust scoring + Dream Engine
   (scheduled, runs every 15 min - reclassified 2026-05-02).
6. **Soul Engine + 10 named department personas** (identity + Departments).
7. **Capability Registry V2 model** (`connection_v2` + 6 boolean truth
   dims; canonical after flag flip).
8. **EVILBOB three-gate** (KEY + LOCAL + role; verified fail-closed).
9. **The 11 frontend primary surfaces** (Chat, Dashboard, Departments,
   Mind, Security, Connections, Tasks/Workstreams, Files,
   Governance/Audit, Settings, **Skills** - Skills added by founder
   amendment 2026-05-02).
10. **The three protected files** (`vault_adapter.py`,
    `vault_migration.py`, `oauth_credentials_store.py` - Rule 18) AND
    the **Skill Refinery cluster** (`backend/app/services/skill_refinery/*`
    - 5 sub-services + 15 API routes; load-bearing for Daena's
    institutional-knowledge accrual; do NOT touch without ticket).

### 9.2 Top 10 things to MERGE

1. **Scan launcher** - one component routed by tier (PR 4).
2. **Connections V1 panels** - hide behind "Legacy / Advanced" (PR 3).
3. **`cve_intelligence.py` + `cve_intel.py`** - canonical = `cve_intel.py`.
4. **`lens_router.py` + `mind_router.py`** - founder pick, then
   single canonical name.
5. **`mcp_bridge.py` stub + `mcp_bridge_runtime_adapter.py`** - delete
   stub, adapter canonical.
6. **`api/v1/runtime` + `api/v1/runtimes`** - plural canonical, 308 redirect.
7. **`display_name` editor** - AccountDetails canonical, remove from
   SettingsGeneral (PR 2).
8. **API keys editor** - AccountApiKeys canonical, remove from
   SettingsDeveloper (PR 2).
9. **`monthly_budget` vocabulary** - one enum across API + BudgetManager
   (PR-S3, scheduled).
10. **HeartbeatDaemon control surface** - either start the daemon OR
    remove the controls; no fake UI (PR 1).

### 9.3 Top 10 things to HIDE (Advanced / internal / Coming Soon)

1. **T0-T4 governance tier internals** - hide behind "Show internal
   tier matrix" Advanced toggle.
2. **Per-message Hard Law check icons** in Unleashed mode.
3. **DCP-level lens picker** - operator picks "QE", lens auto-pick.
4. **Manual Council member selection** - auto-pick by intent.
5. **Manual NBMF tier promotion** - Dream handles.
6. **Webhooks tab** in Settings.
7. **EVILBOB mode** - founder-only; never surface.
8. **`/laevateinn`, `/missions`, `/benchmark`, `/souls`,
   `/department-{budget,message,policy,state}` API surfaces** -
   internal; no UI.
9. **All 8 dead `notif_*` toggles + 4 dead privacy toggles + 5 dead
   routing/billing toggles** - DISABLE_COMING_SOON badge until wired
   (PR 2).
10. **V1 connection panels** - behind "Show legacy" toggle (PR 3).

### 9.4 Top 10 DELETE_CANDIDATE (proposed; NOT deleted in this plan)

Each requires a separate DELETE-PR with founder approval per §7.

1. `backend/backend/.archive/agent_core_browser_agent.py` (and the
   nested duplicate parent dir).
2. `backend/app/services/billing/budget_manager.py` (0 importers;
   superseded by `cost_guard.py`).
3. `backend/app/services/memory_import.py` (0 importers; superseded
   by `memory.py`).
4. `backend/app/services/web_eyes.py` (0 importers; side-experiment).
5. `backend/app/services/user_config.py` (0 importers; superseded by
   `core/config.py`).
6. `backend/app/services/security/async_approval_manager.py`
   (0 importers; superseded by `approval.py`).
7. `backend/app/services/agent_core/daemon.py` `DaenaDaemon`
   (CLI-only; FastAPI bypass).
8. `backend/app/services/runtimes/adapters/mcp_bridge.py` (637 B stub;
   `mcp_bridge_runtime_adapter.py` canonical).
9. One of `backend/app/services/security/cve_intelligence.py` /
   `cve_intel.py` after canonical pick.
10. `backend/{tmp_endpoint_analysis,tmp_endpoint_analysis2}.json` and
    `backend/bandit_*.json` (3 files) - move to `.tmp/`.

### 9.5 First 5 PRs (effort + risk + after that)

| PR | Effort | Risk | Closes |
|---|---|---|---|
| PR 1 - PR-HB-DAEMON-WIRE | 30 min | LOW | Backlog P0-09; Atlas Appendix B.3; Rule 17 violation |
| PR 2 - Settings cleanup | 2-3 h | LOW | Atlas I.4 + I.5 (Coming Soon + Delete labels for 17 settings); Phase 10C-D items 1-7 |
| PR 3 - Connections truth cleanup | 3-4 h | MED (probe stub blocker) | Backlog P2-01; Atlas F.1 + I.2 |
| PR 4 - Security scan UX consolidation | 4 h | MED (UX flow change) | Backlog P1-05; Atlas F.4 |
| PR 5 - Workstream skeleton | 4-5 h | MED (new table + SSE) | PRD §13 TS-01 + TS-02; founds PR-SPINE-02 through PR-SPINE-06 |

**Total first-wave effort:** approximately 14-17 hours = 2 working days
at founder pace, or 1 day with parallel cross-AI delegation
(Codex on PR 1 + PR 2 single-file UI; Claude on PR 3 + PR 4 + PR 5
multi-file architecture).

### 9.6 What this plan does NOT do

- **Does not modify any product code.** Zero `.py` or `.tsx` files
  edited.
- **Does not delete any file.** All deletes scheduled, not executed
  (per §7).
- **Does not flip `USE_CONNECTION_REGISTRY_V2`.** PR 3 stages the cutover
  in dev only.
- **Does not start the HeartbeatDaemon.** PR 1 documents the fix shape;
  the implementation PR is separate.
- **Does not run any tests.** No code touched.
- **Does not create any DELETE-PRs.** The deletion list is a queue, not
  an execution.
- **Does not touch the protected three files** (Rule 18).
- **Does not change CLAUDE.md.** The protocol that governs this plan
  is already in place.

### 9.7 Founder approval needed before starting any PR

| Decision | Why founder must pick |
|---|---|
| PR 1 shape: Start daemon vs Remove controls | Both close the gap; founder picks based on cost/visibility preference |
| §2.2 lens_router vs mind_router canonical | Semantic decision; both are real cognition modules |
| §2.3 V1 -> V2 cutover cadence | Production flag flip is high-risk; founder times it |
| §2.5 ScanPage / EngagementConsolePage merge | UX flow change visible on every demo |
| §1.4 collapse of T0-T4 tier UI in Unleashed | "Do not overwhelm" was the directive; founder confirms what stays |
| Each DELETE-PR | Per §7 protocol, every delete requires founder OK |

---

**End of plan.**

This document is the queue. Each PR in §8 is a one-issue ticket with
its own short report when shipped. PR 1 (PR-HB-DAEMON-WIRE) is the
recommended first ship.
