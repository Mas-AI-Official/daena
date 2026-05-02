# PR-CONN-MCP-PROBE Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Builds on:** `PR_CONN_PLUGIN_PARITY_UX_REPORT.md` (commit `3329069`)

> **Thesis.** The Plugins marketplace looked right after the parity
> PR; what was missing was real callability proof. Until now,
> ``kind=mcp_server`` rows returned `probe_unavailable` from the V2
> probe registry, so cards stayed at "Available" / "Setup guide" even
> after Discover imported them. This PR ships a real stdio MCP probe
> using the official `mcp` Python SDK (already in the codebase via
> `mcp_invoker.py`) so the **Test** button on an MCP card actually
> performs `initialize` + `tools/list` and flips
> `callable=true` only when the server returns >= 1 usable tool.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| 1. No production deploy | Yes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes |
| 3. No `vault --apply` | Yes |
| 4. No V1 file deletions | Yes |
| 5. No secrets printed or committed | Yes -- pinned by `TestMcpProbeNoSecretLeak` (sentinel-secret audit) |
| 6. No external scans | Yes |
| 7. No external messages | Yes |
| 8. No auto-installs of MCP packages | Yes -- `binary_not_found` is the honest failure state when a package is missing; the probe never runs `npm install` or `npx -y` opportunistically |
| 9. No callable claim without probe | Yes -- `success=True` requires both `initialize` AND `tools/list` to return >= 1 tool |
| 10. No new primary tabs | Yes |
| 11. No marketplace UI rewrite | Yes -- frontend unchanged this PR |
| 12. No arbitrary command execution | Yes -- shell-metachar guard rejects pipelines (`;`, `&`, `|`, `>`, `<`, backtick, `$(`); only `command + args` whitelist runs via `StdioServerParameters` |

Project Rule 12 (no em-dashes): **0** added across all files.

---

## 1. Probe design

### 1.1 Files

| File | Status | Lines |
|---|---|---|
| `backend/app/services/connection_v2/probes/mcp_server_probe.py` | A | +345 (NEW) |
| `backend/app/services/connection_v2/probes/__init__.py` | M | +6 / -0 (wires `install_mcp_server_probe()`) |
| `backend/tests/test_mcp_server_probe.py` | A | +375 (NEW, 14 tests) |
| `backend/tests/fixtures/fake_mcp_servers/__init__.py` | A | +20 (NEW) |
| `backend/tests/fixtures/fake_mcp_servers/fake_mcp_ok.py` | A | +75 (NEW) |
| `backend/tests/fixtures/fake_mcp_servers/fake_mcp_no_tools.py` | A | +35 (NEW) |
| `backend/tests/fixtures/fake_mcp_servers/fake_mcp_init_fail.py` | A | +35 (NEW) |
| `backend/tests/fixtures/fake_mcp_servers/fake_mcp_init_hang.py` | A | +15 (NEW) |
| `backend/tests/fixtures/fake_mcp_servers/fake_mcp_crash.py` | A | +14 (NEW) |
| `backend/tests/fixtures/fake_mcp_servers/fake_mcp_echo_env.py` | A | +75 (NEW, env-passthrough sentinel) |

No protected files (Rule 18) touched. No frontend changes -- the
existing **Test** button already calls `/connections/v2/{id}/probe`
which now resolves to `McpServerProbe.run()` for `kind=mcp_server` rows.

### 1.2 Probe class

`McpServerProbe(Probe)` -- registered for `ConnectionKind.MCP_SERVER`.

```python
class McpServerProbe(Probe):
    kind = ConnectionKind.MCP_SERVER

    def __init__(self, timeouts: McpProbeTimeouts | None = None) -> None:
        self.timeouts = timeouts or DEFAULT_TIMEOUTS

    async def run(self, row: ConnectionV2) -> ProbeResult:
        # 1. Transport gate -> unsupported_transport
        # 2. Config gate    -> config_missing
        # 3. shutil.which   -> binary_not_found
        # 4. Build env (NAMES from row.config['env_var_names'],
        #               VALUES from os.environ ONLY)
        # 5. stdio_client(StdioServerParameters)
        #    -> ClientSession.initialize() (init_t timeout)
        #    -> session.list_tools()       (list_t timeout)
        # 6. >= 1 tool -> success + capabilities
        # 7. 0 tools   -> no_tools failure
```

### 1.3 Step budget

`McpProbeTimeouts(spawn=8.0, initialize=8.0, tools_list=8.0, cleanup=5.0)`

* Each step is wrapped in `asyncio.wait_for`; a hung MCP can NEVER
  block the request beyond `spawn + initialize + tools_list + 1.0s`
  (the +1.0s is the safety margin for the outer wait_for).
* Cleanup is implicit through the SDK's async context managers --
  `stdio_client` closes its subprocess pipes when exited; the
  subprocess receives an EOF on stdin and exits gracefully.
* Worst case total: ~25s. Far under any HTTP request timeout.

### 1.4 Truth ladder mapping

| Failure | dim |
|---|---|
| unsupported_transport, binary_not_found, command_failed, initialize_*  | reachable |
| (initialize covers auth too for stdio MCPs)                            | (folded) |
| tools_list_*, no_tools                                                  | callable |
| config_missing                                                          | configured |

On success: `reachable`, `authenticated`, and `callable` ALL flip true
inside `ConnectionRegistryV2.probe_and_record` (via the existing
state machine), and tool descriptors land in the
`ConnectionV2Capability` side table.

---

## 2. Supported transports

| Transport | Status this PR | Notes |
|---|---|---|
| stdio | **Supported** | Spawn via official `mcp` SDK, JSON-RPC over stdin/stdout |
| HTTP  | Returns `unsupported_transport` | Future PR-CONN-MCP-HTTP-PROBE -- needs allowlist + DNS rebinding defense per V2 §14 / ADR-002 |
| SSE   | Returns `unsupported_transport` | Same as HTTP |

`_is_stdio_transport(config)` is the gate. It accepts:
- `config["kind"] in {"mcp_stdio", "stdio"}`, OR
- `config["command"]` is set AND `config["url"]` is unset

Anything else returns `unsupported_transport` with `failure_dim="reachable"`.
The probe never tries to connect to URLs in this PR.

---

## 3. Success criteria

```
success = True
iff
  transport == stdio                             (gate)
  AND command exists on PATH                     (binary_not_found else)
  AND subprocess spawned                         (command_failed else)
  AND initialize round-trip completed in <init_t (initialize_timeout else)
  AND initialize did NOT raise                   (initialize_failed else)
  AND tools/list completed in <list_t            (tools_list_timeout else)
  AND tools/list did NOT raise                   (tools_list_failed else)
  AND tools list contains at least 1 tool        (no_tools else)
```

On success, `capabilities` is populated:

```python
[
  {"name": tool.name, "kind": "mcp_tool", "spec": {"description": ..., "input_schema": {...}}},
  ...
]
```

`ConnectionRegistryV2.probe_and_record` writes one
`ConnectionV2Capability` row per capability (keyed by name; idempotent
on rerun).

---

## 4. Failure states (founder spec, all implemented)

| Prefix | failure_dim | When |
|---|---|---|
| `binary_not_found` | reachable | `shutil.which(command)` returns None, OR command contains shell metachars and is rejected |
| `command_failed` | reachable | Subprocess crashed before MCP handshake (e.g. missing dependency, `npx -y bad-pkg`) |
| `initialize_timeout` | reachable | `session.initialize()` did not return in `init_t` seconds |
| `initialize_failed` | reachable | `session.initialize()` raised (JSON-RPC error, malformed response) |
| `tools_list_timeout` | callable | `session.list_tools()` did not return in `list_t` seconds |
| `tools_list_failed` | callable | `session.list_tools()` raised |
| `no_tools` | callable | Server initialized AND responded to tools/list, but the list was empty |
| `unsupported_transport` | reachable | `kind != mcp_stdio` AND `url` is set; HTTP / SSE in future PR |
| `config_missing` | configured | `kind == mcp_stdio` AND `command` is empty |

Each prefix is a constant exported from `mcp_server_probe.py`:
`FAIL_BINARY_NOT_FOUND`, `FAIL_COMMAND_FAILED`,
`FAIL_INITIALIZE_TIMEOUT`, etc. Frontend can match on these prefixes
to render a distinct icon / message per failure class without parsing
free-form text.

---

## 5. Secret-handling proof

### 5.1 Env handling

```python
def _build_env(row):
    declared_names = list(row.config.get("env_var_names") or [])
    env = {}
    missing = []
    for name in declared_names:
        value = os.environ.get(name)
        if value:
            env[name] = value
        else:
            missing.append(name)
    # PATH + minimal vars passthrough so npx / node / python can run
    for passthrough in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR",
                        "TEMP", "TMP", "HOME", "USERPROFILE",
                        "APPDATA", "LOCALAPPDATA"):
        if passthrough in os.environ and passthrough not in env:
            env[passthrough] = os.environ[passthrough]
    return env, missing
```

Crucially:
- Env VALUES come from `os.environ` ONLY. The probe NEVER re-reads
  `claude_desktop_config.json` (or any source CLI config file) at
  probe time. If the operator wants the MCP to receive a secret, they
  set it in Daena's environment.
- The catalog declared `env_var_names` is the only allowlist.

### 5.2 Logging

The structured `mcp_probe.starting` log line writes:
- `connection_id`
- `slug`
- `command` (resolved path)
- `args_count` (count, not values)
- `env_present_names` (NAMES, sorted)
- `env_missing_names` (NAMES, sorted)

It NEVER writes env values. Pinned by:

```python
def test_env_values_pass_through_but_not_logged(...):
    monkeypatch.setenv("FAKE_PROBE_SECRET_KEY", "sk-fake-do-not-leak-789...")
    ...  # run probe against fake_mcp_echo_env.py
    log_text = capsys.readouterr().out + .err
    assert "sk-fake-do-not-leak-789..." not in log_text  # value
    assert "FAKE_PROBE_SECRET_KEY" in log_text           # name only
```

### 5.3 failure_reason

`failure_reason` is sanitized through `_reason(prefix, detail)` which:
- Truncates at 240 chars
- Strips newlines
- Has no env-substitution path

`test_failure_reason_never_contains_env_values` plants a sentinel and
asserts it does not appear in `failure_reason` even on the
crash-failure path.

### 5.4 capabilities

`_capabilities_from_tools(tools)` reads ONLY `name`, `description`,
and `inputSchema` from each MCP `Tool` descriptor. It NEVER reads
from `os.environ`, `os.getcwd`, or any state outside the tool object.

---

## 6. Tests run

### 6.1 New probe tests (14 / 14 PASS)

```text
$ pytest tests/test_mcp_server_probe.py
  TestMcpProbeHappyPath                    1/1   PASS
  TestMcpProbeNoTools                      1/1   PASS
  TestMcpProbeInitializeFailure            1/1   PASS
  TestMcpProbeInitializeTimeout            1/1   PASS  (uses 1s timeout, runs in ~2s)
  TestMcpProbeCommandCrash                 1/1   PASS
  TestMcpProbeBinaryNotFound               1/1   PASS
  TestMcpProbeUnsupportedTransport         2/2   PASS  (HTTP + shell-pipeline guards)
  TestMcpProbeConfigMissing                1/1   PASS
  TestMcpProbeNoSecretLeak                 2/2   PASS  (sentinel + crash-path)
  TestMcpProbeRegistryWiring               2/2   PASS
  TestMcpProbeDefaults                     1/1   PASS
  ----------------------------------------
  total                                   14/14  PASS in 3.80s
```

### 6.2 Full V2 regression (210 / 210 PASS, was 196)

```text
$ pytest tests/test_connection_v2*.py tests/test_phase7_*.py tests/test_mcp_server_probe.py
  tests/test_connection_v2.py                       22/22  PASS
  tests/test_connection_v2_probe_truth.py            8/8   PASS
  tests/test_connection_v2_reconciliation.py        12/12  PASS
  tests/test_connection_v2_seed_import.py           16/16  PASS
  tests/test_connection_v2_ux_rescue.py             14/14  PASS
  tests/test_connection_v2_marketplace.py           93/93  PASS
  tests/test_phase7_lifespan_seed.py                 3/3   PASS
  tests/test_phase7_provider_probes.py              28/28  PASS
  tests/test_mcp_server_probe.py                    14/14  PASS  (NEW)
  ----------------------------------------------------------
  combined                                         210/210 PASS in 8.67s
```

### 6.3 Live HTTP smoke

* Backend restarted to pick up the new probe (PID 23952 -> fresh).
* `GET /openapi.json` confirms `/api/v1/connections/v2/{connection_id}/probe`
  is registered.
* `install_all_probes()` (called from `app/main.py:627` lifespan)
  registers `McpServerProbe` for `kind=mcp_server`. Verified via
  in-process probe-registry inspection: `PROBE_REGISTRY['mcp_server']`
  is `<McpServerProbe>` after a fresh import.

End-to-end smoke (operator action): create a V2 row pointing at the
fake MCP and probe it. The unit test `test_initialize_and_tools_list_succeed`
covers the same path end-to-end inside the probe class:

```python
row = _row(command=sys.executable, args=[fake_mcp_ok.py path])
result = await McpServerProbe().run(row)
assert result.success is True
assert sorted(c["name"] for c in result.capabilities) == ["echo", "ping"]
```

The unit test invokes the probe with the same code path the V2
endpoint uses (`run_probe(row)` in `probe.py`), so the only
additional thing the live smoke would prove is the HTTP layer --
which is already exercised by `TestMarketplaceLiveSmoke` from the
prior PR.

### 6.4 Frontend tsc

```text
$ cd frontend && npx tsc --noEmit
EXIT=0
```

No frontend changes this PR.

### 6.5 Em-dash hygiene (project Rule 12)

Per-file `git diff` em-dash count across all 10 new files: **0**.

---

## 7. How an operator uses this end-to-end

1. Operator sets `GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...` in Daena's
   environment (or any other env vars the catalog declares).
2. Operator opens `/connections` -> Plugins tab -> finds **GitHub** card.
3. Card status is "Available" because no V2 row exists yet.
4. Operator clicks **Discover installed tools** in the page header.
   - If they have GitHub MCP configured in Claude Code / Codex / Gemini
     CLI, the seeder imports it as a V2 row.
   - The card flips to "Installed" status.
5. Operator clicks the card -> drawer opens -> clicks **Test**.
6. The frontend calls `POST /api/v1/connections/v2/{id}/probe`.
7. `McpServerProbe.run(row)` spawns `npx -y @modelcontextprotocol/server-github`
   with the env vars from the parent process.
8. JSON-RPC `initialize` round-trip completes in ~500ms.
9. JSON-RPC `tools/list` returns ~5 tools.
10. Probe returns `success=True, capabilities=[{name, kind, spec}, ...]`.
11. `ConnectionRegistryV2.probe_and_record`:
    - Sets `reachable=true`, `authenticated=true`, `callable=true`
    - Persists each tool as a `ConnectionV2Capability` row
    - Computes new label "callable"
12. Frontend re-fetches the row and re-renders the card with
    "Connected" status pill, the tools count, and the last-checked
    timestamp.

If anything in steps 7-9 fails, the failure_reason carries one of
the 9 prefixes from §4 and the card honestly shows "Failed" with the
reason inline.

---

## 8. Remaining blockers for install / connect

This PR closes blocker B1 from prior PRs. Remaining:

| # | Blocker | Owner |
|---|---|---|
| ~B1~ | ~`McpServerProbe` (initialize + tools/list)~ | **DONE this PR** |
| B2 | `CliRuntimeProbe` (which + version) | PR-CONN-CLI-PROBE |
| B3 | `OAuthAppProbe` (refresh + userinfo) | PR-CONN-OAUTH-PROBE |
| B4 | OAuth flow wired through V2 (Connect button activates real flow) | PR-CONN-OAUTH-INSTALL |
| B5 | Safe MCP install endpoint (atomic write to a CLI's mcpServers config) | PR-CONN-MCP-INSTALL |
| B6 | `BrowserToolProbe` (spawn + capture exit code) | PR-CONN-BROWSER-PROBE -- could reuse this PR's stdio handler |
| B7 | DXT extension auto-import | PR-CONN-DXT-IMPORT |
| B8 | External catalog mirror (community submissions) | PR-CONN-CATALOG-EXTERNAL |
| B9 | Server-side OS detection | PR-CONN-OS-DETECT-SERVER |
| B10 | Vault-backed Configure modal in-page | PR-CONN-CONFIGURE-MODAL |
| B11 | HTTP / SSE MCP probe (allowlist + DNS rebinding defense) | PR-CONN-MCP-HTTP-PROBE |
| B12 | Source-CLI env passthrough opt-in (read claude_desktop_config.json env at probe time) | PR-CONN-MCP-ENV-OPTIN -- founder review required (secrets in process memory) |

---

## 9. Honesty audit (project Rule 17)

| Surface | Persistence | Failure visibility |
|---|---|---|
| Status pill "Connected" | V2 truth `callable=true` (database) | Pinned by `test_no_card_marked_connected_without_v2_truth` (prior PR) + this PR's success path |
| `failure_reason` in card / drawer | `connection_v2.callable_failure_reason` (database) | One of 9 documented prefixes; never carries env values |
| Last checked timestamp | `connection_v2.callable_at` / `reachable_at` (database) | Visible in PluginCardView + drawer |
| Capabilities count | `connection_v2_capability` row count | Persisted on success; cleared/stale on failure |
| Tool list (in drawer) | `connection_v2_capability` rows | Future drawer enhancement; today shown via probe outcome immediately after Test |
| Install command | Catalog `command_template` (source-tree) | Setup-guide drawer disclaimer "Daena does not execute install commands automatically" |

Nothing in this PR is a "looks complete but does nothing" surface.

---

## 10. Commit message

```
canonicalization: add real MCP probe for plugin marketplace
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting next founder direction.**
