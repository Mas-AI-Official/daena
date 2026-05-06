# PR-4: Complete Business Loop UI Wiring — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE

## What this PR does

Verifies the full business loop is reachable from the UI without
falling back to backend scripts; adds two small navigation links so the
operator can walk the loop with their mouse alone.

## Verified loop (UI-only)

| Step | UI surface | Endpoint | Status |
|---|---|---|---|
| 1. Open `/opportunities` | sidebar Go-to-Market → Opportunities | — | ✅ |
| 2. See Google readiness banner | `useGoogleActivationSummary` | `GET /connections/google-activation-summary` | ✅ Sprint-20 PR-1 |
| 3. Run discovery | "Run discovery" button | `POST /api/v1/opportunities/run-discovery` | ✅ |
| 4. Select opportunity | grid cards, status pill | `GET /api/v1/opportunities` | ✅ |
| 5. Create workstream | "Workstream" button on `discovered` rows | `POST /api/v1/opportunities/{id}/create-workstream` | ✅ Sprint-20 PR-3 |
| 6. Open workstream | assigned_department badge → /workstreams | `GET /workstreams` | ✅ added in this PR |
| 7. Draft outreach | VP chat command `draft outreach for opp <uuid> to <email>` | `POST /api/v1/business/chat` | ✅ Sprint-20 PR-7 |
| 8. Queue Gmail draft | controlled-execution dispatcher (`gmail.create_draft` approval) | dispatcher | ✅ Sprint-19 |
| 9. Open approval | queued/approved status pill → /governance/approvals | `GET /governance/approvals` | ✅ added in this PR |
| 10. Approve create draft | Phase3ApprovalModal | `POST /governance/approvals/{id}` | ✅ |
| 11. Approve send (only if OAuth + allowlist + rate limit + snapshot pass) | second approval | dispatcher → `gmail.send_existing_draft` | ✅ Sprint-19+20 |
| 12. Audit trail | sidebar Governance → Audit | `GET /governance/audit` | ✅ |

## Hard-rule verification

- ✅ **No direct send button bypasses approval** — the OpportunityInboxPage page contract explicitly states: "No external action is taken here — send / submit / post / pay are NOT reachable from this page." Verified by reading the page source.
- ✅ **Every blocker shows exact next action** — activation banner enumerates each missing scope per role with the email address.
- ✅ **Rate limit visible** — `data-testid="opp-send-rate-limit"` chip shows `{remaining}/{cap}` with red/amber styling when 0.
- ✅ **Created workstream link works** — assigned_department badge now links to `/workstreams`.
- ✅ **Draft link works** — drafts surface in WorkstreamsPage `DraftsLane` with Enrich / Council / Create Workstream buttons.
- ✅ **Approval link works** — queued/approved status pill now links to `/governance/approvals`.
- ✅ **Audit link works** — sidebar Governance group has Audit subnav.
- ✅ **No generic send_email** — only `gmail.create_draft` and `gmail.send_existing_draft` exist; `send_existing_draft` is on TRUST_FORBIDDEN_TOOLS (Sprint-19).
- ✅ **No bulk send** — 3-per-tenant-per-UTC-day rate limit enforced (Sprint-20 PR-4); send rate chip surfaces it.

## Code change in this PR (1 file, ~25 lines)

`frontend/src/pages/OpportunityInboxPage.tsx`:

- Wrapped the **status pill** in a `<Link to="/governance/approvals">` when status is `queued` or `approved`.
- Wrapped the **assigned_department badge** in a `<Link to="/workstreams">` so the operator can jump from the Opportunity to its workstream owner page.

Both links carry `title=` tooltips and remain visually identical to non-link siblings; no layout drift.

## Tests

| Check | Result |
|---|---|
| `npx tsc --noEmit` | exit 0 |
| Existing OpportunityInboxPage tests | unchanged, no API or behavior contract modified |

## Hard rules respected

- [x] No deploy
- [x] No new architecture
- [x] No fake success
- [x] No generic send_email / no bulk / no LinkedIn / no scraping behind login
- [x] Status pills + badges remain truthful (link only ATOP existing badges, not replacing)

## Next

PR-5: Complete workstream/draft/approval cycle (verification + small wiring).
