# Daena Wiring Map

Reference for how every major backend service connects to every other
service, and how each frontend page connects to the backend. Keeps
Masoud's "no orphan code" and "no ghost features" rules enforceable
by making mismatches easy to spot.

Current as of the 2026-04-17 cleanup + Border Agent session.

---

## Backend service graph

```
                              ChatOrchestrator (10-stage pipeline)
                                      |
                    +---------+-------+-------+---------+
                    |         |       |       |         |
              SecurityGate  Gov    CostPF  ModelRouter  Memory
                            Engine                       Recall
                              |                            |
                              |                          NBMF
                              v                         (T0-T4)
                       ApprovalService
                              |
                     persists GoaRequest +
                     PendingApproval ---> frontend /governance/approvals

        ExecutionService.execute_tool (tool chokepoint)
                    |
                    +---> permission_resolver (per-tool user pref)
                    |
                    +---> GovernanceEngine (tier)
                    |
                    +---> ApprovalService (persist approval row)

        SwarmExecutor._execute_subtask (parallel dispatch)
                    |
                    +---> DepartmentStateService (WORKING/IDLE/OVERLOADED/OFFLINE)
                    |
                    +---> BorderAgent.emit(TASK_STARTED/COMPLETED/REJECTED/FAILED)
                    |         |
                    |         v
                    |    EventBus (process singleton)
                    |         |
                    |         v
                    |    Every dept's BorderAgent filters relevance -> inbox
                    |
                    +---> _solicit_required_approvers
                               |
                               v
                          DepartmentMessageService (ASK/ANSWER, per-dept)

        Specialized department agents (subclass DepartmentAgent):
           SalesAgent       -- prospect/qualify, emits TASK_COMPLETED
           MarketingAgent   -- author_outreach, emits PROPOSAL_SENT
           SecurityOpsAgent -- start_engagement, emits TASK_STARTED
           (Engineering, Product, Research, Legal, Finance, Ops, Skill Gov: emit via SwarmExecutor auto-hooks)

        ScanWorkflow (security/scan_workflow.py)
           <--- SecurityOpsAgent wraps it with tenant isolation + T4/T5 gate

        DaenaVP (meta-agent)
           <--- chat_orchestrator Stage 2.8 calls plan()
           <--- SwarmExecutor consumes subtask DAG

        KnowledgeBus (sub_agent_spawner.py)
           <--- per-session spawner knowledge share (legacy, still used)

        BorderAgent (11 per tenant: 10 depts + Daena)
           <--- listens on EventBus
           <--- serves GET /department-states/{dept}/peer-signals

        Skill Refinery:
           extract_skill -> LLM via Ollama -> parse -> RefinedSkill (T1_DRAFT)
           ingest_batch -> same path, batch of items, per-item status
           news_monitor -> 90-day staleness check
           retrieval_service.search_skills -> used by ChatOrchestrator Stage 6.5
```

### Key invariants enforced by this graph

- **Tenant isolation** (Hard Law 7): every cross-department primitive
  (DepartmentMessageService, BorderAgent._on_event, retrieval) filters
  by tenant at ingress.
- **Approval persistence** (April 2026 fix): every tier-3+ decision in
  ExecutionService.execute_tool now writes a GoaRequest + PendingApproval
  row so the frontend badge + InlineApprovalBanner see it immediately.
- **Border Agent echo suppression**: a dept never receives its own emits.
- **Self-approval filter** (SwarmExecutor): Finance approving a Finance
  subtask is short-circuited; only OTHER depts can gate.
- **Fail-safe emits**: BorderAgent emit errors log as debug and do not
  block the originating operation.

## Frontend -> backend endpoint map

Per-page inventory. Every entry: `page -> endpoint(s) consumed`.

| Page | Endpoint(s) |
|---|---|
| LoginPage | POST /auth/login |
| RegisterPage | POST /auth/register |
| CompleteProfilePage | PATCH /auth/complete-profile |
| ForgotPasswordPage | POST /auth/reset-password (2-step) |
| ChatPage | GET /chat/sessions, /chat/model-registry; POST /chat/sessions; GET /governance/approvals?status=PENDING (via InlineApprovalBanner) |
| DepartmentChatPage | GET /agents/departments (lookup), /chat/sessions; POST /chat/sessions; GET /department-states/{dept}/peer-signals (via PeerSignalsPane) |
| DepartmentsPage | GET /agents/departments; GET /department-states (via useDepartmentStates hook for live badge) |
| DashboardPage | GET /health, /billing/overview, /governance/audit?page_size=5, /chat/sessions?page_size=1 |
| TasksPage | GET /execution/tasks; PATCH /execution/tasks/{id} |
| GovernanceApprovalsPage | GET /governance/approvals; POST /governance/approvals/{id}/decide |
| GovernanceAuditPage | GET /governance/audit |
| EngagementConsolePage | POST /engagements; GET /engagements, /engagements/{id}, /engagements/{id}/report, /engagements/shield-status |
| SkillsPage | GET /skills, /skills/installed |
| ConnectionsPage | GET /connections/connectors, /connections/extensions, /connections/instances |
| ProjectsPage, ProjectDetailPage | GET /projects, /projects/{id}, /pipeline/projects, /pipeline/summary |
| PipelinePage | GET /pipeline/projects; POST /pipeline/projects/{id}/advance |
| FilesPage | GET /files; POST /files/upload |
| AnalyticsPage | GET /analytics/dashboard |
| AccountPage | GET /settings/user; PATCH /settings/user; GET /billing/my-quota |
| SettingsPage (tabs) | GET /settings/*; various |
| FounderPage | GET /founder/routing/policy, /founder/routing/telemetry |
| SecurityDashboardPage | GET /security/status, /security/tools, /security/shields, /security/scans |
| ScanPage | POST /security/scans/start; GET /security/scans/{id}/status, /security/scans/{id}/report |
| PoliciesPage | GET /department-policies; CRUD |
| DaenaBotPage | redirects to /chat (deprecated) |
| Sidebar (all pages) | GET /governance/approvals?status=PENDING&page_size=1; GET /execution/tasks?status=RUNNING&page_size=1, ?status=PENDING&page_size=1 (parallel) |
| InlineApprovalBanner (in ChatPage) | GET /governance/approvals?status=PENDING; POST /governance/approvals/{id}/decide |
| PeerSignalsPane (in DepartmentChatPage) | GET /department-states/{dept}/peer-signals |

### Legacy redirects (App.tsx)

- `/company` -> `/departments` (merged into DepartmentsPage)
- `/inbox` -> `/departments` (dept-room native Peer Signals replace it)
- `/crm` -> `/departments` (Sales owns CRM in its room)
- `/voice` -> `/departments` (voice is agent infra, not a page)

### Known frontend -> backend gap (pre-existing, out of this session's scope)

- `GET /api/v1/runtimes/subscriptions` -- called by frontend, not
  currently registered on the backend router. Flagged for separate
  refactor.

## Component -> data flow

### InlineApprovalBanner (mounted in ChatPage)

```
poll /governance/approvals?status=PENDING  <--  every 5s
    |
    +--> list cards (up to 3 inline + "N more" link)
    +--> Approve button -> POST /governance/approvals/{id}/decide
    +--> Reject button  -> POST /governance/approvals/{id}/decide
```

### PeerSignalsPane (mounted in DepartmentChatPage)

```
mount -> read :departmentId param -> lookup dept name from /agents/departments
    |
    +--> poll /department-states/{name}/peer-signals?limit=50  <--  every 10s
    |
    +--> render newest-first feed, badged by event_type
    +--> summarize payload into 1-line text
    +--> show "matched {pattern}" caption
```

### Sidebar badges (mounted once globally)

```
interval 30s (with exponential backoff on error)
    |
    +--> GET /governance/approvals?status=PENDING&page_size=1  -> amber pill
    +--> GET /execution/tasks?status=RUNNING                    -+
    +--> GET /execution/tasks?status=PENDING                    -+-> teal pill
```

## What the BorderAgent emits today (auto-wired)

Every subtask execution:
- `TASK_STARTED` -> after SwarmExecutor marks dept WORKING
- `TASK_COMPLETED` / `TASK_REJECTED` / `TASK_FAILED` -> in finally block after mark-idle

Specialized-agent emits (last session):
- SalesAgent.prospect() -> `TASK_COMPLETED` with account + contact_count
- SalesAgent.qualify() -> `TASK_COMPLETED` with stage + score
- MarketingAgent.author_outreach() -> `PROPOSAL_SENT` with draft + contact
- SecurityOperationsAgent.start_engagement() -> `TASK_STARTED` with tier + target

Chokepoint emits (this session):
- PipelineService.advance_stage() -> `Legal.contract_signed` on transition
  to CONTRACT; `Sales.closed_deal` on transition to CLOSED. Payload
  carries project_id, from_stage, to_stage, client, budget_usd.
- ApprovalService.approve()/reject() -> `Finance.expense_approved` or
  `Finance.expense_proposal` when action_type contains "expense";
  `Governance.tier_high` for any tier >= 3 decision. Payload carries
  request_id, risk_level, governance_tier, approved boolean.
- ScanWorkflow._execute_scan() -> `TASK_COMPLETED` on every scan
  completion (operational signal), PLUS `SecurityOps.threat_detected`
  when critical+high findings > 0 (signal-worthy). Payload carries
  job_id, tier, severity_counts, total_findings, target. Regression
  test at tests/test_scan_workflow.py::TestBorderAgentEmitOnComplete.
- PipelineService.mark_lost() -> `Sales.lost_deal` when a project
  is marked lost from any stage. Adds `lost_at` + `lost_reason`
  columns on ProjectPipeline (orthogonal to the 8-stage flow).
  Frontend: PipelinePage shows red "Lost" button on hover + reason
  prompt; lost projects render line-through with LOST badge.
  API: POST /pipeline/projects/{id}/mark-lost.
  Tests at tests/test_pipeline_service.py (6 tests covering emits
  for advance_stage -> CONTRACT / CLOSED and mark_lost).
- GovernanceEngine.evaluate() -> `department.flagged_risk` when a
  decision lands at tier >= 3. Emits as Skill Governance so peer
  rooms listening for flagged_risk (Product, Sales, Finance,
  Research) see the risk surfacing in real time. Tests at
  tests/test_border_signal_emits.py::TestFlaggedRiskEmit.
- ApprovalService._emit_decision_event() -> `Legal.compliance_flag`
  when action_type is legal-flavored (contract / nda / license /
  legal / compliance) OR a CRITICAL-risk request is rejected. Emits
  as Skill Governance (the entity making the call) so Legal's
  `*.compliance_*` lens picks it up -- self-echo suppression would
  silence the signal if Legal emitted to itself. Added
  `await db.refresh(request)` in approve()/reject() so attributes
  stay hot across the emit's async yield. Tests at
  tests/test_border_signal_emits.py::TestComplianceFlagEmit.

## Signal consumption (chat-orchestrator Stage 6.4)

Border Agent signals are no longer just a visual pane -- they are
injected into the chat system prompt at turn start. When a user
sends a message in a department-pinned chat (e.g. the Sales room),
Stage 6.4 pulls the last 5 peer signals from that department's
BorderAgent ring buffer and appends them to the system prompt as:

```
Recent peer-department activity (Sales lens):
- [Marketing] Sales.proposal_sent: Drafted outreach to Acme Corp
- [Skill Governance] Governance.tier_high: Tier-3 DEPLOY approved
- [Legal & Compliance] Legal.contract_signed: Legal advanced project to CONTRACT
```

The LLM now answers Sales questions with Marketing / Legal /
Governance context already in hand -- the "departments aware of
each other without meetings" vision as real runtime behavior.

### Daena VP fallback

When the user chats WITHOUT a department pin (the top-level founder
chat), Stage 6.4 reads from Daena's wildcard BorderAgent instead.
Because Daena's relevance lens is ``["*"]``, her inbox accumulates
every department event for the tenant -- giving the founder chat
company-wide situational awareness as a direct prompt enrichment.
Label in the prompt becomes "Daena VP / company-wide lens".

Invariants pinned by `tests/test_border_agent.py::TestDaenaWildcardInbox`:
- Daena sees signals emitted by any department in her tenant
- Daena respects tenant isolation (no cross-tenant leakage)

Frontend counterpart: `ChatPage.tsx` mounts
`<PeerSignalsPane departmentName="Daena" title="Company-wide" />`
so the founder has both a visual feed AND prompt-level context for
the same signals. The pane polls
`GET /api/v1/department-states/Daena/peer-signals` every 10 seconds.
A new `title` prop on PeerSignalsPane lets DepartmentChatPage keep
its existing "Peer Signals" header while ChatPage relabels to
"Company-wide".

Rendering: `format_signals_for_prompt()` helper lives in
`backend/app/services/departments/border_agent.py`. Tested in
`tests/test_border_agent.py::TestFormatSignalsForPrompt`. Fail-safe:
orchestrator swallows any BorderAgent error silently so a missing
registry entry never blocks the chat turn.

- InteractivePromptManager._send_and_wait -> `department.needs_input`
  when a prompt carries `_tenant_id` + `_department` in its
  ``context`` dict. Opt-in via existing context field so legacy
  callers see zero behavior change; new callers add two keys to
  surface the block in peer rooms (Product, Security Operations
  listen for needs_input). Helper `_maybe_emit_needs_input` lives in
  `interactive_prompts.py`. `ask_confirm` now also accepts
  ``context`` (was missing the kwarg before). Production call-site
  upgrade: `AgentLoop._run_plan` pause-resume prompt passes
  `{_tenant_id, _department}` when those fields are set on the
  loop, so the live Autopilot pause-resume cycle now fires the
  signal. Tests at `tests/test_interactive_prompts.py::TestNeedsInputEmit`
  cover: (a) emit path, (b) no-emit-without-context,
  (c) ask_confirm threading.

## Connections / Plugins UI (Codex-style)

The Plugins tab (formerly "Services") renders the 14 connectors as
Codex-style skill cards:

- CONNECTORS entries keep `tools: []` (just tool-id strings) but the
  `SKILL_DESCRIPTIONS` dict in `ConnectionsPage.tsx` maps each tool to
  a one-line description. Unknown tools fall back to a generic
  "Capability exposed by X" line.
- Each plugin row header now shows a skill-count badge (`4 skills`)
  and a category pill next to the name, matching the Codex plugin
  summary layout.
- Plugins are clustered by category (Productivity, Development,
  Design, ...). Each section header is an uppercase label + count +
  thin divider, preserving the original ordering from CONNECTORS so
  well-known categories stay near the top.
- Expanded view uses Codex's plugin-detail pattern: one card per
  skill with Terminal icon + human-readable name + "Skill" pill +
  description + monospace tool id + permission select. Section label
  reads "Skills (N)".

## MCP install plumbing

- `POST /api/v1/connections/extensions/install` accepts optional
  `command` + `args` and writes them verbatim to
  `claude_desktop_config.json`. When absent, falls back to
  `npx -y <id>` for legacy-client compat.
- Frontend `handleInstallMCP` forwards `mcp.command` + `mcp.args` so
  real npm packages (e.g.
  `@modelcontextprotocol/server-gdrive`) land in the config.
- Modal `onSaved` now triggers
  `fetchExtensions() + fetchRuntimes() + fetchConnectorInstances()`
  so the MCP Servers tab count refreshes immediately; previously the
  count stayed at 0 until page reload even after a successful install.
- Regression tests: `tests/test_connections.py::test_extensions_install_forwards_command_and_args`
  and `test_extensions_install_legacy_fallback`.

### Backend plugin catalog (Option B)

`backend/app/services/plugin_catalog.py` is the single-source-of-
truth catalog. Each entry is a `PluginDefinition` carrying:

  * `id`, `name`, `subtitle`, `category`, `auth_kind`
  * `skills: list[PluginSkill]` (id + name + description)
  * Optional `mcp_package` -- when set, Option A can spawn the MCP
  * Optional `install_note`

Public API:
  * `GET /api/v1/connections/plugin-catalog` -- flat list
  * `GET /api/v1/connections/plugin-catalog?grouped=true` -- by category
  * `GET /api/v1/connections/plugin-catalog/{plugin_id}` -- single entry

Initial coverage: 23 plugins with full skill definitions, 11 of
which have known `mcp_package` values. The frontend still renders
its own richer 116-entry list for visual completeness; a future
session will port the long tail to the backend so frontend can drop
its hardcoded copy.

### Stdio MCP bootstrap (Option A)

`backend/app/services/mcp_bootstrap.py` reads
`claude_desktop_config.json` on startup (via the lifespan hook in
`app/main.py`) and instantiates an `MCPBridgeAdapter` for every
`mcpServers` entry. The adapters live in a process-wide registry;
`list_installed_mcps()` surfaces them to any caller.

Actual process spawn happens lazily on first `execute()` call, so
startup stays fast even with many registered MCPs.

The registry is re-entrant: Daena's plugin-admin agent calls
`bootstrap_installed_mcps()` after an install or uninstall so the
new state is immediately visible without a server restart.

### Daena plugin-admin surface

`backend/app/services/daenabot/plugin_admin_agent.py` exposes
plugin-management operations as a first-class DaenaBot agent
(`agent_prefix = "plugin"`). Supported operations:

  * `list_catalog` -- read the catalog (optionally filter by category)
  * `list_installed` -- read the live MCP bootstrap registry
  * `install_plugin` -- write an entry to `claude_desktop_config.json`
    using the plugin's `mcp_package`, then re-bootstrap
  * `uninstall_plugin` -- remove the entry and re-bootstrap
  * `diagnose_plugin` -- verify the MCP's command is on PATH
  * `refresh_registry` -- re-read the config (manual sync)
  * `fix_plugin` -- uninstall then re-install (best-effort repair)

Every op is mapped to an action_type via `OPERATION_ACTION_MAP` so
governance still gates destructive actions. This means:

  * Founder says "Daena, install the Sentry plugin" -- she calls
    `plugin.install_plugin({"plugin_id": "sentry"})`, governance
    classifies it as `plugin_install`, the write happens, and
    Sentry's MCP appears in the installed registry instantly.
  * Founder says "Daena, Netlify isn't responding" -- she calls
    `plugin.diagnose_plugin({"plugin_id": "netlify"})` and reports
    the command-resolvable / missing status.

Tests at `backend/tests/test_plugin_catalog.py` pin the catalog
structure, bootstrap behavior, and admin-agent dispatch (17 tests).

### MCP tool invoker (live execution path)

`backend/app/services/mcp_invoker.py` uses the official Python MCP
SDK (``mcp.ClientSession`` + ``mcp.client.stdio``) to actually
spawn an installed MCP, complete the handshake, and route
``tools/list`` + ``tools/call`` through the registered adapter.

Each invocation is a short-lived stdio session: spawn -> handshake
-> call -> close. No persistent subprocess management; the cost is
spawn latency per call (~100-400ms for typical MCPs). Acceptable
v1 tradeoff; can evolve to persistent sessions when frequency
warrants.

Exposed as two new PluginAdminAgent ops:

  * ``plugin.list_tools({plugin_id})`` -- returns the MCP's tool
    descriptors (name + description + JSON schema for arguments).
    Governance action_type: ``plugin_read``.
  * ``plugin.call_tool({plugin_id, tool_name, arguments})`` --
    executes the tool and returns the content parts. Governance
    action_type: ``plugin_invoke``.

Every invocation is bounded by a 20s timeout so a broken MCP can't
hang the chat turn. Failures surface as ``{"success": false,
"error": "..."}`` dicts, never uncaught exceptions.

### Chat-level plugin awareness (Stage 6.45)

`chat_orchestrator.py` now injects the installed-plugin list into
the system prompt at turn start. When the LLM thinks "could
Daena do X?", it sees the set of installed MCPs (display name +
npm package) and the hint to call ``plugin.list_tools`` to see
their tools before dispatching ``plugin.call_tool``.

No more hallucinated capabilities, no more incorrect "I can't do
that" for skills the user already installed.

End-to-end flow is now working:

  1. Founder says "Install the GitHub plugin."
  2. Daena dispatches ``plugin.install_plugin({id: "github"})``.
  3. Bootstrap registry refreshes.
  4. Next turn's Stage 6.45 lists GitHub among installed plugins.
  5. Founder says "Search my repos for 'payment'."
  6. Daena dispatches ``plugin.list_tools({id: "github"})`` to
     discover ``search_repos``, then ``plugin.call_tool(...)``
     with the query.

### UI-triggered install path (complete parity)

``POST /connections/extensions/install`` now calls
``bootstrap_installed_mcps()`` after writing the config, so MCPs
installed from the Plugins tab are immediately callable without a
server restart. Response includes ``server_key`` and
``registry_refreshed`` booleans so the frontend can show a
"live" indicator as soon as install succeeds.

New companion endpoint ``POST /connections/extensions/uninstall``
removes an entry and re-bootstraps -- mirror-symmetric with
install. Idempotent (removing a missing entry returns
``removed=False``, not an error).

### Live-registry inspection

Two new endpoints let the frontend and ops tools see exactly what's
adapter-ready in memory (distinct from what's in the raw config):

  * ``GET /connections/mcp-registry`` -- returns the live entries
    with their display name, description, command, args, and npm
    package.
  * ``POST /connections/mcp-registry/refresh`` -- manager-gated
    manual re-scan, primarily for ops/debug affordance.

This gives UIs a way to distinguish "config written but not loaded
yet" from "loaded and ``plugin.call_tool``-ready", closing the
loop on visible install feedback.

### Frontend Live badge

`frontend/src/hooks/useMcpRegistry.ts` polls the registry every
10s and exposes an `isLive(server_key)` lookup. ConnectionsPage
passes `isLive={mcpRegistry.isLive('mcp-${c.id}')}` to each
ConnectorRow in the Plugins tab; when true, the row shows a green
pulsing "Live" pill next to its skill-count + category badges.

The Plugins tab intro also shows a live-count line ("3 plugins
live and callable right now") whenever the registry is non-empty,
so the user has at-a-glance confirmation that install -> registry
round-trip worked.

Install/OAuth callbacks call `mcpRegistry.refresh()` so the badge
appears immediately on install, not 10 seconds later on the next
poll cycle.

### Remaining gaps

Option C (per-plugin native adapters) is intentionally NOT built
out in code. `NATIVE_ADAPTER_PLUGINS` in
`plugin_admin_agent.py` lists the 5 plugins we would write native
code for (github, google-drive, slack, notion, hugging-face) when
richer features are needed. For now, they all have an MCP package
and work through Options A + tool invoker.

LLM-native tool_use binding (so ``plugin.call_tool`` dispatches
show up as Anthropic-style tool schemas in the request) is the
next layer; currently the LLM invokes via the existing DaenaBot
``tool_call`` JSON format. Works, but less elegant than a proper
tool registry integration.

## What's NOT yet emitting (next focused session)

All 16 DepartmentEvent types now emit from real chokepoints. Next
work concerns enrichment, not new events:

- Call-site upgrades: individual agents (vuln_scanner_agent,
  MCPAgent, DaenaBot tools) can opt into the needs_input emit by
  adding `_tenant_id` + `_department` to their prompt ``context``
  arg. Low-risk additive change per call site.
- Signal persistence (DB-backed ring-buffer backup) -- currently
  in-memory only; restart loses history.

One-line emit per lifecycle point when the corresponding agent method
or chokepoint is implemented. Infrastructure ready to receive them.

## Self-check before finishing code changes

1. Did I add or remove an endpoint? -> update the page->endpoint table above.
2. Did I add a new department event type? -> add to `DepartmentEvent` class in border_agent.py AND to the relevance matrix.
3. Did I add a new specialized agent method? -> does it emit an event? One-line `ba.emit(...)` call in the lifecycle exit.
4. Did I delete a frontend page? -> add a legacy redirect so bookmarks survive.
5. Did I add a new frontend page? -> does it belong in a department room first? (If yes, build inside DepartmentChatPage as a pane, not a new route.)
