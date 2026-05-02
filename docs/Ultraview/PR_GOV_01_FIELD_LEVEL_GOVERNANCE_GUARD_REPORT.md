# PR-GOV-01: Field-Level Governance Guard Report

**Date:** 2026-05-02
**Branch:** rebuild-connections-mcp-runtime
**Scope:** Close the Hard Law 8 gap discovered in
`docs/Ultraview/DAENA_GOVERNANCE_TODAY_VS_TARGET.md` Section 5,
Gap #1.
**Status:** Implemented + tested. Ready for commit.

---

## 0. Hard Rules Honored

This PR was executed under nine hard rules from the briefing:

| # | Rule | Honored? |
|---|------|----------|
| 1 | Do not deploy production | YES (no Cloud Run touch) |
| 2 | Do not flip USE_CONNECTION_REGISTRY_V2=true | YES |
| 3 | Do not run `vault --apply` | YES |
| 4 | Do not delete files | YES (only Edit + Write) |
| 5 | Do not print or commit secrets | YES (audit row drops attempted VALUES, only logs field NAMES) |
| 6 | Do not run external scans | YES |
| 7 | Do not send emails / DMs / SMS / webhooks | YES |
| 8 | Do not lock the entire `/settings/user` endpoint behind Founder | YES (field-level guard preserves self-edit for normal prefs) |
| 9 | Do not break normal user preference edits | YES (test pinned: `test_non_founder_can_update_normal_prefs`) |

---

## 1. Vulnerability Description

`PUT /api/v1/settings/user` at `backend/app/api/v1/settings.py:295`
declared only `Depends(get_current_user)`. Any authenticated user
could send a body containing `default_governance_mode: UNLEASHED` and
the server would persist that change to their `User.settings` JSONB
column. On next page load, the frontend hydrator at
`frontend/src/stores/uiStore.ts:274` would read the value and apply it
to the live Zustand store, effectively flipping the operator's
governance mode without Founder consent.

This contradicts **Hard Law 8** at
`backend/app/core/hard_laws.py:83-91`:

> "The governance engine can be toggled by the Founder
> (UNLEASHED/BALANCED/GOVERNED) ... Governance mode toggle requires
> FOUNDER role."

The frontend at `SettingsGovernance.tsx` exposed the picker buttons to
every authenticated user without any role check. The backend trusted
the body without role-gating. Two independent failure modes, both
introducing the same Hard Law 8 violation.

This PR closes both at once:

* **Backend:** field-level guard inside `_update_user_preferences_impl`
  rejects sensitive fields with HTTP 403 unless caller is FOUNDER.
* **Frontend:** picker buttons are disabled with a Founder-only
  tooltip and a status banner explaining the Hard Law 8 lock.

---

## 2. Field-Level Guard Design

### 2.1 SENSITIVE_PREF_FIELDS constant

```python
SENSITIVE_PREF_FIELDS: frozenset[str] = frozenset({
    "default_governance_mode",
    "default_governance_slider",  # deprecated; mirrors default_governance_mode
    "default_routing_mode",       # Council/Quintessence cost multiplier
})
```

Three fields are gated:

1. `default_governance_mode` -- direct Hard Law 8 surface.
2. `default_governance_slider` -- deprecated alias that the UI no
   longer surfaces but the backend still accepts (per the
   backward-compat helper at `constants.py:112-144`). Without gating
   it, a malicious client could bypass guard #1 by posting the
   deprecated field name.
3. `default_routing_mode` -- COUNCIL and QUINTESSENCE multiply LLM
   cost per request. Cost preflight (Stage 5 in the chat pipeline)
   already enforces tenant ceilings at chat time, but the *default*
   should not be self-elevated by non-Founders. This is
   defense-in-depth, not the primary cost gate.

The constant uses `frozenset` so callers cannot mutate it accidentally.

### 2.2 Why field-level not endpoint-level

`require_role("FOUNDER")` would have been one line, but it would have
locked the entire `/settings/user` endpoint behind Founder. That
breaks the very common case of a user updating their own theme,
notifications, or display name. Field-level guard preserves
self-service for non-sensitive prefs while gating only the dangerous
ones.

This is the right boundary: the role check belongs at the *field
intent* level, not the *endpoint method* level.

### 2.3 All-or-nothing rejection

If a payload mixes sensitive + non-sensitive fields, the entire
request is rejected with 403. Examples:

```json
// Rejected -- 403, no theme change applied either
{"default_governance_mode": "UNLEASHED", "dark_mode": false}

// Rejected -- 403
{"default_governance_mode": "UNLEASHED"}

// Allowed -- 200, theme applied
{"dark_mode": false}
```

Why all-or-nothing? Partial application creates a footgun where the
client thinks "well at least the theme landed" while the governance
field silently failed. All-or-nothing forces clients to send
governance changes in a separate request.

### 2.4 Helper signature

```python
def _check_governance_field_permissions(
    body: UserPreferencesUpdate,
    user: CurrentUser,
) -> list[str]:
    """Return sorted list of sensitive field names a non-Founder is
    trying to set. Empty list = allowed."""
    if user.role == "FOUNDER":
        return []
    rejected: list[str] = []
    for field in SENSITIVE_PREF_FIELDS:
        if getattr(body, field, None) is not None:
            rejected.append(field)
    return sorted(rejected)
```

Pure function. Testable in isolation. Sorted output for deterministic
audit rows.

---

## 3. Audit Log on Rejection

Every rejection writes a row to the tamper-evident audit ledger via
`AuditService.log_decision`:

```python
await audit.log_decision(
    tenant_id=user.tenant_id,
    actor_id=user.id,
    actor_type="USER",
    action_type="GOVERNANCE_PREF_UPDATE_REJECTED",
    action_params={
        "attempted_fields": rejected_fields,  # NAMES only, never values
        "user_role": user.role,
    },
    result="BLOCKED",
    risk_level="HIGH",
    governance_tier=4,
)
```

Three intentional design choices:

1. **Field NAMES recorded; attempted VALUES NOT recorded.** A
   malicious payload could embed PII or a probe string designed to
   land in the audit ledger as a side channel. The rejection log only
   needs to surface "operator X tried to change governance mode" --
   the operator does not need to know what value they tried to set.
   Pinned by `test_audit_log_does_not_leak_attempted_values`.

2. **Audit failure does NOT unblock the request.** If the audit
   subsystem is down, the rejection still fires. Audit miss is logged
   locally for operator reconciliation. Pinned by
   `test_audit_failure_does_not_unblock_request`.

3. **Founder bypass does NOT log a rejection row.** Hard Law 4
   (Founder Override) is logged at the action-execution layer
   (downstream), not at the role-check layer. The role-check layer
   only logs failures. Pinned by `test_no_audit_when_founder_passes`.

`risk_level="HIGH"` and `governance_tier=4` mark these rejections as
notable enough to surface in the operator's audit timeline -- a
non-Founder trying to flip governance mode is a legitimate
investigation signal.

---

## 4. Frontend UI Gate

`frontend/src/pages/settings/SettingsGovernance.tsx`:

```tsx
const userRole = useAuthStore((s) => s.user?.role)
const isFounder = userRole === 'FOUNDER'

const handleModeChange = (mode: GovernanceMode) => {
  if (!isFounder) return  // belt-and-suspenders client guard
  setGovernanceMode(mode)
  persistUiPref('default_governance_mode', mode)
}
```

Visual design for non-Founders:

* Status banner above the picker: "Read-only. Governance mode for
  this tenant is set by the Founder (Hard Law 8). The current mode is
  shown highlighted."
* Picker buttons: `disabled={!isFounder}`, `cursor-not-allowed`,
  `opacity-70`, native `title` tooltip on hover pointing to Hard Law
  8.
* Current mode indicator: a `Current` badge appears on the active
  mode button, so the read-only viewer can still see what's selected.
* Soft Laws panel: unchanged (already opacity-40 when not GOVERNED).
* Internal tiers disclosure: unchanged.

The client guard is defense-in-depth. Even if the client guard is
bypassed (e.g. user opens devtools and dispatches the action
manually), the backend guard at `_update_user_preferences_impl` still
enforces the rule.

---

## 5. Tests

`backend/tests/test_settings_governance_guard.py` -- 17 tests across
3 classes, 100% pass.

### TestSensitiveFieldsConstant (4 tests)

Pin the public contract of `SENSITIVE_PREF_FIELDS`:

| Test | Asserts |
|------|---------|
| `test_constant_includes_governance_mode` | core field gated |
| `test_constant_includes_deprecated_slider` | bypass path closed |
| `test_constant_includes_routing_mode` | cost multiplier gated |
| `test_constant_does_not_overcollect` | benign fields NOT in set (anti-overreach guard) |

### TestFieldLevelGovernanceGuard (9 tests)

Pin the impl-level enforcement:

| Test | Asserts |
|------|---------|
| `test_non_founder_blocked_from_governance_mode` | OPERATOR -> 403 |
| `test_admin_blocked_too` | ADMIN < FOUNDER, also 403 |
| `test_non_founder_blocked_from_deprecated_slider` | bypass path closed |
| `test_non_founder_blocked_from_routing_council` | QUINTESSENCE -> 403 |
| `test_non_founder_can_update_normal_prefs` | display_name + theme + notif OK |
| `test_founder_can_update_governance_mode` | Founder bypass works |
| `test_founder_can_update_routing_council` | Founder can pick QE |
| `test_mixed_payload_is_all_or_nothing_reject` | partial apply prevented |
| `test_multiple_sensitive_fields_all_listed` | sorted, deterministic |

### TestAuditLogOnRejection (4 tests)

Pin the audit contract:

| Test | Asserts |
|------|---------|
| `test_audit_log_emitted_with_field_names` | structured fields + correct constants |
| `test_audit_log_does_not_leak_attempted_values` | PII / probe channel closed |
| `test_audit_failure_does_not_unblock_request` | broken audit does not become backdoor |
| `test_no_audit_when_founder_passes` | Founder bypass produces no rejection row |

### Regression check

* `test_new_endpoints.py::TestUserPreferences` (existing) still passes.
* `test_connection_v2_probe_truth.py` (PR-3) still passes (8/8).
* Other phase11 test files pass when run individually. Batch failures
  observed earlier are pre-existing test pollution unrelated to this
  PR (verified: each file passes in isolation).

---

## 6. Files Changed

| File | Change | Lines |
|------|--------|-------|
| `backend/app/api/v1/settings.py` | Added HTTPException import, SENSITIVE_PREF_FIELDS constant, _check_governance_field_permissions helper, guard call + audit log + 403 raise inside _update_user_preferences_impl, narrow except HTTPException re-raise in PUT handler | +85 |
| `frontend/src/pages/settings/SettingsGovernance.tsx` | Added authStore import, FOUNDER_ONLY_TOOLTIP, isFounder check, status banner, button disable + tooltip + Current badge | +40 |
| `backend/tests/test_settings_governance_guard.py` | NEW: 17 tests across 3 classes covering constant, guard, audit | +330 |
| `docs/Ultraview/PR_GOV_01_FIELD_LEVEL_GOVERNANCE_GUARD_REPORT.md` | NEW: this report | +280 |

Net: 4 files, ~735 lines added, 0 deleted (no rip-out, additive guard).

---

## 7. Verification Commands Run

```bash
# Backend unit tests for the guard
backend/.venv/Scripts/python.exe -m pytest \
    backend/tests/test_settings_governance_guard.py -v
# Result: 17 passed in 0.24s

# Regression on adjacent tests
backend/.venv/Scripts/python.exe -m pytest \
    backend/tests/test_new_endpoints.py \
    backend/tests/test_connection_v2_probe_truth.py
# Result: 15 passed in 0.23s

# Frontend type check
frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json
# Result: 0 errors (zero output)

# Em-dash audit (project Rule 12) -- per-file count of U+2014 in
# diff additions (lines starting with '+'). Done by piping git diff
# through grep with the literal U+2014 character class.
# Result: 0 added em-dashes across all PR-GOV-01 files. The single
# pre-existing em-dash at settings.py:3 in the module docstring is
# unchanged by this PR.
```

---

## 8. What This PR Does NOT Cover (Honesty Check)

1. **Direct DB access bypasses this guard.** Any code that updates
   `User.settings` JSONB directly via SQL or via a different service
   bypasses the role check. The guard is a route-layer defense, not a
   model-layer constraint. **Future:** add a SQLAlchemy event
   listener on `User.settings` writes that re-validates. Tracked as
   a follow-up gap.

2. **Tenant-creation-time defaults are not gated.** When a Tenant
   row is first seeded, its `default_governance_mode` comes from
   `_UI_PREF_DEFAULTS` which is hardcoded to `"GOVERNED"`. Safe by
   default, but a future migration that lowers the default would not
   be blocked by this guard. **Mitigation:** code review +
   `git blame` discipline.

3. **Frontend gate trusts the JWT role claim.** The frontend reads
   `role` from the decoded JWT payload at app startup. A user who
   forges a JWT with `role: "FOUNDER"` would see the picker enabled
   client-side. The backend guard still rejects the actual write
   (the JWT signature is verified server-side at `decode_access_token`).
   So the worst-case client-forge attack is "see clickable buttons
   that always 403" -- annoying, not exploitable.

4. **No audit replay tooling for the GOVERNANCE_PREF_UPDATE_REJECTED
   events.** Rejections land in the audit ledger but there is no UI
   surface that aggregates them yet. **Future:** add a
   "Governance attempts" panel under `GovernanceAuditPage` that
   filters by `action_type = "GOVERNANCE_PREF_UPDATE_REJECTED"`.

5. **The Council/Quintessence routing-mode gate is conservative.**
   Non-Founders cannot self-elevate to COUNCIL/QUINTESSENCE *as
   default*, but they can still pick those modes per-request via the
   chat composer (where cost preflight Stage 5 enforces the actual
   ceiling). If the founder later decides per-request COUNCIL also
   needs Founder, a separate PR would gate the chat composer.

---

## 9. Hard Rule Final Check

- [x] No production deploy touched.
- [x] `USE_CONNECTION_REGISTRY_V2` not flipped.
- [x] No `vault --apply` invocation.
- [x] No file deletions (only Edit + Write).
- [x] Audit log records field NAMES not VALUES.
- [x] No external scans, emails, DMs, webhooks, SMS.
- [x] `/settings/user` endpoint NOT locked behind Founder
      (verified: `test_non_founder_can_update_normal_prefs` passes).
- [x] Normal user preference edits still work
      (verified: same test).
- [x] Em-dash count in added lines: 0
      (verified by per-file `git diff` em-dash count).

---

## 10. Commit Message

```
phase11: enforce founder-only governance preference changes

Closes the Hard Law 8 violation surfaced in
docs/Ultraview/DAENA_GOVERNANCE_TODAY_VS_TARGET.md Section 5, Gap #1:
PUT /settings/user previously accepted default_governance_mode from
any authenticated caller, letting a non-Founder flip governance mode
on the public preferences API.

Field-level guard inside _update_user_preferences_impl rejects three
sensitive fields with HTTP 403 unless caller is FOUNDER:
- default_governance_mode (direct Hard Law 8 surface)
- default_governance_slider (deprecated alias, bypass path closed)
- default_routing_mode (Council/Quintessence cost multiplier default)

The endpoint itself remains open to all authenticated users so
non-Founders can still self-edit theme, notifications, display name,
and other non-sensitive preferences. Mixed payloads (sensitive +
non-sensitive) are rejected all-or-nothing to prevent the "well at
least the theme landed" footgun.

Rejection writes a tamper-evident audit row with field names but NOT
attempted values (a malicious payload value could itself be a probe
or PII channel). Audit failure does not unblock the rejection.

Frontend gate at SettingsGovernance.tsx disables the picker buttons
for non-Founders with a Founder-only tooltip and a status banner
pointing back to Hard Law 8. Defense-in-depth: the backend guard is
the actual enforcement; the UI gate prevents the operator confusion
of "click button, see error".

17 new tests in test_settings_governance_guard.py, 100% pass.
Regression check: TestUserPreferences, PR-3 probe truth tests, all
green. Frontend tsc 0 errors.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```
