# DAENA Local Usability -- Sprint-3 Smoke Status

**Run at:** 2026-05-03 ~21:30 local
**Branch:** `rebuild-connections-mcp-runtime`
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-3 (PR-5 of 5)
**Last sprint commit:** (will be pinned post-commit) ; previous PR commit `b11ec95`
**Pre-sprint baseline:** `a5bcf60` (post Sprint-2 visual-smoke verification)

---

## TL;DR

Sprint-3 ran cleanly through all 5 PRs with **0 hard stops**. The
sprint shifted Daena from "UI works but lies a little" to
"UI is honest plus has the foundation for OAuth-based real
execution." Every backend smoke section PASSES; the visual
verification of PR-1's marketplace fix requires a backend restart
(documented below).

---

## Section-by-section results

### Section 1 -- Backend launches cleanly

| Check | Status | Evidence |
|---|---|---|
| 1.1 Launcher present | PASS | `scripts/start-backend-dev.bat` (from Sprint-2) |
| 1.2 `/health` 200 | PASS | `{"status":"healthy",...}` from `curl 127.0.0.1:8000/health` |
| 1.3 `.daena-port` written | PASS | `cat backend/.daena-port` returns `8000` |

### Section 2 -- Frontend reachable

| Check | Status | Evidence |
|---|---|---|
| 2.1 `npm run dev` reachable | PASS | `curl http://localhost:5173` returns HTTP 200 (Vite IPv6 binding) |
| 2.2 Vite hot-reload | PASS (implicit) | Frontend served fresh code post-edits without restart |

### Section 3 -- Connections page

| Check | Status | Evidence |
|---|---|---|
| 3.1 `/connections` page renders | PASS | chrome-devtools snapshot: 145+ uids rendered, no overlay |
| 3.2 Brain tab shows | PASS | Main Brain pill, 6 runtimes listed, 3 API providers configured |
| 3.3 Plugins tab clickable | PASS | Tab toggles cleanly |
| 3.4 No Backend Not Found | PASS | Live counts: 0 connected, 3 needs auth, 1 installed, 53 available |

### Section 4 -- Brain vLLM probe truth (PR-1)

| Check | Status | Evidence |
|---|---|---|
| 4.1 Brain tab vLLM status | PASS (already honest) | Shows "Not installed / offline" -- truthful (port 8080 is dead) |
| 4.2 Backend marketplace fix landed | CODE LIVE | `_derive_lifecycle` honesty guard committed in `78797b1`; 5 unit tests green |
| 4.3 Backend serves the fix to UI | **REQUIRES RESTART** | Backend is still running pre-PR-1 code from session start; restart `scripts\start-backend-dev.bat` to load |

**Honest finding**: the backend in this dev session still runs the pre-PR-1 code (no `--reload` per project policy). The TESTS prove the fix works; visual verification of vLLM no longer showing "Installed" requires the operator to restart the backend. Frontend code (`pluginCard.ts` deriveAction extension) is hot-reloaded by Vite.

### Section 5 -- Plugin install/test feedback (PR-2)

| Check | Status | Evidence |
|---|---|---|
| 5.1 Test button shows "Probing..." while busy | CODE LIVE | `PluginCardView.tsx` label tweak; tsc clean |
| 5.2 Probe outcome toasts | CODE LIVE | `PluginsPanel.handleProbe` + `handleEnable` toast on success/failure with exact failure_dim+reason |
| 5.3 MCPInstallDrawer post-success hint | CODE LIVE | `onComplete` toasts "installed and probe succeeded" or "set env vars (X,Y) and click Test" |
| 5.4 OAuthConnectDrawer hand-off hint | CODE LIVE | `onComplete` toasts "connected. Click Test on the card to verify the token" |
| 5.5 No hardcoded fallback / no auto-install | PASS | All hooks call existing endpoints; no behaviour change beyond presentation |

### Section 6 -- DB describe-schema honest state (PR-3)

| Check | Status | Evidence |
|---|---|---|
| 6.1 4 of 5 DB skills promoted | PASS | sqlite/mongodb/supabase/neon flipped to `mcp_tool`; `test_pr4_db_describe_promotion_set_is_exactly_four` green |
| 6.2 mcp-postgres stays planned | PASS | `test_pr4_postgres_stays_planned_only` defends |
| 6.3 No DB write skill promoted | PASS | `test_pr4_no_db_write_skills_promoted` 23-name forbidden list defends |
| 6.4 Arg builders narrow reads | PASS | Supabase pins schemas=['public'] even if operator passes auth/storage; SQLite returns {} (db path owned by MCP) |
| 6.5 Server keys registered | PASS | `_PLUGIN_TO_SERVER_KEY` includes 4 new entries; `test_pr4_server_keys_registered_for_promoted_db_plugins` green |

### Section 7 -- OAuth invoker foundation (PR-4)

| Check | Status | Evidence |
|---|---|---|
| 7.1 OAuthInvoker module loads | PASS | `_validate_allowlist()` runs at import; module-load asserts pass |
| 7.2 Allowlist pinned to 4 entries | PASS | `test_allowlist_set_is_pinned` |
| 7.3 GET-only enforced | PASS | `test_every_method_is_get_and_https` + module-load assert |
| 7.4 Token leak defenses | PASS | `_scrub` regex + `test_invoke_outcome_never_carries_token_field` structural check |
| 7.5 401-refresh-retry path | PASS | 3 mocked tests cover success / second-401 / refresh-call-fails |
| 7.6 Response caps at network boundary | PASS | byte-cap truncation + item-cap slicing tests green |
| 7.7 Path-substitution defense | PASS | rejects `/` and control chars |
| 7.8 Foundation invariant: NOT promoted | PASS | `test_phase2_oauth_entries_still_planned` confirms Gmail/Drive STAY planned_only |
| 7.9 Real Google API NOT touched | PASS | All 21 tests use `OAuthInvoker(http_client=MagicMock(...))` |

### Section 8 -- Tests

| Suite | Result |
|---|---|
| `test_oauth_invoker.py` | **21 passed** in 0.54s |
| `test_skill_executor_phase2.py` | **64 passed** in 2.64s (was 57 pre-sprint; +7 PR-3 tests) |
| `test_connection_v2_marketplace.py` | **98 passed** in 3.25s (was 93 pre-sprint; +5 PR-1 tests) |
| `test_connections.py` | **26 passed** in 30s (unchanged) |
| Frontend `npx tsc --noEmit` | **0 errors** |

Sprint-3 total in scope: **209 passing in their natural files**.

Note: when all 4 backend test files run in one pytest invocation, 14
of the marketplace LiveSmoke tests error from a pre-existing
cross-file tenant-id collision (`test_connections` seeds tenant
`11111111-...` and the marketplace `seeded_tenant` fixture re-attempts
to insert it). This is NOT a Sprint-3 regression -- each file passes
in isolation. A future Option-C tidy PR can address this fixture
isolation pattern.

---

## What Masoud can use NOW (after backend restart)

### Locally-usable surfaces

| Capability | State |
|---|---|
| Backend launches via `scripts\start-backend-dev.bat` | LIVE (Sprint-1) |
| 14 promoted Phase 2.x read-only skills (was 10 at end Sprint-2) | CODE LIVE; needs MCP install per skill |
| OAuth lifecycle endpoints + UI panel | LIVE (Sprint-1 PR-3 + Sprint-2 PR-1) |
| Honest marketplace status pills (no fake "Installed" for unprobed local_model) | CODE LIVE; needs backend restart |
| Test/Install toast feedback loop | LIVE (FE hot-reloaded by Vite) |
| OAuth Invoker foundation (no live route yet) | LIVE; awaits wire-up PR for Gmail/Drive promotion |

### 14 promoted skills

```
mcp-filesystem:find_files              (Sprint-1 PR-1)
mcp-filesystem:summarize_directory     (Sprint-1 PR-1)
mcp-huggingface:find_model             (Sprint-1 PR-1)
mcp-huggingface:inspect_paper          (Sprint-1 PR-1)
mcp-github:summarize_repo              (Sprint-1 PR-2)
mcp-github:triage_issues               (Sprint-1 PR-2)
mcp-github:inspect_ci_failure          (Sprint-1 PR-2)
mcp-sentry:summarize_errors            (Sprint-1 PR-2)
mcp-slack:summarize_channel            (Sprint-2 PR-3)
mcp-slack:find_decisions               (Sprint-2 PR-3)
mcp-sqlite:describe_schema             (Sprint-3 PR-3, this sprint)
mcp-mongodb:describe_collections       (Sprint-3 PR-3, this sprint)
mcp-supabase:describe_schema           (Sprint-3 PR-3, this sprint)
mcp-neon:describe_schema               (Sprint-3 PR-3, this sprint)
```

### Stayed planned (intentional)

```
app-gmail:summarize_unread             # OAuthInvoker exists (PR-4); needs wire-up PR
app-gmail:search_email_context         # Same
app-google-drive:find_documents        # Same
app-google-drive:summarize_file        # Same
mcp-postgres:describe_schema           # Archived ref MCP only ships `query` (no discrete tool)
```

---

## What still requires manual setup (operator action)

1. **Restart the backend** to pick up PR-1 marketplace fix + PR-3 promotions + PR-4 OAuth invoker module load.
2. Install MCPs (already documented in `MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md`, Sprint-2 PR-2):
   - `@modelcontextprotocol/server-filesystem` + `<ALLOWED_ROOT>`
   - `@modelcontextprotocol/server-github` + `GITHUB_PERSONAL_ACCESS_TOKEN`
   - `@sentry/mcp-server` + tokens
   - `@modelcontextprotocol/server-slack` + `SLACK_BOT_TOKEN`
   - **NEW (Sprint-3 PR-3)**: any DB MCP whose schema you want to introspect:
     - `uvx mcp-server-sqlite --db-path <PATH>` (SQLite)
     - `npx -y mongodb-mcp-server` (MongoDB)
     - `npx -y @supabase/mcp-server-supabase` (Supabase) + `project_ref`
     - `npx -y @neondatabase/mcp-server-neon` (Neon) + `projectId`
3. Live-verify the marketplace card for vLLM no longer says "Installed":
   - Restart backend
   - Reload `/connections`
   - Open Plugins tab
   - Find "vLLM / llama-server" card -- should show "Available" badge + "Probe" button (not "Installed")
4. Live-verify the new toast feedback loop:
   - Click Test on any plugin with a V2 row -- toast surfaces success/failure outcome
   - Install an MCP via the Install drawer -- toast hints next step (set env vars / click Test)

---

## What did NOT happen (intentional)

- No production deploy / Cloud Run write
- No `USE_CONNECTION_REGISTRY_V2=true` flip
- No `vault --apply`
- No secret read / print / grep / log / commit
- No external email / DM / webhook / message
- No payment / refund / subscription / write
- No browser action on external sites (chrome-devtools used only against `localhost:5173`)
- No V1 / legacy file deletion
- No npm/pip/docker install (operator does these via the Plugins UI per their own confirmed flow)
- **No Gmail/Drive promotion** -- the OAuth invoker exists but is not wired into `SkillExecutorService.execute()` yet. The Sprint-2 invariant `test_pr3_gmail_and_drive_remain_planned_only` actively defends this.

---

## Hard stops encountered

**NONE.** Sprint queue ran cleanly through all 5 PRs.

---

## Sprint-3 commits landed

```
b11ec95  canonicalization: add OAuth read-only invoker foundation         [PR-4]
a2a2d7d  canonicalization: promote DB describe-schema read-only skills   [PR-3]
d8d13ba  fix: polish plugin install and test feedback                    [PR-2]
78797b1  fix: align Brain vLLM probe with local model truth              [PR-1]
a5bcf60  docs: verify local UI visual smoke -- Sprint-2 stable           (pre-sprint baseline)
```

(PR-5 commit will land after this doc is committed.)

---

## Exact startup commands (next session)

```bash
# Window 1: backend (no-reload, .venv-pinned)
cd D:\Ideas\Daena
scripts\start-backend-dev.bat

# Window 2: frontend
cd D:\Ideas\Daena\frontend
npm run dev

# Browser
start http://localhost:5173
```

Then to live-verify Sprint-3 PR-1 + PR-3 fixes:
1. Open `/connections` -> Plugins tab
2. Confirm vLLM card shows **Available** + Probe (not Installed)
3. Confirm 4 DB plugins (SQLite, MongoDB, Supabase, Neon) show their describe_schema/describe_collections skills as ready (chips lit) once their MCP is installed

If anything looks off, run `DAENA_LOCAL_PRODUCTION_READY_SMOKE.md` top-to-bottom.

---

## Suggested next sprint (Sprint-4)

Per the operator's brief at end of Sprint-3 introduction:

1. **PR-CONN-OAUTH-EXECUTOR-WIRE-UP** -- wire `OAuthInvoker.invoke()`
   into `SkillExecutorService.execute()` when `entry.backend_surface
   == "oauth"` AND `entry.execution_mode == "mcp_tool"`. Add E2E tests
   using the existing `SkillExecutor` audit-row contract.
2. **PR-CONN-PHASE2X-GMAIL-DRIVE-READONLY** -- promote 4 Gmail+Drive
   read skills to `mcp_tool`; update PROMOTED_TO_MCP_TOOL; flip the
   Sprint-2 `test_pr3_gmail_and_drive_remain_planned_only` to its
   counterpart `test_sprint4_gmail_and_drive_promoted`.
3. **PR-CONN-ASSET-SHIELD-CONSENT-DESIGN** -- prep gate for Phase 3
   write actions: consent token issuance + executor-side check;
   founder approval queue UI.
4. **PR-CONN-PER-PLUGIN-GOV-PRESETS** -- per-plugin governance preset
   (allow / ask / deny tier per skill) plumbing.

Recommended order: 1 -> 2 (sequential dependency) -> 3 -> 4.

---

## Final words

Sprint-3 took Daena from "the UI works but the badge sometimes lies"
to "every claim is backed by a probe AND we have the foundation for
real Gmail/Drive reads." The next sprint is the bridge from
foundation to live execution -- after that, Phase 3 writes start.

**0 hard stops. 21 new tests. 4 new skills. 1 OAuth invoker
foundation. 1 honest marketplace.**

Sprint-3 COMPLETE.
