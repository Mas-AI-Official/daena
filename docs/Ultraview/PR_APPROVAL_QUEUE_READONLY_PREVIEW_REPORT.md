# PR-4 — ApprovalQueue draft kinds (read-only preview)

**Sprint:** DAENA-SUPERVISED-WORK-OPERATOR-SPRINT-11
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Wire local drafts (email replies, form answers, content posts,
application drafts, file-change proposals) into the existing
`GoaRequest` + `PendingApproval` queue **without** spinning up a
sibling table — and **prove in code** that approving a draft does
NOT trigger any external action.

## What changed

### 1. `DRAFT_KINDS` constant + `is_draft_kind` helper (`approval.py`)

```python
DRAFT_KINDS: tuple[str, ...] = (
    "email_draft",
    "form_draft",
    "application_draft",
    "content_post_draft",
    "file_change_proposal",
)
```

These five sentinel values are the `action_type` discriminator on
`GoaRequest`. The existing approval pipeline doesn't recognize them
specially — which is the point: approve a `form_draft` request and
the same `ApprovalService.approve()` flow runs (status → APPROVED,
PendingApproval cleaned up, peer-department event emitted), but no
external dispatcher is ever called.

### 2. `ApprovalService.request_draft_approval()` helper

```python
await svc.request_draft_approval(
    tenant_id=..., user_id=...,
    draft_kind="form_draft",
    draft_ref="<form_draft_id>",
    title="Apply: AI Engineer",
    context=None, session_id=None,
)
```

Builds a `GoaRequest` with `action_type=draft_kind`,
`risk_level="LOW"`, `governance_tier=2`, and stuffs
`{draft_kind, draft_ref, title, manual_action_only: True}` into
`action_params`. The `manual_action_only: True` sentinel is the
"approved_for_manual_action" semantic from the brief, encoded in
data rather than as a sibling status string (one canonical status
taxonomy per CLAUDE.md Rule 2).

Unknown `draft_kind` values raise `ValueError("unknown_draft_kind: ...")`.

### 3. New API endpoint: `POST /governance/approvals/draft`

Thin wrapper over `request_draft_approval`. Validates `draft_kind`,
audits the request with action_type
`draft.approval.requested.<kind>`. Re-uses the existing
`ApprovalResponse` schema so consumer code stays unchanged.

### 4. Static-analysis safety net

`tests/test_approval_queue_drafts.py::TestApprovalServiceSourceClean`
reads the source of `ApprovalService.approve`, `.reject`, and the
whole `app.services.approval` module (excluding comments and
docstrings) and asserts the regex
`(IntegrationRouter|GmailClient|CalendarClient|NotionClient|extract_from_url|send_email|create_draft|create_event|create_page|page\.fill|page\.click|browser\.|webdriver\.)`
finds no match.

This catches the failure mode where a later refactor wires a
"post-approval auto-dispatch" feature directly into `approve()`.

### 5. Runtime guard: AsyncMock wrappers in tests

`TestApprovingDraftDoesNotDispatch` patches three external entry
points with `AsyncMock(side_effect=AssertionError(...))`, then calls
`approve()` for a draft request. If approve happens to invoke any of:

- `IntegrationRouter.execute`
- `IntegrationRouter.execute_qualified`
- `scrape.extract_from_url`

…the test fails with the wired AssertionError. Currently this passes
silently — no dispatcher is touched.

## Tests

`backend/tests/test_approval_queue_drafts.py` — **17 tests, all passing.**

| Group | Cases |
|---|---|
| `TestDraftKinds` | 3 (set membership, classifier, rejects unknown) |
| `TestRequestDraftApproval` | 7 (form_draft persists, parametrized over 5 kinds, unknown raises) |
| `TestApprovingDraftDoesNotDispatch` | 2 (approve flow stays local, reject flow stays local) |
| `TestApprovalServiceSourceClean` | 3 (approve src clean, reject src clean, module src clean) |
| `TestDraftApprovalApi` | 2 (route registered, 400 on unknown kind) |

Regression: 172 passing across PR-1+2+3+4 + research + integrations.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets read/printed/committed | ✅ |
| Approving a draft does NOT execute externally | ✅ — runtime + static asserts |
| No sibling approval queue | ✅ — re-uses `GoaRequest` + `PendingApproval` |
| No Phase 3 writes | ✅ |

## Files touched

```
modified:   backend/app/services/approval.py
modified:   backend/app/api/v1/governance.py
new:        backend/tests/test_approval_queue_drafts.py
new:        docs/Ultraview/PR_APPROVAL_QUEUE_READONLY_PREVIEW_REPORT.md
```

## Next step

PR-5 — supervised-work-operator end-to-end smoke. Pytest covering
the happy path: research draft → form draft → approval queue →
audit trail. Confirms no submit/send/post endpoints exist and
phase-2 read-only gate still blocks writes.
