# PR-5 -- Authorized Security Program Scout

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 5 of 9
**Date:** 2026-05-06

## Goal

Daena researches public bug-bounty + vulnerability-disclosure
programs and produces a local, scope-respecting opportunity draft.
NO scan. NO exploitation. NO target test. The scout is metadata
only -- the draft tells the operator what's in scope and explicitly
forbids automated scanning until the program domains are added to
the operator's `authorized_scope`.

## What ships

`backend/app/services/research_flow.py` `_security_bounty_overlay()`:

When an opportunity is created with `opportunity_type="security_bounty"`,
the structured payload is overlaid with bounty-specific fields:

| Field | Source |
|---|---|
| `program_name` | LLM enrichment (null until enriched) |
| `allowed_domains` | LLM enrichment (empty list until enriched) |
| `out_of_scope_rules` | heuristic: "Out of scope" / "Not in scope" lines |
| `reward_range` | heuristic: nearest text around `$ / USD / EUR / bounty / rewards` |
| `report_url` | heuristic: first URL containing `/report / /submit / /disclos / /policy` |
| `identity_required` | true when text mentions HackerOne / Bugcrowd / Intigriti / YesWeHack / "register" / "create an account" / "must be a member" |
| `safe_next_action` | LITERAL guard text: "Register on the program's official portal manually before any test or scan. Add the allowed_domains to the operator's authorized_scope; Daena will refuse to scan a target that is not explicitly in scope." |
| `scope_check_status` | always `"not_yet_in_scope"` until the operator extends `authorized_scope` |

### What's explicitly absent

The contract test asserts NO key whose name starts with `scan /
exploit / test_target / auto_test` ever appears in the overlay.
The scout produces metadata, not actions. There is no code path in
this PR that:

- runs nmap / sqlmap / nuclei / BloodHound or any scanner
- drives a browser at the target
- sends an HTTP request to a domain mentioned in `allowed_domains`
- bypasses the `yellow_runtime_gate.AuthorizedScope` check

The `yellow_runtime_gate` (added in TICKET-HACKINGTOOL-YELLOW-RUNTIME)
remains the only gate on YELLOW-tier security tools. This PR feeds
metadata that the operator uses to *decide* what to add to the
authorized scope -- and only the operator can add it (founder
role), via the existing `PUT /security/authorized-scope`.

### CLAUDE.md Rule 2 upheld

The single canonical research flow grew an overlay function. No
parallel `BountyDraft` model. No new endpoint. The route is the
same `POST /research/opportunity` from PR-2.

## Tests

`backend/tests/test_security_program_scout.py` -- 8 tests:

```
TestOverlayShape::test_keys_locked
TestOverlayShape::test_no_scan_or_exploit_field
TestOverlayShape::test_scope_check_status_default
TestOverlayShape::test_safe_next_action_has_register_manually_guard
TestOverlayShape::test_identity_required_detected
TestOverlayShape::test_report_url_extracted_when_present
TestPayloadIntegration::test_security_bounty_payload_carries_overlay
```

Sanity regression: 37/37 pass on the combined Sprint-13 fast subset.

## Hard rules audit

| Rule | Status |
|---|---|
| No scanning | enforced -- no scan field, no scanner code path |
| No exploitation | enforced -- no exploit field |
| No target testing | enforced -- no test_target field; safe_next_action explicitly forbids it |
| No bypass of authorized_scope | enforced -- scope_check_status defaults to `not_yet_in_scope`; the YELLOW-runtime gate is unchanged |
| Public scope only | inherited from the existing scrape SSRF guard + URL safety |
| Audit per call | inherits the `plugin.skill_invocation` row from the underlying scrape |
| No duplicate model | reuses `ResearchDraft` + `structured_payload` JSONB |

## Files

```
modified:   backend/app/services/research_flow.py             (+90 lines: _security_bounty_overlay)
new:        backend/tests/test_security_program_scout.py      (170 lines, 8 tests)
new:        docs/Ultraview/PR_AUTHORIZED_SECURITY_PROGRAM_SCOUT_REPORT.md
```

## What this PR does NOT do

- Does NOT extract the program's `allowed_domains` automatically.
  Heuristic extraction would be unreliable; the field is left empty
  for the operator (or future LLM enrichment) to fill.
- Does NOT add the program domains to `authorized_scope`. That
  remains a manual founder action.
- Does NOT trigger ANY scan, even if the operator has the program
  in scope. Scanning is a separate workstream that lives outside
  this scout.

## Next: PR-6 -- Self-Healing Workstream Loop
