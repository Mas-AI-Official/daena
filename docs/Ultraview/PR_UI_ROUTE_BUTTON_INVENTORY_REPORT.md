# PR-1: Full UI Route and Button Inventory — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE
**Doc:** [UI_BACKEND_WIRING_INVENTORY.md](./UI_BACKEND_WIRING_INVENTORY.md)

## What this PR does

Read-only crawl of `frontend/src/**`. Produces the inventory of every route,
sidebar entry, and clickable action, with the backend endpoint each one
addresses. No behavior changes.

## Counts

- **36** routes (7 public + 26 protected + 3 redirects)
- **23** sidebar items across 6 groups (Core, Intelligence, Go-to-Market, Execution, Connections, Governance)
- **180+** clickable actions mapped to backend endpoints or local state
- **10** explicit "coming soon" stubs (3 Settings Developer, 3 Settings Notifications, 3 Settings Privacy, 2 Plugins/Marketplace skill bundles)

## Top-level findings

1. The five operator loops (Chat / Opportunities / Workstreams / Approvals / Audit) are wired end-to-end.
2. The three Settings tabs (Developer / Notifications / Privacy) advertise toggles whose backend has not shipped — these are the explicit Bucket-D contract gaps.
3. Skill Bundles are a Phase-2 placeholder in MarketplaceCard / PluginDetailDrawer.
4. The Engagement Console route is preserved for bookmarks but the sidebar entry was removed; it redirects to /scan.
5. Live polling exists for sidebar badges (30s, exponential backoff) and department status (5s).
6. Error handling was rewritten 2026-04-29 — every error is logged + recorded in `useErrorStore`; toasts are suppressed only for known polling endpoints unless `silent: false` overrides per-call.

## Hard rules respected

- [x] No file modifications
- [x] No new architecture
- [x] No fake success — all "wired" claims based on direct grep of api.* call sites

## Next

PR-2: OpenAPI ↔ frontend contract diff (already complete in same batch — see [PR_OPENAPI_FRONTEND_CONTRACT_DIFF_REPORT.md](./PR_OPENAPI_FRONTEND_CONTRACT_DIFF_REPORT.md)).
