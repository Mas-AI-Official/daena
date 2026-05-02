# T5 / 3vilbob: Think vs Execute Boundary

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime` @ `17be681`
**Author:** Claude Code (Opus 4.7) under founder direction
**Status:** **Planning only.** Zero product code modified. Zero tests
run. Zero scans triggered. Zero external messages sent. Zero
external systems touched. Zero secrets read.
**Companion docs:** `DAENA_GOVERNANCE_REDESIGN_INTERNAL_FIRST.md`
(this doc updates Section 4 of that one),
`DAENA_CANONICALIZATION_PLAN.md`,
`DAENA_BACKEND_BLINDSPOT_INVENTORY.md`. Anchor for project
CLAUDE.md hidden activation rules + canonicalization plan §1.8
(DANGEROUS_LOCAL_ONLY).

> **Thesis.** Real attackers do not respect scope. To defend clients
> well, Daena must think like an attacker. To stay safe and lawful,
> Daena must NOT act like one outside an authorized engagement. The
> answer is to split T5 into two distinct gates: a **Think Mode**
> that grants cognitive freedom (out-of-scope adversarial reasoning,
> exploit-chain modeling, monitoring-bypass analysis) without any
> capability to touch a real external system, and an **Execute Mode**
> that gates real action behind founder + local env + key + active
> engagement + target scope + time window + technique whitelist
> + evidence folder + kill switch + audit. Most of T5's value to
> defenders comes from Think Mode plus the proof-of-risk alternatives
> (canary tokens, sandbox clones, passive evidence). Execute Mode is
> the rare path for an authorized client engagement where the only
> way to prove a finding is to run the real chain end-to-end.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| Do not implement code yet | Yes (planning only) |
| Do not run scans | Yes |
| Do not send messages | Yes (no email / DM / SMS / webhook / social fired) |
| Do not touch external systems | Yes (no outbound HTTP issued from this PR) |
| Do not delete policies | Yes |
| Do not deploy | Yes |
| Em dashes (project CLAUDE.md Rule 12) | None introduced (verified) |
| No secrets printed | Yes (T5 activation key not enumerated; capability codenames cited as filenames only) |
| No protected files modified (Rule 18) | Yes (vault_adapter / vault_migration / oauth_credentials_store untouched) |

---

## 1. Why T5 exists

T5 is not "let Daena hack things." T5 is the cognitive + execution
machinery a senior offensive security engineer uses on an authorized
engagement, packaged inside Daena. The four jobs it does:

1. **Attacker simulation.** Defenders who only think defensively
   miss the attacker's path of least resistance. T5 lets Daena
   reason about a target the way an attacker would: not
   "what should be allowed?" but "what would actually work?"
2. **Blind-spot discovery.** Static analysis + scanners find known
   patterns. T5's adversarial reasoning surfaces blind spots: chained
   misconfigurations, business-logic abuse, supply-chain weak links,
   social-engineering vectors, race conditions under load.
3. **Proof of impact.** A CVSS score is theory. A proof-of-risk
   demonstration (under authorized scope) shows the client what an
   attacker could actually do with the finding. This is what
   converts a tracked-but-deprioritized issue into a fixed one.
4. **Defense validation.** After remediation, T5 re-runs the same
   chain to prove the fix worked. Without this, "we patched it"
   stays unverified.

The founder principle: **Daena must think like an attacker to defend
clients well. Daena must NOT act like one outside authorized scope.**
The Think / Execute split codifies this distinction.

---

## 2. Two-mode design

### 2.A. T5 Think Mode

**Purpose:** Aggressive adversarial reasoning that can reason beyond
scope internally. No real external execution. Produces structured
artifacts that feed either Execute Mode or one of the proof-of-risk
alternatives in Section 3.

**Activation gate:** FOUNDER role + LOCAL env + activation KEY.
**Engagement scope NOT required.** This is pure cognition; it
does not touch any external system.

**What Think Mode is allowed to reason about:**

| Capability | Description |
|---|---|
| Out-of-scope scenario modeling | "If the attacker had access to subnet X (which is NOT in the engagement scope), what would the chain look like?" Think Mode answers honestly. The output is a hypothesis, not an action. |
| Exploit-chain planning | Multi-step kill-chain construction: initial access, persistence, privilege escalation, lateral movement, exfiltration, anti-forensics. Each step labeled with required preconditions and likely controls that would block it. |
| Monitoring-bypass analysis | "How would an attacker evade SIEM rule X / EDR signature Y / WAF pattern Z?" Think Mode reasons about evasion theory. |
| Business-logic abuse | "What if a user ratchets a quota field to -1? What if they replay the OAuth callback?" Logic flaws that no scanner catches. |
| Supply-chain attack pathways | "Which dependency, if compromised, gives the attacker an unobstructed path to the vault?" Reasoning about transitive trust. |
| Social-engineering vectors | "What information is publicly available about the target's CFO that would make a wire-transfer phish credible?" OSINT-driven reasoning, NOT OSINT collection (collection is Execute). |
| Threat-model enumeration | STRIDE, attack-tree, MITRE ATT&CK technique mapping. |

**What Think Mode CANNOT do (capability gate):**

- Issue any outbound HTTP request to a third party
- Read any file outside the local workspace + engagement evidence
  folder (when in an Execute session)
- Send any message (email / DM / SMS / webhook / social)
- Pull credential material from the vault for use in a real call
- Invoke any of the DANGEROUS_LOCAL_ONLY capability functions
  (`red_team_ops`, `exploitation_queue`, `zero_day_engine`,
  `osint_engine`, `opsec`, `credential_chain`, `mission_intelligence`)
- Initiate a network connection to any host

These constraints are enforced at the **capability dispatch layer**:
Think Mode binds to a restricted dispatcher that returns
`OutOfThinkScope` for any attempt to reach an action verb. The
dispatcher itself is the gate; Think Mode prompts cannot bypass it
because the bypass would require code Think Mode does not have
permission to invoke.

**Outputs of Think Mode (structured artifacts):**

| Artifact | Description |
|---|---|
| `attack_hypothesis.md` | Plain-language description of the suspected weakness, attacker motivation, target asset, and confidence score |
| `risk_chain.json` | Ordered list of `(step_id, action, precondition, likely_control, evidence_required)` rows |
| `required_authorization.md` | What the engagement scope would have to include to safely prove this hypothesis (CIDR, domain, time window, technique whitelist) |
| `safe_proof_plan.md` | Which proof-of-risk alternative (Section 3) would prove or disprove this WITHOUT needing real execution; if real execution is the only path, says so explicitly |
| `defensive_recommendations.md` | Controls that would break the chain at each step, ranked by ease of implementation |

**Output destination:** `engagements/think_only/<session_id>/` if no
active engagement; `engagements/<engagement_id>/think/<session_id>/`
if inside an active engagement.

### 2.B. T5 Execute Mode

**Purpose:** Real-world action against an authorized target, scoped
to a specific client engagement, time-bounded, audited, kill-
switchable.

**Activation gate (all required, fail-closed):**

| Gate | Check |
|---|---|
| **Founder-only** | Caller has FOUNDER role |
| **Local-only** | `evilbob_mode.detect_environment() == LOCAL` (host check + interactive session check) |
| **Secret-key-gated** | Activation key matches; checked at every Execute call, not just at unlock |
| **Active engagement required** | An `Engagement` row exists with `kill_switch_at IS NULL` and `expires_at > now()` |
| **Target scope required** | The target of the action matches `engagement.target_scope` (CIDR + domain + recursive subdomain rule) |
| **Time window required** | `now()` is inside `engagement.authorized_window_start..end` |
| **Allowed techniques required** | The capability function being called is listed in `engagement.allowed_techniques` (e.g. `[passive_recon, port_scan, http_probe, sql_injection_test]`; default empty so engagements must opt in to each technique) |
| **Evidence folder required** | `engagement.evidence_folder` exists, is writable, and the per-engagement KEK can decrypt it |
| **Kill switch required** | The kill-switch endpoint (`POST /api/v1/security/mode/kill {engagement_id}`) is reachable; if unreachable at session start, Execute Mode refuses to begin |
| **Audit required** | Hash-chain audit ledger is healthy (`/governance/audit/verify` returns `valid=true`); if broken, refuse |

**Execute Mode capability surface:** the
DANGEROUS_LOCAL_ONLY files in `services/security/` (per
canonicalization plan §1.8) become callable. Each capability
function additionally consults the engagement gate before doing any
real I/O: a function may pass the dispatcher gate but still refuse
at the per-target check.

**Required preconditions on every Execute call:**

1. A Think Mode artifact exists in the engagement folder
   (`attack_hypothesis.md` + `risk_chain.json`). Execute Mode refuses
   to act on a target without a paper trail of "why are we doing
   this?"
2. The specific step about to execute is documented in
   `risk_chain.json` with its `evidence_required` value matching the
   evidence the action will collect.
3. The action's target is inside `engagement.target_scope`.
4. The action's technique is inside `engagement.allowed_techniques`.
5. The kill switch is still off.

**Outputs of Execute Mode (per-engagement, encrypted at rest):**

| Artifact | Description |
|---|---|
| `evidence/<step_id>/<timestamp>.bin` | Raw evidence (HTTP response, screenshot, recovered string) encrypted under engagement KEK |
| `evidence/<step_id>/<timestamp>.meta.json` | Hash, source URL, request bytes hash, response status, redaction map |
| `audit/per_engagement_chain.jsonl` | Hash-chained per-engagement audit (separate from normal `/governance/audit` so client A's pen test never co-mingles with client B's) |
| `report/before.md` | Findings written into the engagement report (Section 5) |

**Kill switch behavior:** flipping `kill_switch_at` causes the
dispatcher to return `EngagementKilled` for ALL subsequent capability
calls for that engagement. In-flight calls are not cancelled
(network requests already on the wire complete) but their results
are written to the audit ledger with `killed_after_dispatch=true` and
NOT written to the evidence folder. This is the safety property:
the kill switch always works, even if a long-running scan is mid-
request.

---

## 3. Proof-of-risk alternatives

The founder principle: **most proof of impact does not require running
the full attack chain.** Think Mode produces the hypothesis; one of
the alternatives below proves or disproves it without escalating
to Execute. Execute Mode is the LAST resort, used only when the
client's contract requires a real chain.

| Alternative | What it proves | What it does NOT require |
|---|---|---|
| **Authorized micro-proof** | A single, narrow capability call inside `engagement.target_scope` confirming one step of the chain (e.g. "the WAF lets through this specific payload but not data exfiltration") | The full chain; the actual exploit |
| **Canary token** | Drop a uniquely identifiable token (URL, document, AWS key tagged for canary alerting) inside the suspected weak link; demonstrate that an attacker reaching the data could exfil it | Real exfil of real data; only the canary fires |
| **Sandbox / staging clone** | Daena runs the full attack chain against a staging clone of the client's infrastructure (provided by the client, isolated from production) | Touching production; risking real customer data |
| **Passive exposure proof** | Demonstrate the weakness from publicly available evidence: open S3 buckets, indexed search results, leaked credentials in public dumps, exposed `.git/` directories | Any active probe; pure observation |
| **Test transaction** | A small, obviously-test transaction (e.g. $0.01 charge with `Test_Daena` reference) confirming a payment-flow weakness | A real-value transaction that would harm the client |
| **Defense validation after fix** | Re-run the same chain (or the equivalent micro-proof) after remediation to confirm the fix worked | Continued exposure if fix is incomplete |

**Selection rule (encoded in `safe_proof_plan.md`):** Think Mode picks
the LEAST invasive alternative that would prove or disprove the
hypothesis with adequate confidence. Execute Mode is only proposed
when no alternative meets the evidence bar that the engagement
contract requires.

**Per-step proof escalation table** (Think Mode emits this):

| Hypothesis confidence after Think | Recommended proof method |
|---|---|
| > 0.9, low-impact finding | Defensive recommendation only; no proof needed |
| > 0.9, high-impact finding | Passive exposure proof OR canary token |
| 0.6 .. 0.9 | Authorized micro-proof |
| 0.3 .. 0.6 | Sandbox / staging clone |
| < 0.3 | More Think Mode reasoning before any proof; ABSTAIN if blocked |

---

## 4. Unleashed mode clarification

The founder asked the redesign doc to clarify what Unleashed
preserves. UNLEASHED is permissive about LOCAL + REVERSIBLE actions
(no human approval needed for routine work). It is NOT permissive
about T5, secrets, payment data, identity data, or unauthorized
external execution. The boundaries below are the canonical list.

| Class | UNLEASHED behavior |
|---|---|
| Routine local work (file read/write, DB read/write inside tenant scope, soft archive, memory writes T0-T2) | Auto-execute, audit |
| Internal cognition (OODA, Council, QE, Think Mode) | Runs when complexity / risk demands it; not gated on mode |
| Shield Laws (1, 5, 7, 8, 9 from `hard_laws.py`) | ALWAYS active, identical behavior to BALANCED + GOVERNED |
| Asset Shield (vault adapter, egress filter, consent tokens, operator initiation) | ALWAYS active, identical behavior |
| Client identity / contracts / reports | NEVER revealed outside an engagement that authorizes it |
| Card / token / PAN data | NEVER rendered in chat; NEVER egressed; NEVER appears in audit log |
| Founder-private memory (NBMF T4) | NEVER readable by any other user, even in UNLEASHED |
| Cross-tenant data | NEVER readable; tenant_id middleware filter is mandatory |
| External payments above per-dept `auto_pay_threshold` | ASK |
| External messages (email / DM / SMS / webhook / social) | DRAFT + ASK (positive); ASK (critical); NEVER (DM / follow / unfollow) |
| Production deploys | ASK regardless of mode |
| **T5 Think Mode** | Founder-only, key-gated, no engagement required; permitted in UNLEASHED |
| **T5 Execute Mode** | Founder-only, key-gated, engagement required; mode is orthogonal (UNLEASHED does not relax engagement gate) |

**The single sentence summary:** UNLEASHED removes unnecessary human
approval for local / reversible work. It does not remove Shield
Laws, Asset Shield, client data protection, payment confidentiality,
or T5 Execute's engagement gate.

---

## 5. Client sales workflow

T5 is most valuable when used inside a structured engagement that
moves a client from "I think we have risk" through "we have proof"
through "we have a verified fix." The six-stage workflow:

```
Stage 1: PRE-SALES PASSIVE RISK REPORT
   Daena (Think Mode + passive proof only) produces a one-page
   risk report from public evidence + public CVE intel + open
   port scans of the client's PUBLIC perimeter only.
   No engagement record yet. No active scans. No T5 Execute.

   Output: passive_risk_report.pdf
   Audience: prospective client decision maker

Stage 2: CLIENT SIGNS MICRO-SCOPE
   Client agrees to a narrow, time-bounded engagement: one
   target subnet OR one application OR one API surface, for a
   one-week window, with a defined technique whitelist.

   Output: signed engagement contract + micro-scope spec
   Daena action: create Engagement record (Section 4 of the
   broader governance doc + PR-GOV-02)

Stage 3: DAENA RUNS AUTHORIZED PROOF
   Inside the engagement scope only:
   - Think Mode produces full attack hypothesis + risk_chain
   - Daena picks the least-invasive proof method (Section 3)
     for each step
   - Execute Mode runs the proof (only when Section 3 alternatives
     do not meet the evidence bar)
   - Evidence is encrypted under the engagement KEK and lives
     in the engagement folder

   Output: before.md (per-step findings) + evidence/

Stage 4: DAENA FIXES / REMEDIATES
   Engagement-scope-bound remediation actions:
   - Code patches written via normal local + reversible tooling
     (file write inside the engagement repo; no T5 needed)
   - Configuration changes proposed, reviewed, applied through
     normal CI/CD with per-action approval per the client's
     governance mode
   - WAF rules / firewall rules drafted; client applies

   Output: remediation_plan.md + applied_changes.json

Stage 5: DAENA RERUNS PROOF
   The same proof method that proved the finding in Stage 3
   re-runs after remediation:
   - If proof still succeeds: fix is incomplete; goto Stage 4
   - If proof fails (the attack chain is broken): fix is
     verified; goto Stage 6

   Output: after.md + evidence/post_fix/

Stage 6: BEFORE / AFTER REPORT
   Final report packet for the client:
   - Executive summary (one page)
   - Per-finding before / after with evidence references
   - Open issues + recommendations (defensive)
   - Engagement audit log (per-engagement chain, decrypted for
     client; hashes preserved for tamper proof)

   Output: engagement_<id>_final_report.pdf
   Daena action: deactivate the engagement (set
   `kill_switch_at = now()`); evidence folder retained for
   contractual retention period
```

**What this workflow makes deliberately impossible:**

- Stage 1 cannot accidentally become Stage 3. Pre-sales is
  passive-only; the founder cannot fast-path to Execute without
  signing the engagement contract first (the engagement record IS
  the gate).
- Stage 3 cannot exceed scope. Even Think Mode hypotheses about
  out-of-scope adjacent systems remain hypotheses; their proof
  requires either re-scoping the engagement or using a
  Section 3 alternative.
- Stage 5 cannot be skipped. The before-vs-after report is the
  client deliverable; no engagement closes without it.

---

## 6. UI design

The founder principle: **do not expose T5 in normal UI. Show T5
only in founder profile / hidden command. Show "Think only" when
no authorized engagement exists. Show "Execute allowed" only when
engagement scope exists.**

### 6.1 What a normal user sees

Nothing. T5 has zero visibility in any UI surface used by a normal
operator. No tab, no button, no menu, no help tooltip, no docs link
inside the application. The activation path is the hidden chat
command (`/3vilbob` and equivalents) or a local CLI tool the founder
runs outside the browser.

### 6.2 What the founder sees (after activation)

Founder-only UI surfaces appear ONLY when:
- Founder role is active in the session, AND
- T5 has been activated for the current local environment, AND
- The host running the browser matches `evilbob_mode.detect_environment()`'s LOCAL check.

If all three are true, an inconspicuous indicator appears in the
founder profile menu (NOT in the main nav, NOT in the chat header):

```
+-------------------------------------------+
|  Founder profile menu                      |
|                                            |
|  ...                                       |
|  T5 status                                 |
|     [ Think only ]                         |
|     No active engagement.                  |
|     /engagement new <client> --scope ...   |
|     to enable Execute Mode.                |
|  ...                                       |
+-------------------------------------------+
```

When an engagement is active and matches the current target context:

```
+-------------------------------------------+
|  Founder profile menu                      |
|                                            |
|  ...                                       |
|  T5 status                                 |
|     [ Execute allowed ]                    |
|     Engagement: <hash>                     |
|     Scope: <CIDR / domains>                |
|     Window: <ends in 4d 12h>               |
|     Techniques: <count> allowed            |
|     [ Kill switch ]                        |
|  ...                                       |
+-------------------------------------------+
```

The "Execute allowed" pill is the ONLY UI affordance that confirms
real execution is permitted. The kill switch button is the ONLY UI
control that triggers an engagement halt; clicking it requires a
typed confirmation string ("kill <engagement_short_id>") to prevent
accidental press.

### 6.3 Per-mode status copy

| State | Status pill | Subline |
|---|---|---|
| T5 not activated | (no pill, no surface) | (nothing in UI) |
| T5 activated, no engagement | "Think only" | "No active engagement. Reasoning artifacts are local. Execute Mode disabled." |
| T5 activated, engagement active | "Execute allowed" | engagement metadata + kill switch |
| T5 activated, engagement killed | "Execute halted" | "Kill switch flipped at <timestamp>. Restart engagement to resume." |
| T5 activated, engagement expired | "Execute expired" | "Engagement window ended at <timestamp>. Renew via founder CLI." |

### 6.4 What the audit page shows

`GovernanceAuditPage.tsx` (the normal audit page) shows every action
EXCEPT T5 Execute calls inside an engagement. Those are recorded in
the per-engagement chain (`engagement.audit/per_engagement_chain.jsonl`)
and appear in the audit page only as a redacted line:

```
2026-05-02 14:33:12  engagement_t5_execute  engagement_id=<hash>  redacted
```

The full per-engagement audit is accessible only via founder-only
endpoint `GET /api/v1/engagements/{id}/report` and renders into the
client report packet at engagement closure.

---

## 7. Guardrails

The founder principle: **do not rely only on hidden command. Require
role + local env + key + engagement scope. Log every T5 transition.
Never hard-delete evidence. Never exfiltrate real client data; prove
with hashes / canaries / redacted evidence unless client explicitly
authorizes otherwise.**

### 7.1 Layered activation gates

T5 Execute requires ALL of the following to be true at every call,
not just at unlock time. Any single failure flips the dispatcher
back to Think-only:

| Gate | Layer | Failure behavior |
|---|---|---|
| FOUNDER role | API auth dependency | 403 Forbidden |
| LOCAL environment | `evilbob_mode.detect_environment()` runtime check | `EnvironmentMismatch` raised |
| Activation key valid | Hash-compared at call time, not session time | `KeyRevoked` raised |
| Engagement record exists | Lookup by `engagement_id` | `NoActiveEngagement` raised |
| Engagement not killed | `kill_switch_at IS NULL` | `EngagementKilled` raised |
| Engagement not expired | `expires_at > now()` | `EngagementExpired` raised |
| Target inside scope | CIDR / domain match against `engagement.target_scope` | `OutOfScope` raised |
| Technique allowed | Capability function name in `engagement.allowed_techniques` | `TechniqueNotAllowed` raised |
| Inside time window | `now() in engagement.authorized_window` | `OutsideTimeWindow` raised |
| Audit chain healthy | `/governance/audit/verify` returns `valid=true` | `AuditChainBroken` raised, T5 disabled until fixed |

If the hidden command path is the ONLY layer (founder forgets to
activate engagement, target accidentally matches a recently-expired
scope), the layered gates fail closed. The hidden command is one of
many gates, not the gate.

### 7.2 Transition logging

Every T5 state transition writes a hash-chained audit entry to BOTH
the normal audit ledger (redacted) AND the per-engagement ledger
(full):

| Transition | Logged? |
|---|---|
| T5 activation (Think unlocked) | Yes (normal: redacted; per-engagement: not yet) |
| Engagement create | Yes (normal: redacted with engagement_id; per-engagement: full) |
| Each Execute capability call | Yes (per-engagement: full; normal: redacted) |
| Engagement scope match check | Yes (whether passed or failed) |
| Engagement kill | Yes (both ledgers) |
| Engagement expire | Yes (both ledgers) |
| T5 deactivation | Yes |
| Activation key rotation | Yes |
| Audit chain integrity check | Yes |

Per CLAUDE.md Hard Law 9, the hash-chain integrity is verified
before each Execute call. Tampered or broken chain = T5 disabled
until repaired.

### 7.3 Evidence retention

The founder principle: **never hard-delete evidence.** Even after an
engagement closes:

| Action | Allowed |
|---|---|
| Soft archive of evidence folder | Yes (default after engagement close + retention period) |
| Hard delete of evidence | NEVER unless client legally requires (GDPR right-to-erasure equivalent) AND founder + key + reason + audit trail are all present |
| Re-encryption of evidence under new KEK | Yes (vault rotation pass; per `vault_migration.py` Rule 18 protected file) |
| Read access by non-founder | NEVER for raw evidence; client report packet only after engagement closure |

### 7.4 Real-data exfiltration rules

The founder principle: **never exfiltrate real client data; prove
with hashes / canaries / redacted evidence unless client explicitly
authorizes otherwise.**

| Default | Behavior |
|---|---|
| Recovered credential | Stored as SHA-256 hash + length + character class; raw value NEVER persisted |
| Recovered PII | Redacted to character class shape (e.g. `XXX-XX-1234`); raw value NEVER persisted |
| Recovered file | Hash + size + first 64 bytes; raw bytes NEVER persisted unless `engagement.evidence_capture_full = true` AND client signed addendum |
| Recovered API token | Hash only; raw token sent to vault via `vault_adapter.fetch_temporary_redaction_handle()` then immediately destroyed in-memory |
| Database row | Schema + row count; raw row data redacted unless engagement explicitly authorizes |

**Override path:** if the client's contract requires raw evidence
(e.g. specific data-leak proof), they sign an `evidence_capture_full`
addendum and the engagement record carries the override flag. The
addendum hash is stored in the engagement record; every full-capture
evidence write logs the addendum hash so client-side audit can trace
authorization.

### 7.5 Canary token + alternative-proof preference

By default, T5 uses canary tokens, hashes, redacted evidence, and
sandbox/staging clones for proof. Real-data capture is a separate
authorization that requires client signature. This is the operating
norm, not the exception.

The dispatcher records, on every Execute call, which proof
alternative was considered AND why the chosen alternative was the
least-invasive viable option. This becomes part of the
per-engagement report.

---

## 8. Cross-references

- Section 4 of `DAENA_GOVERNANCE_REDESIGN_INTERNAL_FIRST.md` is
  superseded by Sections 2.B and 7 of this document. The broader
  doc's PR-GOV-02 spec is updated to include the Think / Execute
  split as part of the engagement-scope gate work.
- `DAENA_CANONICALIZATION_PLAN.md` §1.8 (DANGEROUS_LOCAL_ONLY) lists
  the capability files Execute Mode unlocks. None are touched by
  this PR.
- `DAENA_BACKEND_BLINDSPOT_INVENTORY.md` §10.1 is the source of the
  current 3-gate fail-closed verification of `evilbob_mode`.
- Project CLAUDE.md "Hidden activation command" rule is the canonical
  source of "no UI surface for T5 in normal user flows." This doc
  refines it: founder-profile pill + kill-switch are the ONLY
  visible affordances, gated on three independent activation
  conditions.

---

## 9. What this doc deliberately does NOT do

- Does NOT name the activation key, the chat command alias, or any
  internal codename in plaintext.
- Does NOT enumerate the DANGEROUS_LOCAL_ONLY capability function
  signatures (those are in code; this doc references the file
  set only).
- Does NOT prescribe the activation key rotation policy (that lives
  with the founder + key management protocol, not in product docs).
- Does NOT propose any change to the `vault_adapter` /
  `vault_migration` / `oauth_credentials_store` (Rule 18 protected).
- Does NOT trigger any code change. Implementation is scheduled in
  PR-GOV-02 of the broader governance redesign doc.

---

## 10. Hard rule final check

| Check | Result |
|---|---|
| Em dashes added | 0 (verified by grep) |
| Files modified | 0 |
| Files deleted | 0 |
| Production deploys | 0 |
| Scans run | 0 |
| External messages sent | 0 |
| External systems touched | 0 |
| Secrets read or printed | 0 (activation key, capability codenames, internal aliases not enumerated) |
| Protected files modified (Rule 18) | 0 |
| New tests added | 0 (planning only) |

---

**Stopping here as requested. This doc updates Section 4 of
`DAENA_GOVERNANCE_REDESIGN_INTERNAL_FIRST.md`. The PR-GOV-02 spec in
that doc is amended to include the Think / Execute split as part
of the engagement-scope gate work. Awaiting founder direction.**
