# Sprint-11 — Supervised Work Operator Smoke Report

**Sprint:** DAENA-SUPERVISED-WORK-OPERATOR-SPRINT-11
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)
**Restore point:** `master @ 0c5c2d4` (PR-0 push)
**Sprint head:** `master @ <PR-5 commit>`

## What Daena can now do for Masoud's real work

Daena is **no longer just a chat surface with research drafts**. After
Sprint-11 she is a *supervised work operating layer*:

1. **Research a real opportunity / topic.** Operator pastes a URL +
   goal. ScrapeGraphAI runs (governed, audited, capped). Daena
   produces a structured `ResearchDraft`:
   - For `kind=career`: company, role, requirements, fit_score,
     missing_skills, suggested_answers, outreach_draft_local,
     next_tasks. (Fields the deterministic pass cannot fill carry
     `_llm_pending: true` so the UI is honest.)
   - For `kind=content`: audience, key_points, angle, outline,
     captions, sources, risks_to_verify.

2. **Prepare form answers locally.** Operator pastes questions / form
   HTML / opportunity URL. Daena produces a `FormDraft` with editable
   suggested answers, confidence scores, and `NEEDS_REVIEW` flags.
   Sensitive (passport / SSN / SIN / immigration / visa / driver's
   license / bank account / IBAN) and payment (CC / CVV / billing)
   field types **never** receive an auto-suggested value.

3. **Queue any draft for explicit review.** Operator (or any backend
   service) pushes a draft onto the existing `GoaRequest +
   PendingApproval` queue. Five sentinel kinds: `email_draft`,
   `form_draft`, `application_draft`, `content_post_draft`,
   `file_change_proposal`. **Approving the request flips the status
   to APPROVED but fires no external dispatcher** — the operator
   takes the action manually, off-system. Approve = "I have read
   this and I will act on it myself," not "ship it."

4. **See it all in one place.** `WorkstreamsPage` is the canonical
   command center. The Drafts lane shows Career / Content / Forms
   tabs with counts and previews. No parallel "Work Command Center"
   page exists.

5. **Audit everything.** Every IntegrationRouter dispatch, every
   research draft, every approval request, every approve/reject
   decision lands in the tamper-evident audit ledger via
   `AuditService.log_decision`. Audit rows never carry tokens or
   request bodies — only metadata.

## What still requires manual account setup

- Two pinned Google accounts: `masoud.masoori@mas-ai.co` (founder) +
  `daena@mas-ai.co` (agent). Connect both via Settings > Connections
  before Gmail / Drive / Calendar tools become available.
- The OAuth client_id + client_secret for Google must be supplied
  through Settings > Account > OAuth Clients (one-time).
- ScrapeGraphAI's `venv_daena` worker must be installed and reachable
  before research drafts can be produced.

## What still requires human approval

- **Every** external action. Phase-2 read-only is ON by default; even
  approving a draft request does not authorize Daena to send /
  submit / post / apply. The operator clicks the original form's
  submit button (or pastes an approved email body into Gmail) by
  hand. Phase 3 lifting will arrive in a separate sprint with
  ApprovalQueue → IntegrationRouter wiring AND explicit founder
  toggle.

## Exact first workflow Masoud should run

1. Connect both Google accounts via Settings > Connections.
2. POST `/api/v1/research/career` with a real job posting URL + goal
   (e.g. "Extract role title, required skills, and 3-line summary").
3. POST `/api/v1/form-drafts/from-url` with the same URL +
   `goal: "Extract questions"`. Verify the returned FormDraft has the
   right field labels and sensitive fields are blocked.
4. Open `WorkstreamsPage`, click the Drafts lane Forms tab. The form
   draft should appear.
5. POST `/api/v1/governance/approvals/draft` with `draft_kind=form_draft`,
   the draft id, and a title. Open the Approvals page; the request
   shows up.
6. Approve it. Watch the audit log. Confirm Daena did NOT send / post /
   apply anything.

## Test results

| Suite | Tests | Status |
|---|---|---|
| `test_supervised_work_operator_smoke.py` (PR-5) | 16 | ✅ pass |
| `test_approval_queue_drafts.py` (PR-4) | 17 | ✅ pass |
| `test_form_drafts.py` (PR-3) | 46 | ✅ pass |
| `test_research_structured_payload.py` (PR-2) | 21 | ✅ pass |
| `test_integrations_readonly.py` (PR-1) | 16 | ✅ pass |
| `test_research_flow.py` (Sprint-10 regression) | 33 | ✅ pass |
| `test_integrations.py` (regression) | 39 | ✅ pass |
| **Total Sprint-11 + regression** | **188** | **✅ all green** |

Frontend: `npx tsc --noEmit` exit 0 across `WorkstreamsPage` Drafts
lane changes.

## Hard-rule ledger (full Sprint-11 audit)

| Rule | Status | Where enforced |
|---|---|---|
| No deploy | ✅ | No Cloud Run / docker push command run |
| No push (other than PR-0) | ✅ | Only PR-0's master push happened |
| No secrets read/printed/committed | ✅ | Audit rows + logs scrub tokens |
| No external messages | ✅ | No SMTP / chat client invoked |
| No job applications submitted | ✅ | No /submit, no browser automation |
| No forms submitted | ✅ | OpenAPI test asserts no /submit /send /apply path |
| No social posts | ✅ | No social connector invoked |
| No payments | ✅ | `blocked_payment` field type explicit |
| No browser automation on external sites | ✅ | Static-analysis test enforces |
| No Phase 3 writes | ✅ | `INTEGRATIONS_PHASE2_READONLY=true` default + smoke asserts |
| No duplicate command center page | ✅ | `WorkstreamsPage` extended only |
| No duplicate Opportunity / ContentBrief models | ✅ | Rule-2 test enforces |
| Approving draft does NOT execute externally | ✅ | Static + runtime AsyncMock-trap tests |

## Whether it is safe to push / deploy

**Push: yes** (operator approval pending). The five Sprint-11 commits
on top of `0c5c2d4` are reviewable, atomic, and accompanied by
per-PR reports. Pushing to `origin/master` is a single fast-forward.

**Deploy: NO.** The Sprint-11 brief's hard rule is "no deploy."
Production database needs an Alembic migration for the two new
columns/tables (`ResearchDraft.structured_payload`, `FormDraft`,
`FormDraftField`). The migration is out of scope here and ships in a
follow-up production-deploy PR.

## Five commits that made up Sprint-11

| Commit | PR | Headline |
|---|---|---|
| `7166618` | PR-1 | IntegrationRouter phase-2 read-only gate + owner_email pin |
| `3432a41` | PR-2 | Structured ResearchDraft payload + Drafts lane |
| `478fe31` | PR-3 | FormDraft Assistant — local-only, no submit path |
| `eaccc58` | PR-4 | ApprovalQueue extension for draft kinds |
| `<this>`  | PR-5 | Supervised work operator end-to-end smoke + report |

## What's still pending after Sprint-11 (intentional cuts)

- **LLM enrichment pass** for ResearchDraft and FormDraft `_llm_pending`
  fields. Deterministic shape ships now; LLM fill-in is the next PR.
- **Per-field UI on FormDraft.** The Drafts-lane card view is
  list-only; clicking into a draft to edit fields is a polish PR.
- **Phase 3 unlock.** When the operator clicks "Approve" on a draft,
  Daena still does NOT take the action externally. The next sprint
  will add a controlled-write path that requires both an approved
  ApprovalQueue row AND an explicit founder toggle.
- **Alembic migration** for production DB.

## Mythos closing line

This sprint took Daena from "research + chat" to "supervised work
operator." She can now read your inbox of opportunities, prepare
local artifacts, queue them for your review, and prove with code
that she will not act externally without your hand on the trigger.

Two moves ahead from here: LLM enrichment of the structured payloads
(so opportunity drafts come back with real `fit_score` + concrete
`outreach_draft_local`), then Phase-3 controlled execution where the
ApprovalQueue + founder toggle together unlock IntegrationRouter
writes for one specific draft at a time.
