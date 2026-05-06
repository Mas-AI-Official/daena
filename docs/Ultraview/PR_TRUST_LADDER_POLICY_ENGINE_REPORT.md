# PR-1 -- Trust Ladder Policy Engine

**Sprint:** DAENA-SPRINT-18-TRUST-LADDER-AND-ROUTINE-AUTONOMY
**PR:** 1 of 6
**Date:** 2026-05-06

## Goal

Sprint-14 PR-5 shipped a record-only ladder. This PR layers POLICY
on top: which (tool, template_class) pairs are eligible to
graduate, which are forbidden forever, what tier the operator has
granted, and what auto-approval decision the dispatcher should
reach for any incoming request.

The trust ladder is now a real policy surface, not just a counter.

## What ships

`backend/app/services/trust_policy.py` (new):

* `TrustTier` enum: `none | suggest_only | auto_approve_low_risk |
  auto_execute_low_risk_local`. Sprint-18 unlocks tiers 0..2 only;
  tier 3 (`auto_execute_low_risk_local`) is RESERVED + UNREACHABLE.
* `DispatchInitiator` enum: `operator | scheduler | self_healing |
  delegated`.
* `TRUST_ELIGIBLE_TOOLS` (frozen, locked):
  `gmail.create_draft`, `calendar.create_tentative_event_without_invites`,
  `local.file_change_proposal`.
* `TRUST_FORBIDDEN_TOOLS` (frozen, locked):
  `gmail.send_existing_draft`, `local.file_change_proposal.apply`,
  `local.git_commit_approved_patch`.
* `compute_template_class(tool_id, payload)` -- stable identifier
  for "this kind of action". Trust graduates per-(tool_id,
  template_class), NOT per-tool. So 5 approvals of cold-outreach
  drafts to gmail.com graduates only that class -- a draft to a
  different domain still asks.
* `get_policy(...)` -- always returns a `TrustPolicyEntry` (default
  tier NONE for unknown).
* `set_max_auto_tier(...)` -- founder-only mutation requiring:
    1. `is_founder=True`
    2. `confirmation_phrase` matches `expected_confirmation_phrase`
    3. tool not in `TRUST_FORBIDDEN_TOOLS`
    4. tool in `TRUST_ELIGIBLE_TOOLS`
    5. tier != reserved `AUTO_EXECUTE_LOW_RISK_LOCAL`
    6. ladder rejection_count == 0 (or tier being set is NONE)
* `should_auto_approve(...)` -- pure decision function, NEVER
  raises, returns `AutoApprovalDecision` with stable reason code.

`backend/.gitignore` (modified): adds `.trust_policy.json` and
`.routine_autonomy.json`.

## The six walls of `should_auto_approve`

```
1. tool_id NOT in TRUST_FORBIDDEN_TOOLS
2. initiator == OPERATOR
3. tool_id in TRUST_ELIGIBLE_TOOLS
4. policy.max_auto_tier == AUTO_APPROVE_LOW_RISK
5. trust_ladder.rejection_count == 0
6. trust_ladder.approvals_count >= 5
```

Auto-approval fires ONLY if all six pass. First refusal wins;
reason code is stable (e.g. `tool_forbidden_from_graduation`,
`non_operator_initiator_never_graduates`,
`rejections_reset_trust_to_none`,
`approvals_count_3_below_threshold_5`).

## Mythos design choices

**Initiator-aware trust.** Wall #2 is the load-bearing one. Sprint-18
is only safe because graduation fires for OPERATOR-initiated
dispatches. Scheduler / self-healing / delegated dispatches always
pay full approval freight, regardless of tier. This mirrors the
Asset Shield initiator-aware tier collapse from v3.7.0.

**Founder-only tier raise via confirmation phrase.** Daena CANNOT
raise her own tier. The confirmation phrase is a static template
(not LLM output) -- prompt injection cannot bypass because the
expected string is computed from the (tool_id, tier) tuple.

**Rejection signal is permanent, not a sliding window.** Sprint-18
treats rejection_count > 0 as "trust collapsed; manual approve
required" forever. Future sprints could add a "reset rejections
after N successful approvals" path, but that's a deliberate
unlock, not a default. Wall #5 enforces this even if the founder
left the tier raised.

**Template class hashing.** `compute_template_class` is narrow on
purpose. For Gmail: domain + first 4 alpha words of subject. For
calendar: calendar_id + duration bucket. For file proposals: top
level dir + change_type. A draft to gmail.com graduates a
different class from a draft to example.com -- so trust earned in
one channel cannot leak into another.

## Refusal codes (stable)

```
tool_forbidden_from_graduation
non_operator_initiator_never_graduates
tool_not_in_eligible_set
max_auto_tier_is_none
max_auto_tier_is_suggest_only
rejections_reset_trust_to_none
approvals_count_<n>_below_threshold_<m>
trust_graduated                          (the sole success code)
```

## Locked invariants

| Invariant | Where |
|---|---|
| Forbidden tools cannot graduate even with forged tier | `TestShouldAutoApproveWalls::test_forbidden_tool_never_graduates` |
| Non-operator initiators cannot graduate | `test_non_operator_initiator_never_graduates` |
| Default tier is NONE for unknown templates | `TestNoAutoEscalation::test_default_get_policy_returns_none_tier` |
| Approvals < threshold refuses | `test_approvals_below_threshold_refuses` |
| Rejection arriving after grant collapses graduation | `test_rejection_arriving_after_tier_grant_blocks_graduation` |
| All 6 walls pass returns `trust_graduated` | `test_all_walls_pass_returns_true` |
| `set_max_auto_tier` non-founder refused | `TestSetTier::test_non_founder_refused` |
| `set_max_auto_tier` confirmation phrase mismatch refused | `test_confirmation_phrase_mismatch_refused` |
| `set_max_auto_tier` forbidden tool refused | `test_forbidden_tool_refused` |
| `set_max_auto_tier` reserved tier refused | `test_reserved_tier_refused` |
| `set_max_auto_tier` rejection forces NONE | `test_rejections_force_none` |
| `set_max_auto_tier` lower-to-NONE always allowed | `test_can_lower_to_none_even_with_rejections` |
| Module exposes no auto_grant / self_promote callables | `test_module_has_no_auto_escalate_callable` |
| Persistence file is gitignored | `TestGitignored::test_persistence_file_in_gitignore` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No submit / post / pay | applied (forbidden tools list does not include any submit/post/pay tool, none exists) |
| No file delete | applied |
| No file create on disk | applied (this PR creates only Python source files) |
| No multi-file apply | applied |
| No remote push from this PR | applied |
| No trust graduation for `gmail.send_existing_draft` | enforced -- in TRUST_FORBIDDEN_TOOLS, test pins |
| No trust graduation for `local.file_change_proposal.apply` | enforced -- in TRUST_FORBIDDEN_TOOLS, test pins |
| No trust graduation for `local.git_commit_approved_patch` | enforced -- in TRUST_FORBIDDEN_TOOLS, test pins |
| No auto-escalation without explicit trust policy | enforced -- `set_max_auto_tier` is the only mutator and it requires `is_founder=True` + confirmation phrase |
| Daena cannot raise her own trust tier | enforced -- `is_founder` is a parameter, the API endpoint (PR-2) sets it from JWT, and tool dispatches NEVER call this function |

## Tests

```
backend/tests/test_trust_policy.py    25 tests
```

25/25 pass. No external HTTP, no DB, no live LLM.

## Files

```
new:        backend/app/services/trust_policy.py
new:        backend/tests/test_trust_policy.py
modified:   backend/.gitignore
new:        docs/Ultraview/PR_TRUST_LADDER_POLICY_ENGINE_REPORT.md
```

## Next: PR-2 -- Trust Graduation UI
