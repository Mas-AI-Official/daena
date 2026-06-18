# Daena Execution Spine — Product Requirements Document

**Date:** 2026-05-01
**Author:** Claude Code (Opus 4.7) under founder-direction
**Companion docs:** `DAENA_ARCHITECTURE_ATLAS.md` (sections G + H + I),
`DAENA_SYSTEM_GRAPH.mmd`, `DAENA_ARCHITECTURE_GAP_BACKLOG.md`
**Stance:** documentation-only PRD. No product code modified.

> **Thesis:** Daena's intelligence stack is rich and largely
> wired. Daena's user surface is fragmented across overlapping
> primitives (Tasks, Workstreams, Pipeline, Engagements, Company
> Mode, Chat-EXE, Scan, Files). This PRD specifies a **single
> canonical action lifecycle** — the Execution Spine — that every
> user-initiated action flows through, while preserving every
> intelligence layer underneath.

---

## 1. Goals

1. **One action lifecycle** the operator learns and recognises across
   every surface (chat, scan, company-mode, file process, draft
   email, manual task creation, autopilot continuation).
2. **One artifact** per action (the `Workstream` per Council R3
   lock) — surfaces a single state machine the operator follows.
3. **One launcher** (`+ New action`) that classifies intent and
   routes to the right capability without making the operator
   choose a surface up front.
4. **One status surface** (the bell + the Workstream live console)
   that shows progress, blockers, governance gates, audit links,
   and outputs in one place.
5. **No advertised capability without a real consumer.** Every
   button maps to a backend that actually does the thing or carries
   an honest "Coming Soon" label.

## 2. Non-goals

- **Removing intelligence layers.** The Council, Quintessence, OODA,
  Soul Engine, Asset Shield, Plain-English Policy Compiler, NBMF,
  Dream Engine all stay. They become more visible OR more invisible
  per founder choice — not removed.
- **Changing governance defaults.** Shield always-on, Hard Laws
  immutable, Asset Shield always-on. The new Spine inherits these.
- **Multi-tenant SaaS rebuild.** Single-founder local-first remains
  the primary deployment per `LOCAL_FIRST_DAENA_ARCHITECTURE.md`.
  Multi-tenant code paths stay live but unused.
- **Killing CMD vs EXE distinction.** Both modes traverse the same
  spine; CMD short-circuits at the "Runtime / Tool execution" stage
  (plan-only output).
- **Cloud Run resume.** Per `CLOUD_DEPLOYMENT_PAUSED_DECISION.md`,
  cloud is paused; the Spine is local-first first.
- **Renaming patent IP.** `sunflower-honeycomb` stays as the codebase
  internal name (per `CLAUDE.md` Rule 11). External brand =
  PhiLattice.

## 3. User stories

### 3.1 As the founder, I want to launch any action from one place.

> *"I open Daena. I click `+ New action`. I describe what I want
> in plain English. Daena classifies the intent, picks a brain,
> shows me what it's about to do, and either acts (EXE) or drafts
> (CMD). It surfaces one Workstream I can watch, pause, redirect,
> or close. I never have to remember whether a request is a 'Task,'
> 'Mission,' 'Engagement,' or 'Workstream' upfront."*

### 3.2 As the founder, I want to know what Daena is doing in real time.

> *"I see the Workstream's current OODA phase (Observe / Orient /
> Decide / Act / Reflect), the model picked, the governance tier
> resolved, the Council members invoked (if QE), and progress per
> step. When something blocks, I see the blocker copy + the policy
> rule that triggered it + a one-click 'redirect' affordance."*

### 3.3 As the founder, I want every action to leave a trail.

> *"Every state-changing step writes a hash-chained audit row.
> Every notification surfaces in the bell. Every artifact (file,
> draft, scan report, code change) is reachable in two clicks from
> the Workstream. The audit page lets me verify chain integrity."*

### 3.4 As the founder, I want approvals and external sends to never surprise me.

> *"Tier-3 actions land in /governance/approvals. External sends
> (LinkedIn, email, scan against third-party target) require my
> explicit approval. The approval card shows: action, target,
> blast-radius, governance tier, suggested response, deny reason
> templates. Once approved, the Workstream resumes; once rejected,
> it terminates with the reason logged."*

### 3.5 As the founder, I want Daena to learn from what I do.

> *"After every Workstream completes, the Reflect phase writes an
> agent-experience row to NBMF (tenant-scoped, never my user
> content). Dream Engine consolidates patterns nightly. Successful
> patterns become Skills via Refinery. The next time I face a
> similar problem, the Skill is already loaded into the prompt."*

### 3.6 As the operator, I want the surface to be honest.

> *"If a setting toggle isn't read by any backend service, it
> doesn't render — or it renders disabled with a 'Coming soon —
> Phase X' badge that names the PR. No more placebo controls."*

## 4. Scope

### 4.1 In scope (this PRD)

- The canonical 9-stage Execution Spine (specified §6).
- The Workstream as the canonical artifact (specified §7).
- The Capability Registry contract that fans out to 4 sources
  (specified §8).
- The progress / SSE event taxonomy (specified §9).
- The audit + notification emit contract per spine stage
  (specified §10).
- Acceptance criteria + tests (specified §13).

### 4.2 Out of scope (deferred)

- Implementation PRs (this PRD specifies the contract; PRs follow).
- New intelligence layers. (eDNA wire-up is a separate Phase 12 PR.)
- Cloud Run resume.
- Mobile / responsive surface.
- New runtime adapters.
- Changes to soul vault format (see §11.4 for forward compat).

## 5. Hard constraints

1. **Backwards compatibility.** Every existing endpoint stays live;
   the Spine wraps + supersedes them. Hard cutover comes only when
   100% of consumers migrate.
2. **No data loss.** Existing Task, Engagement, Mission, Draft
   rows remain queryable; the Workstream layer references them.
3. **No new intelligence-layer dependencies.** The Spine is a
   presentation + orchestration refactor, not new ML / new model.
4. **No external send without approval.** Asset Shield egress
   filter remains the gate.
5. **Single founder deployment supported.** Multi-tenant code
   paths stay live but the Spine UX is single-operator-first.

---

## 6. The Execution Spine (9 stages)

### 6.1 Stages (one user-initiated action = one traversal)

```
S0  CLASSIFY      Intent → IntentRecord (action_type, target, options)
S1  BRAIN         Three-Tier Escalation Router → BrainPlan
S2  CAPABILITY    Capability Registry lookup → CapabilityResolution
S3  GOVERN        SecurityGate + GovernanceEngine + OODA Observe → GovernanceDecision
S4  PLAN/EXECUTE  CMD: produce Plan; EXE: invoke runtime + tools (OODA Decide+Act)
S5  PROGRESS      SSE events emitted to /workstreams/:id/stream
S6  ARTIFACT      Result persisted (Workstream.result + linked artifacts)
S7  AUDIT         GoaAuditEvent row per state-changing step (hash-chained)
S8  NOTIFY        NotificationService.emit (gated by per-event flag)
S9  LEARN         OODA Reflect → store_experience to NBMF + queue Dream cycle
```

Every stage is **idempotent on retry**. Every stage emits **at least
one audit row** (S7) when it produces a state change. Every stage
respects **CMD vs EXE** (S4 short-circuits to plan-only in CMD).

### 6.2 Mapping to existing implementation

| Spine stage | Existing service file(s) | New work for Spine |
|---|---|---|
| S0 CLASSIFY | `query_understanding.py` | Generalise from chat-only to all entry points (scan, company-mode, file, draft) |
| S1 BRAIN | `chat_orchestrator.py` Stage 5 + Three-Tier Router | Surface BrainPlan in SSE so operator sees who got picked |
| S2 CAPABILITY | `connection_v2` + `Skill` + `tool_lifecycle/` + `runtimes/registry.py` | Add `registry.find(intent, role, governance_mode)` over 4 sources |
| S3 GOVERN | `security_gate.py` + `governance.py` + `cognition/ooda_engine.py` Observe | Always run OODA Observe (currently EXE-only); produce GovernanceDecision dataclass |
| S4 PLAN/EXECUTE | CMD branch in `chat_orchestrator.py` + EXE via `execution_service.py` + DaenaBot | Generalise execution to non-chat surfaces (scan, company-mode all flow through here) |
| S5 PROGRESS | Existing chat SSE | Standardise event taxonomy across all surfaces (§9) |
| S6 ARTIFACT | `Workstream` + `Task` + `Mission` + `Draft` + `SecurityReport` | Workstream becomes the wrapper; existing artifacts link to it |
| S7 AUDIT | `audit.py` AuditService.log_decision | Cross-cutting requirement: every S0-S8 step emits |
| S8 NOTIFY | `notification_service.py` (PR-S2 + PR-S2.1) | Add fan-out for heartbeat + runtime_disconnect (PR-NOTIF-FANOUT) |
| S9 LEARN | `cognition/ooda_engine.py` REFLECT + `dream_engine.py` + `learning_service.py` | Wire LearningService to PERSIST (currently in-memory only); schedule Dream cycle |

---

## 7. Workstream — the canonical artifact

### 7.1 Schema

```python
class Workstream(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    id: UUID PK
    tenant_id: UUID FK
    user_id: UUID FK              # initiator
    title: str(200)               # human-readable goal
    intent_record_id: UUID FK     # → IntentRecord (S0 output)
    brain_plan_id: UUID FK        # → BrainPlan (S1 output)
    capability_resolution_id: UUID FK  # → CapabilityResolution (S2)
    governance_decision_id: UUID FK    # → GovernanceDecision (S3)
    status: WorkstreamStatus      # see §7.2
    phase: OodaPhase              # OBSERVE/ORIENT/DECIDE/ACT/REFLECT
    blocker: str | None           # human-readable if BLOCKED
    next_step: str | None         # human-readable next intent
    primary_runtime: str          # e.g. "claude_code"
    governance_tier: int          # 0-4
    parent_workstream_id: UUID | None   # if spawned by another
    result_summary: str | None    # one-line outcome
    artifact_refs: dict           # {scan_report_id, draft_id, file_id, task_ids}
    cost_usd: float
    tokens_in: int
    tokens_out: int
    started_at: datetime | None
    completed_at: datetime | None
```

### 7.2 State machine

```
PENDING        → workstream created, awaiting first OBSERVE
OBSERVING      → OODA Observe running (recall, status check, file scan)
ORIENTING      → MetaReasoner picking frameworks
DECIDING       → Council/QE producing strategy (or single mind --effort low)
ACTING         → executing plan via runtime + tools
WAITING_APPROVAL → governance Tier 3+; blocked on /governance/approvals
BLOCKED        → other (rate-limit, missing capability, scope-deny)
PAUSED         → operator-paused
COMPLETE       → success; result persisted; audit + notify done
FAILED         → unrecoverable; error logged; no retry without operator
ARCHIVED       → soft-deleted via SoftDeleteMixin
```

Transitions:
- `PENDING → OBSERVING → ORIENTING → DECIDING → ACTING → COMPLETE`
- Any state → `BLOCKED` / `WAITING_APPROVAL` / `FAILED` / `PAUSED`
- `BLOCKED / WAITING_APPROVAL / PAUSED → ACTING` on operator action
- `COMPLETE / FAILED → ARCHIVED` on soft-delete

### 7.3 Linked artifacts

The `artifact_refs` JSONB carries IDs of the side-effect artifacts:

```json
{
  "scan_report_id": "...",
  "draft_ids": ["..."],
  "file_ids": ["..."],
  "task_ids": ["..."],
  "approval_request_id": "...",
  "audit_event_ids": ["..."],
  "notification_ids": ["..."]
}
```

The frontend Workstream page renders these as "Artifacts produced"
with one-click navigation (Rule 17.3 — every produced artifact
reachable in ≤ 2 clicks).

---

## 8. Capability Registry contract

### 8.1 Single logical surface

```python
class CapabilityRegistry:
    async def find(
        self, *, intent: str, role: str, governance_mode: GovernanceMode,
        tenant_id: UUID, user_id: UUID,
    ) -> CapabilityResolution: ...
```

`CapabilityResolution`:

```python
@dataclass
class CapabilityResolution:
    runtime_id: str | None        # cli_runtime / provider slug
    skill_ids: list[str]          # ranked skill matches
    mcp_server_keys: list[str]    # MCP server keys that expose tools matching intent
    tool_specs: list[ToolSpec]    # tool schemas to inject into LLM prompt
    fallback_chain: list[str]     # runtime IDs to try in order on failure
    rationale: str                # one-line "why this picked"
    risk_factors: list[str]       # e.g. ["external_send", "destructive"]
```

### 8.2 Sources fanned over

1. **`connection_v2` table** (V2 canonical for runtimes / MCP /
   plugins / providers — 6 boolean truth dims + per-dim
   failure_at). Filter by `callable=true AND not archived`.
2. **`Skill` table** — semantic match on description; rank by
   permission (Allow/Ask/Block) per user.
3. **`tool_lifecycle/tool_discovery.py` TOOL_CATALOG** (~170 tools
   hardcoded; future: dynamic registry).
4. **`runtimes/registry.py`** in-memory adapter table (HealthStatus
   filter).

### 8.3 Ranking rules (default)

- Local before cloud (locality 0.25 weight per `model_router.py`)
- Permission "Allow" before "Ask" before "Block"
- Trust score: skills with usage_success_rate > 0.8 boosted
- Cost: cheaper provider wins ties when `cost_aware_routing=true`
  (PR-S4 wires this from user.settings)

### 8.4 Caching

5-minute TTL on full resolution. Invalidate on:
- `connection_v2` row change (probe completed, archived, etc.)
- Skill permission change
- User setting change touching routing flags

---

## 9. Progress / SSE event taxonomy

### 9.1 Channel

`GET /api/v1/workstreams/{id}/stream` (SSE).

### 9.2 Event types

```
spine.classified        { intent_record_id, action_type }
spine.brain_picked      { brain_plan_id, primary_runtime, council_members[], reasoning_mode }
spine.capability_resolved { capability_resolution_id, skill_ids, runtime_id, rationale }
spine.governance_decided  { governance_decision_id, tier, result, hard_laws_checked[] }
spine.ooda_phase        { phase: OBSERVE|ORIENT|DECIDE|ACT|REFLECT, summary }
spine.thinking          { content }                  # extended-reasoning trail
spine.tool_call         { tool, args, status }       # EXE only
spine.delta             { content }                  # LLM stream chunk
spine.governance_notice { notice, action_required }  # mid-flight policy event
spine.approval_required { approval_request_id, blocker }
spine.artifact_emitted  { kind: scan_report|draft|file|task, ref_id }
spine.audit_emitted     { audit_event_id, action_type }
spine.notification_emitted { notification_id, type }
spine.completed         { result_summary, cost_usd }
spine.failed            { error, recoverable: bool }
spine.paused            { reason }
spine.resumed           {}
```

### 9.3 Order guarantee

Per Workstream, events arrive **in monotonic causal order**. The
frontend may render them late but must NOT reorder. (Same SSE
pattern as today's chat stream.)

---

## 10. Audit + notification contract

### 10.1 Audit emit per stage (mandatory)

Every Spine stage that mutates state emits a `GoaAuditEvent` with
the appropriate `action_type`. Stage 7 is the cross-cutting
mandatory check; the audit is not "after" the spine — it is woven
through it.

| Stage | action_type | result |
|---|---|---|
| S0 CLASSIFY | `spine.intent_classified` | OK |
| S1 BRAIN | `spine.brain_picked` | OK / DOWNGRADED |
| S2 CAPABILITY | `spine.capability_resolved` | OK / NO_MATCH |
| S3 GOVERN | resolved governance action_type (e.g. `LLM_CALL`, `EXTERNAL_SEND`) | ALLOWED / BLOCKED / APPROVAL_REQUIRED |
| S4 PLAN/EXECUTE | varies by intent (e.g. `tool.executed`, `file.written`) | OK / FAILED |
| S6 ARTIFACT | `workstream.artifact_emitted` | OK |
| S8 NOTIFY | NOT audited (notifications are routine UX, per PR-S2 §6.7) | — |
| S9 LEARN | `dream.merged`, `dream.promoted` (Dream cycle) | OK |

### 10.2 Hash chain (Hard Law #9)

Each `GoaAuditEvent` row chains to the previous via `prev_hash`.
The Spine adds a **periodic verification job** (24h cron) that
walks the chain end-to-end and flags breaks (operator deletion,
silent corruption). New endpoint:
`POST /api/v1/governance/audit/verify` returns
`{verified: true, last_break: null}` or
`{verified: false, last_break_at: ts, last_break_index: n}`.

### 10.3 Notification emit (S8)

Per Phase 11 PR-S2 + PR-S2.1 spec. Notification types:
`task_complete` (covers Workstream COMPLETE), `budget_alert`,
`governance_rejection`, `heartbeat`, `runtime_disconnect`,
`privacy_blocked`, `system_info`. Each gated by
`users.settings.notif_<type>` flag.

The Spine adds:
- `workstream.completed` notification on S6 success (mapped to
  `task_complete` event type).
- `workstream.blocked_by_governance` notification on S3 BLOCKED
  (mapped to `governance_rejection`).
- `workstream.approval_required` notification on S3
  APPROVAL_REQUIRED (no current type — adds new gated flag
  `notif_approval_required`).

---

## 11. Frontend contracts

### 11.1 The "+ New action" launcher

A single button in the persistent header. Clicking opens a
**command palette** (Ctrl+K already bound) with:
- text input for plain-English intent
- recently-used actions (last 5 Workstreams)
- "popular" actions (Top 5 by usage in last 30d)

The launcher hits `POST /api/v1/workstreams/draft` which runs
S0 (classify) + S1 (brain pick) + S2 (capability resolve) +
S3 (governance pre-check) and returns a **dry-run preview** of
what Daena is about to do. The operator confirms → S4 begins.

### 11.2 Workstream page (canonical)

`/workstreams/:id` — the operator's "what's happening" surface.
Sections:
1. **Header:** title, status badge, OODA phase pill, brain icon,
   governance tier badge.
2. **Live timeline:** SSE event log with each spine stage marker.
3. **Reasoning panel** (collapsed by default): thinking events,
   Council member responses (anonymised in QE), DCP lens picks.
4. **Artifacts:** linked scan reports, drafts, files, tasks,
   approval cards.
5. **Audit links:** "View 7 audit events for this Workstream"
   → `/governance/audit?workstream_id=...`.
6. **Actions:** Pause / Resume / Redirect / Archive.

### 11.3 Workstream list

`/workstreams` — replaces TasksPage as the primary "what's running"
view. Columns: title, status, phase, brain, started_at, cost.
Filters: status × tenant × user × date range × intent type.

Existing `/tasks` becomes a sub-view filtered to
`workstream.intent_type='task'` (or hidden behind Advanced).

### 11.4 Honesty rules (Rule 17 in the Spine)

For every UI control:
1. **Persistent state declaration:** the control names the DB
   column / table / file it writes to.
2. **Failure surface:** if the backend rejects, an inline error
   shows with the rejection reason from the audit row.
3. **Coming Soon contract:** if no backend consumer exists, the
   control is `disabled` with a Badge naming the PR (e.g. "PR-S4
   wires this — currently persists only").

`SettingsNotifications.tsx` (Phase 11 PR-S2) is the model:
5 toggles flipped from amber Coming-Soon to green
"Enforced by backend"; the other 4 (sound / email / digest /
desktop master) stay disabled with reason.

---

## 12. Action state machine — formal

Reuses §7.2 Workstream states. Additional formal transitions
required by the Spine:

```
At S0 CLASSIFY:   intent text → IntentRecord.action_type ∈
                  {chat_response, scan_target, draft_outreach,
                   process_file, deploy_change, query_data,
                   continue_workstream, ...}
                  (~20 canonical action_type strings)

At S3 GOVERN:     GovernanceDecision.result ∈
                  {ALLOWED, NOTIFY, APPROVAL_REQUIRED, BLOCKED}
                  → drives state transition

At S4 EXECUTE:    if CMD → result is plan; transition to COMPLETE
                  if EXE → tool calls execute; OODA loops if needed

At S9 LEARN:      OODA REFLECT → store_experience()
                  + queue Dream cycle (now scheduled per PR-DREAM-01)
```

---

## 13. Tests + acceptance criteria

### 13.1 Backend tests

| Test ID | What it pins |
|---|---|
| TS-01 | Workstream model migration + restart-recovery (Rule 17) |
| TS-02 | S0 CLASSIFY → IntentRecord with 20 canonical action_types covered |
| TS-03 | S1 BRAIN downgrade emits `orchestrator.council_downgraded_to_standard` audit |
| TS-04 | S2 CAPABILITY returns ranked + cached resolution in <50ms warm |
| TS-05 | S3 GOVERN respects per-tier matrix; BLOCKED transitions to BLOCKED state + notification |
| TS-06 | S4 EXE runs tool via DaenaBot; CMD short-circuits to plan |
| TS-07 | S5 PROGRESS SSE event order monotonic per Workstream |
| TS-08 | S6 ARTIFACT links propagate to artifact_refs JSONB |
| TS-09 | S7 AUDIT emits exactly one row per state-changing stage |
| TS-10 | S8 NOTIFY respects all 7 notif_* flag (cross-tenant isolation) |
| TS-11 | S9 LEARN writes agent-experience to NBMF (tenant-scoped, NOT user-content) |
| TS-12 | Dream cycle runs nightly + emits MERGE/PROMOTE/CONTRADICT/SYNTHESIZE/DECAY audit |
| TS-13 | Hash-chain verify endpoint detects deletion + corruption |
| TS-14 | OODA REFLECT does NOT bump `memory_generation` privacy gate (uses store_experience path, not store) |

### 13.2 Frontend tests

| Test ID | What it pins |
|---|---|
| TF-01 | "+ New action" launcher renders + accepts plain-English intent |
| TF-02 | Workstream page renders all 13 SSE event types correctly |
| TF-03 | Workstream list filters work (status × phase × intent_type) |
| TF-04 | Pause / Resume / Redirect / Archive actions reach backend |
| TF-05 | Honesty rule: every control names its persistence target in title=  |
| TF-06 | Coming-Soon badges name the PR that wires the feature |

### 13.3 Acceptance criteria (Definition of Done)

- [ ] All chat / scan / company-mode / file-process / draft-outreach
      flows produce a Workstream artifact and traverse all 9 spine
      stages.
- [ ] `/workstreams/:id` is the canonical "watching" surface;
      `/tasks`, `/engagements`, `/missions`, `/scan`, `/files` all
      link to it.
- [ ] Audit hash chain verify endpoint is operational and surfaces a
      "verify" button on `/governance/audit`.
- [ ] Dream Engine runs on a schedule (default: 02:00 local nightly);
      every cycle writes audit rows.
- [ ] Notification emit covers all 5 backend-enforced flags from real
      services (heartbeat + runtime_disconnect retrofit ships in
      PR-NOTIF-FANOUT).
- [ ] LearningService persists to NBMF T0 (closes the loop).
- [ ] At least 7 of 47 user.settings keys remain enforced; the others
      either ship a backend consumer OR get an honest Coming-Soon
      badge OR get deleted.
- [ ] Frontend tsc clean. Backend pytest sweep ≥ 100 tests pass
      (all PR-S1 + PR-S2 + PR-S2.1 + new spine tests).
- [ ] Operator demo: founder can launch a single `+ New action`,
      confirm preview, watch progress, see artifact, follow audit,
      verify chain — in under 60 seconds.

---

## 14. Dependencies + sequencing

The Spine PRs sequence as follows (estimates from agent reports +
prior Phase 11 hour-counts):

| PR | Scope | Estimate | Depends on |
|---|---|---|---|
| PR-SPINE-01 | Workstream model + state machine + restart recovery | 4h | none |
| PR-SPINE-02 | Capability Registry single surface + 5-min cache | 3h | PR-SPINE-01 |
| PR-SPINE-03 | S0 CLASSIFY generalisation (chat → all entry points) | 3h | PR-SPINE-02 |
| PR-SPINE-04 | S5 PROGRESS unified SSE event taxonomy | 2h | PR-SPINE-01 |
| PR-SPINE-05 | "+ New action" launcher frontend + draft endpoint | 4h | PR-SPINE-03 |
| PR-SPINE-06 | Workstream page (live console + artifact links + audit links) | 5h | PR-SPINE-04 |
| PR-DREAM-01 | Dream cycle scheduler (nightly + on-demand) + DreamReport table | 3h | none |
| PR-LEARN-01 | LearningService persistence to NBMF T0 + agent-experience writer | 2h | none |
| PR-NOTIF-FANOUT | Heartbeat + runtime_disconnect notification emit | 6h | PR-S2.1 |
| PR-AUDIT-VERIFY | Hash-chain verify endpoint + nightly cron + operator UI | 2h | none |
| PR-RAG-HONEST | RAG status endpoint + honest "Not configured" label | 1h | none |
| PR-S3 | Budget vocab unification + wire to user.settings | 3h | none |
| PR-S4 | Routing toggles wire-up | 4h | none |
| PR-S5 | Hydrate completeness | 1h | none |
| PR-H1 | Heartbeat config DB persistence | 3h | none |
| PR-T1 | Tasks audit emit retrofit | 2h | none |
| PR-P1 | Policy soft-archive | 1.5h | none |

**Total Spine effort:** ~21h core spine + ~16h supporting PRs =
~37h. Roughly two weeks at founder pace; one week with parallel
cross-AI delegation (Codex on single-file tickets, Claude on
cross-cutting).

## 15. Risks + mitigations

| Risk | Mitigation |
|---|---|
| Workstream wraps too many existing concepts and confuses operator more | Start as opt-in Phase 12-A flag; existing `/tasks` etc. unchanged until 80% of consumers migrate |
| SSE event taxonomy collides with existing chat stream | Namespace under `spine.*` to avoid collision; chat keeps `chat.*` |
| Capability Registry caching leaks stale state | 5-min TTL + invalidate on connection_v2 row change |
| Dream Engine consumes ~100K tokens/day (Refinery budget) | Reuse existing Refinery circuit breaker (Semaphore + daily budget + emergency stop) |
| LearningService persistence writes overwhelm NBMF | Tier-0 with 30-min TTL; Dream merges quickly |
| Audit hash chain verify takes too long on large ledger | Verify async + cache last verified index; only re-walk from there |
| Founder demo regresses chat UX during migration | Spine wraps chat; chat continues to work as today behind the wrapper |

## 16. Open questions for founder

1. **Workstream as primary primitive — yes/no?** Council R3 lock
   already chose this; PRD assumes yes.
2. **Hide `/tasks` and `/engagements` and `/missions` after Workstream
   ships** — yes (under Advanced) or keep visible?
3. **Single launcher button: in header or in sidebar?** Header
   suggested for global reach; sidebar suggested for keyboard
   navigation.
4. **Dream cycle schedule:** nightly 02:00 local, or hourly?
   Nightly recommended (less compute pressure).
5. **OODA in CMD mode:** run OBSERVE only, or full OBSERVE+ORIENT?
   OBSERVE+ORIENT recommended (cheap; informs the plan).
6. **Council/QE downgrade visibility:** notify operator on every
   downgrade, or only on first per session?

End of PRD.
