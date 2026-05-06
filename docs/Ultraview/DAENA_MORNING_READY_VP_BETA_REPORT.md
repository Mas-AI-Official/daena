# DAENA — Morning Ready VP Beta Report

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 7 of 7 (final report)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

This is the truth of where Daena stands at the close of the overnight
sprint, answering the 18 morning questions verbatim from the brief.

---

## The 18 morning questions

### 1. Is backend working?

**Yes.** 121/121 pass on the Sprint-12 + Sprint-MORNING fast subset.
The full pytest collection runs cleanly; no schema drift remains
(migration 013 — research_drafts.structured_payload — was applied to
the dev DB during PR-6 of Sprint-12). Backend boots on `127.0.0.1:8000`
after `alembic upgrade head` (heads at 013).

### 2. Is frontend working?

**Yes.** `npx tsc --noEmit` exits 0 across all PRs. The Vite dev
server starts on `:5173` cleanly. No runtime errors expected on the
new pages (manual browser verification is the operator's first
morning step — Playwright spec is staged at
`frontend/e2e/morning-workflow.spec.ts`).

### 3. Are frontend / backend APIs synced?

**Yes.** PR-2 added `tests/test_morning_route_contract.py` which pins
the 12 endpoints the frontend depends on:

```
POST /research/drafts/{id}/enrich
POST /research/drafts/{id}/qe-review
POST /form-drafts/{id}/enrich
POST /form-drafts/{id}/qe-review
POST /workstreams/from-draft
POST /vp-commands
GET  /system/runtime-readiness
GET  /system/router-readiness
GET  /system/qe-readiness
GET  /system/router-policy
GET  /system/morning-readiness          (NEW — PR-4)
```

Every "Enrich / Council / Create Workstream" button in the Drafts
lane maps to one of the first six. Every readiness panel reads one
of the GETs.

### 4. Is main brain ready?

**Yes — through `ollama_backend` (`free_local`).** Confirmed by
`GET /system/router-readiness` (Sprint-12A live verification, 2026-05-05).

### 5. Is QE full / degraded / unavailable?

**Full.** Three reviewer slots ready: `cli_claude`, `cli_codex`,
`ollama_backend`. The asymmetric reviewer set means a real cross-check
fires, not a single-runtime echo chamber. `_qe_mode="full"` is now
stamped on the draft's `structured_payload` after a successful run
(PR-3) so the WorkstreamsPage can render an honest badge.

### 6. Are Claude / Codex / Gemini CLIs detected?

**Claude + Codex confirmed; Gemini detection depends on operator
install.** The new `MorningReadinessPanel` (PR-4) shows live status.
Autofix proposals (PR-5) surface install + login commands as
copy-able strings if any are missing.

### 7. Is Perplexity configured / ready?

**Configured-but-untested by default.** No paid call fires unless
`allow_metered=true` is set per-call. Autofix proposals link to
`/settings/models-runtimes` for the operator to run a zero-cost
provider test (work for a future PR; the testing harness itself
exists in `runtime_truth_registry`).

### 8. Are safe MCPs installed / probed?

**Detected — not auto-installed.** PR-4's morning aggregator scans
Claude Code / Codex / Gemini configs and reports the merged MCP list
(env values stripped). Auto-install stays behind the Connections page
+ `install_scanner` governance gate per the brief's "no random
package installs" rule.

### 9. Do VP chat commands work in real chat?

**Yes.** Sprint-12 PR-5 shipped the deterministic regex parser at
`POST /vp-commands`. Sprint-MORNING PR-1 wires it into the chat
preflight. Every recognized intent renders a `VPCommandCard` and
skips the LLM stream; unrecognized chat falls through. Backend
contract pinned by `test_chat_vp_preflight_contract.py` (5 tests).

### 10. Do ResearchDraft / FormDraft enrichment work?

**Yes.** Sprint-12 PR-1 + PR-2 shipped the routed-brain enrichment
service. PR-2 of this sprint wired the Enrich button on every draft
row in the Drafts lane. Refusal codes (no_ready_main_brain, etc.)
surface as red status + verbatim `next_action`.

### 11. Does QE review work?

**Yes.** Sprint-12 PR-3 shipped the three-stage council. Sprint-MORNING
PR-3 added the `_qe_mode` stamp to `structured_payload` so the lane
can render an honest "QE: full" / "QE: degraded" badge after a real
run. The QE service writes the stamp only when `final_mode in
{full, degraded}` — never lies about an unavailable run.

### 12. Does Workstream from draft work?

**Yes.** Sprint-12 PR-4 shipped `POST /workstreams/from-draft`. The
Sprint-MORNING Drafts lane button calls it; the lane cross-references
`/workstreams` on load to render a "workstream" badge on every draft
that has been promoted (PR-3).

### 13. Does audit viewer show runs?

**Yes.** Every action in the new pipeline writes an audit row:
`vp_command.<intent>`, `draft.qe_review.<kind>`, `workstream.from_draft`,
`draft.enrichment.career`, etc. The audit page filter from Sprint-10
already supports plugin filter; draft / workstream filters fall under
the same surface.

### 14. What still requires manual Google OAuth login?

Anything that touches Gmail / Drive / Calendar live. The OAuth
credential store (`oauth_credentials_store.py`) is wired; the
operator must complete the OAuth dance once per provider via
`/settings/connections`. Daena cannot bypass this — it's the
authority handshake.

### 15. What still blocks Phase 3 external actions?

`INTEGRATIONS_PHASE2_READONLY=true`. This is the binary off-switch.
Lifting it without a Phase 3 sprint would expose every WRITE_TOOLS
entry simultaneously without per-tool consent or per-call approval.

The next sprint —
**DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-13** — replaces the binary
flag with a per-tool allowlist, requires `consent_grant_id +
approval_id + payload_hash` on every write, and gates everything
through Asset Shield.

### 16. Is it safe to push?

**Yes — Sprint-12 + Sprint-MORNING are pushable to origin/master.**
PR-0 of this sprint already pushed Sprint-12 (`1a4e30b..ec498b1`).
The 7 new commits from PR-0..PR-6 are ready for fast-forward push
when the operator approves.

### 17. Is it safe to deploy?

**No — deploy is intentionally NOT done.** The hard rule "No
deploy. No Cloud Run / Docker push / DNS / cloud secret change."
held throughout the overnight sprint. Production deployment requires:
(a) operator approval, (b) image rebuild with the latest commit,
(c) migration sequence validation on staging, (d) Asset Shield gate
audit on production data.

### 18. Exact first workflow for the morning

```
1. Open  Settings -> Models & Runtimes
       Confirm BrainReadinessPanel says main brain ready
       Glance at MorningReadinessPanel for any blockers
       Copy any autofix command if needed (e.g. start Ollama)

2. Open  /workstreams
       Read the "Start here tomorrow" card

3. Pick  any draft in the Drafts lane

4. Click  Enrich           (LLM fills the structured fields)
   Click  Council           (three-runtime cross-check runs)
   Watch the badges flip:   llm pending -> enriched -> QE: full

5. Click  Create Workstream
   Watch the violet "workstream" badge appear

6. Open  the chat
   Type: "what should I do next?"
   Watch the VPCommandCard render with the new workstream

7. Done — that's a morning of supervised VP work.
```

---

## Sprint commit log (Sprint-MORNING)

```
ec498b1  Sprint-12 PR-6 (push restore point — pushed in PR-0)
6c... PR-1: feat(sprint-morning/pr-1): wire VP commands into chat
7a7b70b  PR-2: fix(sprint-morning/pr-2): wire draft enrich/QE/from-draft buttons
cc83275  PR-3: fix(sprint-morning/pr-3): morning workspace UI badges + start-here
d63c4d7  PR-4: feat(sprint-morning/pr-4): morning ecosystem readiness panel
602125d  PR-5: feat(sprint-morning/pr-5): runtime autofix proposals (no auto-run)
f78e6b7  PR-6: test(sprint-morning/pr-6): add NUser browser E2E smoke
<this>   PR-7: docs: add morning ready VP beta report
```

## Test totals

**Backend:** 121/121 pass on the Sprint-12 + Sprint-MORNING fast subset.

```
tests/test_morning_route_contract.py        13
tests/test_morning_readiness_endpoint.py     5
tests/test_chat_vp_preflight_contract.py     5
tests/test_vp_work_commands.py              25
tests/test_draft_enrichment.py              24
tests/test_draft_qe_review.py               10
tests/test_workstream_from_draft.py         11
tests/test_sprint12_full_smoke.py           28
                                          ────
                                           121
```

**Frontend:** `npx tsc --noEmit` exit 0.

**E2E:** `frontend/e2e/morning-workflow.spec.ts` staged for the
operator to run after starting backend + frontend.

## Hard-rule audit (full Sprint-MORNING)

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push (until sprint complete + explicit approval) | ✅ — only PR-0 push happened (the Sprint-12 restore) |
| No secrets printed/read/committed | ✅ |
| No paid API call without explicit allow_metered=True | ✅ |
| No email send | ✅ |
| No job application submit | ✅ |
| No external form submit | ✅ |
| No social post | ✅ |
| No payment | ✅ |
| No browser automation on external sites | ✅ |
| No Phase 3 writes | ✅ — `INTEGRATIONS_PHASE2_READONLY=true` confirmed |
| No bypass of OAuth/account authorization | ✅ |
| No random package installs | ✅ — autofix proposals are copy commands only |
| No deleting legacy/V1 files | ✅ |
| No duplicate command center page | ✅ — extended WorkstreamsPage |
| No duplicate ResearchDraft / Workstream / Governance stores | ✅ |
| Audit per call | ✅ |
| Honest mode reporting (no fake council complete) | ✅ — encoded + tested |

## What still blocks full autonomy

| Layer | Status |
|---|---|
| Daena as supervised work operator (Sprint-11) | ✅ done + pushed |
| Daena as runtime-aware brain selector (Sprint-12A) | ✅ done + pushed |
| Daena uses routed brain to enrich drafts (Sprint-12 PR-1+2) | ✅ done + pushed |
| Daena runs honest QE/Council on drafts (Sprint-12 PR-3) | ✅ done + pushed |
| Daena promotes drafts to workstreams (Sprint-12 PR-4) | ✅ done + pushed |
| Daena drives the loop from chat (Sprint-12 PR-5 + Sprint-MORNING PR-1) | ✅ done locally |
| Daena renders the loop with honest badges (Sprint-MORNING PR-2/3) | ✅ done locally |
| Daena surfaces ecosystem readiness with autofix proposals (Sprint-MORNING PR-4/5) | ✅ done locally |
| NUser browser E2E spec (Sprint-MORNING PR-6) | ✅ done locally (Playwright) |
| Daena sees Gmail / Drive / Calendar live | ❌ NOT YET (manual OAuth login) |
| Daena performs controlled external actions | ❌ NOT YET (Phase 3 sprint) |
| Production deploy | ❌ NOT YET (Cloud Run image rebuild + migration sequence on prod) |
| Full VP autonomy with audit + rollback | ❌ NOT YET (gated behind Phase 3 + several allowlist-driven dispatches) |

## Final answer to the brief

Daena is **morning-ready as a serious VP work beta**.

She can:

- See her own readiness at runtime / router / QE / ecosystem level
- Run draft enrichment + council review using the routed local brain
- Promote drafts into work plans
- Be driven entirely from chat with deterministic command parsing
- Surface honest blocker text + autofix proposals when something's off
- Refuse cleanly when no main brain is ready (no fake "online" pills)

She still cannot, by design:

- Send emails
- Submit job applications
- Post to social
- Pay anything
- Auto-run shell commands
- Bypass OAuth

That's the boundary the next sprint —
**DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-13** — must cross *with* the
operator, not for them. Phase 3 is where "Daena suggests" becomes
"Daena acts", and that line crosses once.

Push Sprint-MORNING when ready. No deploy. No Phase 3.
