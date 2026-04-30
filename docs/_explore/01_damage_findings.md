# Damage Findings (synthesized from prior audits)

All 11 source docs exist and are non-empty. Source refs used: PLUGIN_INSTALL, SEC_STAB, CLI_MCP, CODEX_BRUTAL, DUPS, FE_BE_TRUTH, UI_BE_TRUTH, RT_POLISH, ID_QUOTA, BE_MAP/FE_MAP (2026-03-25 pre-rebuild).

## Executive verdict - what is broken, in one paragraph

The Connections/MCP/Plugins/Runtime stack is a half-finished rebuild on top of a still-active legacy monolith, with optimistic UI labels papering over six unrelated truth dimensions. CODEX summarizes: surface "mixed detection, config, import, persistence, reachability, callability, and authentication into optimistic UI labels" - hence "5 MCPs found" but only 4 rendered, and "Imported" without callable proof. A new `/connections` (3 tabs: Main Brain / Plugins / MCP Servers), `connector_install.py`, 116-connector JSON catalog, `RuntimeTruthRegistry`, and modular `frontend/src/pages/connections/*` tree were added, but the legacy `ConnectionsPage.tsx` monolith still lives, modular split is unfinished, Cloudflare OAuth never completed, several MCPs still fail handshake, and full typecheck/pytest never ran in the 2026-04-30 pass (Codex shell Node aborted at `ncrypto::CSPRNG`, Python `asyncio` failed `_overlapped` / `WinError 10106`). Legacy `/runtime/import` was a known lie - "only marked an item persisted in Daena's runtime truth JSON ... did not import from Claude, Codex, Gemini, or a plugin source." Identity/quota show duplicate Masoud rows no audit could validate because backend was offline. Net: surface honest in pockets after 2026-04-30, still a mix of repaired/partial/missing - nothing end-to-end proven.

## Specific failures, table form

| Symptom | Source | File / endpoint | Sev | Quoted evidence |
|---|---|---|---|---|
| Install dialog wired to inactive route | PLUGIN_INSTALL | `pages/connections/ConnectionsConnectors.tsx` (orphan); active is `pages/ConnectionsPage.tsx` | P0 | "wired into ... ConnectionsConnectors.tsx, which is not the active /connections route" |
| `/runtime/import` faked imports | SEC_STAB | `POST /api/v1/runtime/import` | P0 | "only marked an item persisted in Daena's runtime truth JSON" |
| Skill-pack rows showed bearer-token form | PLUGIN_INSTALL | `connector_install.py`, `/connectors/build-macos/install/start` | P0 | "auth_type=none ... defaulted missing auth.method to api_token ... That was fake" |
| `ConnectionService.install()` faked connected state | PLUGIN_INSTALL | `ConnectionService` | P0 | "treated every no-auth connector as connected immediately" |
| MCP detection vs registry count mismatch | CLI_MCP | `/mcp-sync/detected` (5) vs `/connections/mcp-registry` (4) | P0 | "detection count and rendered/registered count were using different sources" |
| `install-all` installed prowler/scoutsuite/trufflehog w/o confirm | SEC_STAB | `POST /api/v1/security/tools/install-all` | P0 | "background job reached prowler, scoutsuite, and trufflehog" |
| "Imported" shown without callable proof | CODEX_BRUTAL / CLI_MCP | runtime truth UI | P0 | "'Imported' without callable proof" |
| Identity/quota duplicate Masoud rows | ID_QUOTA | `/settings/user`, tenant/quota tables | P0 | "duplicate Masoud Masoori identity/plan surfaces" |
| Legacy `/connections` was RuntimeTruth-centric, not connector-centric | SEC_STAB | `ConnectionsPage.tsx` legacy | P0 | "centered on RuntimeTruthRegistry rows" |
| Cloudflare OAuth not proven end-to-end | PLUGIN_INSTALL | `/connectors/mcp-oauth/callback` | P1 | "implemented but not end-to-end proven" |
| Figma OAuth metadata discovery failed | PLUGIN_INSTALL | `/connectors/figma/install/start` | P1 | "falls back to token setup because metadata discovery failed" |
| Provider rows mislabeled `failed` when only key set | CODEX_BRUTAL | `/runtime/truth` | P1 | "fake failed/imported to configured_untested when only a key exists" |
| Daena MCP package shown persisted because file existed | CODEX_BRUTAL / CLI_MCP | `packages/daena-mcp` | P1 | "Daena MCP package existing on disk is not persistence" |
| `/security/status` did sync FS reads in async handler | SEC_STAB | `security_dashboard.py` | P1 | "filesystem scan-history reads ... inside an async request handler" |
| `gitnexus`/`local-llm` MCPs detected but not callable | CLI_MCP | runtime truth | P1 | "not callable from backend path evidence" |
| vLLM `127.0.0.1:8080` failed; backend-local Ollama failed | CLI_MCP | runtime detection | P1 | "Configured vLLM endpoint ... failed connection attempts" |
| Browse marketplace catalog frontend-static, not DB | DUPS + UI_BE_TRUTH | `ConnectionsPage.tsx` browse modal | P1 | "browse modal extension catalog is still frontend-static" |
| Old monolith active alongside new modular tree | DUPS + FE_BE_TRUTH | `ConnectionsPage.tsx` vs `pages/connections/*` | P1 | "newer modular connections surface ... old monolith still active" |
| `web_search_stub` in cognitive prod code | DUPS | `services/laevateinn/tool_augmented.py` | P1 | "Multiple web_search_stub references" |
| `laevateinn.py` is a placeholder | DUPS | `api/v1/laevateinn.py` | P1 | "placeholder until fully wired" |
| MCP Test surfaced raw `TaskGroup` errors | PLUGIN_INSTALL | `McpServersPanel`, `mcp_invoker` | P2 | "raw unhandled errors in a TaskGroup or stale not in bootstrap registry" |
| Install dialog kept stale token form state | PLUGIN_INSTALL | `ConnectorInstallDialog` | P2 | "Cloudflare could still show the previous bearer-token form" |
| Header `AGI ACTIVE` wording mismatched semantics | CODEX_BRUTAL | `Header.tsx` | P2 | "AGI ACTIVE wording to AUTOPILOT ON/OFF" |
| RAG/Obsidian status has no first-class API | UI_BE_TRUTH | `/memory/*` | P2 | "lacks a first-class API and should be either implemented or labeled" |
| Webhook UI exists but no backend route | FE_BE_TRUTH | `SettingsDeveloper.tsx` | P2 | "No persistent webhook route/audit contract in current backend" |

## Fake/dummy UI elements that lie about state

| UI element | Lie | Source |
|---|---|---|
| Skill-pack rows (Build macOS etc.) | `Install` + bearer-token form; not callable | PLUGIN_INSTALL |
| Legacy `Import` button on `/connections` | only persisted to JSON; no real import | SEC_STAB |
| API provider rows | `failed` when only env key existed (no probe) | CODEX_BRUTAL |
| Daena MCP package row | `persisted` because file existed on disk | CLI_MCP |
| Header `AGI ACTIVE` chip | mismatched autopilot toggle | CODEX_BRUTAL |
| Cloudflare install dialog | stale bearer-token form after backend returned `mcp_remote_oauth` | PLUGIN_INSTALL |
| MCP Test results | leaked raw TaskGroup / `not in bootstrap registry` | PLUGIN_INSTALL |
| `Configure` connector button | inline disabled; "made the surface look broken" | RT_POLISH |
| Browse modal connector marketplace | static frontend array, not DB-sourced | DUPS + UI_BE_TRUTH |
| Webhook controls in `SettingsDeveloper` | no backend route exists | FE_BE_TRUTH |
| Founder identity/quota in Billing | duplicate Masoud rows as separate plans | ID_QUOTA |
| `RuntimeSwapper.DEFAULT_RUNTIMES`, fake departments, fake `/export`/`/compact` slash cmds, fake cost toast | hardcoded fallbacks/lies; removed 2026-04-29 | FE_BE_TRUTH |

## Backend endpoints that don't actually do what they claim

| Endpoint | Claimed | Actual | Source |
|---|---|---|---|
| `POST /runtime/import` | Import runtime/MCP from CLI | only marked persisted in JSON | SEC_STAB |
| `POST /connectors/{slug}/install/start` (skill packs, pre-fix) | Start install | bearer-token form for non-installable rows | PLUGIN_INSTALL |
| `POST /security/tools/install-all` (pre-fix) | Plan only (presumed) | spawned background install w/o confirm gate | SEC_STAB |
| `GET /security/status` (pre-fix) | Fast async status | sync FS scans inside async; timed out | SEC_STAB |
| `/mcp-registry` vs `/mcp-sync/detected` | Same source (implied) | Different sources - counts diverged 4 vs 5 | CLI_MCP |
| `/connections/catalog` | Single catalog | 116 JSON + 23 code-defined `/plugin-catalog` | SEC_STAB |
| `POST /connections/instances` (pre-fix) | Install + connect | marked no-auth rows connected even if not callable | PLUGIN_INSTALL |
| `/runtimes/{id}/test` (pre-fix) | Real test | API providers returned `failed` even with valid key | CODEX_BRUTAL |

## Duplicate/dead/unwired files identified by prior audits

All from DUPS unless tagged otherwise.

| Path | Type |
|---|---|
| `D:\Ideas\Daena_old_upgrade_20251213` | legacy/missing on disk |
| `Doc\v1-docs`, `landing/`, `agent-harness/` | legacy docs / outside frontend / unclear ownership |
| `backend/app/api/v1/ws.py` | removed/dead route |
| `frontend/src/pages/DaenaBotPage.tsx` | removed; `/daenabot` -> `/chat` |
| `frontend/src/pages/FounderPage.tsx` | removed; `/founder` -> settings |
| `backend/app/api/v1/laevateinn.py` | placeholder |
| `backend/app/services/laevateinn/tool_augmented.py` | `web_search_stub` references |
| `frontend/src/pages/ConnectionsPage.tsx` | monolith still active alongside `pages/connections/*` |
| `frontend/src/pages/connections/ConnectionsConnectors.tsx` | orphan from Plugins-tab pivot (PLUGIN_INSTALL) |
| `frontend/src/pages/connections/ConnectionsRuntimes.tsx` | "orphaned since the Runtime Truth pivot" (RT_POLISH) |
| `backend/testssl.sh` | vendored third-party tree under backend |
| `venv_daena`, `venv_daena_main_py310` | duplicate historical venvs |
| `services/heartbeat/work_queue.py` vs `autopilot/background_queue.py` | "two task-queue mental models" |

## Prior rebuild attempts already started (untracked files in git)

Pre-PLUGIN_INSTALL pass (Codex):
- `backend/app/api/v1/connector_install.py`, `frontend/src/components/connections/ConnectorInstallDialog.tsx`, `frontend/src/pages/connections/installFlow.ts`, `scripts/scrape_codex_plugins.py` (all added)
- `backend/app/config/connector_catalog.json` expanded to 116 connectors
- `skills/connector-*` folders copied from Codex plugins

CODEX_BRUTAL pass: `RuntimeTruthRegistry` service + `/api/v1/runtime/*` endpoints; `/connections` rebuilt as "Runtime & Connections Center".

SEC_STAB pass: 3-tab `/connections` (Main Brain / Plugins / MCP Servers); MCP Servers panel separating live registry / detected / installable / Claude Desktop config.

FE_BE_TRUTH 2026-04-29 repairs: `/connections/extensions/install`, `/connectors/{id}/oauth/authorize`, MCP sync hooks; new `/memory/status` honest endpoint.

**Status: rebuild unfinished.** Legacy `ConnectionsPage.tsx` monolith STILL ACTIVE alongside `pages/connections/*` modular tree.

## Inconsistencies between layers

| Symptom | Frontend | Backend | DB / persistence | Source |
|---|---|---|---|---|
| MCP count | 4 rendered | `/mcp-sync/detected` returned 5 | registry had 4 | CLI_MCP |
| Skill-pack callability | `Install` + token form | (post-fix) 409 skill-pack-only | `auth_type=none`, no MCP, no adapter | PLUGIN_INSTALL |
| Daena MCP "imported" | persisted | file on disk | never imported, never health-checked | CLI_MCP |
| API provider status | `failed` chip | only `.env` key, no probe | no failure record | CODEX_BRUTAL |
| Connector catalog count | 146 (older copy) | JSON 116 | code plugin catalog 23 | SEC_STAB |
| Identity / Plan | multiple Masoud rows | `/settings/user` returns founder | duplicates suspected, never validated | ID_QUOTA |
| Cloudflare connection | UI: `connected` | started `mcp_remote_oauth` | no encrypted token (consent not completed) | PLUGIN_INSTALL |

**Disagreement:** BE_MAP (2026-03-25) lists `/connections/*` against `connectors`/`connector_instances`/`connector_permissions` DB tables - but 2026-04-30 audits add `connector_catalog.json` + `connector_install.py` as a parallel path. Per PLUGIN_INSTALL the backend now "Merges database connector rows with backend/app/config/connector_catalog.json" - layered, not unified.

## Patterns that must be eliminated in V2

1. **Single source of truth per row.** One backend-owned materialized view; no "JSON says X, DB says Y, FE cache says Z."
2. **Six truth dimensions are explicit fields, not one badge.** detected / configured / imported / persisted / reachable / callable / authenticated - each a boolean with `last_checked_at` + `last_failure_reason`.
3. **`auth_type=none` NEVER defaults to `api_token`.** Skill packs render as `Skill pack` / `Not installable`.
4. **No "ran but did nothing" jobs.** Cron + import endpoints persist a run record with side-effect evidence (CLAUDE.md Rule 17). `/runtime/import` deleted, not patched.
5. **No hardcoded fallback lists posing as live state.** `DEFAULT_RUNTIMES` pattern banned. "Detecting..." / "Empty" only.
6. **No async handlers doing sync FS/network probes.** `asyncio.to_thread` + TTL caches + stale-while-refresh.
7. **No destructive endpoints without `confirm=` gate.** `install-all` requires explicit confirm; dry-run default.
8. **No two parallel UI surfaces for the same concern.** Monolith collapses into `pages/connections/*`.
9. **No raw exceptions in UI.** TaskGroup/handshake errors sanitized to `Not callable: <reason>`.
10. **No "Imported"/"Persisted" UI without callable proof.** Persistence = authenticated round-trip recorded in DB.
11. **No backend-local assumptions.** `localhost:11434` != Windows host - auto-detect bridge.
12. **Install dialog state clears on every open.**
13. **`configured_untested` not `failed` when only env key exists.**
14. **Header chips match semantics** (no `AGI ACTIVE` for `AUTOPILOT ON`).

## Open questions the prior audits couldn't answer

1. **Identity/quota duplicates** - never validated; "validation is blocked because backend is currently ECONNREFUSED". Root cause (user/tenant/quota/seed/UI-merge?) unknown.
2. **Cloudflare end-to-end OAuth** - token persistence "implemented but not end-to-end proven"; consent never completed.
3. **Figma MCP OAuth** - discovery failed; whether Figma exposes a usable endpoint or Daena's discovery is wrong is unknown.
4. **Are 116 connector rows actually all non-fake?** Only Cloudflare/GitHub/Figma/Hugging Face install starts were exercised. ~112 untested.
5. **`gitnexus` and `local-llm` MCP rows** - detected but not callable; per-row root cause never enumerated.
6. **vLLM `127.0.0.1:8080` failure** - root cause unknown.
7. **Skill injection scan** - "Imported Codex skill files were not independently injection-scanned in this pass" - security risk unverified.
8. **Global `~/.claude/skills` mirroring** - "was not performed in this pass"; cross-runtime consistency unproven.
9. **Full pytest / typecheck / build never ran** in 2026-04-30 audit - Codex Node aborted (`ncrypto::CSPRNG`), Python `asyncio` failed (`_overlapped` / `WinError 10106`). **NO regression evidence exists for the entire 2026-04-30 connections rebuild.**
10. **Legacy `ConnectionsPage.tsx` retirement plan** - DUPS recommends "Finish split after tests pass" but no concrete deletion roadmap exists.
11. **Plugin catalog truth** - older UI/docs said 146; SEC_STAB corrects to "116 connectors, not 146". Single canonical figure not yet enforced.
12. **`heartbeat/work_queue` vs `autopilot/background_queue`** - "may be intentional ... but should be documented to avoid two task-queue mental models". Unresolved.
13. **MCP rows not callable** - "several are not callable because their npm package, command, or env config fails during handshake" - per-row root cause not enumerated.
14. **Browse marketplace static array** - contents and intent (aspirational vs current?) never documented.
