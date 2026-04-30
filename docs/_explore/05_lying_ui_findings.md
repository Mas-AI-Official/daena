# Lying UI / Lying API Findings

Scope: `D:\Ideas\Daena\backend\app` and `D:\Ideas\Daena\frontend\src` only.
Generated: 2026-04-30. Cross-reference: `Daena\CLAUDE.md` Rule 17 (ADR-001 Honesty + Persistence + Visibility, locked 2026-04-29).

Note: ADR-001 already deleted the worst offender (`RuntimeSwapper.DEFAULT_RUNTIMES`). This pass reports what survives that refactor - patterns where the UI/API still claims a capability is live without verifying it.

## Frontend lies

| file:line | pattern | excerpt | why it lies |
|---|---|---|---|
| `frontend\src\components\chat\DaenaAvatar.tsx:121` | `Math.random()` | "sizeMult: 0.7 + Math.random() * 0.6," | Random visual jitter, not data. Not a lie (purely aesthetic), recorded for completeness. |
| `frontend\src\pages\ScanWalkthroughPage.tsx:192` | `Math.random()` | "Math.random().toString(36).slice(2, 8)" | Generates a fake-looking ID for client-side log entries - not synced to the backend, so the user sees an "id" that the server has never heard of. |
| `frontend\src\pages\settings\SettingsGeneral.tsx:266` | hardcoded "imported" tag | "tags: ['imported', 'user-context', 'migration']" | The tag is appended client-side regardless of whether the import call actually succeeded. |
| `frontend\src\pages\settings\SettingsGeneral.tsx:269` | optimistic success toast | "Your data has been imported into Daena memory!" | Toast fires on the same code path as the tag append above; no inspection of the response body. |
| `frontend\src\pages\connections\McpServersPanel.tsx:296` | string-prefix-based status | "Alive" prefix decides Callable/Not callable | `probe[entry.server_key].startsWith('Alive')` - any backend message starting with "Alive" prints the green Callable pill. Stringly-typed status. |
| `frontend\src\pages\connections\McpServersPanel.tsx:369` | name-only liveness | "plugin.mcp_package && livePackages.has(plugin.mcp_package)" | "Installed" badge fires when a package name appears in the registry - never verifies the server responds. |
| `frontend\src\pages\connections\McpServersPanel.tsx:218` | toast lies on first success | "${serverKey} is callable" | Posted on the basis of a single `tools/list` reply; row state is not persisted back to a backend "callable" flag, so a refresh reverts the badge. |
| `frontend\src\pages\connections\PluginsCatalogBrowser.tsx:98` | hardcoded copy | "Skill pack only. Xcode/macOS tooling is not callable from this Windows Daena runtime." | This message is fired purely from a string match on platform name, not by introspecting whether the adapter is wired. |
| `frontend\src\pages\security\SecurityOverview.tsx:222` | dictionary-driven badge | "Object.entries(opsec.stealth_tools_installed).map" | Renders "installed/missing" purely from the dict the backend returned. The opsec endpoint behind it (see backend section) does not actually probe each binary. |
| `frontend\src\components\chat\RuntimeSwapper.tsx:29-43` | `STATUS_DOT_CLASS` lookup | "online: 'runtime-dot-online'" | The dot color is mapped from whatever string the backend put in `runtime.status`. Backend returns ONLINE based on binary presence alone, so the dot lies for every CLI runtime that's installed but not authenticated. |
| `frontend\src\pages\settings\SettingsDeveloper.tsx:90` | static "Not connected" | "<Badge variant=\"warning\" size=\"sm\">Not connected</Badge>" | Hardcoded string, no probe. Tells the user a state without checking. |
| `frontend\src\pages\connections\ConnectionsConnectors.tsx:277` | binary connected/not pill | "{connected ? 'Connected' : 'Not connected'}" | The `connected` boolean reduces to "instance row exists in DB" - it does NOT mean the connector responds. See backend `_status_for_install`. |
| `frontend\src\pages\connections\ConnectionsConnectors.tsx:608` | aggregate "live" claim | "${liveMcpCount} plugins live and callable right now" | "live and callable" is a strong claim; underneath, `isLiveConnector` is a `Set.has()` over MCP registry rows. |
| `frontend\src\pages\connections\OAuthSetupModal.tsx:81` | optimistic success | "${mcp.name} installed. The MCP server will prompt you to sign in..." | Shown on POST success regardless of whether the MCP server was ever spawned/probed. |

## Backend lies

| file:line | pattern | excerpt | why it lies |
|---|---|---|---|
| `backend\app\services\connection_service.py:139-143` | `_status_for_install` returns CONNECTED | "if cls._is_no_auth_connector(connector): return ConnectorStatus.CONNECTED.value" | Marks connector CONNECTED when `auth_type=='none'` AND `config_schema.callable_without_auth=True`. The flag is metadata; nobody verifies a Daena adapter exists. |
| `backend\app\services\connection_service.py:142` | credentials presence implies CONNECTED | "if credentials: return ConnectorStatus.CONNECTED.value" | A credentials dict - even an unverified one - flips the status to CONNECTED without a probe of the upstream. |
| `backend\app\services\runtimes\adapters\claude_code.py:182-186` | health = installed | "if not await self.check_installed(): return RuntimeStatus.NOT_INSTALLED; return RuntimeStatus.ONLINE" | "Health" only checks the binary exists; never runs an LLM round-trip. CLI may be expired (`loggedIn: false`) yet status is ONLINE. |
| `backend\app\services\runtimes\adapters\codex.py:93-97` | health = installed | "if not await self.check_installed(): return RuntimeStatus.NOT_INSTALLED; return RuntimeStatus.ONLINE" | Same pattern - binary present = ONLINE, no auth or RPC check. |
| `backend\app\services\runtimes\adapters\gemini_cli.py:59-63` | health = `which gemini` | "return shutil.which(\"gemini\") is not None" + "return RuntimeStatus.ONLINE" | Comment even admits "gemini --version hangs when not authenticated" - so they skip the auth probe AND still report ONLINE. |
| `backend\app\services\runtimes\adapters\grok_cli.py:49-53` | health = installed | "if not await self.check_installed(): return RuntimeStatus.NOT_INSTALLED; return RuntimeStatus.ONLINE" | Same as above. |
| `backend\app\services\runtimes\adapters\mcp_bridge.py:88-93` | health = installed | "installed = await self.check_installed(); ... return RuntimeStatus.ONLINE" | Even the MCP bridge - whose entire job is to verify a server can be talked to - declares ONLINE on binary presence. |
| `backend\app\services\benchmarks\suite.py:91-107` | "measure overhead" via no-op | "await asyncio.sleep(0)  # Placeholder for actual SecurityGate call" | Function pretends to measure pipeline-stage overhead. Each stage is `asyncio.sleep(0)` - measurement is structurally meaningless. Repeats 8+ times: security_gate, query_understanding, governance_check, cost_preflight, model_router. Reports near-zero ms as if the pipeline were instantaneous. |
| `backend\app\services\daena_vp.py:485` | placeholder provider | "provider=ModelProvider.ANTHROPIC,  # placeholder" | A type-shape filler that the rest of the function depends on. If hit, the audit trail records a wrong provider. |
| `backend\app\services\dynamic_model_service.py:101` | placeholder provider | "provider=ModelProvider.OLLAMA,  # placeholder for unknown" | Failure path returns OLLAMA as a "default", so failed provisions are recorded as OLLAMA failures rather than unknown. |
| `backend\app\services\departments\security_operations_agent.py:67` | demo-only guard | "# demo runs inside a single worker process." | Comment indicates the "single-process demo" code path is in use even in production deployments. |
| `backend\app\services\chat_orchestrator.py:4155-4162` | demo mode forges responses | "Demo mode: return mock response instead of error" | When all real LLMs fail, `is_demo_mode()` injects a hardcoded keyword-matched mock string. Audit trail says provider="demo", model="demo-mock" but the chat UI streams it to the user as a normal assistant message. |
| `backend\app\services\extension_scanner.py:148` | "tools list" can be empty | "Missing = empty; frontend shows a placeholder so the user knows why." | Even when the manifest declares no tools, the extension is still emitted with `enabled=True`. The UI then renders a "tools" placeholder over an empty list. |
| `backend\app\api\v1\connector_install.py:160-161` | docstring still claims `connected: True` | "- none: ``{\"method\": \"none\", \"popup\": False, \"connected\": True}``" | Stale docstring documents the old lying behavior. The actual `_start_none` (line 686) raises HTTP 409 instead - but other tools/scripts may follow the docstring. Documentation lie. |
| `backend\app\services\agent_core\system_access.py:63,92,98` | `return True` after subprocess | "return True" (write_file/copy_file/move_file always claim success) | These return True unconditionally after `await asyncio.to_thread(...)`. If the underlying call raised it would propagate, but partial writes (file truncated, partial copy) still report True with no verification. |
| `backend\app\services\benchmarks\real_benchmarks.py:1502-1548` | repeated `return True` in eval scoring | (count: 5 occurrences across is_correct/grading helpers) | Several heuristic graders return True on partial-match conditions; the benchmark report aggregates these as if they were strict pass/fail, inflating the score. Example line 1502: "return True". |
| `backend\app\services\daenabot\vuln_scanner_agent.py:163` | localhost auto-pass | "return True, \"localhost/private (always allowed)\"" | Allowlists 127.0.0.1 / RFC1918 ranges without any policy check. UI says "scanned", which is true, but the scan was waved through. |

## Endpoints that lie about success

| route | file:line | excerpt | why it lies |
|---|---|---|---|
| `POST /connections/install` | `backend\app\api\v1\connections.py:323` | "return {\"success\": True, \"data\": {\"installed\": instances, \"count\": len(instances)}}" | The `installed` rows are DB inserts only; no upstream probe. Caller treats this as "the connector is now usable." |
| `GET /chat/...` (multiple) | `backend\app\api\v1\chat.py` (~12 endpoints, e.g. lines 344, 369, 390, 403, 425, 439, 536, 554) | repeating "{\"success\": True, \"data\": ...}" | These are wrapper-success responses. Not lying when they reflect real DB state, but no endpoint has an explicit "what could be stale here" disclaimer. The pattern is consistent across `auth.py`, `agent_ops.py`, `execution.py`. |
| `POST /connections/extensions/install` | `backend\app\api\v1\connections.py:655` | docstring: "Writes the server config to Claude Desktop config file so it appears in the extensions list on next scan, then persists the tenant-scoped MCP row" | Returning success means "we wrote the JSON file"; it does NOT mean "we ran the MCP server and it responded." The frontend toast says "MCP installed and persisted" which the user will read as "now usable." |
| `POST /connections/extensions/{server_key}/probe-auth` | `backend\app\api\v1\connections.py:877` | "Calls the MCP's standard ``tools/list`` over stdio." | This one IS real - included as the counter-example. Probe actually spawns a stdio session. |
| `POST /connectors/{slug}/install/start` (auth=none) | `backend\app\api\v1\connector_install.py:686-704` | "raise HTTPException(status_code=409, detail=\"This catalog row is a skill pack only...\")" | Behavior is honest. But the function-level docstring at line 160-161 STILL documents `connected: True` for this branch (documentation lie that misleads downstream consumers). |

## Buttons that lie about action (no handler)

No `onClick={() => {}}`, `onClick={() => alert(...)}`, or `disabled={true}` patterns were found in `frontend\src` - those classic dummy patterns are absent.

The lying-button category in this codebase is more subtle: buttons that fire a real network call but the call's success means less than the button label promises.

| file:line | button text | what it actually does |
|---|---|---|
| `frontend\src\pages\connections\McpServersPanel.tsx:407` | "Install MCP" | Calls `POST /connections/extensions/install` which writes a JSON config file. Does NOT spawn or probe the server. Badge then flips to "Installed" because the package name appears in the registry. |
| `frontend\src\pages\connections\McpServersPanel.tsx:353` | "Import to Daena" | Calls `/mcp-sync/import` which scans + inserts a registry row. "Imported" status thereafter does NOT mean the server is alive. |
| `frontend\src\pages\connections\McpServersPanel.tsx:312` | "Test" | This one IS honest - runs `probe-auth` which actually contacts the server. Counter-example. |
| `frontend\src\pages\connections\ConnectionsConnectors.tsx` (Install Recommended) | "Install Recommended" | Calls `install_default_instances` → service rows inserted with status from `_status_for_install`. Each row's "Connected" claim depends on the lying status function. |

## Status badges based on hardcoded state

| file:line | badge | hardcoded source |
|---|---|---|
| `frontend\src\components\chat\RuntimeSwapper.tsx:29-43` | online/offline/error/rate_limited dot | Status comes from backend `RuntimeStatus` enum. Backend hands out ONLINE based on binary presence. The dot is honest about WHAT the backend said and dishonest about what that means. |
| `frontend\src\pages\connections\McpServersPanel.tsx:379` | "Installed" pill | `livePackages.has(plugin.mcp_package)` - name match, not health |
| `frontend\src\pages\connections\McpServersPanel.tsx:296` | "Callable" / "Not callable" pill | `probe[entry.server_key].startsWith('Alive')` - string-prefix check |
| `frontend\src\pages\security\SecurityOverview.tsx:222-231` | per-tool "installed/missing" | `opsec.stealth_tools_installed[tool]` boolean from backend; backend opsec endpoint relies on path lookups, not exec |
| `frontend\src\pages\connections\ConnectionsConnectors.tsx:174` | "Live" indicator | `isLive` flag piped down from MCP registry membership only |
| `frontend\src\pages\settings\SettingsLLM.tsx:91` | "connected via subscription" | Joins names from `subscriptions.filter((s) => s.is_authenticated)` - the `is_authenticated` flag itself can come from a CLI's lying response (Linux Claude Code reporting loggedIn=true after token expiry - see global CLAUDE.md). |

## Probe / health / test methods that don't actually probe

| file:line | method | what it skips |
|---|---|---|
| `claude_code.py:182` | `check_health` | No `claude --print "ping"` round-trip; only binary presence |
| `codex.py:93` | `check_health` | Same - `--version` only |
| `gemini_cli.py:59` | `check_health` | Even more lax: `shutil.which("gemini") is not None` |
| `grok_cli.py:49` | `check_health` | Same as claude_code |
| `mcp_bridge.py:88` | `check_health` | Same - does not call `tools/list` |
| `connection_service.py:131` | `_status_for_install` | Returns CONNECTED based on `auth_type` + credentials presence, never probes the upstream |
| `benchmarks\suite.py:80-115` | "Measure end-to-end time" | All five pipeline stages are `asyncio.sleep(0)` placeholders. The reported overhead is structurally zero. |

The legitimate probes in the codebase (counter-examples, NOT lying):
- `backend\app\services\runtimes\adapters\ollama_adapter.py:58-66` - actually GETs `/api/tags`
- `backend\app\api\v1\connections.py:877-893` - actually opens an MCP stdio session
- `backend\app\services\dynamic_model_service.py:111-113` - actually calls `provider.health_check()`

## Top 10 worst offenders ranked by user-visible deception

1. **CLI runtime adapters (claude_code / codex / gemini_cli / grok_cli / mcp_bridge) - `check_health` returns ONLINE on binary presence.** Five files, identical pattern. The chat header dot is green for runtimes that will fail the next `check_subscription()` call. Highest blast radius - directly contradicts the value prop "Choose your brain, unleash the full system."

2. **`connection_service._status_for_install` (lines 131-143).** The single most misleading function in the backend: emits CONNECTED for any no-auth-flagged catalog row OR any credentials-present row. Drives the entire Connections page status pills.

3. **`benchmarks/suite.py` overhead measurement (lines 80-115).** Pretends to measure governance pipeline cost; uses `asyncio.sleep(0)` placeholders. Any benchmark report based on this is structurally zero overhead.

4. **`McpServersPanel.tsx:296` - "Callable" pill via string-prefix.** `probe[...].startsWith('Alive')` is a stringly-typed health check. Not persisted (refresh wipes it), not retried, not periodic. The pill goes stale silently.

5. **`chat_orchestrator.py:4155` - Demo mode forges assistant responses.** When real LLMs all fail and `DEMO_MODE=true`, a hardcoded keyword-matched mock streams to the user as a normal message. Auditable as `provider="demo"` but the user has no UI signal.

6. **`McpServersPanel.tsx:407` - "Install MCP" writes JSON, doesn't spawn server.** Badge flips to "Installed" purely from package-name match; user has no way to know the server hasn't been attempted.

7. **`SettingsLLM.tsx:91` - "connected via subscription" trusts CLI auth flag.** Linux Claude Code is documented (in global CLAUDE.md) to report `loggedIn=true` for expired tokens. UI reproduces that lie verbatim.

8. **`connector_install.py:160-161` docstring still documents `connected: True`** for `auth=none`. Behavior was fixed (line 686 raises 409); the docstring lies and any tooling that reads the docstring will be misled.

9. **`vuln_scanner_agent.py:163` - `return True, "localhost/private (always allowed)"`.** Scan history shows the address was scanned; nothing tells the operator the policy check was waved.

10. **`SecurityOverview.tsx:222` "stealth_tools_installed" mapping.** Renders "installed/missing" from a backend dict. The backend opsec endpoint behind it (referenced but not opened in this scan) determines presence by lookup, not by exec - so a corrupted binary still shows green.
