# Phase 9E — Multi-Model Review Council Synthesis

**Date:** 2026-05-01
**Pattern:** MoA + Karpathy 3-stage council per global CLAUDE.md (proposers → anonymized peer rank → chairman synthesis)
**Review pack distributed:** `docs/Ultraview/PHASE_9_REVIEW_PACK.md` (sanitized, no secrets)

| Reviewer | Role | Input bytes | Output | Tokens | Cost |
|---|---|---:|---|---:|---:|
| **Codex CLI** (gpt-5.5, xhigh effort) | Architecture / regression / tests | 18,424 | 40,288 chars | 36,007 | (subscription) |
| **Gemini CLI** | UX / product flow | 18,820 | 6,601 chars | n/a | (subscription) |
| **Perplexity API** (sonar-pro) | Public best practices | 18,609 | 4,434 chars + 8 cites | 5,944 | $0.040 |

Total elapsed wall-clock: ~3 min (parallel fan-out). Total council cost: $0.04 (Perplexity only).

---

## 1. Proposer A — Architecture (Codex)

**Headline calls:**

1. **Commit-1 (gates):** Use ONE shared `target_matches_scope()` validator at both REST and workflow layers. Don't write two conditionals — they will drift. Explicit audit event for every founder-bypass: `security.scan.scope_bypass`.

2. **Commit-2 (settings persistence):** **Hard pushback against one-big-replace.** The 25 FAKE settings are NOT all the same shape — purely-visual prefs (e.g., dark mode) should stay on `persistUiPref`. Backend-governed settings (governance mode, routing, budgets, notifications) need a *centralized* Zustand `settingsStore` slice with patch/merge semantics, optimistic UI, per-key rollback. Split into 2A/2B/2C/2D incremental commits, not one monolith. Stale `{...current, [key]: value}` PUT can clobber concurrent writes.

3. **Commit-3 (scan report-ready):** Notification effect must use **transition tracking** (only fire when previous status was in-flight AND next is complete). Otherwise polling/refetch will fire repeated notifications.

4. **Commit-4 (file removal semantics):** **Recommends Option C** explicitly — X removes from chat draft only (current behavior, label honestly), separate "Detach + delete" item for the destructive case. Audit helper should fail-closed only for security-critical actions; ordinary audit gaps log + continue.

5. **Required test priority** (most-to-least valuable test budget):
   1. U2 scan REST scope gate
   2. U3 engagement scope gate
   3. U1 Company Mode contradiction
   4. Governance Mode backend persistence
   5. Budget/routing persistence
   6. Scan completion report findability
   7. Chat file removal semantics
   8. Audit-event coverage

**Sharpest insight:** "The REST boundary IS the security boundary. If the agent already checks scope deeper, still keep the route check."

**Diff sketch for U1 (most concrete):**
```py
if payload.auto_send and not payload.require_founder_approval:
    raise HTTPException(422, detail="auto_send_requires_founder_approval")
```
```tsx
const autoSendDisabled = !form.require_founder_approval;
// + clear auto_send when approval toggles off:
setForm({ ...form, require_founder_approval: checked, auto_send: checked ? form.auto_send : false });
```

## 2. Proposer B — UX (Gemini)

**Headline calls:**

1. **0.5s / 2s / 10s expectation framework** for every action class. Predictability of intent > speed of completion.

2. **Report-ready UX:** **Sticky toast + persistent sidebar notification dot.** Toast alone is missable; dot stays until user visits Security Dashboard.

3. **Archive vs Delete grammar:**
   - "Archive" is the **primary** action (95% of mutations).
   - "Delete" is the **secondary** action, only visible **inside the archived view**.
   - Archive dialog: blue/gray "Move to Archive."
   - Delete dialog: explicit "This cannot be undone" + red "Destroy Forever" button.
   - **Rule:** anything that contributes to AuditLog row CANNOT be hard-deleted from primary UI.

4. **Save Settings feedback:** Persistent top-right toast, with explicit copy distinguishing **"Settings saved successfully"** (remote) vs **"Preferences updated locally"** (local-only). This single copy choice exposes the FAKE pattern to the user.

5. **Multi-step mutation:** "Sub-component header banner" (per-component status bar). States: `[Pending Install] → [Installed: Needs Config] → [Probing...] → [Enabled]`. Keeps user in context of the asset.

6. **The ONE UX change for coherence:**

> **"Global Sync Status" indicator** in the global header.
> - **Green check:** all settings persisted to DB.
> - **Amber sync:** local changes pending sync (exposes the 25 FAKE settings DIRECTLY).
> - **Red X:** disconnected / local-only mode.

**Sharpest insight:** This single indicator creates accountability for the FAKE settings and immediately alerts the founder when "Governed" mode hasn't actually reached the Shield. Prevents the false sense of security that the matrix audit flagged as the most damaging UX failure.

## 3. Proposer C — Public Best Practices (Perplexity)

**Headline calls (with public sources):**

1. **Agent-dashboard action semantics:** The established pattern is **OpenTelemetry hierarchical spans per action state** (queued: pending span; sent: active with token/latency; failed: error span). Tools like Sentry / Mastra use 100% trace sampling. **Anti-pattern:** unstructured logs instead of searchable span hierarchies; sampling traces below 100% for agents drops entire runs.

2. **Approval gates:** Established pattern is **server-side dependency (FastAPI guard) + UI disable/tooltip with founder-override audit-emit** — mirrors AWS Bedrock guardrail spans in agent traces. **Anti-patterns:** client-side-only guards bypassable via API (this is exactly Daena's U1 form contradiction); missing scope checks at REST boundaries before workflow dispatch.

3. **Security scan report UX:** No direct public docs for Snyk/Dependabot/Tenable/Burp UI patterns specifically, but the broader observability literature converges on: traces should reconstruct full execution flow with spans for queued/active/failed, and reports should be findable via the same trace ID. Daena's `var/security_reports/<job_id>.json` model matches this.

4. **Settings persistence:** Strong recommendation to treat localStorage as **cache only**, never source-of-truth. Server round-trip is expected for any setting that downstream code (e.g., governance pipeline, model router) reads. Public guidance leans heavily on "if a setting controls behavior outside this browser tab, it MUST round-trip."

**Cited (8 sources):** Arthur AI agent observability, Dash0 Agent0 guide, OpenTelemetry AI agent observability blog, dev.to comprehensive guide, Microsoft Azure agent factory observability, Galileo cost optimization, Nexla AI readiness, plus implicit framework docs for OpenTelemetry spans.

**Sharpest insight:** "Client-side-only guards bypassable via API" — Perplexity flagged Daena's U1 form contradiction as an instance of a well-known anti-pattern. The fix is in line with industry standard: server-side guard + UI courtesy.

---

## Stage 2 — Anonymized peer ranking

| Pair | Stronger argument | Why |
|---|---|---|
| A vs B (commit-2 settings) | **A (Codex)** | A correctly identifies that not all 25 FAKE settings are the same shape (some are local-only by design). B treats them as a uniform "FAKE" cluster and proposes one toast pattern; that's right at the *feedback* layer but doesn't address the *taxonomy* layer A surfaces. |
| A vs B (commit-3 report-ready) | **B (Gemini)** | A's "transition tracking" is correct but mechanical. B's "sticky toast + sidebar dot" is the actual UX contract that makes the user trust the system. The two compose: A is the implementation guard, B is the surface. |
| A vs C (gates) | **A** | A is more concrete (specific HTTP status, specific exception shape, specific founder-bypass audit event). C correctly cites the anti-pattern but doesn't differentiate between U2 (REST gap) and U3 (delegation gap) the way A does. |
| B vs C (settings) | **C** | C's "if a setting controls behavior outside this browser tab, it MUST round-trip" is the correct *rule*. B's UX framing helps users *see* the rule but doesn't establish it. C and A together close the loop: C provides the rule, A provides the architecture. |
| B vs C (overall) | **Tie** | B is product-shaping; C is industry-grounding. Both contribute different value to the chairman synthesis. |

**Convergence (where all three agree):**
- Server-side guards are non-negotiable for U1/U2/U3 (A explicit, B implicit, C explicit).
- localStorage is cache, never truth (A explicit, B implicit via "exposes the FAKE settings", C explicit).
- The user must SEE failure honestly (A: audit; B: amber dot; C: client-side-only is anti-pattern).
- Audit emit is required for every meaningful mutation (A explicit, B via "if it contributes to AuditLog", C via "trace ID").

**Disagreement (notable):**
- A says split commit-2 into 4 sub-commits (2A/2B/2C/2D); B and C are silent on packaging.
- B's "Global Sync Status indicator" is genuinely novel and isn't proposed by A or C. It belongs in the chairman synthesis as an additive item.

---

## Stage 3 — Chairman synthesis (Daena's call)

**Adopting from each proposer:**

| Decision | Source | Rationale |
|---|---|---|
| Shared `target_matches_scope()` validator at both REST + workflow | A | Concrete, prevents drift, matches Daena's existing pattern in `runtimes.py` |
| `HTTPException(422, "auto_send_requires_founder_approval")` for U1 | A | Smallest possible safe diff; defense-in-depth for non-UI clients |
| Founder-bypass MUST emit `security.scan.scope_bypass` audit row | A | Closes the audit-event gap from 9B and the founder-loophole-becomes-silent risk |
| **Split commit-2 into 2A (governance), 2B (routing/chat), 2C (billing), 2D (notifications/privacy)** | A | Reduces blast radius; lets each tier soak before the next lands |
| Zustand `settingsStore` slice with optimistic UI + per-key rollback | A | Single canonical mutation path; eliminates per-component debounce drift |
| **Sticky toast + sidebar notification dot for scan-ready** | B | Composes with A's transition-tracking guard |
| **Archive primary, Delete secondary (only inside archived view)** | B | Closes the policies hard-delete gap with a UI-grammar fix that scales beyond just policies |
| Save settings feedback: "Settings saved" vs "Preferences updated locally" copy distinction | B | Surfaces the local-only vs round-trip distinction at the user-visible layer |
| **Sub-component header banner for multi-step (install→probe→configure)** | B | Right granularity — per-asset state, not global wizard |
| **Add "Global Sync Status" navbar indicator (Green/Amber/Red)** | B | NOVEL contribution; deserves own micro-commit. Single highest-leverage UX change. |
| Server-side dependency for ALL approval gates | C | Mirrors AWS Bedrock/Vault industry standard |
| LocalStorage = cache only, never source of truth | A + C | Doctrinal reinforcement |

**Rejecting (with reason):**

- **A's "treat audit-helper failures as best-effort except for security"**: too nuanced for v1. Simpler rule: audit-helper failures NEVER block the primary mutation; surface as `audit_emit_failed` log + retry-queue entry. Accept the rare audit gap; never block a user.
- **B's "Sub-component header banner" for ALL multi-step flows**: scope-creep for Phase 10. Adopt for connector install only; defer scan walkthrough variants.
- **C's "OpenTelemetry hierarchical spans"**: out of scope for Phase 10. Daena already has structured logging via `structlog`; mid-term roadmap item, not immediate.

---

## 4. Revised Phase 10 plan (chairman's commit list)

The Phase 9E review has changed the original 5-commit plan into **7 smaller commits** plus 1 polish micro-commit. Adopting Codex's incremental settings-split.

| # | Commit | What | Source-of-decision |
|---|---|---|---|
| **1** | **`phase10: U1+U2+U3 unsafe action gates`** | Backend: shared `target_matches_scope()` route guard at scan-start AND engagements-start. Backend 422 on U1 contradiction. Frontend: disable auto_send when approval=false; clear auto_send when approval toggles off. Founder-bypass audit row. | A primary, C reinforcement |
| **2A** | **`phase10: Zustand settingsStore + governance mode persistence`** | New `frontend/src/stores/settingsStore.ts` with optimistic-UI + per-key rollback + debounced PUT. Migrate `daena:governanceMode` → `users.settings.governance_mode`. Add e2e regression. | A primary |
| **2B** | **`phase10: routing + chat-mode defaults persistence`** | Migrate `daena:routingMode`, `daena:chatMode`, local-first/cost-aware via the new store. | A |
| **2C** | **`phase10: billing budget + over-budget action persistence`** | Migrate budget/threshold/over-budget. Backend: cost-tracker reads from settings. | A |
| **2D** | **`phase10: notification + privacy toggle persistence`** | Migrate the 8 notification toggles + 4 privacy toggles. Defer downstream notification-emission wiring (separate Phase 11 item). | A |
| **3** | **`phase10: scan rerun + report-ready notification + show-archived toggle`** | Add Re-run button. Add transition-tracked toast + sidebar notification dot. Add show-archived toggle. | A guard + B surface |
| **4** | **`phase10: chat file remove honest semantics + session/task/file audit emit`** | Adopt Option C (X = remove from draft; new "Detach + delete" menu item). Add `app/services/audit/emit.py` helper. Wire to chat-session PATCH/DELETE, task PATCH/DELETE, file DELETE handlers. | A primary |
| **5** | **`phase10: archive-primary delete-secondary UI grammar`** | Convert policies from hard-delete to soft-archive. Standardize delete-only-from-archived-view across files/tasks/sessions. | B primary |
| **6** | **`phase10: Global Sync Status navbar indicator`** | Add `<GlobalSyncStatus>` reading from `errorStore` + `settingsStore.statusByKey` + connection health. Green/Amber/Red. | B novel contribution |
| **7** | **`docs: phase10 verification report + 9E synthesis`** | Final `PHASE_10_PRODUCT_INTEGRATION_VERIFICATION.md` + this synthesis doc. | All |

**Test priority** (Codex's order, adopted verbatim):
1. U2 scan REST scope gate
2. U3 engagement scope gate
3. U1 Company Mode contradiction
4. Governance Mode backend persistence
5. Budget/routing persistence
6. Scan completion report findability
7. Chat file removal semantics
8. Audit-event coverage

**What gets implemented in this autonomy run (per founder's "execute through Phase 10" directive):**

Given the autonomy mandate and remaining context budget, the implementation prioritizes the highest-impact subset:
- **Commit 1** (P0 — all 3 UNSAFE gates) — must ship.
- **Commit 2A** (Governance Mode persistence — highest-impact FAKE) — must ship.
- **Commit 4** (audit emit + chat file remove) — high impact, low risk.
- **Commit 7** (verification report).

Commits 2B/2C/2D/3/5/6 will be queued as ranked Phase 10b backlog in the verification report. The chairman call: ship the safety-and-honesty commits now; let the founder review before continuing the persistence-migration sweep.

---

## 5. Cross-model agreement matrix

| Question | Codex (A) | Gemini (B) | Perplexity (C) | Chairman |
|---|---|---|---|---|
| Server-side guard required for U1/U2/U3? | YES | (implicit) | YES | YES |
| One-big-replace for FAKE settings safe? | NO — split 4-way | (n/a) | (n/a) | NO — adopt Codex split |
| LocalStorage acceptable as truth? | NO | NO | NO | NO |
| Soft-archive over hard-delete for policies? | (n/a) | YES | (n/a) | YES |
| Founder-bypass needs audit row? | YES | (implicit) | (implicit) | YES |
| Sticky toast + sidebar dot for report-ready? | (n/a) | YES | (n/a) | YES |
| Global sync indicator? | (n/a) | YES (novel) | (n/a) | YES (adopt) |
| 0.5s/2s/10s UX framework? | (n/a) | YES | (n/a) | Adopt as design guide for commit 3 |
| Hierarchical OTel spans for action states? | (n/a) | (n/a) | YES | DEFER (out of scope) |

Convergence is high on safety/honesty; divergence is mostly on packaging granularity (Codex split won) and additive UX (Gemini's sync indicator added).

## 6. References

- `docs/Ultraview/PHASE_9_REVIEW_PACK.md` — input to all reviewers
- `docs/Ultraview/PHASE_9_PERPLEXITY_RAW.md` — Perplexity raw output + 8 citations
- `/tmp/codex_review.md` — Codex raw output (40 KB)
- `/tmp/gemini_review.md` — Gemini raw output (6.6 KB)
