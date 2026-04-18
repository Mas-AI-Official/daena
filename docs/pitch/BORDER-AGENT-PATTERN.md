# Border Agent Pattern

Masoud's vision, verbatim from the session:

> "that is the reason of existing cfo cto etc we put all intellegence to
> a living system that they are already connected to each other and
> know what is going on in real time not by having meeting ... we put
> a agent as a border agent that for each department the data is
> sharing between all and base on the project they will related things
> to them"

Departments mostly run their own lanes. But they stay aware of what
peers are doing in real time, without meetings, so any one department
can pivot when another's state changes. This doc defines the Border
Agent layer that delivers that awareness using primitives Daena
already had.

---

## Vocabulary

- **Border Agent** -- one per (tenant, department). **11 total per
  tenant**: the 10 canonical departments (Engineering, Product,
  Marketing, Sales, Finance, Operations, Research, Legal &
  Compliance, Skill Governance, Security Operations) plus **Daena**
  herself as the 11th -- the supervisor/VP the founder talks to,
  with a wildcard relevance lens so she sees every signal across
  every department. A long-lived in-process liaison that publishes
  its department's lifecycle events and filters inbound peer events
  through a relevance lens. Lives in
  `backend/app/services/departments/border_agent.py`.
- **Relevance lens** -- a static glob-pattern map
  (`DEPARTMENT_RELEVANCE`) keyed by listening department. Filters
  out noise; surfaces only events the owning department cares about.
- **Signal** -- one relevant peer event received into a department's
  BorderAgent inbox. `{id, source_department, event_type, payload,
  created_at, relevant_because}`.
- **Event envelope** -- when a department emits, we wrap the payload
  with `_source_department`, `_source_tenant_id`, `_event_type`,
  `_timestamp` so handlers can filter + strip before surfacing.

## Primitives already in the codebase

| Primitive | File | Role |
|---|---|---|
| `EventBus` (singleton `event_bus`) | `app/core/events.py` | Process-wide async pub/sub |
| `KnowledgeBus` | `app/services/sub_agent_spawner.py` | Per-session shared knowledge for spawned sub-agents |
| `DepartmentStateService` | `app/services/department_state_service.py` | WORKING / IDLE / OVERLOADED / OFFLINE state |
| `DepartmentMessageService` | `app/services/department_message_service.py` | Point-to-point ASK / ANSWER |
| `DepartmentPolicyService` | `app/services/department_policy_service.py` | Rulebook, required_approvers |
| `DaenaVP` | `app/services/daena_vp.py` | Cross-department planner |
| `SwarmExecutor` | `app/services/swarm/executor.py` | Parallel subtask execution with state tracking |

The Border Agent is NOT a new primitive. It is the thin layer that
wires these together into the self-aware company Masoud described.

## What the Border Agent does

1. **Publishes** its department's lifecycle events to the EventBus.
   Today's auto-emits (wired into SwarmExecutor):
   - `department.task_started`
   - `department.task_completed`
   - `department.task_rejected`
   - `department.task_failed`

   Specialized agents (SalesAgent, MarketingAgent, SecurityOperationsAgent)
   can emit richer domain-specific events via `ba.emit(event_type,
   payload=...)`. Event-type catalog in `DepartmentEvent` class.

2. **Subscribes** to every known event type in `_known_event_types()`
   on start. When a peer event arrives, the handler:
   - Skips if the event is from a different tenant (Hard Law 7).
   - Skips if the event is from the same department (no echo).
   - Matches against the listener's glob patterns in
     `DEPARTMENT_RELEVANCE`. If any pattern hits, the signal lands
     in the ring-buffer inbox.

3. **Caches** the last ~200 relevant signals in memory (tenant-scoped).
   The owning department's chat room or agent reasoner polls
   `recent_signals(limit)` to pull the feed.

## The Relevance Matrix

Keep each dept to 5 to 8 patterns. Broader dilutes signal; narrower
misses real ones.

| Listener | Pattern | Why |
|---|---|---|
| Engineering | `department.task_failed` | Fix what broke |
| | `SecurityOps.threat_detected` | Fix it before exploit lands |
| | `Legal.compliance_flag` | Fix code to comply |
| Product | `department.needs_input` | Any dept asking for a product decision |
| | `department.flagged_risk` | Steer roadmap around risk |
| | `Sales.closed_deal` | Customer context for next release |
| | `SecurityOps.incident` | Postmortem candidate |
| Marketing | `Sales.closed_deal`, `Sales.proposal_sent`, `Sales.lost_deal` | Feedback loop on what's working in outreach |
| Sales | `Legal.contract_signed` | Move deal to CLOSED_WON |
| | `Finance.expense_approved` | Confirm budget to close |
| | `department.flagged_risk` | Customer-impact flags |
| Finance | `Sales.closed_deal`, `Sales.lost_deal` | Revenue ledger |
| | `Finance.expense_proposal` | Own inbox for approvals |
| | `department.flagged_risk`, `*.budget_*` | Anything budget-adjacent |
| Operations | `department.task_started`, `task_completed`, `task_failed` | Ops sees the whole pulse |
| | `Sales.closed_deal` | Trigger onboarding |
| Research | `department.flagged_risk`, `SecurityOps.threat_detected`, `Marketing.*` | Feeds competitive / market intel |
| Legal & Compliance | `Sales.proposal_sent`, `Sales.closed_deal` | Review before sign |
| | `Finance.expense_proposal`, `*.compliance_*`, `SecurityOps.incident` | Classic legal inputs |
| Skill Governance | `department.task_completed`, `task_failed` | Learn from wins + losses |
| | `*` | Learn from everything; wildcard opt-in |
| Security Operations | `*.threat_*`, `*.incident*`, `Governance.tier_high` | Active threat / governance escalation |
| | `Legal.compliance_flag`, `department.needs_input` | Inputs the dept reasons over |
| **Daena (supervisor)** | `*` | The founder-facing VP. Sees every signal across all 10 departments so when Masoud asks "what's going on", her chat_orchestrator has full company-wide awareness already in hand. Distinct role from Skill Governance's `*` (which learns for skill refinement) -- Daena's feed is for situational awareness and cross-department orchestration. |

The matrix is a dict, not an LLM. Fast. No per-event LLM cost. The
matrix gets refined by Skill Governance based on usage telemetry
(which signals led to which agent actions that delivered value).

## Standard Event Catalog (`DepartmentEvent` class)

```
department.task_started
department.task_completed
department.task_rejected
department.task_failed
department.flagged_risk
department.needs_input

Sales.proposal_sent
Sales.closed_deal
Sales.lost_deal

Legal.contract_signed
Legal.compliance_flag

Finance.expense_proposal
Finance.expense_approved

SecurityOps.threat_detected
SecurityOps.incident

Governance.tier_high
```

Ad-hoc event types emit fine at runtime, but subscribers only see
them if their concrete type was registered at BorderAgent init time
(EventBus keys by exact string). Register new types in
`DepartmentEvent` or in the `DEPARTMENT_RELEVANCE` map (concrete
patterns get auto-subscribed).

## Wire-In Points

### Auto-emitted today (live in prod path)

- `SwarmExecutor._execute_subtask` emits:
  - `TASK_STARTED` at the beginning (after state-mark-working).
  - `TASK_COMPLETED` / `TASK_REJECTED` / `TASK_FAILED` in the
    finally block (after state-mark-idle), keyed to `subtask.status`.

Those two hooks give every department a live pulse across the whole
company with zero extra effort on the part of specialized agents.

### Specialized agents should emit (Phase I.2+)

- `SalesAgent.closed_deal()` -> emits `Sales.closed_deal`.
- `MarketingAgent.send_outreach()` (future) -> emits
  `Sales.proposal_sent` (or Marketing equivalent).
- `SecurityOperationsAgent.finding_detected()` -> emits
  `SecurityOps.threat_detected`.
- `LegalAgent.contract_sign_confirmed()` -> emits
  `Legal.contract_signed`.
- `FinanceAgent.expense_approve()` -> emits
  `Finance.expense_approved`.

These are one-line additions at the right lifecycle point in each
specialized agent. The boilerplate is already taken care of in
`BorderAgent.emit()`.

## Frontend Integration (per-department rooms)

Each department's chat room at `/departments/{id}/chat` gets a new
right-side pane:

**Peer Signals** -- polls
`GET /api/v1/department-states/{department}/peer-signals?limit=20`
every 10 seconds. Renders a scrollable feed, newest first.
Each signal shows:

- Source department + icon
- Event type as a tag (color-coded by severity)
- Payload summary (first 1-2 key fields)
- Relative time ("2m ago")
- Why-relevant caption ("matched Sales.closed_deal")

Signals are read-only. Clicking one opens a context drawer with the
full payload and, if applicable, a suggested follow-up action for
this department (the department's chat orchestrator consumes the
signal and proposes a response turn).

This replaces the deleted DepartmentInbox page with a per-department,
relevance-filtered view -- aligned with the canonical "capabilities
live in their department room" rule from `DEPARTMENT-ROOM-INTEGRATION.md`.

## What the Border Agent Is NOT

- NOT an LLM. It is a pure event filter + cache. Latency is nanoseconds.
  Reasoning over signals happens when the owning department's chat
  orchestrator pulls them at turn start.
- NOT a meeting replacement via conference calls. It replaces the
  PURPOSE of a meeting (cross-team awareness) with continuous state
  propagation. Humans and agents still have `DepartmentMessageService`
  for point-to-point questions that demand an explicit answer.
- NOT a database. The inbox is in-memory ring-buffer (200 per dept
  per tenant). Long-term audit lives in the existing audit chain and
  DepartmentMessage table. If an operator restarts the process, peer
  signal history clears -- that is fine, because the owning dept's
  chat sessions, CRM, audit log, and NBMF memory all persisted
  independently.
- NOT a rate-limited channel. Every emit goes to every subscriber.
  If a department starts spamming, Skill Governance flags it and
  tightens the relevance lens.

## Governance

- Tenant isolation enforced at filter time (`_on_event` skips events
  with a different `_source_tenant_id`).
- Same-department echo suppressed (a dept never sees its own emits).
- Relevance lens pruning happens via Skill Governance reading the
  signal usage telemetry (what signals an agent consumed -> what
  actions it took -> what outcomes those produced). Over time the
  lens tightens to the highest-value signal types per department.

## Ownership

- **Published by**: every dept via `SwarmExecutor` lifecycle hooks
  (automatic) + specialized agents via one-line `ba.emit(...)` calls.
- **Consumed by**: every dept's BorderAgent inbox + the corresponding
  chat room's Peer Signals pane + that dept's chat orchestrator at
  turn start.
- **Evolved by**: Skill Governance -- pruning the relevance matrix
  based on telemetry.

## Sequence for a sample signal

1. `Sales.SalesAgent.close_deal(deal_id="acme-2026")` called.
2. Agent method runs, persists deal row, then calls
   `await ba.emit(DepartmentEvent.CLOSED_DEAL, payload={"deal_id": "acme-2026", "amount_usd": 90000})`.
3. EventBus invokes every registered handler concurrently.
4. `Finance.BorderAgent._on_event`: tenant matches, source not self,
   pattern `Sales.closed_deal` in Finance's list -> signal appended.
5. `Legal.BorderAgent._on_event`: same result, signal appended.
6. `Marketing.BorderAgent._on_event`: signal appended.
7. `Engineering.BorderAgent._on_event`: no pattern match, signal ignored.
8. `Skill Governance.BorderAgent._on_event`: wildcard `*` matches,
   signal appended. Telemetry loop kicks in.
9. Finance's chat room polls `/peer-signals` within 10s, shows the
   signal, the department's orchestrator proposes "update forecast
   with $90K" as next turn.

No meeting. No spreadsheet. No Slack ping. The company knew.

## Metrics

- Signal volume per dept per hour (target: 5 to 50; outside that range
  the lens needs retuning).
- Signal -> action conversion rate (signals that led to a dept agent
  action within the next session).
- Relevance precision (actioned signals / all received signals). Target >= 0.4.
- Cross-dept latency (emit -> peer inbox append). Target < 10ms in-process.

## What ships today

Phase I.2 piece:

- `BorderAgent` class + singleton registry + 8 passing tests.
- `DepartmentEvent` catalog.
- `DEPARTMENT_RELEVANCE` matrix for all 10 departments.
- `SwarmExecutor._execute_subtask` auto-emits TASK_STARTED / TASK_COMPLETED
  / TASK_REJECTED / TASK_FAILED in the existing wrap-around state hooks.
  No existing test broke.
- `GET /api/v1/department-states/{department}/peer-signals` endpoint
  registered before the parametric `{department}/offline` route so
  path resolution is unambiguous.

## What's deferred (small, focused next-session work)

- Frontend Peer Signals pane inside `DepartmentChatPage.tsx`. ~80
  lines of TSX + a new `useDepartmentSignals` hook.
- Specialized agents (SalesAgent, SecurityOperationsAgent, etc.)
  emitting their domain events -- one line per lifecycle point.
- Persistent ring-buffer backup to the DepartmentMessage table so
  signal history survives restart (optional; in-memory is deliberate
  for now).
- Relevance-lens tuning from Skill Governance telemetry (Phase N work).
