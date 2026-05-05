# SPRINT-11 SCOPE AUDIT — what exists vs what's actually missing

**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)
**Trigger:** PR-0 done; before writing one line of new code, the audit found
that the brief's PR-1..PR-6 substantially overlap with code that already
shipped in Sprint-10 and earlier. This document names the truth and proposes
a tighter Sprint-11 that respects CLAUDE.md Rule 2 ("one canonical file per
concern, never create a parallel file").

---

## Executive summary

Sprint-11 brief assumes a clean greenfield supervised-work surface.
**It is not greenfield.** Roughly 60-70% of the asked-for endpoints,
models, and pages already exist. Building the brief verbatim would:

1. Create duplicate models (`OpportunityDraft` vs the live `ResearchDraft(kind=career)`).
2. Create duplicate pages (a new "Work Command Center" vs the live `WorkstreamsPage`).
3. Wire tool execution that is already wired through `IntegrationRouter`.

The genuinely-missing pieces are smaller and tighter:

- **Read-only enforcement** on Gmail / Drive / Calendar tool dispatch
  (currently `send_email`, `create_draft`, write methods are reachable in
  `gmail_client.py.TOOLS`).
- **`owner_email` pinning** — operator selects which Google account a tool
  call runs against (founder vs agent), no implicit selection.
- **Form Draft Assistant** — no `FormDraft` model, no endpoints, no UI.
- **Drafts surface** in the Work Command Center — research/content/form
  drafts are listable via API but not surfaced inside `WorkstreamsPage`.
- **Approval-queue draft kinds** — `email_draft`, `form_draft`,
  `application_draft`, `content_post_draft`, `file_change_proposal` as
  queue states (read-only preview, no execution).
- **Smoke** — end-to-end supervised-work happy-path test.

---

## Per-PR truth table

### PR-1 — OAuth read-only execution wireup
**Brief asks:** Make Gmail/Drive/Calendar read-only skills usable; reject
write methods; add `owner_email` selector; audit every run.

**Reality on disk:**
- `backend/app/services/integrations/gmail_client.py` — Gmail API client with
  `search_emails`, `read_email`, **`send_email`**, **`create_draft`** all in
  `TOOLS`. Send is reachable today.
- `backend/app/services/integrations/calendar_client.py` — Calendar client.
- `backend/app/services/integrations/integration_router.py` — central
  dispatcher with `IntegrationError`, `NotConnectedError`, `PermissionDeniedError`.
- `backend/app/api/v1/integrations.py` — `/integrations/execute` and
  `/integrations/execute/qualified` already audit and govern.

**Real gap:**
1. Strip / gate write tools (`send_email`, `create_draft`, any future write)
   behind a Sprint-11 hard-stop guard. Not "remove from `TOOLS`" — explicit
   `READONLY_ONLY=True` flag at the router level that returns
   `permission_denied: write_disabled_phase2`.
2. `owner_email` parameter required on every Google call so the operator
   picks `masoud.masoori@mas-ai.co` vs `daena@mas-ai.co`. Pull from the
   `ConnectorInstance.owner_email` already populated by `google_setup.py`.
3. Tests for the write-block + the owner-email mismatch path.

**Estimated scope:** small. ~2 files modified, ~1 test file added.

---

### PR-2 — Work Command Center
**Brief asks:** Add a new page with sections: Opportunities / Research drafts /
Content drafts / Forms to prepare / Approval queue / Audit trail. Buttons
are Prepare / Draft / Review, not Submit / Send.

**Reality on disk:**
- `frontend/src/pages/WorkstreamsPage.tsx` (~990 lines) is *already* the
  command center. Per its file header it's "Daena's Live Workstream Console"
  with goal, owner department, blocker / next step, governed timeline, source
  badges, redirect, archive, lifecycle actions, SSE updates.
- `frontend/src/pages/GovernanceApprovalsPage.tsx` — approval queue page.
- `frontend/src/pages/GovernanceAuditPage.tsx` — audit trail page.
- Research drafts API exists (`/research/drafts`).

**Real gap:**
1. `WorkstreamsPage` does not link out to the four draft types as tabs / lanes.
2. No surface for "Forms to prepare" — that's the new draft type, blocked on PR-3.
3. No unified "supervised-work overview" landing card that aggregates counts
   across the four draft types + the live workstream count.

**Recommendation:** **Do not build a parallel page.** Add a "Drafts" tab
(or sibling section) inside `WorkstreamsPage` that lists CareerDrafts,
ContentBriefs, FormDrafts. Keep one canonical command center.

**Estimated scope:** medium. 1 file modified (~150 lines), 1 hook added.

---

### PR-3 — Form Draft Assistant
**Brief asks:** Daena helps fill forms locally without submitting. Inputs:
pasted questions, uploaded form HTML, opportunity URL. Output: local
`FormDraft` with fields, suggested answers, confidence, missing-info markers.
Hard rules: no submit endpoint, no browser autofill, no payment, no
government / immigration submission, every answer editable, low-confidence
fields marked `NEEDS_REVIEW`.

**Reality on disk:** **Nothing.** `grep -r "FormDraft" backend/` returns zero hits.

**Real gap:** Net-new feature.
- `backend/app/models/form_draft.py` (new) — `FormDraft`, `FormDraftField`.
- `backend/app/services/form_draft_service.py` (new) — answer suggester
  using LLM router; SSRF-guarded URL fetch reusing the `scrape` worker.
- `backend/app/api/v1/form_drafts.py` (new) — POST create, GET list, GET one,
  PATCH (edit answer), DELETE (archive).
- `frontend/src/pages/FormDraftsPage.tsx` (new) — list + drafting UI.
- Tests: model, service (incl. confidence scoring + NEEDS_REVIEW gating),
  API (incl. no `/submit` endpoint exists).

**Estimated scope:** large. The single biggest piece of net-new work.

---

### PR-4 — CareerOps OpportunityDraft pipeline
**Brief asks:** URL → ScrapeGraphAI → structured `OpportunityDraft` with
company / role / requirements / fit score / missing skills / suggested
application answers / outreach draft (local) / next tasks.

**Reality on disk:**
- `backend/app/api/v1/research.py` `/research/career` already accepts a URL +
  goal, runs ScrapeGraphAI, persists a `ResearchDraft(kind="career")` with
  `summary`, `raw_extract`, `source_url`, `source_host`, `goal`, `status`,
  `audit_event_id`.

**Real gap:** Schema is shallow vs the brief. A "career research draft" today
captures the extracted text + summary but not the structured opportunity
shape.

**Recommendation — Rule 2 conflict:** **Do not build a parallel
`OpportunityDraft` model.** Extend `ResearchDraft` with optional structured
fields (or a JSONB `structured_payload` column) and have the career flow
post-process the extract into the structured shape. Two writes, one row:
`raw_extract` + `structured_payload`. Single canonical entity.

**Estimated scope:** medium. 1 model migration, 1 service file modified,
1 frontend card update, tests.

---

### PR-5 — ContentOps ContentBrief pipeline
**Brief asks:** topic / source URL → ScrapeGraphAI → `ContentBrief` with
audience / key points / angle / outline / captions / sources / risks.

**Reality on disk:** `/research/content` already runs the same pattern via
`ResearchDraft(kind="content")`.

**Real gap:** identical to PR-4 — schema shallow vs brief.

**Recommendation:** Same as PR-4. Extend `ResearchDraft.structured_payload`
with a content-shaped JSON. One canonical entity.

**Estimated scope:** medium (combine with PR-4).

---

### PR-6 — Approval queue read-only preview
**Brief asks:** Queue item types: `email_draft`, `form_draft`,
`application_draft`, `content_post_draft`, `file_change_proposal`. States:
`draft` / `needs_review` / `approved_for_manual_action`. Approving does NOT
execute externally.

**Reality on disk:**
- `frontend/src/pages/GovernanceApprovalsPage.tsx` — the queue exists, used
  for tier 3+ governance approvals (tool calls awaiting consent).
- `backend/app/models/governance.py` `ApprovalQueue` model.

**Real gap:**
1. The queue currently models tool-call approvals, not draft approvals.
   Need to either (a) add a `draft_id` foreign key + `kind=draft_*` to the
   existing `ApprovalQueue` table, or (b) add a sibling `DraftApprovalQueue`
   table.
2. The "approved_for_manual_action" state is critical: approving must NOT
   trigger any external dispatcher. Need a code-level guard plus a test.

**Recommendation:** Extend `ApprovalQueue` (option a) with `kind` + `draft_ref`.
Avoid sibling-table sprawl.

**Estimated scope:** small-medium.

---

### PR-7 — End-to-end smoke
**Brief asks:** Daena starts; Work Command Center loads; ScrapeGraphAI creates
a research draft from a safe public URL; Form Draft Assistant creates local
form answers; CareerOps creates OpportunityDraft; ContentOps creates
ContentBrief; approval queue shows local drafts; audit viewer shows plugin
runs; Gmail/Drive/Cal show setup status; no send/submit/post/apply endpoints
exist.

**Real gap:** Test only. Should be the last thing.

**Estimated scope:** small. ~1 pytest file + 1 Playwright spec.

---

## Proposed tighter Sprint-11 scope

I recommend collapsing the 8 PRs into **5 PRs** that close the actual gaps
without violating CLAUDE.md Rule 2. PR numbers preserved for cross-reference;
"merged" PRs noted.

### PR-0 ✅ done
Push restore point. Already shipped in this session.

### PR-1 — Read-only execution gate on Google integrations
- Hard-block all write methods (`send_email`, `create_draft`, any
  drive-write or calendar-write) at `IntegrationRouter` level with feature
  flag `INTEGRATIONS_PHASE2_READONLY=true` (default ON, founder-overridable
  via env in dev — never via UI).
- Require `owner_email` on every Google tool call, validate against
  `ConnectorInstance.owner_email`, mismatch → `permission_denied`.
- Audit row carries `owner_email` + `read_only=true`.
- Tests: write-blocked, owner-mismatch-blocked, owner-match-allowed.
- Report: `PR_OAUTH_SIDE_SKILL_EXECUTION_WIREUP_REPORT.md`.

### PR-2+4+5 (merged) — Structured drafts + drafts surface in Workstreams
- Add `ResearchDraft.structured_payload` (JSONB) column + migration.
- Career flow: post-process to `OpportunityDraft` shape (company, role,
  requirements, fit_score, missing_skills, suggested_answers,
  outreach_draft_local, next_tasks).
- Content flow: post-process to `ContentBrief` shape (audience, key_points,
  angle, outline, captions, sources, risks).
- Frontend: add a "Drafts" lane to `WorkstreamsPage` with three sub-lists
  (career / content / form-draft-placeholder until PR-3 lands).
- Report: `PR_STRUCTURED_DRAFTS_AND_WORK_CENTER_REPORT.md`.

### PR-3 — Form Draft Assistant
- New `FormDraft` model + service + API + page.
- LLM-based answer suggester with confidence + `NEEDS_REVIEW` flag for
  low-confidence fields.
- Hard rules in code: no `/submit` endpoint, no autofill, no payment field
  generation. Test asserts the absence of these endpoints.
- Report: `PR_FORM_DRAFT_ASSISTANT_REPORT.md`.

### PR-6 — Approval-queue draft kinds
- Extend `ApprovalQueue` with draft kinds + `draft_ref` FK.
- Approving = sets state `approved_for_manual_action`. Code asserts no
  outbound dispatcher fires.
- Report: `PR_APPROVAL_QUEUE_READONLY_PREVIEW_REPORT.md`.

### PR-7 — End-to-end smoke
- Pytest + Playwright covering the full happy path.
- Report: `DAENA_SUPERVISED_WORK_OPERATOR_SPRINT11_SMOKE.md`.

---

## What I recommend you decide

1. **Approve the merged scope** (5 PRs, not 8). Saves maybe 40-50% of the
   work without losing any user-visible capability and respects Rule 2.
2. **Confirm one architecture call:** extend `ResearchDraft` with
   `structured_payload` JSONB (canonical-single-entity) **vs** spawn
   parallel `OpportunityDraft` + `ContentBrief` tables (literal-brief).
   I recommend extend.
3. **Confirm the read-only enforcement strategy:** flag at
   `IntegrationRouter` level (recommended) **vs** trim `TOOLS` dict in
   each client (more invasive, risks losing the code path when Phase 3
   un-blocks writes).

If you approve as-recommended, I run PR-1 next without asking. If you want
the literal 8-PR brief, say so and I'll execute it but with the duplication
flagged in each PR's report.

Either way, no new code lands until you sign off — building duplicate
models is a hard stop per Rule 2, and surfacing the conflict beats
silently merging or silently splitting.
