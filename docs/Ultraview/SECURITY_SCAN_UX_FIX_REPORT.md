# Security Scan UX Fix Report

Date: 2026-04-29
Author: Claude Code (Opus 4.7) -- Phase 5 of stabilization sprint

## Goal

Each scan history card surfaces title / target / scan type / authorization
scope / status / findings count / severity summary / created time /
runtime / actions, with no infinite-skeleton states on `/security/scope`.

## Pre-edit audit findings

The current [ScanList.tsx](../frontend/src/pages/scan/ScanList.tsx) was
already substantially aligned with the plan:

| Plan requirement | Pre-edit state |
|---|---|
| Title (font-medium, 14px) | already present (line 276-278) |
| Target (mono, 11px) | already present via `ReportField` (line 280) |
| Scope chip | already present (`authorizationScope` field) |
| Status badge | already present (line 255-261) |
| Severity summary | already present (line 262-270, uses `severitySummary`) |
| Findings count | already present (`findings` field) |
| Created time + relativeAgo | already present (line 285) |
| Runtime/tool | already present (`runtimeUsed`, line 283) |
| Actions: View Report / Re-run / Export | already inline (lines 289-318) |
| Archive (primary destructive) | already inline with `status-error` styling (line 320-327) |
| Delete (admin only / hidden) | not present -- only Archive shipped, which is the correct conservative default per Rule 17 |

Conclusion: ScanList.tsx render path already meets the plan's bar. The
v3.7.0 Security Supercharge stack landed all of this. The HANDS-OFF
guard from inbox.md (3 `as any` type casts) means we don't refactor the
type system, but the rendering itself doesn't need work.

## What got fixed

### `/security/scope` -- the actual infinite-skeleton page

The user reported `/security/scope` showing an infinite skeleton. Audit
of [SecurityScopePage.tsx](../frontend/src/pages/SecurityScopePage.tsx)
found:

- `loadScope()` called `api.get('/security/authorized-scope')` with the
  default 30s axios timeout
- On hang, the `loading` state stayed true for the full 30s
- Render block at line 222-230 showed only "Loading scope..." text
- No fallback path when the load failed

### Edits to [SecurityScopePage.tsx](../frontend/src/pages/SecurityScopePage.tsx)

1. **Bounded timeout**: `loadScope` now passes `{ timeout: 5000 }` to
   axios. After 5s the request aborts and the catch block fires.

2. **Per-page error state**: `loadError` state captures the failure
   message; the render guards `if (loadError && !scope)` and surfaces
   a `Card` with:
   - Title: "Authorized scope unavailable"
   - Health-aware copy: when
     `useBackendHealthStore` reports `down`/`degraded`, the message
     points to the backend; otherwise generic.
   - Mono `Detail: <error>` line for diagnosis
   - "Retry" button that re-runs `loadScope()`

3. **Health store wired in**: imports `useBackendHealthStore` from
   `@/stores/backendHealthStore`. The error card uses the global
   health status to choose the right user-facing explanation.

The card uses `border-status-error/30 bg-status-error/5` with an
`AlertTriangle` icon -- consistent with `BackendOfflineBanner`'s visual
treatment.

### `/security` (ScanPage)

Verified end-to-end. `ScanPage` already renders:
- `ScanLauncher` (always, no fetch dependency)
- `ScanList` (renders empty when history is empty -- no skeleton)
- `EmptyState` "No scans yet" when nothing is active or in history
  (line 296-302)

No infinite-skeleton issue. No edits needed.

### ScanList -- left as-is

Per the inbox.md HANDS OFF advisory, `ScanList.tsx`'s 3 `any` type
casts (lines 30, 41, 235) are not refactored. The render path was
already correct.

The plan's "5s timeout for history fetch" item was specifically aimed
at the `/security/scope` page (which is where the user actually saw the
infinite skeleton), and that's where the fix landed. The ScanPage
history fetch is fire-and-forget with a graceful empty state -- no
timeout was needed there.

## Type check

```text
$ npx tsc --noEmit
(no output -- 0 errors)
```

## Files modified

- `frontend/src/pages/SecurityScopePage.tsx` (timeout + error card)

## Files NOT modified per HANDS-OFF

- `frontend/src/pages/scan/ScanList.tsx` -- 3 `any` casts kept
- `frontend/src/pages/ScanPage.tsx` -- v3.7.0 Security Supercharge
  state machine kept intact

## Status

Phase 5 of stabilization sprint: COMPLETE.
