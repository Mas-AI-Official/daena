# PR-1 -- Business Autonomy Mission Control

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 1 of 9
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Give the operator a single, honest meta-control over what classes of
action Daena is allowed to take autonomously. The mode is the policy;
every other autonomous-business surface (opportunity discovery, draft
factory, security scout, self-healing) consults it before doing
anything visible.

This PR ships the *control surface only*. PR-2..PR-6 wire it into
consumers.

## What ships

### Backend

`backend/app/api/v1/autonomy_mode.py` (new). Mounted under `/system/`
adjacent to the readiness endpoints:

```
GET  /api/v1/system/autonomy-mode
PUT  /api/v1/system/autonomy-mode { mode: AutonomyMode }
```

Five-state enum (locked):

```
off                       no autonomous action at all
observe                   read-only surveillance only
research_draft (default)  research + create local drafts
propose_actions           draft + queue approvals
approved_execution        execute already-approved items only
```

Persistence: single JSON file at `backend/.autonomy_mode.json`
(gitignored). Survives restart, inspectable from other services
without a DB hop.

Response shape (`AutonomyState`):

```ts
{
  mode: AutonomyMode
  allowed_action_classes: string[]
  blocked_action_classes: string[]   // hard-blocked, never lifted
  active_workstreams: number
  queued_approvals: number
  last_changed_at: string | null
}
```

Counts come from existing tables:
- `active_workstreams` = `Workstream` rows whose `status` is not
  `COMPLETE` or `FAILED`.
- `queued_approvals` = `GoaRequest` rows whose `status == "pending"`.

Both are best-effort: query failure -> 0, never raises.

### Frontend

`frontend/src/components/common/AutonomyMissionControl.tsx` (new).
Mounted at the top of `WorkstreamsPage` (above the Drafts lane), so
the operator sees the policy before what Daena did under it.

Five-card mode selector with tone-coded pills:

| Mode | Tone | What it allows |
|---|---|---|
| Off | rose | nothing |
| Observe | slate | research_read_only |
| Research + Draft | teal | research + draft + qe + workstream |
| Propose Actions | amber | + approval_queue_enqueue |
| Approved Execution | violet | + execute_approved_item |

The hard-blocked set renders verbatim under a collapsible `<details>`
section so the operator can see the wall.

### Hard-blocked action classes (always, in every mode)

```
external_send_unapproved
external_submit_unapproved
external_post_unapproved
external_apply_unapproved
external_pay
scan_unauthorized_target
install_packages_globally
deploy_production
force_push
secret_read
```

These map to the Sprint-13 brief's hard stops + the v3.7 Asset Shield
rules. The locked test `TestHardBlockedAlways::test_no_mode_lifts_hard_blocks`
asserts that no mode -- not even `approved_execution` -- can lift any
of them.

## Tests

`backend/tests/test_autonomy_mode_endpoint.py` -- 10 tests, all pass:

```
TestEndpointMounted::test_get_mounted_under_v1
TestEndpointMounted::test_put_mounted_under_v1
TestEnumLocked::test_five_states_locked
TestEnumLocked::test_default_is_research_draft
TestHardBlockedAlways::test_hard_blocked_set_present
TestHardBlockedAlways::test_no_mode_lifts_hard_blocks
TestPersistenceRoundTrip::test_write_then_read
TestPersistenceRoundTrip::test_corrupt_file_falls_back_to_default
TestNoSecretSurface::test_response_model_has_no_secret_fields
TestPersistenceFileGitIgnored::test_in_gitignore
```

`npx tsc --noEmit` exits 0.

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secret read/print | enforced + tested (no token/secret/api_key/env field on response) |
| No paid API call | n/a (read/write to local JSON file only) |
| No external send/submit/post/apply | encoded into hard-blocked set |
| No Phase 3 writes | unaffected (`INTEGRATIONS_PHASE2_READONLY=true`) |
| No bypass of OAuth | unaffected |
| No random package installs | applied |
| No duplicate command center | extended `WorkstreamsPage`, no new route |
| Audit per call | `logger.info("autonomy.mode_changed", ...)` on PUT |
| Honest mode reporting | counts are real DB queries, not stubs; mode persists to disk |

## Files

```
new:        backend/app/api/v1/autonomy_mode.py             (242 lines)
modified:   backend/app/api/v1/__init__.py                  (+11 lines: import + mount block)
modified:   backend/.gitignore                              (+2 lines: .autonomy_mode.json + .llama-server.pid)
new:        backend/tests/test_autonomy_mode_endpoint.py    (170 lines, 10 tests)
new:        frontend/src/components/common/AutonomyMissionControl.tsx (260 lines)
modified:   frontend/src/pages/WorkstreamsPage.tsx          (+7 lines: import + mount block)
new:        docs/Ultraview/PR_BUSINESS_AUTONOMY_MISSION_CONTROL_REPORT.md
```

## What this PR does NOT do

- Does NOT yet gate any consumer service on the mode value. PR-2..PR-6
  wire that in.
- Does NOT change governance pipeline behavior. SecurityGate, Shield,
  Asset Shield, approval queue thresholds remain as Sprint-12.
- Does NOT introduce a new audit row class. Mode changes log via the
  existing structured logger; PR-2 introduces the
  `autonomy.action_class.allowed/blocked` audit rows when a consumer
  consults the mode.
- Does NOT expose the mode in chat. PR-2 adds the
  `what is autonomy mode` VP-command intent.

## Next: PR-2 -- Opportunity Discovery Engine
