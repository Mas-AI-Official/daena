# PR-SCAN-ADD-TO-SCOPE-INLINE-CTA · Sprint-9 PR-1 Report

**Branch:** `master` (this PR commits directly to the merged Sprint-8 line)
**Date:** 2026-05-05
**Author:** Claude (under bounded-autopilot brief)

---

## Verdict

**Ready for review. Do NOT push to origin or deploy.**

The /scan page now offers a founder-only "Add this target to Scan Scope" CTA when a scan is blocked by `target_not_in_scope`. Click → confirmation modal → operator picks scope_type (default exact_url, never wildcard) → backend appends to authorized scope → success notice. **No auto-scan.** Operator must click Start Scan again.

The existing `target_matches_scope` enforcement at `POST /security/scans/start` is unchanged. PR-1 only edits the **input data** the gate consumes; it never touches the gate logic itself.

---

## What changed

### Backend
**`backend/app/api/v1/security_authorized_scope.py`** — new founder-gated endpoint:

```
POST /api/v1/security/authorized-scope/add
Body: { target: string, scope_type: "exact_url" | "domain" | "wildcard_subdomain" }
```

- `parse_target` classifies the input (domain / ipv4 / path / unknown).
- `unknown` → `400 target_unparseable`. The gate cannot match what it cannot parse, so we refuse to write entries that would never trigger.
- `wildcard_subdomain` only valid for domain-kind targets. For IPs / repo paths → `400 scope_type_mismatch`. (Wildcard semantics in the gate match domains by suffix; they never apply to IPs or paths.)
- Read-modify-write on `authorized_scopes.json` via the existing `_write_all_scopes` atomic helper.
- Idempotent: re-adding an existing entry returns `already_present=true` with no duplicate write.
- Default `scope_type` is `exact_url` — wildcard is **opt-in**, never default.
- Audit row written via `AuditService.log_decision`:
  - `action_type = "security.scope.added_from_scan"`
  - `actor_type = "FOUNDER"`, `result = "ALLOWED"`, `risk_level = "HIGH"`, `governance_tier = 4`
  - `action_params = { target, kind, scope_type, bucket, stored_value, already_present }` — names + intent only, **no secrets**
- Audit failures are logged but never block the operator (audit is a side channel, not a gate).

### Frontend
**`frontend/src/pages/ScanPage.tsx`** — CTA + modal:

- Imports `useAuthStore` so the CTA is gated client-side on `role === 'FOUNDER'`. (Backend role gate is the second line of defense.)
- New state: `scopeBlockedTarget`, `scopeModalOpen`, `scopeType`, `scopeAdding`, `scopeAddError`, `scopeAddSuccess`.
- `startScan` catch path: when `code === 'target_not_in_scope'`, also stash `detail.target` in `scopeBlockedTarget`. The CTA renders below the launcher when both `scopeBlockedTarget` and `isFounder` are truthy.
- "Add this target to Scan Scope" button (`data-testid="scan-scope-cta-add"`) opens a confirmation modal (`data-testid="scan-scope-cta-modal"`).
- Modal:
  - Read-only target display.
  - 3 radio options (`exact_url` / `domain` / `wildcard_subdomain`) — each with a `data-testid="scan-scope-cta-radio-<id>"`.
  - **Default initializer:** `useState<ScopeType>('exact_url')` — wildcard cannot be selected without an explicit click.
  - Warning banner: "Only add targets you are authorized to test."
  - Confirm button (`data-testid="scan-scope-cta-confirm"`) → POST `/security/authorized-scope/add` → on success: toast + clear `scopeBlockedTarget` + close modal. **No call to `/scans/start`.** Operator clicks Start Scan again.
- Non-founder: CTA is invisible. The existing scope-blocked error message and the existing `ScopeStatusBanner` provide the "go to /security/scope" guidance unchanged.

---

## Hard rules verified

| # | Rule | How verified |
|---|---|---|
| 1 | No production deploy | No GCP / Cloud Run touch in this commit |
| 2 | No push to origin | Local commit only; user runs `git push` manually |
| 3 | No `USE_CONNECTION_REGISTRY_V2` flip | Untouched |
| 4 | No `vault --apply` | Untouched |
| 5 | No secrets read/printed/committed | Audit `action_params` checked for forbidden substrings (`password`, `secret`, `bearer`, `token`, `sk-`, `pplx-`, `xai-`); none present |
| 6 | No external scans | This PR adds NO new outbound HTTP. `/scans/start` still gated by `target_matches_scope` |
| 7 | No auto-start scan after add | Test `test_add_does_not_auto_start_a_scan` checks the response shape rejects `job_id`/`scan_id`/`scan_dispatched`. Frontend test pins that the success handler does not POST to `/scans/start`. |
| 8 | Non-founder cannot add scope | `require_role("FOUNDER")` on the route + frontend `isFounder` gate. Test `test_add_endpoint_rejects_non_founder` proves a MANAGER token returns 403 |
| 9 | No default-to-wildcard | Backend Pydantic default is `"exact_url"`; frontend `useState<ScopeType>('exact_url')`. Tests `test_default_scope_type_is_exact_not_wildcard` and `test_scope_modal_does_not_default_to_wildcard` pin both |
| 10 | No bypass of `target_matches_scope` | Pivot test `test_scan_blocked_before_add_and_allowed_after`: `/scans/start` still 403s before the add, only passes after. Gate logic itself is unmodified |

---

## Tests

13 new in `backend/tests/test_security_scope_add_from_scan.py`:

| # | Test | What it pins |
|---|---|---|
| 1 | `test_add_endpoint_rejects_non_founder` | MANAGER role gets 403 |
| 2 | `test_founder_can_add_exact_host_from_url` | URL → host stripped → exact_domains |
| 3 | `test_founder_add_is_idempotent` | Second add returns `already_present=true`, no duplicate row |
| 4 | `test_default_scope_type_is_exact_not_wildcard` | Body without `scope_type` defaults to exact_url |
| 5 | `test_wildcard_subdomain_lands_in_wildcard_bucket` | Explicit wildcard goes to `wildcard_domains` |
| 6 | `test_scan_blocked_before_add_and_allowed_after` | Pivot: gate enforced both sides of the add |
| 7 | `test_add_does_not_auto_start_a_scan` | Response has no scan-side fields |
| 8 | `test_add_writes_audit_row_with_no_secrets` | Audit row exists, action_type/actor_type/governance_tier correct, params have no secret substrings |
| 9 | `test_unparseable_target_is_rejected` | "not a url or hostname" → 400 |
| 10 | `test_wildcard_rejected_for_ip_target` | IP + wildcard → 400 |
| 11 | `test_scan_page_renders_scope_cta_for_founder` | Source-grep on ScanPage: testids + FOUNDER reference + target_not_in_scope wired |
| 12 | `test_scope_modal_does_not_default_to_wildcard` | `useState<ScopeType>('exact_url')` literal in source |
| 13 | `test_scope_modal_does_not_auto_start_scan` | Forbidden patterns absent from source |

**Sweep:** `13/13 new + 164/164 across full Sprint-7 + Sprint-8 + scope-related suite`. Frontend `tsc --noEmit` clean (exit 0).

---

## Files

```
backend/app/api/v1/security_authorized_scope.py   (+148 lines: ScopeAddRequest/Response, /add endpoint)
backend/tests/test_security_scope_add_from_scan.py (+393 lines, 13 tests)
frontend/src/pages/ScanPage.tsx                    (+150 lines: state + CTA + modal)
docs/Ultraview/PR_SCAN_ADD_TO_SCOPE_INLINE_CTA_REPORT.md  (this file)
```

No other files touched. No deletions. No renames.

---

## Operator flow

Tomorrow morning, with the fixed Daena running locally:

1. Open `/scan`. Type `https://dashboard.rapyd.net/login`. Click Start Scan.
2. Existing scope gate: 403, error reads `Target "https://dashboard.rapyd.net/login" is not in your authorized scope.`
3. **NEW** below the launcher: amber banner with "Add this target to Scan Scope" button.
4. Click the button. Modal opens with the target prefilled and "Exact URL" radio selected by default.
5. (If you actually own the target's testing rights) click Confirm. Toast: "Target added to Scan Scope."
6. Banner clears. Click Start Scan again — the scan proceeds because `dashboard.rapyd.net` is now in `exact_domains`.
7. Audit row landed: `goa_audit_events.action_type = "security.scope.added_from_scan"` for grep-reproducible compliance trail.

Non-founder operators see exactly what they saw before — the existing `ScopeStatusBanner` plus the existing "Add to /security/scope before scanning" hint. No CTA, no modal.

---

## What's next (NOT shipping in this PR)

- **`PR-CONN-FS-PROBE-AUTO-INSTALL-NOTICE`** — npx-not-on-PATH copy + first-probe-timeout retry hint.
- **`PR-CONN-CONSENT-EXECUTOR-DB-CUTOVER`** — Sprint-6 carryover.
- **Audit-log viewer plugin filter** — operator-facing read pane for `security.scope.*` events.

The Sprint-9 queue stays in priority order. PR-1 ships, then we pause for your manual verification before #2.

**Stop and report.**
