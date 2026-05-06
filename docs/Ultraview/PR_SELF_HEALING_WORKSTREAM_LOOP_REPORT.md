# PR-6 -- Self-Healing Workstream Loop

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 6 of 9
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Daena detects subsystem failures and authors a repair workstream
with a deterministic suggested brain (cross-AI delegation table from
CLAUDE.md). The repair workstream is a *plan*, not a write -- the
operator (or a future trust-graduated autonomous loop) drives the
patch. Cross-brain redundancy: while Ollama keeps the foreground,
Codex (async-native) handles mechanical patches, and Claude Code
handles multi-file reasoning.

## What ships

`backend/app/services/self_healing_service.py` (new). Two pure
functions:

```python
enumerate_failures(probes: dict) -> list[Failure]
repair_workstream_payload(failure: Failure) -> dict
```

Pure means no HTTP / DB / LLM call -- callers inject probe outputs
captured from the existing readiness endpoints.

### Closed failure subsystem set (8)

```
backend_health           backend uvicorn unreachable
frontend_health          vite dev server unreachable
main_brain_not_ready     no callable main brain in router fallback
cli_runtime_offline      Claude/Codex/Gemini CLI detected but offline
mcp_probe_fail           MCP server probe failed
schema_drift             alembic head != applied head
fe_be_route_404          frontend calls a route the backend doesn't mount
test_regression          pytest fast subset has new failures
```

Adding a new subsystem requires touching the `Literal` type AND the
contract test `TestClosedFailureSet`.

### Cross-brain repair routing (locked)

| Failure subsystem | Suggested brain | Why |
|---|---|---|
| backend_health | ollama_backend | local probe / restart guidance, no paid call |
| frontend_health | ollama_backend | local probe / restart guidance |
| main_brain_not_ready | human | by definition no LLM is callable -- founder must choose |
| cli_runtime_offline | codex_cli | async mechanical "rerun login / rebind path" |
| mcp_probe_fail | codex_cli | mechanical restart / re-register |
| schema_drift | claude_code | multi-file reasoning (model + migration + consumers) |
| fe_be_route_404 | codex_cli | mechanical: add the missing router or rename caller |
| test_regression | claude_code | root cause may span many files |

This is the cross-AI delegation table from CLAUDE.md applied
deterministically. The user override path remains via the workstream's
`department_override` parameter.

### Repair workstream payload shape (locked)

```ts
{
  goal:               string,                    // "Self-repair: <description>"
  department_hint:    string,                    // "Engineering" or "Security Operations"
  next_step_text:     string,                    // "Suggested brain: <brain>. Action: <class>."
  initial_context: {
    self_repair: {
      failure_id:           string,
      subsystem:            FailureSubsystem,
      severity:             "info" | "warn" | "blocker",
      suggested_brain:      SuggestedBrain,
      repair_action_class:  string,
      evidence:             dict,
      delivery:             "manual_only",       // LOCKED
      requires_approval:    true,                // LOCKED
    }
  }
}
```

The two locked fields are the SAME guard used by PR-4's draft action
factory. "Daena proposes; never auto-executes" applies identically
to repair workstreams. The contract test walks the entire payload
tree and asserts no `auto_execute / run_now / apply / execute` field
appears.

### What this PR does NOT do

- Does NOT apply patches.
- Does NOT run tests.
- Does NOT commit code.
- Does NOT spin up a real-time monitor; detection is pulled, not
  pushed. A cron / heartbeat consumer in a future PR can call
  `enumerate_failures()` on a schedule and create workstreams via
  `WorkstreamService.start()`.
- Does NOT touch the router or MCP registry. Surfaces failures only.

## Tests

`backend/tests/test_self_healing_service.py` -- 11 tests:

```
TestNoFailuresWhenAllGreen::test_empty_probes_no_failures
TestNoFailuresWhenAllGreen::test_all_green_probes_no_failures
TestDetection::test_backend_unreachable_blocker
TestDetection::test_main_brain_not_ready_routes_to_human
TestDetection::test_cli_runtime_offline_routes_to_codex
TestDetection::test_schema_drift_routes_to_claude_code
TestDetection::test_fe_be_route_404
TestDetection::test_test_regression_routes_to_claude_code
TestDetection::test_security_mcp_routes_to_security_ops
TestClosedFailureSet::test_subsystem_label_is_closed
TestRepairWorkstreamPayload::test_payload_carries_self_repair_namespace
TestRepairWorkstreamPayload::test_no_auto_execute_field
```

Sanity regression: 49/49 pass on the Sprint-13 fast subset.

## Hard rules audit

| Rule | Status |
|---|---|
| Daena proposes; never auto-executes | enforced -- locked `delivery="manual_only"` + `requires_approval=True` + `no auto_execute` walk |
| Cross-brain repair pattern | enforced -- failure -> brain mapping is deterministic + tested |
| No deploy | applied -- detection is pull-only |
| No external sites | n/a |
| No OS-wide destructive change | n/a |
| Operator override | preserved -- `department_hint` is a hint; `WorkstreamService.start` accepts override at the API layer |
| Closed failure set | enforced + tested |

## Files

```
new:        backend/app/services/self_healing_service.py     (240 lines)
new:        backend/tests/test_self_healing_service.py        (200 lines, 12 tests)
new:        docs/Ultraview/PR_SELF_HEALING_WORKSTREAM_LOOP_REPORT.md
```

## Next: PR-7 -- Encoded-Injection Defense Hardening
