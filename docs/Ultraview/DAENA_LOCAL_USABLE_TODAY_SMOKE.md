# DAENA LOCAL USABLE TODAY -- Sprint-7 Smoke Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-7 of 7 / FINAL)

---

## TL;DR

**Yes, Masoud can use Daena tomorrow.**

- One command starts the whole stack: `scripts\start-daena-local.bat`.
- Daena answers "are you ok?" / "why 0 callable?" in chat with a
  deterministic snapshot.
- A first-run wizard turns the empty Connections page into a 5-step
  path to a callable plugin.
- Once Filesystem is callable, a hero block in the plugin drawer
  surfaces "Run find_files (read-only)" -- one click to the first
  real skill execution.
- Google OAuth setup is documented in-product so the founder/agent
  account split is unambiguous.
- The pre-existing Sprint-5 cross-test flake is fixed.

The remaining manual work is account-bound (you have to sign in to
Google as you, and as Daena). Everything else is mechanical.

---

## 1. Sprint commits (in order)

```
44be6b3  test: stabilize Phase 2 skill executor tenant fixture     [PR-6]
aa182d5  docs/ui: clarify Google account setup for Daena           [PR-5]
88849a5  fix: guide first read-only skill run from Connections     [PR-4]
b217e15  fix: add first callable plugin wizard                     [PR-3]
eda3792  canonicalization: let Daena answer self diagnostic questions  [PR-2]
f67c9b8  chore: add one-click local Daena startup smoke            [PR-1]
```

Pre-sprint baseline: `f863a3a` (Sprint-6 PR-8).

---

## 2. Tests

In-scope sweep (PRs 1-6 plus the Sprint-6 surface area each PR
touches):

```
$ .venv/Scripts/python.exe -m pytest \
    tests/test_local_startup_smoke.py \
    tests/test_self_diagnostic_advisor.py \
    tests/test_first_callable_wizard_contract.py \
    tests/test_first_skill_run_contract.py \
    tests/test_google_oauth_setup_guide_contract.py \
    tests/test_phase2_fixture_idempotency.py \
    tests/test_skill_executor_phase2.py \
    tests/test_skill_consent_api.py \
    tests/test_consent_db_persistence.py \
    tests/test_marketplace_diagnostic.py \
    tests/test_oauth_orphan_reclaim.py \
    tests/test_plugin_policy_overrides_api.py \
    tests/test_system_self_diagnostic.py \
    tests/test_marketplace_coming_soon_classifier.py -q

216 passed, 1 warning in 27.50s
```

**Per-PR test contributions:**

| PR | Test file | Tests |
|---|---|---:|
| PR-1 | test_local_startup_smoke.py | 8 |
| PR-2 | test_self_diagnostic_advisor.py | 53 |
| PR-3 | test_first_callable_wizard_contract.py | 6 |
| PR-4 | test_first_skill_run_contract.py | 8 |
| PR-5 | test_google_oauth_setup_guide_contract.py | 6 |
| PR-6 | test_phase2_fixture_idempotency.py | 1 |

PR-7 contributes no new tests (smoke-only).

**Sprint progression:** end of Sprint-6 = 235 in scope.
Sprint-7 adds 82 tests = **317 in scope** (Sprint-7 in-scope).
The extended cluster above includes Sprint-6 surfaces these PRs
touch, totaling 216 in the smoke run.

Pre-existing baseline failures (NOT caused by Sprint-7):
* `test_orchestrator_pipeline.py::test_full_pipeline_10_stages`
* `test_orchestrator_pipeline.py::test_pipeline_with_governance_slider`
Both fail on master baseline as well (confirmed via git stash in
PR-2). Out of scope.

Frontend:
```
$ npx tsc --noEmit
EXIT=0
```

---

## 3. Exact command to start Daena tomorrow

```cmd
D:\Ideas\Daena> scripts\start-daena-local.bat
```

This script (PR-1):

1. Cleans stale Daena dev processes (path-scoped; never kills
   unrelated python.exe / node.exe).
2. Opens a "Daena Backend" console window and starts uvicorn.
3. Opens a "Daena Frontend" console window and starts Vite.
4. Polls `/health` and `127.0.0.1:5173` for up to ~30s each.
5. Prints the 6 URLs you need:
   - Backend: http://127.0.0.1:8000
   - Health: http://127.0.0.1:8000/health
   - Self-diagnostic: http://127.0.0.1:8000/api/v1/system/self-diagnostic
   - OpenAPI: http://127.0.0.1:8000/docs
   - Frontend: http://127.0.0.1:5173
   - Connections: http://127.0.0.1:5173/connections

If a service doesn't come up, the script prints the exact recovery
command (cleanup, pip install, alembic upgrade head, npm install).

---

## 4. Exact first workflow Masoud should run

Goal: take 0 callable -> 1 callable -> 1 successful read-only skill
in one session.

1. **Start the stack** -- `scripts\start-daena-local.bat`.
2. **Open Connections** -- http://127.0.0.1:5173/connections.
3. **Read the wizard** at top of the Overview tab: "Make your
   first plugin callable" (PR-3).
4. **Copy the npx command** the wizard surfaces. Run it once in a
   shell to confirm `@modelcontextprotocol/server-filesystem`
   downloads + starts cleanly (Daena does NOT auto-run it).
5. **Click "Continue in MCP Store"** in the wizard. Find Filesystem.
6. **Click Install** -- Daena writes the entry into one of your
   CLI configs (Claude Desktop / Claude Code / Codex / Gemini)
   atomically.
7. **Click Probe** on the resulting V2 row. Lifecycle flips to
   `callable`; the Overview's "0 of N callable" copy updates and
   the wizard auto-hides.
8. **Open the Filesystem plugin's drawer**. The new emerald hero
   block (PR-4) shows "Try your first Daena skill -- Run
   find_files (read-only)".
9. **Click Run find_files**. The existing Phase 2 confirmation
   modal fires with the no-writes/no-deletes/no-external-network
   statement.
10. **Type a folder path** (the modal does NOT auto-fill). Click
    Run. Phase 2 returns a planned preview.
11. **Ask Daena in chat**: "are you ok?". The new self-diagnostic
    short-circuit (PR-2) answers from the deterministic snapshot,
    ending with the safety boundary.

You're now using Daena.

---

## 5. What still requires manual login / account setup

**In Daena's control:** local stack, callable plugins, read-only
skills, self-diagnostic awareness. All shipped in this sprint.

**Manual (you must do these awake):**

| Task | Why |
|---|---|
| Configure the Google OAuth client in `Settings -> OAuth Clients` | Daena needs YOUR `client_id` + `client_secret`; she never asks for them outside Settings. |
| Sign in to Google as `masoud.masoori@mas-ai.co` (founder) | Per PR-5 guide. Connect Gmail / Calendar / Drive. |
| Sign in to Google as `daena@mas-ai.co` (agent voice) | Second OAuth run. Gives Daena her own seat for company-facing actions. |
| Connect any other paid-API providers | API keys land in `Settings -> Provider Keys` (already wired pre-sprint). |
| Run `alembic upgrade head` on production deploy | Sprint-6 migrations 010 / 011 / 012 still need to land on Cloud Run when you deploy. |
| Approve any Tier 3+ governance prompts | The approval queue stays interactive; Daena never auto-approves. |

---

## 6. Phase 3 writes status

**STILL BLOCKED.** Verified:

```
Phase 2 allowlist: 19 entries, 0 non-read-only
Phase 3 BLOCKED
```

All four floors intact:

1. `PHASE2_ALLOWLIST` has zero `read_only=False` entries.
2. Phase 2 read-only defense at Step 3 of the executor.
3. Consent gate (DB grants from Sprint-6 PR-5 don't change
   semantics, only durability).
4. Governance preset DENY recommendations + per-tenant overrides
   (Sprint-6 PR-6) cannot weaken Phase 2.

Sprint-7 added zero new entries to the allowlist. The new code paths
(self-diagnostic chat, first-run wizard, hero block, Google guide,
Phase 2 fixture fix) are all read-only or test-only.

---

## 7. New HTTP surface in Sprint-7

None. Sprint-7 is purely UI / chat-routing / test-stability.

Routes carrying over from Sprint-6 (verified live in OpenAPI today):

```
GET  /api/v1/connections/v2/marketplace/diagnostic
GET  /api/v1/connections/v2/governance/plugin-policy-overrides
PUT  /api/v1/connections/v2/governance/plugin-policy-overrides
GET  /api/v1/system/self-diagnostic
```

Backend `/health` returns 200; `/api/v1/system/self-diagnostic`
returns 401 without auth (gate intact).

---

## 8. Hard stops encountered

**NONE.** All 14 hard stops in the Sprint-7 brief honored:

1. No production deploy / Cloud Run / GCP write / DNS / cloud
   secret change.
2. No `USE_CONNECTION_REGISTRY_V2=true` flip.
3. No `vault --apply`.
4. No secret read / print / grep / log / commit.
5. No external email / DM / webhook / Slack / GitHub comment / Gmail send.
6. No payment / refund / subscription / financial write.
7. No browser automation on external websites.
8. No V1 / legacy file deletion.
9. No npm / pip / docker install outside the existing safe MCP
   install flow.
10. No test failure attributable to Sprint-7 (the 2 pre-existing
    pipeline failures fail on master too).
11. No unexpected secret-risk file in `git status`.
12. No action requiring real credentials while Masoud is asleep.
13. No Phase 3 write enablement.
14. No architectural uncertainty path taken (every PR has a clear
    primary path documented in its report).

---

## 9. Recommendations for Sprint-8

Quality-of-life and operational depth, in priority order:

1. **`PR-DAENA-SELF-DIAGNOSTIC-AUTO-FIX-PROPOSALS`** -- when overall
   is `blocked`, surface a "propose fix" CTA that opens an approval
   queue ticket. Operator approves; Daena applies a single safe
   local fix, tests, reports. Diagnose -> Propose -> Approve ->
   Apply ladder.
2. **`PR-CONN-CONSENT-EXECUTOR-DB-CUTOVER`** (carries over from
   Sprint-6 recommendations) -- flip executor read path to
   DBConsentStore so consent grants survive process restart.
3. **`PR-CONN-POLICY-OVERRIDE-IN-CONSENT-GATE`** -- plumb the merged
   per-tenant policy tier into `check_consent_or_request`.
4. **`PR-CONN-FIRST-RUN-MORE-RECIPES`** -- extend `FIRST_RUN_SKILLS`
   to other easy plugins (`mcp-time`, `mcp-everything-search`).
5. **`PR-CONN-GOOGLE-ACCOUNT-PICKER`** -- once both Google rows
   exist, surface a per-skill "act as" picker.
6. **`PR-CONN-WIZARD-INTEGRATED-INSTALL`** -- "Continue in MCP Store"
   currently switches tabs; could open the install drawer
   pre-selected to Filesystem.
7. **Phase 3 writes** -- gated behind 1-3 above. Separate sprint.

---

## 10. Honest closing

The Sprint-7 brief said "80% local usability / 10% UI/UX comparison
/ 10% architecture cleanup." The PR shape matches:

* Local usability: PR-1, PR-2, PR-3, PR-4, PR-5 (5 of 7 PRs).
* Architecture cleanup: PR-6 (1 of 7 PRs).
* Comparison: applied as a quality gate per-PR (e.g. the FirstCallable
  wizard checked itself against Claude Desktop's plugin install
  pattern at design time -- friendlier than a wall of catalog cards
  but doesn't try to imitate the install-everything style of
  Paperclip's `npx onboard`). No deep comparison sprint.

Daena is now usable today on the laptop. Tomorrow morning's sequence
is: start, ask, install, probe, run. Five clicks from black screen
to first read-only skill output.

Stop and report.
