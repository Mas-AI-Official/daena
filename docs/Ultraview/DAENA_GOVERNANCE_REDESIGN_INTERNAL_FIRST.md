# DAENA Governance Redesign: Internal-First

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime` @ `17be681`
**Author:** Claude Code (Opus 4.7) under founder direction
**Status:** **Planning only.** Zero product code modified. Zero tests
run. Zero migrations, no flag flips, no `vault --apply`, no
deletions, no external scans, no external messages, no secrets
read.
**Companion docs:** `DAENA_CANONICALIZATION_PLAN.md`,
`DAENA_BACKEND_BLINDSPOT_INVENTORY.md`,
`PR_CONNECTIONS_TRUTH_CLEANUP_REPORT.md`,
`PR_HB_DAEMON_WIRE_REPORT.md`,
`PR_SETTINGS_CLEANUP_REPORT.md`. Anchor for project CLAUDE.md
governance modes section + Hard Laws + T5 hidden activation.

> **Thesis.** Governance must feel internal. The operator should
> experience Daena as action-first like OpenClaw, but Daena should be
> safer because she actually thinks before acting. The cognitive
> stack (OODA, Council, Quintessence, confidence scoring,
> NBMF memory, audit, scope checks, Shield Laws) is the real
> governance. Human approval is the LAST resort, reserved for
> genuinely irreversible / external / high-risk actions. Today's
> system already has every primitive needed; what's missing is the
> deliberate decision to put intelligence in front of approval, hide
> tier internals, and surface only three knobs to the operator:
> Unleashed, Balanced, Governed. T5 stays for authorized client
> security testing, founder-unlocked, engagement-scoped, never
> visible in normal UI.

---

## 0. Hard rules honored by this plan

| Rule | Status |
|---|---|
| No production deploy | Yes (planning only) |
| No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes (governance redesign does not touch V2 flag) |
| No `vault --apply` | Yes (vault not invoked) |
| Do not delete policies | Yes (policy primitives all KEEP_HOT_PATH) |
| Do not implement code yet | Yes (every PR specified, none executed) |
| Do not deploy | Yes |
| Do not run scans | Yes |
| Do not remove governance | Yes (every governance primitive remains; this plan reframes how they're surfaced and gated, not whether they exist) |
| Do not expose T5 in normal UI | Yes (T5 surface stays hidden; only chat command path documented) |
| No secrets printed or committed | Yes (Explore agent sweep confirmed no secret material in design content) |
| Em dashes (project CLAUDE.md Rule 12) | None introduced (verified in Section 13 below) |
| No protected files modified (`vault_adapter.py`, `vault_migration.py`, `oauth_credentials_store.py`) | Yes (they are referenced as KEEP_HOT_PATH; not edited) |

---

## 1. Internal governance model

**Founder principle (locked):** Internal intelligence governance does
the heavy lifting. Human approval only fires when something is
genuinely irreversible / external / high-risk.

### 1.1 The decision ladder

Every action that is not pure information retrieval flows through
this ladder. Each rung either DECIDES or PROMOTES to the next.

```
                          ACTION REQUEST
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 1: SHIELD                                        |
   |  - PromptInjectionScanner  (always)                    |
   |  - BehaviorGuard           (always)                    |
   |  - Tenant isolation        (always)                    |
   |  - Asset Shield egress     (always)                    |
   |  - Hard Laws 1, 5, 7, 8, 9 (always, all modes)         |
   |  ACTION: BLOCK if violation; otherwise PROMOTE         |
   +--------------------------------------------------------+
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 2: OODA Observe + Orient                         |
   |  - Classify intent / complexity / risk                 |
   |  - Identify scope (tenant, dept, project, client)      |
   |  - Identify reversibility (local file / DB write /     |
   |    external API / payment / deploy)                    |
   |  ACTION: emit (complexity, risk, scope, reversibility) |
   |  signal                                                |
   +--------------------------------------------------------+
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 3: Reasoning escalation                          |
   |  - TRIVIAL / SIMPLE   -> Standard, single mind         |
   |  - MODERATE           -> Standard, --effort medium     |
   |  - COMPLEX / MULTI_STEP / VERY_COMPLEX                  |
   |  - HIGH / CRITICAL risk                                 |
   |       -> Council (3 minds, parallel + peer review)     |
   |  - Operator picked QE in Advanced toggle                |
   |       -> Quintessence (Council + 15 DCP lenses)        |
   |  ACTION: produce candidate plan + confidence score     |
   |  (0.0..1.0)                                            |
   +--------------------------------------------------------+
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 4: Confidence + scope check                      |
   |  - confidence < threshold -> ABSTAIN or ask one         |
   |    clarifying question (Communication Protocol §1)      |
   |  - scope outside permitted dept / project / client      |
   |    -> ABSTAIN with named gap                            |
   |  ACTION: PROMOTE iff confidence >= threshold AND        |
   |  scope-OK                                                |
   +--------------------------------------------------------+
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 5: Policy + tier resolution                      |
   |  - Plain-English Policy Compiler rules (per tenant /    |
   |    per department) lookup                               |
   |  - 9 Hard Laws applicable to this action                |
   |  - Compute T0..T4 tier from RoutingMode + risk_level    |
   |  - Department permission lookup (allowed_tools,         |
   |    external_action, scan, auto_send)                   |
   |  ACTION: emit (tier, required_approvers, log_level)     |
   +--------------------------------------------------------+
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 6: Mode-aware gate                               |
   |  - UNLEASHED: tier <=2 auto-execute; tier >=3 EXTERNAL  |
   |    -> ask; tier >=3 LOCAL/REVERSIBLE -> auto-execute    |
   |  - BALANCED:  tier <=1 auto-execute; tier 2 NOTIFY;     |
   |    tier >=3 -> ask                                      |
   |  - GOVERNED:  tier 0 auto; tier >=1 NOTIFY; tier >=3    |
   |    -> approval queue                                    |
   |  ACTION: AUTO_EXECUTE | NOTIFY | ASK | QUEUE_FOR_APPROVAL |
   +--------------------------------------------------------+
                                |
                                v
   +--------------------------------------------------------+
   |  Stage 7: Execute + audit                               |
   |  - Hash-chained audit entry written (Hard Law 9)       |
   |  - Cost recorded (cost_guard)                           |
   |  - Memory tier write per NBMF policy                    |
   |  - Outcome surfaced via SSE / toast / approval queue    |
   +--------------------------------------------------------+
```

### 1.2 What changes vs today

The pipeline above is **already implemented in stages 1, 5, 7**.
The redesign clarifies stages 2, 3, 4, 6:

| Stage | Today | After redesign |
|---|---|---|
| 2. OODA | Runs in `cognition/ooda_engine.py` for EXE path; not consistently consulted for CMD path actions that look "harmless" | Consult OODA for ANY action that mutates state, regardless of CMD/EXE label |
| 3. Reasoning escalation | Three-tier router exists in spirit (CLAUDE.md global) but Council/QE fires on operator toggle, not on auto-detected complexity/risk | Add **auto-promote** rules: HIGH/CRITICAL risk OR COMPLEX/VERY_COMPLEX intent triggers Council without operator click |
| 4. Confidence + scope | Confidence score is computed per-call by some adapters but not consistently consulted at the gate | Make confidence + scope a HARD gate: below threshold -> ABSTAIN or one clarifying question (never silently guess) |
| 6. Mode-aware gate | Mode is read at chat orchestrator entry; UNLEASHED has tier-skip behavior, but the LOCAL-vs-EXTERNAL split inside UNLEASHED is not codified | Make the LOCAL-vs-EXTERNAL split the founder-stated rule: in UNLEASHED, tier 3+ local-reversible auto-executes; tier 3+ external still asks |

The plumbing exists. The redesign is mostly **decision logic
tightening + correct surfacing**, not new primitives.

### 1.3 Key invariants

- **Stage 1 SHIELD never collapses.** Even in UNLEASHED, a prompt
  injection attempt is still blocked. Hard Law 5 (data exfiltration)
  and Hard Law 7 (tenant isolation) are enforced regardless of mode.
- **Audit always writes.** Hard Law 9 (audit trail integrity) means
  every action above tier 0 leaves a hash-chained entry. UNLEASHED
  does not silence audit; it only widens auto-execute.
- **Asset Shield always enforces.** Vault adapter + egress filter
  + consent tokens run in all modes. They are CLAUDE.md Rule 18
  protected files; nothing in this redesign touches them.

---

## 2. External approval model

**Founder principle:** Daena asks ONLY for irreversible / external /
high-risk actions. Local, reversible, dept-scoped actions execute
without a click.

### 2.1 What counts as "external"

| Class | Examples | Default treatment |
|---|---|---|
| **External-network mutating** | Outbound HTTP POST/PUT/DELETE to non-Daena origin, OAuth-authenticated write to Google / Notion / GitHub / Slack / etc. | ASK (BALANCED + GOVERNED); UNLEASHED still ASKS for these |
| **External-message-out** | Email send, DM, SMS, webhook fire, social media post, push notification to a third party | ASK in all modes (project CLAUDE.md social-media table is the canonical default; T5 may override for engagement-scoped pen test) |
| **Money** | Stripe charge / refund, PayPal send, crypto tx, vendor purchase, subscription renewal beyond auto-pay band | Always ASK above per-department `auto_pay_threshold`; never expose card / token details (Section 5) |
| **Production deploy** | Cloud Run service revision, Docker image push to prod registry, terraform apply touching prod, schema migration on prod DB | Always ASK regardless of mode; FOUNDER-only |
| **Client-sensitive** | Read or write to a client's repository / domain / IP / report folder; cross-tenant query | Always ASK; surfaced in approval queue with client-name redaction (Section 6) |
| **High-tier scan** | T3+ `scan_workflow` against any target; CVE intel fanout against client property | ASK in BALANCED + GOVERNED; UNLEASHED auto-runs T2 only; T3+ requires engagement scope (Section 4) |

### 2.2 What counts as "local + reversible"

These auto-execute in UNLEASHED, NOTIFY in BALANCED, log only in
GOVERNED (no approval prompt):

- File read / write under workspace root
- DB read / write within tenant scope (any table not under
  `migrations/` or `secret`)
- Soft archive (Hard Law 6: no permanent deletion outside founder
  override)
- Memory tier write (T0-T2)
- Local LLM inference (no external token spend)
- Read-only API hits to the running Daena backend
- Skill catalog updates within the operator's department

### 2.3 What this means for the existing approval queue

The `GovernanceApprovalsPage` (frontend) and `GoaRequest` /
`PendingApproval` (backend) survive unchanged in mechanism. What
changes: **what lands in the queue**. Today the queue receives any
tier 3+ action regardless of class. After redesign:

- **UNLEASHED:** queue receives only EXTERNAL tier 3+ actions.
  Local-reversible tier 3+ actions auto-execute and land in audit
  log only.
- **BALANCED:** queue receives EXTERNAL tier 2+ AND LOCAL tier 3+.
  Most everyday actions never reach the queue.
- **GOVERNED:** queue receives EXTERNAL tier 2+ AND LOCAL tier 3+
  AND any tier 1+ action that matches a custom plain-English policy
  rule.

This is the dial that turns governance from "tier N + above prompts"
to "irreversibility + externality + risk prompts."

---

## 3. Shield Laws (always active)

Per `backend/app/core/hard_laws.py` (lines 27-100). Reproduced here
in operator-readable form because the founder asked the redesign
doc to be explicit about what survives in UNLEASHED.

| # | Law | Always on? | What enforces it today |
|---|---|---|---|
| 1 | **No unlogged actions.** Every governance decision writes an audit row. | YES (SHIELD) | `audit.py` pre-check before action commit |
| 2 | **No self-modification of laws.** Daena cannot rewrite `hard_laws.py` or its policy registry. | GOVERNED only today; redesign promotes to **always on** | Immutable source check at runtime |
| 3 | **No unbounded execution.** Every async/exec call has timeout + resource cap. | BALANCED + GOVERNED today; redesign promotes to **always on** with UNLEASHED getting longer caps | `cost_guard.py` + asyncio timeouts |
| 4 | **Founder override.** Founder role bypasses tier gates but still logs. | All modes | Role check + audit entry tagged `founder_override` |
| 5 | **No data exfiltration.** Outbound bytes are scanned against vault asset fingerprints (API keys, finance, identity, legal, founder memory). | YES (SHIELD) | `asset_shield/egress_filter.py` + `consent_token.py` |
| 6 | **No permanent deletion.** Soft archive only; hard delete is founder + key + reason gated. | GOVERNED only today; redesign keeps as is (UNLEASHED still soft-archives) | `archive.py` enforces; `_developer_mode` enables hard delete in dev only |
| 7 | **Tenant isolation.** Every query injects `tenant_id` filter at DB middleware. | YES (SHIELD) | DB middleware in `core/database.py` |
| 8 | **Shield always active.** SecurityGate.shield_scan + BehaviorGuard run on every chat request. | YES (SHIELD) | `chat_orchestrator.py` Stage 1 |
| 9 | **Audit trail integrity.** Hash-chain append-only; tampering raises `AuditChainBroken` | YES (SHIELD) | `audit.py` chain verifier; `GET /governance/audit/verify` |

**Promotion summary in the redesign:**
- Laws 2 and 3 promote from GOVERNED-only to **always-on** so
  UNLEASHED cannot accidentally allow Daena to overwrite her own
  policy file or run a runaway loop. UNLEASHED still keeps generous
  caps; the cap just exists.

---

## 4. T5 / 3vilbob rules (founder-unlocked, engagement-scoped)

> **Updated 2026-05-02 by founder amendment.** This section is now a
> SUMMARY. The canonical T5 specification is
> `docs/Ultraview/T5_3VILBOB_THINK_EXECUTE_BOUNDARY.md`, which adds
> the Think Mode vs Execute Mode boundary, proof-of-risk
> alternatives, the client sales workflow, and the layered guardrails.
> PR-GOV-02 below is amended to include the Think / Execute split as
> part of the engagement-scope gate work.

**Founder principle:** Keep T5 for authorized client security
testing. Founder unlocks locally with hidden command. T5 EXECUTION
requires an active authorized engagement / scope; T5 THINK MODE can
reason adversarially without engagement (no real external execution).
Local-only, founder/admin-only, secret-key-gated, engagement-scoped
for Execute, audited, kill-switchable. Never expose in normal UI.
Never run external tests without explicit authorized target scope.

### 4.1 Today's state (verified by Explore agent)

| Component | Where | What it does |
|---|---|---|
| Hidden activation REST | `backend/app/api/v1/security_mode.py` | `POST /api/v1/security/mode/activate {key}`, FOUNDER-only |
| Hidden activation chat | `chat_orchestrator.py` (intercept) + `missions.py` | `/3vilbob` chat command (silent); no UI surface, no help text |
| State endpoint | `GET /api/v1/security/mode/state` | returns `{active, environment, capabilities, activated_at, reason_denied}`; never returns the activation key or internal codename |
| Mode service | `backend/app/services/security/evilbob_mode.py` | 3-gate fail-closed: KEY + LOCAL + role per `detect_environment()` |
| T5 capabilities | `services/security/{red_team_ops,exploitation_queue,zero_day_engine,osint_engine,opsec,credential_chain,mission_intelligence,report_tiers}.py` | All flagged DANGEROUS_LOCAL_ONLY in canonicalization plan §1.8 |

### 4.2 Redesign deltas

The redesign adds **engagement scoping** as a hard precondition.
Today, T5 unlocks the capability set globally. After the redesign:

| Property | Today | After redesign |
|---|---|---|
| Activation | KEY + LOCAL + FOUNDER role | KEY + LOCAL + FOUNDER role + **active engagement record** |
| Engagement record | Not modeled | New table (PR-GOV-02): `engagements` with `(id, client_name_hash, target_scope, authorized_at, expires_at, kill_switch_at)` |
| Target check | Caller passes target | T5 endpoint refuses any target outside `engagement.target_scope` (CIDR or domain allowlist + recursive subdomain rule per engagement spec) |
| Kill switch | None | `POST /api/v1/security/mode/kill {engagement_id}` flips `kill_switch_at`; subsequent T5 calls return 423 LOCKED |
| Audit | Hash-chain entry | Hash-chain entry + per-engagement separate audit ledger (so a client's pen test results are scoped to their engagement, never co-mingled with another client's) |
| Surface | No menu, no help, no docs | No menu, no help, no docs (unchanged); engagement is created via founder-only chat command (e.g. `/engagement new <client> --scope <cidr> --expires 7d`) or local CLI tool, never via UI |
| Default mode | Off | Off; auto-deactivates on engagement expiry, host change, or kill switch |
| Reporting | Co-mingled with normal audit log | Separate per-engagement report packet; redacted in normal `GovernanceAuditPage`; visible only via founder-only `/engagements/{id}/report` |

### 4.3 Hard "do not"s for T5

- **Never** auto-discover a target. T5 only operates within
  `engagement.target_scope`.
- **Never** surface T5 in `SettingsGovernance.tsx` or any other
  user-facing page. Even the FOUNDER role does not see a "Enable T5"
  button in the UI.
- **Never** persist a client identifier in the normal audit feed.
  The hash-chain ledger uses `engagement_id`; client identity lives
  in the engagement record, encrypted under the same KEK as
  Asset Shield secrets.
- **Never** run external tests without engagement scope check
  (this is a separate gate from `ASK on external` because T5 actions
  may be EXTERNAL by design).

---

## 5. Spending rules

**Founder principle:** Daena should be allowed to do safe purchases
under budget. Card / token details NEVER exposed.

### 5.1 Per-department budget envelope

The infrastructure exists (`DepartmentBudget` model, `cost_guard.py`,
`cost_router.py`). The redesign formalizes how it's consumed:

| Field | Today | After redesign |
|---|---|---|
| `allocated_amount` | Set at seed; manual edit via API | Same; surfaced under Department Settings (PR-GOV-05 frontend) |
| `spent_so_far` | Updated by `cost_tracker.log_usage` | Same |
| `approval_threshold` | One number | Replaced by **two thresholds**: `auto_pay_threshold` (below which Daena auto-pays) and `escalate_threshold` (above which Finance approval is required regardless of mode) |
| `auto_pay_threshold` | Implicit zero | New: per-dept (e.g. Engineering=$50, Marketing=$200, Operations=$1000); editable by FOUNDER |
| `escalate_threshold` | Implicit max | New: per-dept; if NULL, no upper bound (still subject to `allocated_amount` cap) |
| `escalate_to` | `approving_department_id` (single) | Same field; default = Finance |

### 5.2 Card / token confidentiality

The vault adapter (`asset_shield/vault_adapter.py`, AES-256
envelope) already classifies payment material as `SecretClass.FINANCE`.
The redesign adds two consumer-side rules:

1. **Egress filter scans** payment material fingerprints on every
   outbound request (already happening per Hard Law 5). Any
   accidental inclusion of a card number, CVV, expiry, or PAN
   pattern in a chat response triggers `RefuseToSend` from the
   asset shield.
2. **UI never renders payment material.** Even in
   `SettingsBilling.tsx` the card detail is the LAST 4 digits +
   provider only. The full PAN never leaves the vault. Any new UI
   that touches payment data must consult `vault_adapter.fetch()`
   with a typed `secret_class=FINANCE` request and render via the
   "redacted-by-default" component (PR-GOV-03).

### 5.3 Recurring vs one-shot

- **Recurring** (subscription renewals, scheduled vendor invoices,
  cloud bill auto-pay) follow the per-dept `auto_pay_threshold`;
  Daena auto-pays under threshold and never asks.
- **One-shot** (e.g. "buy this domain", "purchase API credits beyond
  the monthly cap") goes through the same threshold but additionally
  triggers a **rationale capture**: Daena writes a one-line
  justification to the audit log so Finance can review the spending
  pattern weekly.

---

## 6. Client data rules

**Founder principle:** Never reveal client identity, secrets, IPs,
reports, or sensitive data outside approved scope.

### 6.1 Three-tier client data classification

| Class | What | Default protection |
|---|---|---|
| `CLIENT_IDENTITY` | Client name, contact email, contract reference, account manager | Stored in vault (FOUNDER-readable); referenced elsewhere by `client_id_hash` |
| `CLIENT_TARGET_SCOPE` | CIDRs, domains, GitHub orgs, S3 buckets the client authorized for testing | Per-engagement record; never co-mingled across clients |
| `CLIENT_REPORTS` | Findings, CVE matches, evidence chains, screenshots, recovered creds (T5 only) | Per-engagement report packet; redacted in normal audit feed |

### 6.2 Egress + chat rendering rules

- **Outbound bytes** scanned by `asset_shield/egress_filter.py` for
  client identity fingerprints. If a chat reply tries to include a
  client name and the request is not scoped to that client's
  engagement, the egress filter rewrites the name to `<CLIENT_REDACTED>`.
- **Chat replies** about Daena's own work for "Client X" are
  permitted only when:
  - The current session has an active engagement matching `client_id_hash`, OR
  - The operator is FOUNDER and explicitly opted in via the activation chat command.
- **Audit page** displays `engagement_id` instead of client name in
  the normal feed. The FOUNDER-only `/engagements/{id}/report`
  endpoint resolves IDs to names with audit trail.

### 6.3 Cross-tenant isolation

Hard Law 7 (tenant isolation) already enforces this at DB middleware
level. The redesign adds a runtime invariant: **no T5 capability
function may accept a `client_id` argument that doesn't match the
operator's active engagement**. This is enforced in the engagement
gate (PR-GOV-02), not in each capability function.

---

## 7. Human approval thresholds

This is the master table the founder asked for. Each row maps a
trigger to whether Daena pauses for human approval, in which mode.

| Trigger | UNLEASHED | BALANCED | GOVERNED |
|---|---|---|---|
| **Money: dept auto-pay below `auto_pay_threshold`** | auto | auto | auto, audit |
| **Money: between auto-pay and `escalate_threshold`** | auto, audit, notify | ASK once per session | ASK every time |
| **Money: above `escalate_threshold`** | ASK | ASK | ASK + Finance dept review |
| **External message: positive social reply / draft post** | DRAFT (notify) | DRAFT, then ASK to publish | DRAFT, then ASK |
| **External message: critical reply / DM / follow** | ASK | ASK | NEVER (project CLAUDE.md social-media table) |
| **Production deploy: Cloud Run revision / prod migration / prod terraform** | ASK | ASK | ASK + 2-of-2 (Founder + Ops) |
| **T5 scan against authorized engagement scope** | auto, audit (T5 unlock + engagement required) | same | same |
| **T5 scan outside engagement scope** | REFUSED | REFUSED | REFUSED |
| **Hard delete (file / row / branch)** | ASK + reason | ASK + reason | ASK + reason + 2-of-2 |
| **Soft archive** | auto | auto | auto, notify |
| **Reading client data inside active engagement** | auto | auto, audit | auto, audit, notify |
| **Reading client data outside active engagement** | REFUSED | REFUSED | REFUSED |
| **Confidence below `confidence_threshold` (default 0.6)** | one clarifying question OR ABSTAIN | same | same |
| **Confidence below 0.3 on irreversible action** | REFUSED | REFUSED | REFUSED |
| **Tier 3+ LOCAL/REVERSIBLE** | auto | NOTIFY | ASK |
| **Tier 3+ EXTERNAL** | ASK | ASK | ASK + custom policy lookup |
| **Plain-English policy match (e.g. "ask before posting on LinkedIn")** | ASK (rule wins over mode) | ASK | ASK |

**Key invariants of this table:**
- The approval queue receives **fewer, higher-value items**.
  UNLEASHED operators rarely see prompts; BALANCED operators see
  prompts for genuinely external things; GOVERNED operators see the
  full enterprise gate.
- T5 is orthogonal to mode: it requires the engagement gate
  regardless of mode.
- Custom policies (Plain-English Policy Compiler) override the
  defaults: an operator-authored "always ask before LinkedIn" rule
  takes precedence over UNLEASHED's "external = ASK once".

---

## 8. UI simplification

**Founder principle:** Show simple labels (Unleashed / Balanced /
Governed). Hide T0-T4 internals. Governance rules under Advanced.

### 8.1 What the operator sees

After PR-GOV-05 (UI), `SettingsGovernance.tsx` shows:

```
+-------------------------------------------------------+
|  Governance Mode                                       |
|                                                        |
|  ( ) Unleashed                                         |
|      Daena acts. Local + reversible work flows         |
|      without prompts. External / money / deploys      |
|      still ask. Shield Laws + audit + asset shield     |
|      always active.                                    |
|                                                        |
|  (o) Balanced  [DEFAULT]                               |
|      Daena handles routine work. Asks for external    |
|      irreversible actions, money above threshold,      |
|      production deploys, client-sensitive actions,     |
|      high-tier scans.                                  |
|                                                        |
|  ( ) Governed                                          |
|      Enterprise mode. Approvals required for high-     |
|      risk and policy-defined actions. Full audit /     |
|      reporting.                                        |
|                                                        |
|  [v] Show advanced                                     |
+-------------------------------------------------------+
```

When **Show advanced** is toggled (mirrors the Settings show-advanced
pattern from PR-SETTINGS-CLEANUP), the panel reveals:

- **Confidence threshold** slider (0.4 .. 0.9)
- **Council/QE auto-promote rules** editor (which complexity/risk
  values trigger which mode)
- **Plain-English policy** rules list + add-rule button (already
  exists at `PlainEnglishPolicies.tsx`)
- **Per-department permission matrix** (Section 9)
- **T0-T4 tier internals** read-only view (was the legacy
  "advanced internal tiers" disclosure)
- **Audit chain integrity** check (links to `GovernanceAuditPage`)

T5 / 3vilbob is **not visible even under Show advanced**. The
founder activates it via the chat command path or local CLI tool.

### 8.2 Tier badge policy in chat

| Mode | Tier 0-1 (gray) | Tier 2 (yellow) | Tier 3+ (red) |
|---|---|---|---|
| UNLEASHED | hidden | hidden | shown only if action is queued (rare) |
| BALANCED | hidden | shown | shown |
| GOVERNED | hidden | shown | shown + count badge in nav |

PR-GOV-05 implements the gray/yellow/red badge classes per the
CLAUDE.md spec. Today the frontend renders tier as plain text and
uses risk-level colors instead.

### 8.3 Approval queue surfaces

The approval queue page stays at `/governance/approvals`. The nav
badge now shows count of items the operator needs to act on; in
UNLEASHED this is usually zero. The approval card UI (Approve /
Reject / View context) is unchanged from today.

---

## 9. Department rules

**Founder principle:** Per-department budget, allowed tools,
external action permission, scan permission, auto-send permission.

### 9.1 Department permission matrix

The 10 departments are defined in `constants.py:312-353`. Today
each department has a budget row but no per-tool permission matrix.
The redesign adds:

```
Department: Engineering
  Budget:                allocated, spent, auto_pay, escalate
  Allowed tools:         file/*, terminal/*, git/*, http/*
  Allowed runtimes:      claude_code, codex, gemini_cli, ollama
  External action:       ASK (default UNLEASHED)
  Scan permission:       T0-T2 auto, T3+ engagement-required
  Auto-send permission:  draft + ASK (never auto-send DM)
  Custom policies:       (links to PlainEnglishPolicies)
```

| Department | External action default | Scan permission default | Auto-send default |
|---|---|---|---|
| Engineering | ASK | T2 auto, T3+ engagement | DRAFT (never auto) |
| Product | ASK | T1 auto, T2+ ASK | DRAFT |
| Marketing | ASK in all modes | T0 only | DRAFT (project CLAUDE.md social-media defaults) |
| Sales | ASK in all modes | T0 only | DRAFT |
| Finance | ASK | T0 only | NEVER auto-send |
| Operations | ASK | T2 auto, T3+ engagement | DRAFT |
| Research | DRAFT (notify) | T2 auto, T3+ ASK | DRAFT |
| Legal & Compliance | ASK | T0 only | NEVER auto-send |
| Skill Governance | DRAFT | T1 auto | DRAFT |
| Security Operations | DRAFT (notify) | T3 auto, T4+ engagement | NEVER auto-send |

These are **defaults per project CLAUDE.md social-media-marketing
soul rules + canonicalization plan §1.4**. Founder edits per dept
via PR-GOV-05 frontend.

### 9.2 Department -> Action ladder integration

Stage 5 of the decision ladder (Section 1.1) consults the department
permission matrix in addition to global Hard Laws and tenant
policies. If a department permission says "Marketing cannot do
external scan T1+", that overrides UNLEASHED's permissive default.

---

## 10. Frontend wiring analysis

This section addresses the founder's "wire them to frontend too"
note. Below is the gap inventory based on the current-state map
(Section 12 references the Explore agent output that produced this).

### 10.1 What's wired today

| Surface | Status |
|---|---|
| `SettingsGovernance.tsx` 3-mode picker | UI exists; **frontend-only state** (uiStore + `persistUiPref`); does NOT POST mode change to backend |
| `GovernanceApprovalsPage.tsx` approval queue | Wired; `PATCH /governance/approvals/{id}/decide` |
| `GovernanceAuditPage.tsx` audit log + verify | Wired; `GET /governance/audit/verify` |
| `PlainEnglishPolicies.tsx` policy compiler | Wired; `POST /policies/compile` + persist |
| Per-skill / per-tool ALLOW/ASK/BLOCK dropdown | Wired in `SkillsPage.tsx` + `ConnectionsV2Panel.tsx` |
| Approval streaming | `useApprovalsStream()` hook (likely SSE / polling) |

### 10.2 What's documented but not wired

| Gap | Effect today | PR that wires |
|---|---|---|
| **Mode change persistence** | Operator flips mode in UI; backend approval path still uses system-default mode. Each user sees their own UI mode but approval/tier behavior is global. | PR-GOV-01 (backend `PUT /api/v1/settings/governance_mode` with FOUNDER gate) + frontend POST call |
| **FOUNDER role check on mode endpoint** | Any user can flip mode via API; no backend role guard | PR-GOV-01 (FastAPI dependency) |
| **Tier-colored badges (gray/yellow/red) per CLAUDE.md** | Code uses RISK colors instead of TIER colors | PR-GOV-05 (CSS + Badge component) |
| **Per-department budget / policy / permission UI** | Backend models exist (DepartmentBudget, DepartmentPolicy); no UI page to edit | PR-GOV-05 (DepartmentGovernancePanel) |
| **Council / Quintessence selector** | Backend RoutingMode enum + engines exist; no operator-facing selector | PR-GOV-05 (chat reasoning-mode picker, hidden under Show advanced) |
| **Confidence threshold control** | No UI; threshold lives in code constant | PR-GOV-01 (slider under Show advanced) |
| **Auto-promote rules editor** | No UI; rules live in code constant | PR-GOV-05 |
| **Department permission matrix UI** | No UI; matrix lives in default-seed only | PR-GOV-05 |
| **T5 activation** | Hidden chat command + REST exist; no UI surface (CORRECT per founder rule) | NOT wired to UI; engagement creation goes through chat command + local CLI per Section 4 |
| **Engagement record UI** | No table, no UI | PR-GOV-02 (DB model + founder-only `/engagements/*` endpoints; no normal-UI page) |
| **Spending audit-side ledger view** | Cost rows visible in `SettingsBilling`; no per-dept governance view | PR-GOV-03 (per-dept spending + auto-pay-vs-escalate split surfaced under Department Settings) |
| **External-send approval UX** | Approval queue handles it generically; no per-platform draft/approve banner pattern in non-social contexts | PR-GOV-04 (generalize the social-platform draft/approve banner from `social_action_pending.tsx` style) |

### 10.3 What's wired but should retire / hide

| Surface | Today | After redesign |
|---|---|---|
| Tier label as plain text in chat ("Tier 3 / HIGH risk") | Visible in all modes | Hidden in UNLEASHED; shown in BALANCED / GOVERNED |
| "Show advanced internal tiers" disclosure | Open by default in `SettingsGovernance` | Behind Show advanced toggle (mirror of PR-SETTINGS-CLEANUP pattern) |
| Risk-color badges | Used for governance tier (mismatch with CLAUDE.md spec) | Reserved for risk_level only; tier gets its own gray/yellow/red palette |

---

## 11. Implementation PR sequence

Five sequential PRs. Each has its own brief, hard rules, and
report. Nothing in this design doc executes; PRs ship from this
document.

### PR-GOV-01: Policy / risk decision ladder

**Goal:** Tighten Stages 2-6 of the decision ladder. Add the
mode-aware gate split (LOCAL/REVERSIBLE vs EXTERNAL) inside
UNLEASHED. Persist `governance_mode` + `confidence_threshold` to
`User.settings` JSONB and gate the PUT endpoint on FOUNDER role.

**Backend:**
- `services/governance.py`: add `classify_externality(action) ->
  {LOCAL_REVERSIBLE | EXTERNAL_NETWORK | EXTERNAL_MESSAGE | MONEY |
  PROD_DEPLOY | CLIENT_SENSITIVE | T5_SCAN}` (auto-derived from
  intent + tool_call signature)
- `services/governance.py`: extend `evaluate_action()` to consult
  the externality classification + mode + dept permission matrix
  before deciding queue / notify / auto
- `api/v1/settings.py`: `PUT /settings/governance_mode` with
  FOUNDER dependency; persists to `User.settings.governance_mode`
- `services/cognition/ooda_engine.py`: ensure CMD path also runs
  Observe + Orient when intent is mutating

**Frontend:**
- `pages/settings/SettingsGovernance.tsx`: POST mode change to
  backend (drop frontend-only Zustand path)
- Add confidence-threshold slider under Show advanced

**Tests:** unit tests for `classify_externality`, integration test
for full ladder per mode, regression that audit chain stays intact
through mode swap.

**Effort:** ~3-4h. **Risk:** MED (touches every governance decision
point). **Stop-and-report.**

### PR-GOV-02: T5 engagement-scope gate

**Goal:** Add engagement record + scope gate to T5 activations.
Today T5 unlocks globally; after this PR, T5 calls require an
active engagement record whose target_scope matches.

**Backend:**
- New model `Engagement(id, client_name_hash, target_scope: list[str],
  authorized_at, expires_at, kill_switch_at, created_by_founder_id)`
  in `models/engagement.py`
- New table migration (alembic)
- `services/security/evilbob_mode.py`: enforce
  `requires_engagement_for_t5_call(target)` -> raises
  `EngagementOutOfScope` if no active engagement covers `target`
- New founder-only endpoints `/api/v1/engagements/{create,list,kill,
  report}` (no UI surface; chat command + local CLI consumers)
- `audit.py`: emit `engagement_id` instead of client name in normal
  feed
- `api/v1/security_mode.py`: `POST /security/mode/kill` flips
  kill switch

**Frontend:** none (T5 stays hidden per Section 4.3).

**Tests:** unit tests for engagement scope match (CIDR + domain +
recursive subdomain); integration test that T5 capability function
refuses out-of-scope target; regression that engagement expiry
auto-deactivates.

**Effort:** ~5-6h. **Risk:** HIGH (security-sensitive code path).
**Stop-and-report.**

### PR-GOV-03: Spending / payment safety rules

**Goal:** Split `approval_threshold` into `auto_pay_threshold` +
`escalate_threshold`. Add typed `vault_adapter.fetch(secret_class=
FINANCE)` consumer rule + redacted-by-default render component.
Surface per-dept spending split in Department Settings.

**Backend:**
- `models/department_budget.py`: add `auto_pay_threshold`,
  `escalate_threshold` columns; default-fill from existing
  `approval_threshold` for backward compat
- `services/cost_guard.py`: consult new thresholds in
  `check_action_cost(action, dept_id)`
- `services/billing/cost_tracker.py`: tag rationale string on
  one-shot purchases

**Frontend:**
- `pages/settings/SettingsBilling.tsx`: render LAST 4 + provider
  only via `<RedactedSecret class="finance"/>` component
- New `components/RedactedSecret.tsx`: typed wrapper that calls a
  hook to get the redacted view; never accepts the raw value as a
  prop
- `pages/DepartmentGovernancePanel.tsx` (PR-GOV-05 page): per-dept
  threshold editor

**Tests:** unit tests for the new threshold logic; integration
test that egress filter blocks an outbound request containing a
PAN-shape match; component test that `<RedactedSecret>` cannot
accidentally render plaintext.

**Effort:** ~3h. **Risk:** MED. **Stop-and-report.**

### PR-GOV-04: External-send rules

**Goal:** Generalize the social-platform draft/approve banner to
all external messaging (email, DM, SMS, webhook, social).
Implement the per-mode external-send treatment from Section 7.

**Backend:**
- `services/notification_service.py` (or a new `external_send_service.py`):
  add `propose_send(channel, payload, dept_id) -> ExternalSendProposal`
  that returns either `auto-sent` (rare) or a `pending_approval_id`
- `models/external_send.py`: new `ExternalSendProposal` table with
  drafted payload, channel, dept_id, reviewer_id, decided_at
- `api/v1/external_send.py`: `GET /external-send/pending`,
  `POST /external-send/{id}/approve`, `POST /external-send/{id}/reject`

**Frontend:**
- `components/ExternalSendBanner.tsx`: inline draft preview +
  approve/reject buttons, similar to existing
  `InlineApprovalBanner.tsx` but channel-aware (email / DM / SMS /
  webhook / social-platform-X)
- Wire into chat orchestrator SSE stream so the banner appears
  inline in the chat where the proposed send originated

**Tests:** unit tests for channel classification; integration test
for the full draft -> approve -> send loop in BALANCED + GOVERNED;
regression that UNLEASHED still asks for external-message-out
class actions.

**Effort:** ~4h. **Risk:** MED. **Stop-and-report.**

### PR-GOV-05: Simplified governance UI

**Goal:** Implement the operator-facing UI from Section 8. Add
gray/yellow/red tier badges, the per-department permission matrix
editor, the Council/QE auto-promote rules editor, the confidence
threshold slider. Hide all T0-T4 internals behind Show advanced.

**Frontend:**
- `pages/settings/SettingsGovernance.tsx`: rewrite per Section 8.1
  layout
- `components/TierBadge.tsx`: new component with gray/yellow/red
  classes; consumes `tier` prop and renders per CLAUDE.md spec
- `pages/governance/DepartmentGovernancePanel.tsx` (NEW):
  per-dept matrix from Section 9.1
- `pages/governance/ReasoningRulesPanel.tsx` (NEW):
  Council/QE auto-promote rules; lives under Show advanced
- `components/ChatReasoningModePicker.tsx`: hidden by default;
  visible in chat header when Show advanced is on; lets operator
  pick STANDARD / COUNCIL / QE per-message override
- Inline tier badge replacement: replace risk-color badges in chat
  with `<TierBadge>` consuming TIER not risk

**Backend:** GET endpoints for department permission matrix and
reasoning rules; PUT endpoints with FOUNDER guard. No new business
logic; just persistence.

**Tests:** Playwright e2e for `/settings/governance` showing 3
buttons + Show advanced reveal; component test for `<TierBadge>`
color contract; component test for `<DepartmentGovernancePanel>`
matrix edits.

**Effort:** ~5-6h. **Risk:** LOW (pure UI plumbing). **Stop-and-report.**

### PR ordering rationale

| PR | Reason for ordering |
|---|---|
| GOV-01 first | Decision ladder is the foundation; everything else assumes it works |
| GOV-02 second | T5 gate is independent and high-priority security; ship before any subsequent T5-touching work |
| GOV-03 third | Spending rules block on GOV-01 thresholds being honored |
| GOV-04 fourth | External-send blocks on GOV-01 externality classification |
| GOV-05 last | UI cannot ship until backend gates are correct (otherwise the operator changes a knob and nothing happens) |

---

## 12. Honesty notes (CLAUDE.md project Rule 17)

This redesign was written from a **code-grounded current-state map**.
The Explore agent that produced the map flagged these as facts that
would otherwise have been silently assumed:

1. **`GovernanceMode` exists at `constants.py:159-170`** with the
   three values UNLEASHED / BALANCED / GOVERNED.
2. **Hard Laws are real and numbered** at `hard_laws.py:27-100`.
   Laws 1, 5, 7, 8, 9 enforce in SHIELD (always-on); Laws 2, 3, 6
   are mode-gated today (this redesign promotes 2 and 3 to
   always-on).
3. **T5 is fully wired today** via the hidden activation surface
   (REST + chat command + service); engagement scoping is the new
   piece (PR-GOV-02).
4. **Asset Shield is fully wired** (vault_adapter + egress_filter +
   consent_token + operator_initiation). It is CLAUDE.md Rule 18
   protected; this redesign does not touch it.
5. **The plain-English policy compiler is fully wired** (backend +
   `PlainEnglishPolicies.tsx`); the redesign uses it as the
   "custom rules" hook for per-tenant governance.
6. **Mode change is frontend-only today.** The
   `SettingsGovernance.tsx` selector does NOT POST to the backend.
   This is the single biggest wiring gap (PR-GOV-01 fixes it).
7. **No tier-colored badges today.** The frontend uses risk-level
   colors instead. PR-GOV-05 adds the gray/yellow/red TierBadge.
8. **No per-department permission UI today.** Backend models exist;
   no frontend page. PR-GOV-05 adds it.
9. **No engagement record today.** T5 unlocks globally without a
   client-scope gate. PR-GOV-02 adds it.

Anything in this doc not labeled as "today" or "after redesign"
should be assumed to be **target state**, not current state.

---

## 13. Hard rule final check

| Check | Result |
|---|---|
| Em dashes in this doc | 0 (verified by grep) |
| Code modified | 0 files |
| Files deleted | 0 |
| Production deploys triggered | 0 |
| Scans run | 0 |
| External messages sent | 0 |
| Secrets read or printed | 0 (Explore agent confirmed none surfaced; T5 activation key not enumerated by file/line in this doc) |
| Protected files modified (Rule 18) | 0 (vault_adapter / vault_migration / oauth_credentials_store all referenced as KEEP_HOT_PATH) |
| New tests added | 0 (planning only) |
| Migration files generated | 0 (PR-GOV-02 schedules one for engagement table; not run) |

---

**Stopping here as requested. Awaiting founder direction for PR-GOV-01
(policy / risk decision ladder) per Section 11.**
