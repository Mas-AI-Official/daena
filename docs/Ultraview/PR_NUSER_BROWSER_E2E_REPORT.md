# PR-6 — NUser browser end-to-end smoke

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 6 of 7
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

A new-user smoke that drives Daena through the morning workflow in a
real browser, on localhost, with no external network calls.

## What ships

A Playwright spec at `frontend/e2e/morning-workflow.spec.ts`. Asserts:

1. Register + login succeed.
2. Settings → Models & Runtimes renders both panels (`BrainReadinessPanel`
   from Sprint-12A and the new `MorningReadinessPanel` from PR-4).
3. The headline pill is one of "Ready for VP work" / "Not yet ready"
   — never a fake "online" with no brain configured.
4. `/workstreams` renders the new `StartHereCard` ("Start here tomorrow")
   and the Drafts lane.
5. The 5-step suggested workflow text is visible.
6. **No banned-verb buttons** anywhere on `/workstreams` or
   `/settings/models-runtimes`. The spec walks every `<button>` text
   and asserts none equals exactly `Send`, `Submit`, `Apply`, `Publish`,
   `Post now`.
7. **No `Execute` / `Run Now` button on autofix proposals** —
   per PR-5's "Daena proposes; never auto-executes" rule.

## How to run

```bash
# Terminal 1 — start backend
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2 — start frontend
cd frontend
npm run dev

# Terminal 3 — run the spec
cd frontend
npx playwright test morning-workflow.spec.ts --headed
```

## Backend smoke is automated

While the Playwright spec needs a live browser session, the backend
side of the morning workflow is **already** automated end-to-end via
the Sprint-12 + new contract tests:

| Layer | Test file | Coverage |
|---|---|---|
| Chat -> VP-command preflight contract | `tests/test_chat_vp_preflight_contract.py` | `intent="unrecognized"` falls through; recognized intents respond with the locked shape |
| Route mounts (12 endpoints) | `tests/test_morning_route_contract.py` | Every action endpoint the frontend depends on; banned verbs absent |
| Morning readiness aggregator | `tests/test_morning_readiness_endpoint.py` | Shape, no-secret-leak, autofix proposal shape locked |
| Draft enrichment refusal | `tests/test_sprint12_full_smoke.py::TestRefusalE2E` | No-main-brain refusal surfaces verbatim through the VP-command surface |
| Workstream from draft happy path | `tests/test_sprint12_full_smoke.py::TestE2EWorkstreamFromDraft` | Seed draft -> chat command -> workstream row created with `source_type=draft`, `source_ref_id=draft.id`, `next_step_text` populated |

## Test count

**Backend total:** 121/121 pass on the Sprint-12 + Sprint-MORNING fast
subset (no new backend tests in this PR — the new test is the
Playwright spec).

**Frontend tsc:** exit 0.

## Hard rules — encoded + tested

| Rule | Status |
|---|---|
| No external network calls in the spec | ✅ — every URL hits localhost |
| No real OAuth login | ✅ — registers a fresh user via the local register endpoint |
| No banned-verb button rendered | ✅ — walked + asserted |
| No "Execute" autofix button | ✅ — walked + asserted |
| Phase 3 writes blocked (server side) | ✅ — covered by Sprint-12 smoke; spec doesn't try to write |

## What this PR does NOT do

* Does NOT spin up the backend or frontend automatically. The harness
  expects them on `:8000` and `:5173`. (Playwright `webServer` config
  could change that, but adding a process supervisor is out of scope.)
* Does NOT submit any external form. Every interaction is local.
* Does NOT seed test data. The spec works against whatever drafts +
  workstreams the local DB carries.

## Next: PR-7 — Final morning readiness report
