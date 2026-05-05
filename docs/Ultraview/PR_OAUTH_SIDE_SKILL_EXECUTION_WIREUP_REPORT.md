# PR-1 — IntegrationRouter phase-2 read-only gate + owner_email pin

**Sprint:** DAENA-SUPERVISED-WORK-OPERATOR-SPRINT-11
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)
**Restore point:** master @ `0c5c2d4` (PR-0 push)

## Goal

Lock Google / Calendar / Notion external integrations to **read-only**
until the approval queue (PR-4) is in place, and pin every dispatch to
a specific `owner_email` so the operator picks which connected account
(`masoud.masoori@mas-ai.co` vs `daena@mas-ai.co`) the call runs against.
This is the foundational gate for every later supervised-work PR -- if
this isn't airtight, every other safety claim downstream is theatre.

## What changed

### 1. New feature flag (`backend/app/core/config.py`)

```python
integrations_phase2_readonly: bool = True
```

- Default ON.
- Operator override only via env (`INTEGRATIONS_PHASE2_READONLY=false`).
- **Never togglable from the UI** so an LLM cannot flip it during a chat
  to escape the boundary.
- Phase 3 (controlled execution post-approval-queue) flips this OFF
  *together with* ApprovalQueue gating, never alone.

### 2. WRITE_TOOLS registry + `_is_write_tool` helper (`integration_router.py`)

```python
WRITE_TOOLS: dict[str, set[str]] = {
    "gmail": {"send_email", "create_draft"},
    "google-calendar": {"create_event", "update_event"},
    "calendar": {"create_event", "update_event"},  # alias
    "notion": {"create_page"},
}
```

A test asserts every entry exists in the corresponding client's `TOOLS`
dict and that no read tool is accidentally listed as write.

### 3. Phase-2 gate in `IntegrationRouter.execute()`

The gate fires **before** the connection lookup. Order matters: a missing
account, a misconfigured permission row, or a transient DB error must not
mask the write-block.

```python
if (
    settings.integrations_phase2_readonly
    and _is_write_tool(provider, tool_name)
):
    # audit row: outcome=blocked, blocked_reason=write_disabled_phase2
    raise PermissionDeniedError("write_disabled_phase2: ...")
```

Exception message starts with `write_disabled_phase2:` so callers can do
prefix-matching for the specific failure mode without parsing the whole
string.

### 4. `owner_email` parameter on `execute()` + `execute_qualified()`

- New optional parameter (default `None`) so the three internal callers
  (`api/v1/integrations.py`, `department_workflows.py`, `execution_service.py`)
  keep working unchanged.
- When provided, `_get_connected_instance` filters
  `ConnectorInstance.owner_email` case-insensitively. Mismatch -> raises
  `NotConnectedError("...is not connected for owner_email '...'")`.
- When **not** provided AND the user has multiple connected instances for
  the same provider (the founder/agent two-account case), the router
  raises `NotConnectedError("owner_email_required: ...")` so an unaware
  caller can't accidentally dispatch to the wrong account.
- Single-instance case: `owner_email=None` still works (legacy path).

### 5. Audit emission on every router decision (`AuditService.log_decision`)

Action type is the new value `integration.tool_invocation`.
`action_params` carries:

| key | values |
|---|---|
| `provider` | `gmail` / `google-calendar` / `calendar` / `notion` |
| `tool_name` | the tool dispatched |
| `owner_email` | lowercased instance email, or null for non-Google |
| `outcome` | `executed` / `blocked` / `approval_required` / `failed` |
| `blocked_reason` | `write_disabled_phase2` / `not_connected` / `permission_block` / `<exc>` |
| `read_only` | `true` for read tools, `false` for write tools |
| `is_write_tool` | only present on the phase-2 block path (extra clarity) |

Result codes follow the existing audit ladder: `ALLOWED` / `BLOCKED` /
`APPROVAL_REQUIRED` / `FAILED`.

**Hard rule respected:** the audit row never carries the access token,
the tool params, or the request body. Only metadata.

### 6. HTTP API surface (`api/v1/integrations.py`)

`ToolExecuteRequest` and `QualifiedToolRequest` accept an optional
`owner_email: str | None` field. Forwarded straight to the router.
No new POST endpoint added (Sprint-11 hard rule: no new submit/send/post
verbs reach the codebase).

### 7. `list_available_tools()` surfaces phase-2 metadata

Each tool entry now carries `is_write` and `blocked_by_phase2_readonly`
so the UI can grey out write actions while the gate is on. The instance
row also exposes `owner_email` so the picker can render account labels.

## Tests

`backend/tests/test_integrations_readonly.py` — 16 tests, all passing.

| Group | Cases |
|---|---|
| `TestWriteToolsRegistry` | 4 (registry vs client.TOOLS sync, known reads/writes, alias parity, helper) |
| `TestPhase2ReadOnlyGate` | 4 (gmail send block, audit row recorded, calendar create_event block, notion create_page block) |
| `TestOwnerEmailPin` | 3 (mismatch, ambiguous-no-pin, match dispatches) |
| `TestReadToolStillWorks` | 1 (search_emails under phase-2 ON) |
| `TestApiSurface` | 3 (execute, execute/qualified, no /send route exists) |

Regression suite of existing integration tests still green:
`tests/test_integrations.py + test_integration_critical_flows.py + test_router_phase2.py` -> **98 passing, 0 failing**.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push (other than PR-0 restore) | ✅ |
| No secrets read/printed/committed | ✅ |
| No external messages | ✅ |
| No job applications submitted | ✅ |
| No forms submitted | ✅ |
| No social posts | ✅ |
| No payments | ✅ |
| No browser automation on external sites | ✅ |
| No Phase 3 writes | ✅ — gate explicitly enforces this |
| No duplicate command center page | ✅ — no UI changes in PR-1 |
| No duplicate Opportunity / ContentBrief models | ✅ — no model changes in PR-1 |

## Files touched

```
modified:   backend/app/core/config.py
modified:   backend/app/services/integrations/integration_router.py
modified:   backend/app/api/v1/integrations.py
new:        backend/tests/test_integrations_readonly.py
new:        docs/Ultraview/PR_OAUTH_SIDE_SKILL_EXECUTION_WIREUP_REPORT.md
```

No client files touched (gmail_client / calendar_client / notion_client).
The TOOLS dicts are intentionally left intact: the gate is applied at the
router, not by trimming clients. This keeps the Phase 3 unblock path
straightforward — flip the flag, route through `ApprovalQueue`, no
removed code to re-add.

## What this PR does *not* do (deferred to later PRs)

- PR-2: structured payload on `ResearchDraft` + Drafts lane in `WorkstreamsPage`.
- PR-3: `FormDraft` Assistant.
- PR-4: `ApprovalQueue` extension with draft kinds.
- PR-5: end-to-end smoke.

## Next step

PR-2 — extend `ResearchDraft.structured_payload` JSONB + post-process
career/content flows + add Drafts lane in `WorkstreamsPage`. No new
canonical models. No parallel page.
