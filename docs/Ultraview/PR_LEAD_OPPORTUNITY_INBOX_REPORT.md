# PR-2 -- Lead and Opportunity Inbox

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 2 of 8
**Date:** 2026-05-06

## Goal

Operator-facing inbox for discovered opportunities. Read state +
narrow status mutations (archive / reject) + run-discovery
on-demand button. NO send / submit / post / pay surface.

## What ships

`backend/app/api/v1/opportunities.py` (new):

* `GET /opportunities/` -- tenant-scoped, score-desc, optional
  status / type filters with enum validation.
* `GET /opportunities/{id}` -- one row.
* `POST /opportunities/run-discovery` -- runs the orchestrator
  with `initiator='operator'`.
* `POST /opportunities/{id}/archive` -- mark archived.
* `POST /opportunities/{id}/reject` -- mark rejected.

`backend/app/api/v1/__init__.py` (modified): mounts router under
`/api/v1/opportunities`.

`frontend/src/pages/OpportunityInboxPage.tsx` (new):

* Fetches `/opportunities/` on mount + reload-count.
* Status pill per row (gray/gold/green/red).
* "Run discovery" button triggers orchestrator + summarises result
  inline ("Discovered N -> deduped M -> persisted P").
* Per-row archive / reject buttons (only visible when status =
  discovered, to avoid status churn).
* Empty state explains how to seed `.opportunity_seed.json`.
* No "send" button anywhere on this page.

`frontend/src/App.tsx` (modified): routes `/opportunities`.

`frontend/src/components/layout/Sidebar.tsx` (modified): adds
sidebar entry under Governance.

## Mythos design choices

**No send button on the inbox page.** Even though the data model
allows it, the UI does NOT expose a path. Send is a SEPARATE
controlled-execution endpoint reached only via the dedicated draft
flow (PR-4 + PR-5). Avoids accidentally one-click-sending.

**Archive / reject status mutations DO commit but do NOT
auto-approve anything.** They are local audit moves. Same as the
`/policies/{id}/decide` pattern -- the operator's decision is
recorded; the world stays unchanged.

**Refresh row before serializing response.** Avoids the
SQLAlchemy MissingGreenlet trap that hits when a server-default
column (`updated_at`) is accessed during Pydantic serialization
after a flush but before the next async op. Tested.

**Honesty rules from ADR-001.** Empty state honestly explains how
to seed; failed load shows a retry card; no fake demo rows.

## Locked invariants

| Invariant | Where |
|---|---|
| GET / lists tenant-scoped, score-desc | `TestListEndpoint::test_empty_initially` + `TestRunDiscovery::test_seeded_file_creates_rows` |
| Invalid status / type returns 400 | `TestListEndpoint::test_invalid_status_400`, `test_invalid_type_400` |
| run-discovery executes orchestrator | `test_seeded_file_creates_rows` |
| /archive sets status=archived | `TestStatusMutations::test_archive_and_reject` |
| /reject sets status=rejected | same |
| Invalid UUID returns 400 | `test_invalid_uuid_400` |
| No /send /submit /post /pay routes exist | `TestNoForbiddenEndpoints::test_no_send_submit_post_pay_routes` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No generic send_email | applied -- no /send endpoint exists |
| No bulk sending | applied |
| No social post | applied |
| No payment | applied |
| No browser automation | applied -- discovery is file-only |
| Frontend tsc clean | exit 0 |
| Backend tests pass | 7/7 |

## Tests

```
backend/tests/test_opportunities_api.py    7 tests
```

## Files

```
new:        backend/app/api/v1/opportunities.py
new:        backend/tests/test_opportunities_api.py
modified:   backend/app/api/v1/__init__.py
new:        frontend/src/pages/OpportunityInboxPage.tsx
modified:   frontend/src/App.tsx
modified:   frontend/src/components/layout/Sidebar.tsx
new:        docs/Ultraview/PR_LEAD_OPPORTUNITY_INBOX_REPORT.md
```

## Next: PR-3 -- Outreach Draft Factory
