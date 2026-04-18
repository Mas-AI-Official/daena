# Autonomous Execution Loop

The gap Masoud flagged directly: today I ship individual agent methods
(prospect, qualify, author_outreach), but the user has to trigger each
step manually. The real product is "I ask, I accept, Daena executes
the full chain end-to-end until delivery, pausing only at governance
gates."

This doc defines the Autonomous Execution architecture that closes
that gap. Phase O in `ROADMAP-V2.md`.

---

## The Gap in One Picture

**Today:**

```
User -> prospect() -> list returned -> User clicks qualify ->
User clicks author_outreach -> User clicks send -> ...
```

Manual. Every step requires a click. Fatigue. Human is the glue.

**Phase O:**

```
User: "Find 20 mid-market fintech SOC 2 gaps, qualify, draft outreach"
  -> Plan proposed + cost estimate + governance tier per step
User: "Accept"
  -> SwarmExecutor kicks off the full chain
  -> Pauses ONLY at tier 3+ approval gates
  -> Runs to completion, streams progress to the UI
  -> Final summary + full audit trail
```

Human is the director. Daena is the company.

---

## What Already Exists

- `backend/app/services/daena_vp.py` — the meta-agent that plans
  cross-department work (Session B, flag now ON).
- `backend/app/services/swarm/executor.py` — dispatches subtasks
  with state tracking (Session A).
- `backend/app/services/department_message_service.py` — inter-
  department ask/answer (Session C).
- `backend/app/services/department_policy_service.py` — rulebook +
  required-approver resolution (Session D).
- `ExecutionService.execute_tool` — the governance + approval
  chokepoint (April 2026 fix).

The pieces exist. They do not compose end-to-end into an autonomous
loop yet. Phase O is the composition.

## What Phase O Builds

### 1. `AutonomousPlan` primitive

`backend/app/services/autopilot/autonomous_plan.py` NEW.

A structured plan produced from a user goal:

```python
@dataclass
class PlanStep:
    id: str
    department: str
    skill_ref: str             # e.g. "skill:sales.cold-email.problem-agitate-solve"
    tool_refs: list[str]       # e.g. ["apollo.prospect", "hubspot.contact.upsert"]
    inputs: dict[str, Any]
    governance_tier: int       # 0-4, resolved from skill + tool + action
    depends_on: list[str]      # other step ids
    estimated_cost_usd: float
    estimated_minutes: int
    requires_approval: bool
    approval_reason: str = ""


@dataclass
class AutonomousPlan:
    goal: str
    steps: list[PlanStep]
    total_cost_usd: float
    total_minutes: int
    gate_count: int
    created_by: UUID
    tenant_id: UUID
    # The audit link to the original user prompt for replay.
    source_prompt_id: str
```

Plans are pure data. They serialize to JSON, survive restarts, and
ship over the SSE stream for the frontend to render.

### 2. Planner: `AutopilotPlanner`

`backend/app/services/autopilot/autopilot_planner.py` NEW.

Takes a free-form user goal + optional constraints (budget cap, time
cap, departments allowed). Calls Daena VP + Quintessence Council to
decompose into `PlanStep` list. Each step is bound to a specific
skill from the Refinery + concrete tool references from the connector
catalog.

Output: `AutonomousPlan` ready for user review.

### 3. User review surface

Frontend `AutopilotPlanPage.tsx` NEW:

- Renders the plan as a gantt-ish view with dependencies.
- Shows total cost, total estimated time, governance gate count.
- Each step expands to show: which skill, which tools, inputs,
  approval reason.
- Big green "Accept and Execute" button.
- Alternative: "Edit Plan" to swap skills, tighten scope, lower budget.

Per CLAUDE.md autonomy-gradient: the plan-acceptance interaction is
explicit. After accept, execution runs without further clicks except
at tier-3+ gates.

### 4. Executor: `AutopilotExecutor`

`backend/app/services/autopilot/autopilot_executor.py` NEW.

On accept:

1. Persists the plan as an `AutopilotRun` row in a new table.
2. Walks the dependency DAG with `asyncio.gather` where steps are
   independent, sequential where they depend.
3. Each step:
   - Loads the referenced skill from Skill Refinery.
   - Injects the skill as system-prompt context for the agent call.
   - Routes through `ExecutionService.execute_tool` so approval
     persistence (April 2026 fix) creates rows at tier 3+.
   - On approval-required, **pauses the step** and subscribes to the
     approval resolution event. When approved, continues. When
     rejected, marks step FAILED and asks Daena VP whether to
     re-plan the remainder.
   - Emits SSE events: `step_started`, `step_progress`,
     `step_approval_pending`, `step_complete`, `plan_complete`.
4. On plan complete, writes a summary report (reuse
   `security/report_generator.py` shape) + persists to the
   ChatSession.

### 5. Live execution UI

`AutopilotRunPage.tsx` NEW. Route: `/autopilot/runs/:id`.

- Left pane: step list with live status icons.
- Center pane: currently-running step's agent output + tool calls.
- Right pane: approval queue for this run (mini version of the
  `/governance/approvals` page, filtered).
- Top bar: cost burn, elapsed time, ETA.
- Pause / Resume / Cancel controls.

### 6. Pause / Resume / Cancel semantics

- **Pause**: stops dispatching new steps. In-flight steps complete.
  Can be resumed.
- **Resume**: re-dispatch from the last unstarted step.
- **Cancel**: stops dispatching, marks run CANCELLED, persists the
  partial state. In-flight steps complete (no mid-tool kill).
- **Auto-pause rules**: if rolling cost exceeds budget cap, auto-pause.
  If a step fails and dependent steps cannot run, auto-pause for
  founder review.

---

## Governance Mapping

Every step carries a `governance_tier` derived from:
- The **skill's** inherent risk (cold email authoring is LOW; sending
  paid ads is HIGH).
- The **tool's** inherent risk (read-only API is LOW; send-email is
  MEDIUM; mass-send is HIGH).
- The **scope** (internal vs external; 5 recipients vs 500).

Tier 0-2: auto-proceed (logged, notified).
Tier 3: approval row persists. Sidebar badge lights up. Plan pauses
at that step until resolved.
Tier 4: approval row + founder-only decider.

UNLEASHED governance mode: tier 4 still requires founder approval,
everything else auto-proceeds.
BALANCED: tier 3+ pauses.
GOVERNED: tier 2+ pauses.

## Skill-Executor Binding

This is where `CONNECTOR-CATALOG.md` and `SKILL-MINING-PIPELINE.md`
meet `AUTONOMOUS-EXECUTION.md`. A step's `skill_ref` points at a
specific skill pack. The executor:

1. Retrieves the skill via `retrieval_service.search_skills`.
2. Injects the skill's `steps[]` as instructions for the agent.
3. Injects the skill's `anti_patterns` as negative constraints.
4. Records which skill was used in the `AutopilotRun.step_events`
   so Skill Governance can see telemetry: reply rate per skill,
   conversion per skill, error rate per skill.
5. If the skill's `tool_refs` mention a connector that is not yet
   authorized for this tenant, pause the step with a "connect
   {tool}" action prompting the user to grant access.

## Example Walk-Through

User prompt:
> "Find 20 mid-market fintech companies with SOC 2 gaps, qualify the
> top 10 by decisioning power, draft governed cold emails using the
> Hormozi PAS skill, and wait for my approval before sending."

Planner output (`AutonomousPlan`):

| # | Department | Skill | Tools | Tier | Est. Cost | Est. Time |
|---|---|---|---|---|---|---|
| 1 | SecOps | `skill:osint.breach-and-gap-cross-reference` | apollo, breach_intel | 1 | $1.20 | 2 min |
| 2 | Research | `skill:research.tech-stack-fingerprint` | supply_chain_analyzer, hunter | 1 | $0.40 | 1 min |
| 3 | Sales | `skill:sales.qualify-by-decisioning-power` | internal | 1 | $0.30 | 1 min |
| 4 | Marketing | `skill:marketing.cold-email.problem-agitate-solve` | internal | 2 | $0.80 | 2 min |
| 5 | Legal | `skill:legal.claim-substantiation-check` | internal | 2 | $0.20 | 30 s |
| 6 | Sales | `skill:sales.send-cold-sequence` | gmail | **3** (approval) | $0.10 | stops at gate |

Total: $3.00 estimated, ~7 minutes, 1 governance gate (the send).

User clicks Accept. Steps 1-5 execute in ~7 minutes with live SSE.
Step 6 creates 10 approval rows (one per email) at `/governance/approvals`,
Sidebar badge reads "10 pending". User reviews, approves in batch,
run resumes, 10 emails dispatch with audit trail, plan marked complete.

That is the single most important user experience Daena can ship.

## What Phase O Explicitly Does NOT Do

- It does **not** accept open-ended "take over my company" prompts.
  Every plan must resolve to finite steps with concrete tool refs
  and a cost estimate before user sees the Accept button.
- It does **not** bypass governance. Tier-3+ approvals are unskippable.
- It does **not** self-modify plans mid-execution without founder
  approval. If a step fails in a way that requires re-planning, the
  executor pauses and presents the re-plan option explicitly.

## Success Metric

**Ratio of founder clicks to value delivered**.

Today a "cold outreach to 20 prospects" workflow takes ~30 manual
clicks (per-step triggers + per-email approvals). After Phase O, the
same workflow takes 2 clicks (Accept + batch-approve). Goal: 90%
reduction in founder clicks for the top 10 recurring plays.

## Dependencies

- Phase N (Skill Mining) must be live for skills to exist to bind to
  steps. Without skills, the Planner falls back to generic DCP
  prompts, which is the current state.
- Phase M (Connector Fleet) must be live for tool references in plans
  to resolve to real API calls.
- The permission_resolver + ApprovalService wiring (April 2026 fix,
  already live) is what makes tier-3 pauses actually persist rows.

Phase O sequences **after** Phase M and N are at least half-shipped.
The minimum-viable Phase O can run with only the seed skills and one
CRM connector; it gets better every time Phases M and N add another.
