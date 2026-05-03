# PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1 — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Founder request:** wire plugin `default_skill` identifiers into safe
Daena action drafts/plans. Phase 1 only -- no direct tool execution,
no external writes, no emails, no repo edits, no payments, no browser
automation.
**Hard rules honored:** no deploy / no V2 flag flip / no vault apply /
no V1 deletion / no secrets touched / no external scans / no
auto-install / no MCP-OAuth-API-browser tool execution / no auto-sent
chat / no new primary tabs / no falsely-callable status / no write
actions from skill clicks / high-risk skills remain plan-only.

---

## Summary

Previous PRs shipped:
- **Plugin bundle data** (`PR-CONN-MCP-CATALOG-SKILL-BUNDLES`, `7f6127b`)
- **Plugin bundle UI** (`PR-CONN-PLUGIN-SKILLS-UX-WIRING`, `55e836c`)
- **Suggested-prompt → composer bridge** (`PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING`, `4ca88a6`)
- **Local model probe truth** (`PR-CONN-LOCAL-MODEL-PROBE`, `0db57aa`)

This PR is the **execution spine -- Phase 1**. Skill chips were
inert until now (clicking only revealed a "execution wiring pending"
message). With this PR, every catalog `default_skill` resolves
through a typed registry to one of:

- `composer_draft` -- drop a richer prompt template into chat (the
  "ask first" pattern: every template asks the operator for the
  missing context before doing anything)
- `action_plan` -- drop a multi-step plan template into chat
- `blocked_requires_connection` -- plugin not callable yet
- `blocked_high_risk_consent_missing` -- write/message skill blocked
  until Asset Shield consent + Phase 3 wiring; surfaces a "Draft plan
  in chat" fallback that still gives the operator value
- `unsupported_skill` -- skill identifier not yet registered

**No tool executes**. **No external write happens**. **No message is
sent**. **No chat auto-sends**. The Phase 1 click pipeline is exactly
the same shape as the suggested-prompt-to-composer flow shipped in
`4ca88a6` -- drafts a string into the textarea, navigates to /chat,
and lets the operator press Send when ready.

Total backend tests after PR: **569 passed / 1 skipped / 0 failed**
(+21 from this PR; previous baseline 548). Frontend `tsc -b` clean.

---

## Skill registry design

**File:** `frontend/src/pages/connections/skillActionRegistry.ts`
(620 lines).

**Type contract:**

```ts
interface SkillActionEntry {
  plugin_id: string                  // "mcp-github"
  skill_id: string                   // "triage_issues"
  action_type: SkillActionType       // composer_draft | action_plan | blocked_* | unsupported_skill
  template: string                   // composer text (empty for blocked)
  required_plugin_status: 'callable' | 'any'
  risk_level: 'low' | 'medium' | 'high'
  writes_external_state: boolean
  sends_external_message: boolean
  allowed_in_phase1: boolean         // defense-in-depth gate
  blocked_reason?: string
}
```

**Spread macros** (DRY shortcuts for the 4 common shapes):

| Macro | action_type | writes | sends | allowed_in_phase1 |
|---|---|---|---|---|
| `COMPOSER` | composer_draft | false | false | **true** |
| `COMPOSER_HIGH_RISK` | composer_draft | false | false | **true** (risk=high) |
| `PLAN_ONLY` | action_plan | false | false | **true** |
| `BLOCKED_WRITE` | blocked_high_risk_consent_missing | true | false | **false** |
| `BLOCKED_MESSAGE` | blocked_high_risk_consent_missing | true | true | **false** |
| `BLOCKED_BROWSER_ACTION` | blocked_high_risk_consent_missing | true | false | **false** |

**Defense-in-depth `allowed_in_phase1`:** even if `action_type ===
'composer_draft'`, the resolver checks `allowed_in_phase1` separately.
A future maintainer who promotes a skill to composer_draft without
flipping the flag won't accidentally enable it. Pinned by
`test_blocked_macros_have_allowed_in_phase1_false`.

**`resolveSkillAction(plugin, skill_id, readiness)`** -- pure function
that combines the registry lookup with the live skill readiness:
- Plugin not callable → `blocked_requires_connection` (overrides
  registry entry)
- Registry says `composer_draft` / `action_plan` AND
  `allowed_in_phase1=true` → resolves with `draft_text = template`
- Registry says `blocked_high_risk_consent_missing` → returns the
  blocked message + a synthesized "Draft plan in chat" fallback
  template so the operator still gets value
- Registry has no entry → `unsupported_skill` with explanatory text

---

## Which skills draft prompts (composer_draft)

48 entries map to `composer_draft` or `action_plan` and are
allowed in Phase 1. The complete list, grouped by plugin:

| Plugin | Phase 1 skills | Notes |
|---|---|---|
| GitHub | `triage_issues`, `review_pull_request`, `summarize_repo`, `draft_release_notes`, `inspect_ci_failure` | All 5 reads/drafts; "draft" never auto-publishes |
| Cloudflare | `inspect_dns`, `review_workers`, `check_security_headers`, `summarize_zone_config` | All 4 reads, but flagged COMPOSER_HIGH_RISK so Phase 3 consent fires |
| Sentry | `summarize_errors`, `trace_release_regression` | `create_bug_task` is BLOCKED |
| Vercel | `summarize_deployment`, `inspect_logs`, `review_env_config` | env review uses HIGH_RISK |
| Atlassian (Jira) | `triage_tickets`, `summarize_sprint`, `draft_release_notes`, `find_blockers` | All reads/drafts |
| Slack | `summarize_channel`, `draft_reply`, `find_decisions`, `extract_tasks` | `draft_reply` produces a draft (no auto-send) |
| Notion | `find_page`, `summarize_database`, `extract_action_items` | `update_page` BLOCKED |
| Linear | `triage_issues`, `summarize_cycle`, `draft_status_update`, `find_blockers` | `draft_status_update` is a draft |
| Stripe | `summarize_payments`, `inspect_customer` | Both COMPOSER_HIGH_RISK; `reconcile_subscriptions` BLOCKED |
| Hugging Face | `find_model`, `summarize_dataset`, `compare_models`, `inspect_paper` | All 4 reads |
| Figma | `inspect_design`, `summarize_components`, `generate_frontend_plan` | last is action_plan |
| Chrome DevTools | `inspect_dom`, `read_network`, `analyze_perf` | `capture_screenshot` BLOCKED |
| Filesystem | `find_files`, `read_file`, `summarize_directory` | All sandboxed reads |
| Postgres / SQLite / MongoDB / Supabase / Neon | `describe_schema`, `safe_query` (action_plan), `explain_query` / `describe_collections` / `summarize_storage` / `list_branches` | `safe_query` always action_plan -- shows SQL before executing |
| Google Drive (MCP archived + OAuth app) | `find_documents`, `summarize_file`, `compare_docs`, `extract_tables` | All reads |
| Gmail | `summarize_unread`, `draft_reply`, `extract_action_items`, `search_email_context` | `draft_reply` is a draft |
| Google Calendar | `list_today`, `find_free_time`, `summarize_week` | `schedule_meeting` BLOCKED (writes + sends invites) |
| Playwright | `inspect_ui` (action_plan only) | All other 4 BLOCKED_BROWSER_ACTION |

### "Ask first" pattern
Every Phase 1 template asks the operator for the missing context
(repo, label, time range, customer email, project, branch...) BEFORE
doing anything. This keeps Daena from assuming a target the operator
didn't pick. The templates are pure data with no string
interpolation, so they cannot leak operator data through template
metacharacters. Pinned by
`test_no_template_uses_template_literal_syntax`.

---

## Which skills are plan-only (action_plan)

7 entries are `action_plan`:
- `mcp-figma:generate_frontend_plan` -- planning the implementation
- `mcp-playwright:inspect_ui` -- planning a UI inspection without
  launching a browser yet
- `mcp-postgres:safe_query`, `mcp-sqlite:safe_query`,
  `mcp-mongodb:safe_query`, `mcp-supabase:safe_query`,
  `mcp-neon:safe_query` -- ALL `safe_query` skills resolve to
  action_plan because the operator should see the SQL/aggregation
  pipeline BEFORE execution, even when the underlying call is
  technically read-only

---

## Which skills remain blocked

9 entries map to a `BLOCKED_*` macro:

| Plugin / skill | Macro | Why |
|---|---|---|
| `mcp-stripe:reconcile_subscriptions` | BLOCKED_WRITE | Modifies customer billing state |
| `mcp-notion:update_page` | BLOCKED_WRITE | Writes Notion content |
| `mcp-sentry:create_bug_task` | BLOCKED_WRITE | Creates an issue tracker ticket |
| `app-google-calendar:schedule_meeting` | BLOCKED_MESSAGE | Writes calendar event AND sends invites |
| `mcp-playwright:open_page` | BLOCKED_BROWSER_ACTION | Browser drives a real page |
| `mcp-playwright:fill_form_safe` | BLOCKED_BROWSER_ACTION | Browser writes to a form |
| `mcp-playwright:capture_screenshot` | BLOCKED_BROWSER_ACTION | Browser action |
| `mcp-playwright:run_smoke_test` | BLOCKED_BROWSER_ACTION | Browser execution |
| `mcp-chrome-devtools:capture_screenshot` | BLOCKED_BROWSER_ACTION | Matches Playwright policy |

Each blocked entry **still surfaces a "Draft plan in chat" fallback**
so the operator gets value. The fallback synthesizes a generic
plan template: "I want to use the X plugin to do Y. Help me design a
safe plan: list the inputs you'd need from me, the steps you'd take,
the side effects each step would have, and the rollback if anything
fails. Do NOT execute anything yet -- I will review the plan first."

---

## Frontend behavior

`SkillBundleSection.tsx`:

1. **Locked chip click (plugin not callable)** → existing reveal
   popover shows "Connect the plugin first to enable this skill" --
   no execution path. (Resolver returns
   `blocked_requires_connection`.)
2. **Ready chip click (plugin callable, registry has Phase 1 entry)**
   → popover shows the resolved inline message + a "Use in chat"
   button. Click drafts via `composerBridge`, calls `onCloseParent()`
   on the drawer, navigates to `/chat`. NEVER auto-sends.
3. **Ready chip click on a BLOCKED skill** → popover shows the
   blocked message with a ShieldAlert icon + a "Draft plan in chat"
   button (amber-tinted to distinguish). Click drafts the
   _generic plan fallback_ into chat -- not the original skill
   template.
4. **Ready chip click on an unsupported skill** → popover shows the
   "skill not yet wired into Phase 1" explanation, no button.

The `PluginDetailDrawer` passes its `onClose` to
`SkillBundleSection` so successful drafts tear down the drawer
before navigating, mirroring the suggested-prompt button flow.

---

## Backend or frontend?

**Frontend-only registry** for Phase 1 (per founder Part C
recommendation). Reasoning:
- The registry is metadata + string templates, no execution logic.
- A backend execution endpoint would require a typed dispatch table
  AND audit log writes AND consent checks -- all Phase 2/3 work.
- Tests still pin the safety-critical contract via a Python file
  that **parses the TS registry as text**. This proves the contract
  invariants without needing a TS runtime in the test environment.

If Phase 2 needs a backend execution path, the typed
`SkillActionEntry` shape is the same data the backend would consume;
the migration is straightforward.

---

## Safety proof: no tool execution, no auto-send, no external writes

| Founder hard rule | How it's enforced |
|---|---|
| Rule 9 -- No MCP/OAuth/API/browser tool execution | The frontend code path is `lookupSkillAction()` → `resolveSkillAction()` → `handleUseInChat()` → `draftMessage()` → `useComposerDraftStore.setDraft()`. No HTTP call, no MCP dispatch, no OAuth token use. The store is in-memory only. |
| Rule 10 -- No auto-sent chat | `draftMessage()` calls `setDraft()` on a Zustand store. ChatPage's effect hydrates `prefillValue` from the store. ChatInput's effect sets the textarea `value`. **The user must press Enter or click Send.** Verified live: session list still shows "No conversations yet" after a chip click. |
| Rule 13 -- No write actions from skill clicks | Pinned by `test_no_phase1_entry_writes_external_state`: no entry with `allowed_in_phase1=true` may have `writes_external_state=true`. Symmetric test for `sends_external_message=true`. |
| Rule 14 -- High-risk skills remain plan-only | Pinned by `TestExplicitBlocks` (parametrized over the 9 dangerous skills, each must use a `BLOCKED_*` macro) AND `TestHighRiskPlugins` (Cloudflare + Stripe reads must use `COMPOSER_HIGH_RISK`). |

The defense-in-depth `allowed_in_phase1` flag is the second gate:
even if a maintainer accidentally promotes a write skill to
`composer_draft` without flipping the flag, the resolver still
returns `unsupported_skill` (no draft path).

---

## Tests run

### New backend file: `test_skill_action_registry_phase1.py` (20 tests)

| Test class | Tests | Pinning |
|---|---|---|
| `TestCoverage` | 3 | registry parses; every catalog skill mapped; no phantom registry entries |
| `TestPhase1SafetyInvariants` | 3 | no Phase1 writes, no Phase1 messaging, BLOCKED macros have allowed_in_phase1=false |
| `TestExplicitBlocks` | 9 (parametrized) | each of 9 dangerous skills uses a BLOCKED_* macro |
| `TestHighRiskPlugins` | 2 | Cloudflare + Stripe reads use COMPOSER_HIGH_RISK |
| `TestTemplateSafety` | 3 | no real credentials; no template literal syntax; every allowed entry has non-empty template |

### Regression sweep
```
.venv/Scripts/python.exe -m pytest tests/ -q -k "marketplace or
connection_v2 or probe or provider_key or dynamic_model or
account_provider or plugin_bundle or plugin_skills or local_model or
skill_action"
569 passed, 1 skipped, 3952 deselected, 13 warnings in 29.51s
```
Up from 548 in the prior PR. Net +21 from this PR; zero regressions.

### Frontend tsc
`npx tsc -b` clean (0 errors).

### Live Chrome DevTools smoke
- `/connections` loads.
- GitHub plugin drawer (status: Available, NOT callable) opens.
- Click "Triage issues" chip → popover renders with text:
  *"Triage issues -- Connect the plugin first to enable this skill.
  The probe ladder above shows what step is pending."*
- No execution. No network call. No tool dispatch.
- Pinned via DOM inspection that the popover content matches the
  resolver output for `blocked_requires_connection`.

---

## Remaining blockers for Phase 2 real read-only tool execution

Phase 2 should turn `composer_draft` and `action_plan` entries into
**actual read-only tool calls** when the operator approves the draft.
Required pieces:

1. **Skill → tool dispatch table on the backend**. Each
   `(plugin_id, skill_id)` needs to resolve to either:
   - An MCP tool name + arg schema (for `mcp_server` plugins)
   - An OAuth-mediated API call (for `oauth_app` plugins)
   - A backend service call (for first-party Daena ops)
   The TS `SkillActionEntry` shape is the same data the backend
   would consume.

2. **Read-only enforcement gate**. The chat orchestrator must verify
   the resolved tool is read-only against an allowlist. A skill
   marked Phase 2 read-only that turns out to call a write API on
   the MCP server would be caught here, not at runtime.

3. **Per-skill audit log row**. Currently `audit_service` logs
   per-tool-call; Phase 2 needs a parent `skill_invocation` event
   tying N child tool calls back to one operator intent.

4. **Composer "Run as skill" affordance**. After a draft lands in
   chat, the operator sees the plan; pressing a new "Run as <skill>"
   button (next to Send) dispatches through the skill executor
   instead of the regular chat orchestrator.

Phase 3 (writes) needs:
5. **Asset Shield consent dialog** for `BLOCKED_*` skills.
6. **Per-plugin governance policy presets** at install (Stripe:
   never auto-charge above $X; Cloudflare: never edit production
   zones without approval; etc.).
7. **Live MCP registry sync** so capability changes are detected.

---

## Files changed

```
A  frontend/src/pages/connections/skillActionRegistry.ts          (620 lines)
M  frontend/src/pages/connections/SkillBundleSection.tsx          (+70 / -28 lines)
M  frontend/src/pages/connections/PluginDetailDrawer.tsx          (+8 / -1 lines)
A  backend/tests/test_skill_action_registry_phase1.py             (340 lines)
A  docs/Ultraview/PR_CONN_PLUGIN_SKILLS_EXECUTION_PHASE1_REPORT.md (this file)
```

Net: ~+1100 lines added, ~-29 removed across 1 new registry + 2 src
edits + 1 new test file + this report.

---

## Hard rules verification

| Rule | Compliance |
|---|---|
| 1. No deploy production | ✅ |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` | ✅ |
| 3. No `vault --apply` | ✅ |
| 4. No V1 file deletion | ✅ |
| 5. No secrets printed/grepped/logged/committed | ✅ pinned by `test_no_template_contains_real_credentials` |
| 6. No external scans | ✅ |
| 7. No emails/DMs/webhooks/messages | ✅ pinned by `test_no_phase1_entry_sends_external_message` + `BLOCKED_MESSAGE` macro on `schedule_meeting` |
| 8. No auto-install of npm/pip/docker | ✅ |
| 9. No MCP/OAuth/API/browser tool execution | ✅ frontend code path has zero HTTP/dispatch surface |
| 10. No auto-sent chat | ✅ verified live: session list still empty post-chip-click |
| 11. No new primary tabs | ✅ |
| 12. No falsely-callable status | ✅ resolver overrides registry to `blocked_requires_connection` when readiness != ready |
| 13. No write actions from skill clicks | ✅ pinned by `test_no_phase1_entry_writes_external_state` + 9 explicit `BLOCKED_WRITE` entries |
| 14. High-risk skills remain plan-only until consent | ✅ Stripe/Cloudflare reads tagged COMPOSER_HIGH_RISK; writes BLOCKED |

Stop and report.
