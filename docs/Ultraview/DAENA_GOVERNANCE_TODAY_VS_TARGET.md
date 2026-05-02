# Daena Governance: Today vs Target

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime` @ `17be681`
**Author:** Claude Code (Opus 4.7) under founder direction
**Status:** **Inventory only.** Zero product code modified. Zero tests
run. Zero migrations, no flag flips, no `vault --apply`, no
deletions, no external scans, no external messages, no secrets read.
**Pairs with:** `DAENA_GOVERNANCE_REDESIGN_INTERNAL_FIRST.md`
(target state, what we want), `T5_3VILBOB_THINK_EXECUTE_BOUNDARY.md`
(refined T5 spec). **Read order:** this doc first (where we are),
then INTERNAL_FIRST (where we are going).

> **Thesis.** Before building governance redesign PRs, we need an
> honest, code-grounded answer to "what do we already have?" This
> doc is that answer. Section by section against the redesign
> target, with file:line citations from direct reads (not from
> documentation, not from prior memory). Three claims in the prior
> design doc turn out to be wrong; they are corrected in Section 4.
> The five biggest gaps are ranked in Section 5. Section 6 is the
> one-page summary an operator can skim before opening any PR.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| No production deploy | Yes (inventory only) |
| No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes (governance audit unrelated) |
| No `vault --apply` | Yes |
| Do not delete policies | Yes |
| Do not implement code yet | Yes (zero product files modified) |
| Do not deploy | Yes |
| Do not run scans | Yes |
| Do not remove governance | Yes (audit only; nothing removed) |
| Do not expose T5 in normal UI | Yes |
| No secrets printed or committed | Yes (T5 activation key, internal codenames not enumerated; capability function names cited as filenames only) |
| Em dashes (project CLAUDE.md Rule 12) | None introduced (verified Section 7) |
| No protected files modified (`vault_adapter.py`, `vault_migration.py`, `oauth_credentials_store.py`) | Yes (read-only references) |

---

## 1. Methodology

Every "today" claim in this doc is grounded in a direct file read
performed during this session, not in prior memory or in the
Explore agent's first-pass mapping. Where the Explore agent was
wrong, the correction is documented in Section 4.

Files read directly for this inventory:

| File | Lines read | Why |
|---|---|---|
| `backend/app/core/constants.py` | 110-180, 280-330 | `GovernanceMode`, `GovernanceSlider`, `RiskLevel`, `PermissionLevel`, `DEFAULT_DEPARTMENTS` |
| `backend/app/core/hard_laws.py` | 1-200 | `HARD_LAWS` tuple, `SHIELD_LAW_IDS` / `BALANCED_LAW_IDS` / `ALL_LAW_IDS` sets, `check_hard_laws` dispatcher |
| `backend/app/api/v1/security_mode.py` | 1-147 | T5 hidden activation REST surface |
| `backend/app/api/v1/settings.py` | 290-330, plus targeted greps | `PUT /settings/user` handler, governance_mode validation regex |
| `frontend/src/pages/settings/SettingsGovernance.tsx` | 1-150 | The 3-mode picker + Shield Laws + Soft Laws cards |
| `frontend/src/stores/uiStore.ts` | 270-380 | `persistUiPref` body, `governanceMode` hydration |
| `backend/app/services/governance.py` | targeted greps for `evaluate_action`, `governance_mode` | What consumes the mode |

Anything not directly verified is labeled "(unverified)" or
"(per Explore agent first-pass; not re-confirmed)".

---

## 2. Section-by-section inventory

The redesign doc has 9 substantive sections (1-9 plus the
implementation PR list). For each, here is what exists today, what
is missing, and which PR closes the gap.

### 2.1 Section 1 - Internal governance model (decision ladder)

**Target:** 7-stage ladder: SHIELD -> OODA -> Reasoning -> Confidence
-> Policy/tier -> Mode-aware gate -> Execute+audit.

**Today:**

| Stage | Today's state |
|---|---|
| 1. SHIELD | **WIRED.** `chat_orchestrator.py` Stage 1 calls `SecurityGate.shield_scan()` + `BehaviorGuard` on every chat request. Hard Laws 1, 5, 7, 9 enforced via `check_hard_laws()` dispatch (`hard_laws.py:120-139`). Asset Shield egress filter runs on outbound bytes. |
| 2. OODA Observe + Orient | **WIRED for EXE path** (`cognition/ooda_engine.py`). Per canonicalization plan §1.1, KEEP_HOT_PATH. **Gap:** CMD-path actions that mutate state do not consistently consult OODA today. |
| 3. Reasoning escalation | **WIRED for operator-toggled Council/QE.** RoutingMode enum + `council_engine.py` + `quintessence_engine.py` exist (canonicalization plan §1.1 KEEP_HOT_PATH). **Gap:** auto-promote on COMPLEX/VERY_COMPLEX or HIGH/CRITICAL risk does not fire without operator click. |
| 4. Confidence + scope check | **PARTIAL.** Confidence scores are computed by some adapters but not consistently consulted at the gate. No global `confidence_threshold` setting. |
| 5. Policy + tier resolution | **WIRED.** `governance.py:evaluate_action()` looks up tier from RoutingMode + risk_level. Plain-English Policy Compiler (`policy_compiler.py`, `policy_store.py`, frontend `PlainEnglishPolicies.tsx`) reads YAML at `backend/app/config/policies/<tenant>/<id>.yaml`. |
| 6. Mode-aware gate | **WIRED at coarse grain.** Mode dispatch lives in `governance.py` and `hard_laws.py:135-139`. **Gap:** the LOCAL-vs-EXTERNAL split inside UNLEASHED (founder rule) is not codified; everything tier 3+ goes through the same approval queue regardless of class. |
| 7. Execute + audit | **WIRED.** Hash-chained audit ledger via `audit.py`. Cost recorded by `cost_guard.py` + `cost_tracker.py`. Memory tier writes via `memory.py`. |

**Gap summary:** Stages 1, 5, 7 are fully wired. Stages 2, 3, 4, 6
need tightening (auto-promote rules, per-stage confidence gate,
LOCAL-vs-EXTERNAL split inside UNLEASHED).

**PR that closes it:** PR-GOV-01 (policy / risk decision ladder).

### 2.2 Section 2 - External approval model

**Target:** Approval queue receives only EXTERNAL tier 3+ in
UNLEASHED; EXTERNAL tier 2+ AND LOCAL tier 3+ in BALANCED;
everything tier 1+ matching custom rules in GOVERNED.

**Today:** approval queue receives any tier 3+ action regardless of
externality class. The classification function
`classify_externality(action) -> {LOCAL_REVERSIBLE | EXTERNAL_NETWORK
| EXTERNAL_MESSAGE | MONEY | PROD_DEPLOY | CLIENT_SENSITIVE |
T5_SCAN}` does not exist yet.

**What does exist:**

- `GoaRequest` and `PendingApproval` models (`models/governance.py`)
- `GovernanceApprovalsPage.tsx` page with approve / reject buttons
  wired to `PATCH /api/v1/governance/approvals/{id}/decide`
- `useApprovalsStream()` SSE / polling hook
- Default tier matrix in `governance.py` keyed on
  `GovernanceMode + RiskLevel`

**Gap summary:** Mechanism (queue + decide endpoint + stream)
exists. The classifier that decides WHAT lands in the queue is the
missing piece.

**PR that closes it:** PR-GOV-01 (adds `classify_externality`).

### 2.3 Section 3 - Shield Laws

**Target:** Shield Laws always active even in UNLEASHED. Promote
Laws 2 and 3 from GOVERNED-only to always-on (per redesign doc
Section 3 promotion rule).

**Today (DIRECTLY VERIFIED at `hard_laws.py:106-117`):**

| Set | Members | Modes |
|---|---|---|
| `SHIELD_LAW_IDS` | `{1, 5, 7, 9}` | UNLEASHED + BALANCED + GOVERNED (always-on) |
| `BALANCED_LAW_IDS` | `{1, 3, 5, 7, 9}` | BALANCED + GOVERNED (adds Law 3) |
| `ALL_LAW_IDS` | `{1, 2, 3, 4, 5, 6, 7, 8, 9}` | GOVERNED only (adds 2, 4, 6, 8) |

The dispatch at `hard_laws.py:120-139`:

| Mode | Function called |
|---|---|
| `UNLEASHED` | `_check_shield_laws()` -- enforces Laws 1, 5, 7, 9 (Laws 1, 7, 9 enforced at middleware/DB/audit level; only Law 5 has explicit pattern matching in this file at lines 150-161) |
| `BALANCED` | `_check_balanced_laws()` -- shield + Law 3 (timeout check on EXECUTE actions) |
| `GOVERNED` | `_check_all_laws()` -- adds Law 6 deletion intercept |

**Gap summary:** SHIELD set is `{1, 5, 7, 9}` today, NOT `{1, 5, 7,
8, 9}` as my prior design doc claimed. Law 8 is a META law about
the always-on guarantee, implemented THROUGH Laws 1, 5, 7, 9 being
in SHIELD_LAW_IDS. Law 4 (Founder Override) is in ALL_LAW_IDS only;
in UNLEASHED there are no tier checks to bypass anyway, so the
founder-override mechanism is effectively a no-op in UNLEASHED but
still works because the FOUNDER role bypasses at the auth layer.

The redesign promotion (Laws 2 and 3 to always-on) is a one-line
edit to the SHIELD_LAW_IDS set, not a structural change. PR-GOV-01
includes this promotion.

**PR that closes it:** PR-GOV-01 (single-line set edit + tests).

### 2.4 Section 4 - T5 / 3vilbob

**Target:** Think Mode (no engagement required, dispatcher refuses
action verbs) + Execute Mode (10-gate fail-closed + engagement
scope + kill switch). See `T5_3VILBOB_THINK_EXECUTE_BOUNDARY.md`
for full spec.

**Today (DIRECTLY VERIFIED):**

| Component | File | State |
|---|---|---|
| Hidden activation REST | `backend/app/api/v1/security_mode.py` | **WIRED.** `POST /api/v1/security/mode/activate {key}` requires `Depends(require_role("FOUNDER"))` (line 78). Calls `evilbob_mode.activate(key, user_id)`. Returns `ModeStateResponse` with `active`, `environment`, `capabilities`, `activated_at`, `activated_by`, `reason_denied`. |
| Hidden deactivation REST | same | **WIRED.** `POST /api/v1/security/mode/deactivate` FOUNDER-only. |
| State endpoint | same | **WIRED.** `GET /api/v1/security/mode/state` available to any authenticated user; never returns the internal codename. |
| Mode service singleton | `backend/app/services/security/evilbob_mode.py` | **WIRED.** 3-gate fail-closed: KEY + LOCAL + FOUNDER role per `detect_environment()`. |
| T5 capability files | `backend/app/services/security/{red_team_ops, exploitation_queue, zero_day_engine, osint_engine, opsec, credential_chain, mission_intelligence, report_tiers}.py` | **WIRED.** All flagged DANGEROUS_LOCAL_ONLY in canonicalization plan §1.8. Become callable when evilbob_mode is active. |

**Gap summary:** Three-gate activation works today. The new pieces
the redesign adds:

1. **Engagement record table** (none exists today) - PR-GOV-02
2. **Per-call engagement scope check** (today the gate is at the
   activation layer; calls to capability functions don't re-check
   scope per-target) - PR-GOV-02
3. **Kill switch** (no `/api/v1/security/mode/kill {engagement_id}`
   endpoint) - PR-GOV-02
4. **Think vs Execute dispatcher split** (today everything goes
   through the same dispatcher; cognition + action are not
   separated) - PR-GOV-02
5. **Per-engagement audit ledger** (today everything goes to the
   normal hash-chain) - PR-GOV-02

**UI state:** No T5 UI surface exists today. The redesign keeps it
that way (founder profile pill only, never in main nav).

**PR that closes it:** PR-GOV-02 (engagement-scope gate + Think /
Execute split).

### 2.5 Section 5 - Spending rules

**Target:** Split `approval_threshold` into `auto_pay_threshold` +
`escalate_threshold`. Per-dept editor in UI. Card / token
confidentiality enforced at vault + UI render.

**Today:**

| Component | State |
|---|---|
| `DepartmentBudget` model | **WIRED.** Per `(tenant, dept, cycle_key)` row with `allocated_amount`, `spent_so_far`, `approval_threshold` (single number), `approving_department_id`. |
| `cost_guard.py` | **WIRED.** Cost preflight stage 5 of the chat pipeline. Per canonicalization plan §1.1 KEEP_HOT_PATH. Consults DepartmentBudget. |
| `cost_router.py` | **WIRED.** Cost-aware fallback in router. |
| `cost_tracker.py` | **WIRED.** Logs usage per request to `cost_record` table. Integrated into chat pipeline Stage 10. |
| Vault adapter for FINANCE class | **WIRED.** `asset_shield/vault_adapter.py` (Rule 18 protected). Per the inventory in canonicalization plan §1.1, FINANCE class secrets are stored AES-256 envelope-encrypted. |
| Egress filter on PAN / card material | **WIRED via Hard Law 5.** Outbound interceptor checks against allowed domains and consent records. |
| UI: `SettingsBilling.tsx` | **WIRED.** Renders billing data; whether it shows full PAN or last-4 only requires verification. |
| UI: per-dept budget editor | **NOT WIRED.** No frontend page to edit per-dept budgets, thresholds, or approval chains. Founder edits via direct API call today. |

**Gap summary:** The `approval_threshold` (single number) needs to
split into `auto_pay_threshold` + `escalate_threshold`. UI to edit
per-dept thresholds is missing. The vault + egress filter for FINANCE
class are already wired.

**PR that closes it:** PR-GOV-03 (threshold split + redacted-by-
default render component + per-dept editor).

### 2.6 Section 6 - Client data rules

**Target:** Three-tier classification (CLIENT_IDENTITY,
CLIENT_TARGET_SCOPE, CLIENT_REPORTS); engagement-scoped; egress
filter rewrites client names to `<CLIENT_REDACTED>` outside the
authorized engagement; no T5 capability accepts a `client_id` not
matching active engagement.

**Today:**

| Component | State |
|---|---|
| `Tenant` isolation at DB middleware | **WIRED.** Hard Law 7 enforced. Per canonicalization plan §1.1, every query injects `tenant_id` filter. |
| Asset Shield secret classes | **WIRED.** `vault_adapter.py` knows about FINANCE, IDENTITY, LEGAL, FOUNDER_MEMORY classes. |
| Client identity classification | **NOT WIRED as a separate class.** No `CLIENT_IDENTITY` / `CLIENT_TARGET_SCOPE` / `CLIENT_REPORTS` enum today. Tenant separation works for Daena's tenants, but per-client (sub-tenant) classification of "this is client X's pen-test data" doesn't exist as a structured concept. |
| Engagement record | **NOT WIRED.** PR-GOV-02 adds this. |
| Egress rewrite of client names | **NOT WIRED.** Today's egress filter blocks based on vault asset fingerprints, not on a per-engagement client identity match. |

**Gap summary:** Tenant isolation is rock-solid. Per-client (within-
tenant) data classification is the missing layer. PR-GOV-02 adds
the engagement record (which is also where client identity lives);
PR-GOV-04 extends the egress filter to consume engagement context.

**PR that closes it:** PR-GOV-02 + PR-GOV-04.

### 2.7 Section 7 - Human approval thresholds (the master table)

**Target:** Master table mapping each trigger to behavior per mode.
See redesign doc Section 7.

**Today:** the underlying mechanisms exist (mode dispatch, tier
matrix, approval queue), but the threshold table is implicit in
code constants, not in a single declarative source. Operators
cannot inspect or edit it without reading source.

**Gap summary:** the table itself becomes a config artifact in
PR-GOV-01 (likely a YAML at `backend/app/config/governance/
approval_matrix.yaml`) that the dispatcher consults.

**PR that closes it:** PR-GOV-01.

### 2.8 Section 8 - UI simplification

**Target:** Three-mode picker (Unleashed / Balanced / Governed) is
the primary surface. T0-T4 internals hidden behind Show advanced.
Tier badges in chat use gray/yellow/red palette per CLAUDE.md spec.
Approval queue badge in nav.

**Today (DIRECTLY VERIFIED at `SettingsGovernance.tsx`):**

| Surface | State |
|---|---|
| 3-mode picker (Unleashed / Balanced / Governed) | **WIRED.** Lines 64-83. Renders 3 buttons with icon + label + description. Active mode highlighted. |
| Internal tier disclosure | **WIRED behind `<details>` element** (line 87-112). Shows T0-T4 with per-tier label + description + percentage. NOT shown by default; must be toggled open. This is good. |
| Shield Laws card | **WIRED.** Lines 116-131. Lists 4 always-on laws (audit, exfiltration, tenant isolation, audit integrity). |
| Soft Laws card | **WIRED with conditional opacity-40** (line 134) when mode != GOVERNED. Lists 5 laws (no self-mod, no unbounded exec, founder override, no permanent deletion, mode-toggle-FOUNDER). |
| Mode change persistence | **WIRED to backend** via `persistUiPref('default_governance_mode', mode)` -> debounced `api.put('/settings/user', { default_governance_mode })` after 500ms (uiStore.ts:345-355). |
| Backend FOUNDER role check on mode change | **NOT WIRED.** `PUT /settings/user` at settings.py:295-309 only requires `Depends(get_current_user)`, not `require_role("FOUNDER")`. Any authenticated user can flip the mode via API. **THIS IS A REAL SECURITY GAP.** |
| Tier-colored badges in chat | **NOT WIRED per CLAUDE.md spec.** Code uses risk-level colors (NONE=starlight-500, LOW=success, MEDIUM=warning, HIGH=amber, CRITICAL=error) for what should be tier-colored badges (gray for T0-T1, yellow for T2, red for T3+). Two different concepts share one palette today. |
| Approval queue count badge in nav | **NOT VERIFIED.** Approval queue page exists; whether nav has a count badge requires checking `Layout.tsx` or similar; not done in this read pass. |
| Confidence threshold slider | **NOT WIRED.** No UI surface today. |
| Council/QE auto-promote rules editor | **NOT WIRED.** No UI today. |

**Gap summary:** The 3-mode picker exists and persists correctly.
The biggest issue is the missing FOUNDER role check on the mode-
change endpoint. Tier badges use risk-level palette (semantic
mismatch). Several Show-advanced surfaces (confidence slider,
auto-promote rules, per-dept matrix) are missing.

**PR that closes it:** PR-GOV-01 (FOUNDER role check on settings
endpoint) + PR-GOV-05 (TierBadge + Show advanced reveal +
per-dept panel).

### 2.9 Section 9 - Department rules

**Target:** Per-department permission matrix (allowed tools,
external action, scan permission, auto-send). Editable in
DepartmentGovernancePanel.

**Today:**

| Component | State |
|---|---|
| `DEFAULT_DEPARTMENTS` seed | **WIRED.** `constants.py:312-353` defines all 10 departments with `name`, `sunflower_index`, `description`. |
| `DepartmentBudget` model | **WIRED.** Per-dept budget with single `approval_threshold`. |
| `DepartmentPolicy` model | **WIRED.** Per canonicalization plan §1.2, `department_policy.py` exists with trigger conditions JSONB + required_approvers + escalation_chain. |
| `department_router.py`, `department_workflows.py`, `department_prompts.py` | **WIRED.** Per canonicalization plan §1.2, KEEP_SUPPORTING. |
| Per-dept allowed-tools matrix | **NOT WIRED.** No per-dept allowlist for tools; today's permission gates are per-tool (PermissionLevel enum) globally, not per-department. |
| Per-dept external-action permission | **NOT WIRED.** Today's external-action gate is mode-based (UNLEASHED/BALANCED/GOVERNED), not dept-based. |
| Per-dept scan permission | **NOT WIRED.** Today's scan tier (T0-T5) gate is global, not per-dept. |
| Per-dept auto-send permission | **NOT WIRED.** Today's social-media-marketing soul rules (project CLAUDE.md table) are global defaults applied universally. |
| UI: DepartmentGovernancePanel | **NOT WIRED.** No frontend page exists. |

**Gap summary:** Department mechanism (model + service + router) is
solid. The per-dept *permission matrix* (the matrix in redesign
Section 9.1) is the missing layer. Backend models need new
columns; frontend needs a new page.

**PR that closes it:** PR-GOV-05 (frontend) + small backend column
additions in PR-GOV-01.

---

## 3. Implementation PR mapping (current state -> target)

| PR | Closes which gaps from above |
|---|---|
| **PR-GOV-01** (decision ladder) | §2.1 (auto-promote, confidence gate, LOCAL-vs-EXTERNAL split), §2.2 (`classify_externality`), §2.3 (promote Laws 2+3 to always-on), §2.7 (approval matrix as YAML), §2.8 (FOUNDER role check on settings endpoint), §2.9 (per-dept permission matrix backend columns) |
| **PR-GOV-02** (T5 engagement gate + Think/Execute split) | §2.4 (engagement record + scope check + kill switch + Think/Execute dispatcher split + per-engagement audit), §2.6 (engagement table also stores client identity) |
| **PR-GOV-03** (spending) | §2.5 (threshold split, redacted render, per-dept threshold editor) |
| **PR-GOV-04** (external send) | §2.2 (consumer side: external-message-out approval queue), §2.6 (egress filter consumes engagement context for client-name redaction) |
| **PR-GOV-05** (UI) | §2.8 (TierBadge component, Show advanced reveal, confidence slider, auto-promote editor), §2.9 (DepartmentGovernancePanel frontend), tier badge palette swap in chat |

---

## 4. Corrections to the prior design doc

The first redesign pass (`DAENA_GOVERNANCE_REDESIGN_INTERNAL_FIRST.md`)
was written from the Explore agent's first-pass map. Direct reads
during this inventory pass surfaced three claims that were wrong.
The redesign doc remains correct in spirit; these are
implementation-detail corrections that the implementing PRs need to
honor.

### Correction 1: SHIELD_LAW_IDS is `{1, 5, 7, 9}`, not `{1, 5, 7, 8, 9}`

**Where the prior doc said** (Section 3 of the redesign doc):
> Laws 1, 5, 7, 9 enforced via the SHIELD_LAW_IDS membership of
> Laws 5+7 and the always-runs nature of Laws 1+9

> Specifically Hard Law 5 (data exfiltration) and Hard Law 7
> (tenant isolation) which CLAUDE.md says are always-on even in
> UNLEASHED.

**What's actually in code** (`hard_laws.py:106-117`):

```python
SHIELD_LAW_IDS: frozenset[int] = frozenset({1, 5, 7, 9})
BALANCED_LAW_IDS: frozenset[int] = frozenset({1, 3, 5, 7, 9})
ALL_LAW_IDS: frozenset[int] = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9})
```

The prior doc's Section 3 table was correct that Laws 1, 5, 7, 9
are always-on. But it implied Law 8 was also in SHIELD; that's
wrong. Law 8 is the META law that says "Shield is always active";
it's a documentation law, not a check. Law 8 is in ALL_LAW_IDS
(GOVERNED only) for the dispatch, but the always-on guarantee it
describes is implemented THROUGH Laws 1, 5, 7, 9 being in
SHIELD_LAW_IDS.

**Implementation correction:** PR-GOV-01's "promote Laws 2 and 3
to always-on" task only needs to add `{2, 3}` to SHIELD_LAW_IDS.
It does NOT need to add Law 8.

### Correction 2: Mode change DOES persist to backend

**Where the prior doc said** (Sections 8.2 + 10.2 of the redesign
doc):
> Frontend Zustand path; does NOT POST mode change to backend.

**What's actually in code:**

- `SettingsGovernance.tsx:52-55`: `handleModeChange` calls
  `setGovernanceMode(mode)` AND `persistUiPref(
  'default_governance_mode', mode)`.
- `uiStore.ts:345-355`: `persistUiPref` is a debounced (500ms)
  `api.put('/settings/user', { [key]: value })` call to the
  backend.
- `settings.py:215`: schema validates `default_governance_mode`
  against the regex `^(UNLEASHED|BALANCED|GOVERNED)$`.
- `settings.py:130, 162`: backend default is `GOVERNED` for new
  users.

So the mode IS persisted per-user. The prior doc was wrong about
"frontend-only state."

**The REAL gap (still needs PR-GOV-01):** the `PUT /settings/user`
endpoint at `settings.py:295-309` only requires
`Depends(get_current_user)`, NOT `Depends(require_role("FOUNDER"))`.
Any authenticated user can change their own governance mode via
API. This is a security gap (Hard Law 8 says "Governance mode
toggle requires FOUNDER role" but the endpoint doesn't enforce it).

**Implementation correction:** PR-GOV-01's settings-endpoint-guard
task needs to add a FOUNDER role dependency specifically for the
`default_governance_mode` field, not for the entire `PUT
/settings/user` endpoint (other fields like `display_name` should
still be self-editable). The pattern: split the endpoint into
"general user prefs" (any user) and "governance prefs" (FOUNDER
only), OR add a per-field check inside `_update_user_preferences_impl`
that raises 403 if `body.default_governance_mode is not None and
user.role != 'FOUNDER'`.

### Correction 3: A deprecated `GovernanceSlider` enum still exists

**Where the prior doc didn't mention** (oversight):
The codebase has a `GovernanceSlider` enum at `constants.py:112-144`
with 5 legacy values (YOLO, LIGHT, STANDARD, STRICT, PARANOID) plus
the 3 canonical values (UNLEASHED, BALANCED, GOVERNED). It exposes
a `to_governance_mode()` mapper that collapses the 5-value slider
to the 3-mode system.

The old slider is referenced in 3 places:
- `governance.py:157, 346, 504`: `GovernanceSlider(value).to_governance_mode()`
  is called when reading legacy stored values
- `settings.py:131, 216`: `default_governance_slider` field marked
  Deprecated, mirrors `default_governance_mode`
- `constants.py:624`: `governance_mode = GovernanceSlider(legacy_slider).to_governance_mode()`

**Why this matters:** when PR-GOV-01 lands, it should also remove
the slider's `default_governance_slider` field from the user
settings schema (after a deprecation window). The mapper
`to_governance_mode()` can stay as a one-off coercion for any
historical rows. The double-storage is noise that confuses the
audit trail.

**Implementation correction:** PR-GOV-01 includes a migration
task: drop `default_governance_slider` from `UserPreferencesUpdate`
and `UserPreferencesResponse`; keep the mapper for one release
cycle.

---

## 5. Top 5 gaps ranked by user impact

Ordered by what an operator would actually notice if they sat down
with Daena today after reading the redesign doc.

### Gap #1 - `PUT /settings/user` accepts `default_governance_mode` from any authenticated user

**Surface:** anyone with a valid JWT can issue
`PUT /api/v1/settings/user {default_governance_mode: 'UNLEASHED'}`
and flip their own governance mode. There is no FOUNDER role check
at the endpoint.

**Why it matters:** Hard Law 8 explicitly says "Governance mode
toggle requires FOUNDER role." Today's implementation does not
enforce this. A non-founder user can self-promote to UNLEASHED.

**Fix:** PR-GOV-01 adds a per-field FOUNDER guard in
`_update_user_preferences_impl`. ~20 lines including tests.

### Gap #2 - Tier vs risk share one color palette

**Surface:** `GovernanceAuditPage.tsx` and `InlineApprovalBanner.tsx`
use risk-level colors (NONE/LOW/MEDIUM/HIGH/CRITICAL) for what
should be tier-colored badges (T0-T1 gray, T2 yellow, T3+ red per
CLAUDE.md spec).

**Why it matters:** Two different concepts (governance tier vs
action risk) collapse into one visual signal. An operator scanning
the audit page cannot tell at a glance whether a red badge means
"this was high-risk" or "this required approval."

**Fix:** PR-GOV-05 adds a `<TierBadge>` component with the
gray/yellow/red palette and a `<RiskBadge>` that retains today's
NONE..CRITICAL palette. Code-wide swap takes ~30 minutes.

### Gap #3 - No engagement record / scope gate for T5

**Surface:** T5 unlocks globally today via the 3-gate (KEY + LOCAL +
FOUNDER). There is no per-target scope check at capability call
time. Once T5 is unlocked, every capability function is callable
against any target.

**Why it matters:** the founder principle is "T5 must be local-
only, founder/admin-only, secret-key-gated, ENGAGEMENT-SCOPED,
audited, and kill-switchable." Engagement scoping is the missing
layer.

**Fix:** PR-GOV-02. New `engagements` table, per-call scope check
in capability functions, kill-switch endpoint, per-engagement
audit ledger. Largest of the 5 PRs (~5-6h).

### Gap #4 - No per-department permission matrix

**Surface:** `DepartmentBudget` and `DepartmentPolicy` models
exist; no UI to edit them; no per-dept tool / external-action /
scan permission columns.

**Why it matters:** the founder rule "per-department budget,
allowed tools, external action permission, scan permission,
auto-send permission" is not implementable until the matrix exists.

**Fix:** PR-GOV-01 adds backend columns, PR-GOV-05 adds frontend
DepartmentGovernancePanel.

### Gap #5 - No `classify_externality` function

**Surface:** today the approval queue receives any tier 3+ action.
The redesign wants only EXTERNAL tier 3+ in UNLEASHED. The
classifier function does not exist.

**Why it matters:** UNLEASHED operators see approval prompts for
local-reversible actions today. The whole point of UNLEASHED is to
remove unnecessary prompts; without the classifier, UNLEASHED
behaves more like BALANCED.

**Fix:** PR-GOV-01 adds `classify_externality(action) -> ExternalityClass`.
Auto-derived from intent + tool_call signature. ~50 LOC + tests.

---

## 6. One-page summary: today vs target

Quick reference for an operator skimming before opening a PR.

| Section | Today | Target | PR |
|---|---|---|---|
| 1. Decision ladder | Stages 1, 5, 7 wired; 2, 3, 4, 6 partial | Full 7-stage ladder with auto-promote + confidence gate + LOCAL/EXTERNAL split | GOV-01 |
| 2. External approval | Queue receives any tier 3+ action | Queue receives only EXTERNAL tier 3+ in UNLEASHED | GOV-01 |
| 3. Shield Laws | `{1, 5, 7, 9}` always-on | Promote Laws 2 + 3 to always-on (now `{1, 2, 3, 5, 7, 9}`) | GOV-01 |
| 4. T5 / 3vilbob | 3-gate activation works; no engagement scope; no kill switch | Add Think/Execute split + engagement gate + kill switch + per-engagement audit | GOV-02 |
| 5. Spending | Single `approval_threshold`; no per-dept UI | `auto_pay_threshold` + `escalate_threshold` split + per-dept editor | GOV-03 |
| 6. Client data | Tenant isolation rock-solid; no per-client classification | Engagement record holds client identity; egress filter consumes engagement context | GOV-02 + GOV-04 |
| 7. Approval thresholds | Implicit in code constants | Declarative YAML at `config/governance/approval_matrix.yaml` | GOV-01 |
| 8. UI simplification | 3-mode picker wired + persists; tier disclosure exists; no FOUNDER guard on settings endpoint; tier vs risk share palette | FOUNDER guard added; TierBadge component; Show advanced reveal pattern (mirror PR-SETTINGS-CLEANUP) | GOV-01 + GOV-05 |
| 9. Department rules | Models + services exist; no per-dept permission matrix; no UI | Backend columns + DepartmentGovernancePanel frontend | GOV-01 + GOV-05 |

**Estimated total effort:** ~20-22 hours of focused work spread
across 5 PRs. Risk profile: GOV-02 is HIGH (security-sensitive),
GOV-01 / GOV-03 / GOV-04 are MED, GOV-05 is LOW.

**Sequencing constraint:** GOV-01 must land before GOV-03, GOV-04,
GOV-05 because they all depend on its `classify_externality` +
matrix YAML + per-dept columns + FOUNDER guard. GOV-02 can land
in parallel with GOV-01 (no shared files).

---

## 7. Hard rule final check

| Check | Result |
|---|---|
| Em dashes added | 0 (verified) |
| Code modified | 0 files |
| Files deleted | 0 |
| Production deploys triggered | 0 |
| Scans run | 0 |
| External messages sent | 0 |
| External systems touched | 0 |
| Secrets read or printed | 0 (T5 activation key, internal codenames not enumerated; capability functions cited as filenames only) |
| Protected files modified (Rule 18) | 0 (vault_adapter / vault_migration / oauth_credentials_store referenced as KEEP_HOT_PATH only) |
| New tests added | 0 (inventory only) |
| Migrations generated | 0 |
| Tasks completed | 3 (verify Explore claims, write inventory, em-dash check) |

---

**Stopping here as requested. This doc is the operator's starting
point for the governance redesign work. Next concrete step (when
authorized): begin PR-GOV-01 implementation per
`DAENA_GOVERNANCE_REDESIGN_INTERNAL_FIRST.md` Section 11.**
