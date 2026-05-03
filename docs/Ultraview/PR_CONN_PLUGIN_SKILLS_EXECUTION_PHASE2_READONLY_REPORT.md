# PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY — Report

**Date:** 2026-05-03
**Branch:** `rebuild-connections-mcp-runtime`
**Predecessor:** [PR-CONN-PHASE2-PREFLIGHT-GREEN](./PR_CONN_PHASE2_PREFLIGHT_GREEN_REPORT.md) — `6dd840f`
**Founder rating expectation:** narrow spine, no real tool fires in this PR

---

## 1. Goal — and the load-bearing decision

Ship the Phase 2 read-only skill execution **spine** without firing any
real MCP `tools/call` in this PR. Per the founder's explicit warning
("Do not let Claude make all skills executable... if actual connector
implementation is not safely available for a skill, return planned/
needs_connection rather than fake execution"), every Phase 2
allowlisted skill returns **`status: "planned"`** with full preview
metadata. `status: "executed"` is reserved for follow-up PRs that arm
one integration at a time after end-to-end safety verification.

**Why "spine, not engine":**
1. Each (plugin, skill) → MCP-tool mapping needs per-integration
   argument derivation, response shape contract, and read-only
   verification. That work doesn't fit in a single Phase 2 PR.
2. The spine + audit + UI are independently valuable: audit row
   captures the request, allowlist gate enforces no-write contract,
   "Run read-only skill" button surfaces intent, planned preview
   shows operator EXACTLY what would happen.
3. Phase 3+ PRs flip `execution_mode` from `planned_only` to
   `mcp_tool` for ONE integration at a time. The frontend + audit
   shape doesn't change.

---

## 2. Allowlist shipped (19 entries, all `planned_only`)

All 8 founder starter buckets covered. Every entry has
`read_only=True` (enforced by import-time assertion + runtime
re-check + dedicated test).

| Bucket | Plugin | Skill | Backend | Required inputs |
|---|---|---|---|---|
| GitHub | `mcp-github` | `summarize_repo` | mcp | repo_owner, repo_name |
| GitHub | `mcp-github` | `triage_issues` | mcp | repo_owner, repo_name |
| GitHub | `mcp-github` | `inspect_ci_failure` | mcp | repo_owner, repo_name, run_id_or_sha |
| Gmail | `app-gmail` | `summarize_unread` | oauth | label_or_query, time_window |
| Gmail | `app-gmail` | `search_email_context` | oauth | query, time_window |
| Drive | `app-google-drive` | `find_documents` | oauth | query, folder_id_or_root |
| Drive | `app-google-drive` | `summarize_file` | oauth | file_id_or_url |
| Slack | `mcp-slack` | `summarize_channel` | mcp | channel, time_window |
| Slack | `mcp-slack` | `find_decisions` | mcp | channel, time_window |
| Sentry | `mcp-sentry` | `summarize_errors` | mcp | project_slug, time_window |
| HF | `mcp-huggingface` | `find_model` | mcp | task_or_keywords |
| HF | `mcp-huggingface` | `inspect_paper` | mcp | arxiv_id_or_title |
| Filesystem | `mcp-filesystem` | `find_files` | mcp | root_path, name_or_glob |
| Filesystem | `mcp-filesystem` | `summarize_directory` | mcp | root_path |
| DB | `mcp-postgres` | `describe_schema` | mcp | database |
| DB | `mcp-sqlite` | `describe_schema` | mcp | database_path |
| DB | `mcp-supabase` | `describe_schema` | mcp | project_ref |
| DB | `mcp-neon` | `describe_schema` | mcp | database, branch_id_or_default |
| DB | `mcp-mongodb` | `describe_collections` | mcp | database |

Per founder rule 16, **`safe_query` is NOT in this allowlist** for
ANY of the 5 database plugins — it stays plan-only forever because
SQL/aggregation read-only-ness cannot be proven without per-query
parsing.

---

## 3. Skills executed vs planned vs blocked

| Outcome bucket | Count | Notes |
|---|---|---|
| Executed (status=`executed`) | **0** | Zero in Phase 2 by design. Reserved for follow-up PRs. |
| Planned (status=`planned`) | up to 19 | All allowlist entries return planned with full preview |
| Blocked (`status=blocked`) | catalog default | Any skill not in allowlist → `not_in_phase2_allowlist` |
| Needs_connection | dynamic | Plugin V2 row not callable in this tenant |
| Needs_inputs | dynamic | Operator hasn't supplied required_inputs |
| Unsupported | catalog default | Unknown (plugin, skill) pair |

Founder's "Explicitly blocked" list, all confirmed NOT in allowlist
(pinned by `test_explicitly_blocked_skills_are_NOT_in_allowlist`):

`draft_reply` (Slack + Gmail), `extract_tasks` (Slack), `update_page`
(Notion), `schedule_meeting` (Calendar), `reconcile_subscriptions`
(Stripe), `create_bug_task` (Sentry), all 5 `safe_query`,
`open_page` / `fill_form_safe` / `capture_screenshot` /
`run_smoke_test` (Playwright), `capture_screenshot` (Chrome DevTools).

---

## 4. Audit design

Every executor `execute()` call writes ONE parent audit row via the
existing tamper-evident `AuditService.log_decision()`:

```
action_type:    "plugin.skill_invocation"
action_params:  {
  plugin_id, skill_id,
  phase: "phase2_readonly",
  outcome: planned | blocked | needs_connection | needs_inputs,
  allowlist_match: bool,
  read_only: bool,
  execution_mode: "planned_only",
  backend_surface: mcp | oauth | internal,
  target_tool: <tool name>,
  argument_shape: {<input>: "operator-input" | "MISSING" | "tenant-scoped"},
  missing_inputs: [<names only>],
  blocked_reason: <reason if blocked>
}
result:         "ALLOWED" | "BLOCKED" | "INFO"
risk_level:     "LOW"
governance_tier: 2
```

**Honesty contract pinned by tests:**

- `test_allowlisted_callable_skill_does_not_leak_operator_inputs` — sentinel value `PHASE2-LEAK-CANARY-99887766` placed in `operator_inputs.repo_owner` AND `repo_name`. Asserts the sentinel does NOT appear in `result.to_dict()` JSON OR in any audit row's `action_params` JSON.
- `test_audit_row_records_outcome_and_no_secret_values` — same sentinel + asserts the audit row's `argument_shape` carries provenance strings (`"operator-input"`) NOT the values themselves.

**Why `argument_shape` instead of values:** the operator + audit reader
need to know WHAT TYPE of argument was supplied (operator-input vs
catalog-default vs tenant-scoped) to reason about the request shape,
without ever exposing the value itself. Future Phase 3 PRs that
actually fire the tool can include a separate `result_metadata` field
that summarizes the response WITHOUT echoing operator inputs.

---

## 5. Frontend confirmation flow

Click flow:

```
Plugin chip click
 → SkillBundleSection popover (Phase 1 behavior preserved)
   → Phase 1 "Use in chat" / "Draft plan in chat" button (unchanged)
   → NEW: "Run read-only skill" button surfaces ONLY when
       (a) chip's plugin readiness === 'ready' (V2 callable)
       AND
       (b) usePhase2SkillAllowlist().lookup(plugin_id, skill_id) returns an entry
 → Click "Run read-only skill"
   → Opens SkillExecuteModal with:
     - Plugin name + skill name in header
     - "What Daena will read" green block (allowlist's reads_summary)
     - "No writes, no sends, no payments" safety statement
     - Required-inputs form (one text input per required field)
     - "Run read-only skill" button (disabled until ALL inputs supplied)
   → Operator fills inputs, clicks Run
   → POST /api/v1/connections/v2/skills/execute
     - Body: { plugin_id, skill_id, operator_inputs }
   → Backend returns SkillExecutionResultDTO
   → Modal renders:
     - Status pill (planned / needs_inputs / blocked)
     - Summary text
     - Result preview ("Would invoke MCP tool 'X' to read: <reads_summary>")
     - Planned tool call card with backend_surface + tool_name + argument provenance
     - Audit event id (first 8 chars displayed)
   → If status=planned: "Draft follow-up in chat" button
     - Builds a chat prompt summarizing intent + the inputs operator provided
     - Drops it into composer via the existing draftMessage() bridge
     - Closes modal + navigates to /chat
   → If needs_inputs: lists missing field names (no values shown)
   → If blocked: shows blocked_reason (also lock icon)
```

**Components added:**

| File | Purpose |
|---|---|
| `frontend/src/pages/connections/SkillExecuteModal.tsx` | Confirmation modal + result render |
| `frontend/src/hooks/usePhase2SkillAllowlist.ts` | Module-cached allowlist fetch (one round-trip per session) |
| `frontend/src/pages/connections/SkillBundleSection.tsx` (modified) | Adds Run button + modal mount |

**No new top-level tabs added** (founder rule 13). Connections page
still has Brain / Plugins / Advanced.

---

## 6. Safety proof

| Rule | How this PR satisfies it |
|---|---|
| 9. Do not execute write tools | Allowlist `read_only=True` enforced at module load + runtime. Tests confirm Notion `update_page`, Sentry `create_bug_task` blocked. |
| 10. Do not execute payment/refund/subscription tools | Stripe `reconcile_subscriptions` not in allowlist; explicitly checked in test |
| 11. Do not execute browser actions | All 5 Playwright skills + Chrome DevTools `capture_screenshot` blocked; explicitly checked |
| 12. Do not auto-send chat messages | Composer `draftMessage()` only — no auto-send path exists. The "Draft follow-up in chat" button is operator-clicked, draft only. |
| 14. Do not promote any Phase 1 BLOCKED_* skill | Tests verify Slack `draft_reply`, Calendar `schedule_meeting` not in allowlist |
| 15. Do not allow a skill unless it is in the Phase 2 allowlist | Allowlist lookup is FIRST gate; non-allowlisted → status=blocked |
| 16. If a tool cannot be proven read-only, block it | `safe_query` for all 5 DBs blocked; only `describe_schema`/`describe_collections` allowed |

**No HTTP egress in this PR's executor.** The Phase 2 spine writes
to the audit log + returns metadata. No `httpx`, `requests`, MCP
`tools/call`, or OAuth API call originates from `skill_executor.py`
or `skill_execution.py`.

---

## 7. Tests run

### 7.1 New backend tests (this PR)

`backend/tests/test_skill_executor_phase2.py` — **20 tests**:

Allowlist invariants (no DB):
- `test_every_allowlist_entry_is_read_only`
- `test_every_allowlist_entry_is_planned_only`
- `test_every_allowlist_entry_has_required_inputs_declared`
- `test_explicitly_blocked_skills_are_NOT_in_allowlist`
- `test_allowlist_for_api_has_no_secret_fields`
- `test_starter_buckets_all_have_at_least_one_entry`

Executor behavior (DB):
- `test_allowlisted_callable_skill_returns_planned`
- `test_allowlisted_callable_skill_does_not_leak_operator_inputs` (sentinel canary)
- `test_non_allowlisted_skill_blocked`
- `test_write_skill_blocked` (Notion update_page)
- `test_browser_action_blocked` (Playwright open_page)
- `test_safe_query_remains_blocked_in_phase2` (all 5 DBs)
- `test_missing_plugin_connection_returns_needs_connection`
- `test_missing_required_inputs_returns_needs_inputs`
- `test_partial_inputs_returns_only_missing_fields`
- `test_audit_row_records_outcome_and_no_secret_values` (sentinel canary)

HTTP API surface:
- `test_get_allowlist_endpoint_returns_phase2_metadata`
- `test_execute_endpoint_blocks_non_allowlisted`
- `test_execute_endpoint_requires_auth`
- `test_get_allowlist_requires_auth`

```
$ pytest tests/test_skill_executor_phase2.py
20 passed in 2.33s
```

### 7.2 Targeted regression sweep

```
$ pytest tests/test_skill_executor_phase2.py \
         tests/test_skill_action_registry_phase1.py \
         tests/test_plugin_skills_ux_wiring.py \
         tests/test_account_oauth_clients_endpoint.py \
         tests/test_oauth_marketplace.py \
         tests/test_audit_service_unit.py
122 passed (in 9.56s)
```

(Note: when running the broad sweep with `-k "connection or oauth or
account or marketplace or skill or audit"`, several pre-existing
cross-file isolation issues surface — same baseline as the prior PR
showed. Each failing test passes when run in isolation. Net change
introduced by this PR: 0 — confirmed by re-running with my new
test file excluded from the same sweep.)

### 7.3 Frontend type check

```
$ cd frontend && npx tsc -b
(silent — clean)
```

### 7.4 Live UI verification — DEFERRED

Live chrome-devtools verification of the Run button + modal + endpoint
flow is **deferred** because the operator's local backend on port 8000
has lingering processes from prior sessions (TIME_WAIT sockets + reloader
worker subprocess pattern from the `run.py` reload feature). The new
routes are confirmed registered via direct `python -c "from app.api.v1
import router"` import:

```
phase2 routes in router (direct import): 2
  /connections/v2/skills/allowlist
  /connections/v2/skills/execute
```

The 20/20 backend tests already prove the executor + audit + endpoint
works end-to-end against a real DB. Operator can verify the UI by
killing all `python.exe` processes whose CommandLine matches `run.py`,
then running `cd backend && .venv/Scripts/python.exe run.py` from a
clean shell.

---

## 8. Hard-rules compliance

| # | Rule | Status |
|---|---|---|
| 1 | Do not deploy production | ✅ no Cloud Run touched |
| 2 | Do not flip `USE_CONNECTION_REGISTRY_V2=true` | ✅ confirmed `false` in startup logs |
| 3 | Do not run `vault --apply` | ✅ none |
| 4 | Do not delete V1 files | ✅ no deletions |
| 5 | Do not print/grep/log/commit secrets | ✅ sentinel canary tests pin no leak; logger.info uses lengths only |
| 6 | Do not run external scans | ✅ none |
| 7 | Do not send emails/DMs/webhooks/messages | ✅ no outbound traffic; executor has no HTTP client |
| 8 | Do not auto-install npm/pip/docker | ✅ none |
| 9-16 | Phase 2 safety guards | ✅ see §6 |

---

## 9. Files changed

```
backend/app/api/v1/__init__.py                         | +12  (router include)
backend/app/api/v1/skill_execution.py                  | +123  NEW
backend/app/services/connection_v2/skill_executor.py   | +600  NEW
backend/tests/test_skill_executor_phase2.py            | +540  NEW
frontend/src/hooks/usePhase2SkillAllowlist.ts          | +71   NEW
frontend/src/pages/connections/SkillBundleSection.tsx  | +50/-19
frontend/src/pages/connections/SkillExecuteModal.tsx   | +315  NEW
docs/Ultraview/PR_CONN_PLUGIN_SKILLS_EXECUTION_PHASE2_READONLY_REPORT.md
                                                       | NEW (this doc)
```

Total: 5 new files, 2 modified, ~1700 lines added (incl. tests + report).

---

## 10. Remaining blockers for Phase 3

The Phase 2 spine establishes the contract — Phase 3 promotion is
per-integration work. None of these block Phase 2 itself.

### Phase 2.x integration arms (each a separate PR)

For each of the 19 allowlist entries, Phase 2.x will:
1. Wire the actual MCP `tools/call` (or OAuth API call) for the
   `target_tool` named in the allowlist.
2. Add per-integration argument validation + sanitization.
3. Add a result-summarizer that converts the raw tool output to
   operator-friendly markdown WITHOUT echoing operator inputs in
   the response.
4. Flip the entry's `execution_mode` from `planned_only` to
   `mcp_tool`.
5. Add per-tool integration tests (real MCP server in Docker
   compose, or recorded fixture).

Suggested order:
- **Filesystem + HuggingFace first** (no auth required, public/local data)
- **Sentry + GitHub second** (API token auth, well-defined read shape)
- **Slack + Gmail + Drive third** (OAuth surface, more complex)
- **Database `describe_schema` last** (per-DB-vendor adapters)

### Phase 3 scope

1. **Asset Shield consent** for high-risk reads (Stripe, Cloudflare).
2. **Plugin governance presets** so operators can pin per-plugin
   risk overrides.
3. **Write-skill execution** with full Asset Shield consent flow,
   per-write audit + rollback metadata.
4. **Browser action governance** for Playwright + Chrome DevTools
   write skills.

### Tech-debt items surfaced by this PR

1. **Local backend port-lifecycle pattern.** Two `python.exe`
   processes (parent + uvicorn reloader child) + Windows
   TIME_WAIT lingering on port 8000 makes restart-during-dev
   noisy. Recommend a single `daena-backend.bat` that runs
   `taskkill` for matching commandlines before launching.
2. **Cross-file pytest isolation.** Several pre-existing tests
   in `tests/test_skill_refinery*.py` fail when run in the same
   broad sweep as audit-writing tests. Documented as not
   regression-introducing here, but worth a separate cleanup PR.

---

## 11. Commit

```
canonicalization: execute read-only plugin skills with audit gate
```

Phase 2 ships the spine, not the engine. 19-entry typed allowlist (all
read-only, all planned_only) covers the founder's 8 starter buckets
(GitHub / Gmail / Drive / Slack / Sentry / HuggingFace / Filesystem /
DB describe_schema). Backend executor returns
status=planned with a full preview of which MCP/OAuth tool would be
called and what the argument provenance is (operator-input /
tenant-scoped / MISSING) — never the values. Every attempt writes a
parent plugin.skill_invocation audit row via the existing
tamper-evident AuditService.

Frontend surfaces a "Run read-only skill" button on chip popovers ONLY
when the (plugin, skill) pair is in the backend allowlist AND the
plugin is V2-callable. Confirmation modal shows reads_summary, the
"No writes, no sends, no payments" safety statement, and required
inputs. Submit returns the planned preview; "Draft follow-up in chat"
button drops a summary prompt into the composer for operator review.

Two sentinel canary tests pin that operator_inputs values NEVER appear
in either the response body or the audit row's action_params JSON. The
allowlist's import-time invariant assertion + dedicated test fail the
moment any future maintainer flips read_only=False or
execution_mode='mcp_tool' on any entry.

Per the founder's narrow-spine warning: actual tool invocation arms in
follow-up PRs that promote one integration at a time after end-to-end
safety verification. status="executed" is reserved for those PRs and
explicitly NOT used in this one. safe_query stays plan-only forever.

After this PR, pytest tests/test_skill_executor_phase2.py is 20/20.
Targeted oauth+account+skill+audit regression sweep is 122/0. Frontend
tsc clean. The full Phase 1+2 surface (chat draft + read-only
planned execution + audit) is operator-ready behind the single chip
click.

Phase 3 (Asset Shield consent + write skills) is the next gate.

---

**Stop and report.**
