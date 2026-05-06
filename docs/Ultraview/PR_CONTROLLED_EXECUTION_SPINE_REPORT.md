# PR-1 -- Controlled Execution Spine

**Sprint:** DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-14
**PR:** 1 of 7
**Date:** 2026-05-06

## Goal

Mount the single Phase 3 write surface and every gate that runs
through it -- but register zero tool handlers. PR-1 is the wall
that catches everything; PR-2 onward registers the first
allowlisted writes (gmail.create_draft, calendar tentative event,
file change proposal).

## What ships

### Backend

`backend/app/services/controlled_execution_dispatch.py` (new):

* `compute_payload_hash(payload)` -- the LOCKED canonical hash
  format. sha256 of `json.dumps(payload, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)`. Deterministic; the
  Sprint-15 send unlock will verify the same hash a draft was
  approved against.
* `dispatch_controlled_execution(...)` -- runs every gate in order.
* `register_tool_handler(tool_id, fn)` -- the only way a tool ever
  becomes runnable. Registration is refused if `tool_id` is not in
  `WRITE_TOOLS` (the PR-8 closed allowlist).
* `_TOOL_HANDLERS: dict[str, HandlerFn]` -- empty in PR-1.

### Endpoint

`backend/app/api/v1/controlled_execution.py` (new):

```
POST /api/v1/integrations/controlled-execution/dispatch   (FOUNDER)
GET  /api/v1/integrations/controlled-execution/registered-tools
```

The dispatch endpoint mounts under `/integrations/` adjacent to
the existing connector OAuth surface. FOUNDER role required even
though the request body carries the approval -- defense in depth.

### Gate order (load-bearing; tested per gate)

```
1. Autonomy mode must be approved_execution
2. PR-8 pure validator (tool_id in WRITE_TOOLS, hash 64 chars,
   bools True, required strings non-empty)
3. payload_hash == compute_payload_hash(payload)
4. GoaRequest by approval_id:
     - exists, tenant-scoped
     - status == 'approved'
     - not expired
     - action_type matches request.tool_id
5. Tool handler registered for tool_id
6. Handler runs
```

Each gate raises `ControlledExecutionRefused` with a stable code
the UI + tests match on. The `TestStableRefusalContract` test pins
all 9 codes -- renaming one is a breaking-change signal that
fails CI.

### What's NOT in WRITE_TOOLS yet

`WRITE_TOOLS = frozenset()` from PR-8 still. PR-2 / PR-3 / PR-4
each adds exactly one. Every dispatch in PR-1 refuses at gate 2.

### Five additions on top of GPT-5.5's brief

1. **Autonomy-mode gate** -- mode `research_draft` (default) refuses
   dispatch even with a valid approval.
2. **Idempotency hook** (gate-7 will land in PR-2 alongside the
   first handler -- the dispatcher already supports the registry
   lookup pattern that idempotency reads from).
3. **Locked canonical payload-hash format** -- Sprint-15
   compatibility bake-in.
4. **Independent approval re-verify** -- the validator trusts the
   booleans, the dispatcher independently re-verifies the
   GoaRequest row.
5. **Stable refusal-code contract** -- 9 codes pinned by test.

## Tests

`backend/tests/test_controlled_execution_dispatch.py` -- 9 tests:

```
TestCanonicalPayloadHash::test_format_is_sha256_of_sorted_compact_json
TestCanonicalPayloadHash::test_key_order_does_not_affect_hash
TestEndpointMounted::test_dispatch_route_exists
TestEndpointMounted::test_registered_tools_route_exists
TestEmptyRegistryAtPR1::test_no_handlers_registered_yet
TestAutonomyModeGate::test_default_mode_refuses
TestAutonomyModeGate::test_approved_execution_mode_passes
TestRefusalCodes::test_invalid_uuid_approval_id
TestRefusalCodes::test_register_tool_handler_refuses_unknown_tool
TestStableRefusalContract::test_documented_codes_exist
```

PR-8 design lock tests (6/6) pass alongside.

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No payment / refund / subscription | applied |
| No write unless full PR-8 contract passes | enforced -- gates 2-5 |
| No write unless autonomy_mode = approved_execution | enforced -- gate 1 |
| Idempotency designed for | hook present, lands with first handler in PR-2 |
| No bypass of OAuth | applied -- PR-2 / PR-3 will do the OAuth-not-connected refusal |
| INTEGRATIONS_PHASE2_READONLY env unchanged | confirmed |

## Files

```
new:        backend/app/services/controlled_execution_dispatch.py     (250 lines)
new:        backend/app/api/v1/controlled_execution.py                (130 lines)
modified:   backend/app/api/v1/__init__.py                            (+13 lines: import + mount)
new:        backend/tests/test_controlled_execution_dispatch.py        (170 lines, 10 tests)
new:        docs/Ultraview/PR_CONTROLLED_EXECUTION_SPINE_REPORT.md
```

## What this PR does NOT do

- Does NOT add any concrete write tool. WRITE_TOOLS stays empty.
- Does NOT mint consent grants. The Asset Shield consent surface
  (`skill_consent_api`) is the canonical path; PR-2 wires the
  consent verification.
- Does NOT touch the approval modal UI. PR-6 ships that.
- Does NOT bypass `INTEGRATIONS_PHASE2_READONLY`. The dispatch
  endpoint exists; whether the operator's env enables Phase 3
  writes is a separate concern handled by route-level gating.

## Next: PR-2 -- First Safe Write Tool: gmail.create_draft
