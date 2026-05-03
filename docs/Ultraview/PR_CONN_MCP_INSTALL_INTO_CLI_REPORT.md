# PR-CONN-MCP-INSTALL-INTO-CLI -- Safely install MCP plugins into CLI configs

**Branch:** rebuild-connections-mcp-runtime
**Date:** 2026-05-02
**Founder brief:** Add a safe MCP install flow from the Daena Plugins
marketplace into supported local CLI MCP configs (Claude Desktop /
Claude Code / Codex / Gemini CLI). Browse plugin -> Install/Setup ->
Daena writes the correct MCP config safely -> Test -> Connected only
if MCP probe succeeds.

---

## TL;DR

Daena now writes MCP catalog entries into the right CLI config file
through two new endpoints + a 4-step install drawer.

- **Backend writer** (`cli_mcp_writer.py`, ~565 lines): per-target spec
  table, safe binary path resolution, backup + atomic rename, idempotent
  JSON merge. Never writes secret values; never overwrites a malformed
  config; never auto-installs npm/pip/docker packages.
- **Two new endpoints** on `connections_v2`:
  - `POST /marketplace/install-plan/{entry_id}/preview` -- diff only
  - `POST /marketplace/install-plan/{entry_id}/apply` -- backup + atomic
    write + V2 row import + optional post-apply MCP probe
- **4-step install drawer** (`MCPInstallDrawer.tsx`, ~470 lines):
  Choose CLI -> Preview diff -> Confirm -> Test. "Connected" pill ONLY
  after the MCP probe succeeds.
- **28 writer unit tests + 9 endpoint integration tests** = 37 new
  passing tests. Combined V2 regression: 163/163.
- Zero em-dashes added. Zero V1 file touched. Zero new top-level tabs.

**Hard rules honored:** no production deploy, no V2 flag flip, no
vault apply, no V1 deletion, no secret printing/writing, no external
scans/messages, no npm/pip/docker auto-install, no overwrite without
backup + atomic rename, callable=true requires the post-apply probe
to prove it, no new tabs, no marketplace UI rewrite.

---

## Supported target configs

| Target | Display | Default candidate paths (first match wins) | Block key |
|---|---|---|---|
| `claude_desktop` | Claude Desktop | Windows: `%APPDATA%/Claude/claude_desktop_config.json` -> `~/AppData/Roaming/Claude/claude_desktop_config.json`; macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`; Linux: `~/.config/Claude/claude_desktop_config.json`; WSL: bridges through `/mnt/c/Users/<win>/AppData/Roaming/Claude/...` | `mcpServers` |
| `claude_code` | Claude Code (CLI) | `~/.claude.json`, `~/.claude/mcp.json` | `mcpServers` |
| `codex` | Codex CLI | `~/.codex/config.json`, `~/.codex/mcp.json` | `mcpServers` |
| `gemini_cli` | Gemini CLI | `~/.gemini/settings.json`, `~/.gemini/mcp_servers.json` | `mcpServers` |

Resolution policy: writer prefers the FIRST candidate that exists. If
none exist AND `allow_create=true` is passed, it creates the FIRST
candidate. If none exist AND `allow_create=false`, it returns
`config_path_missing` -- no silent file creation.

WSL bridging (claude_desktop): when the backend runs in WSL but the
operator installed Claude Desktop on the Windows side, the writer also
checks `/mnt/c/Users/<win-user>/AppData/Roaming/Claude/...`. Same logic
the read-only `mcp_sync.detector` already uses. This is **detection
only** for now -- writes target the Linux-side path first; the WSL
bridge candidate is offered when no Linux-side candidate exists.

---

## Preview / apply endpoint behavior

Both endpoints share a common `McpInstallTarget` body:

```json
{
  "target": "claude_code",         // one of the 4 supported targets
  "allow_create": false,            // create config file if missing
  "probe_after_apply": false        // run McpServerProbe after write
}
```

### POST `/marketplace/install-plan/{entry_id}/preview`

**Never touches the filesystem.** Returns the proposed JSON block, the
existing block (if any), the action (`create` / `update` / `skip` /
`create_file` / `failed`), required env var NAMES, risk warnings, and
`apply_allowed` (so the UI can disable the Confirm button when the
operator's config is malformed or the entry has unresolved
placeholders like `<ALLOWED_ROOT>`).

Status codes:
- `200` -- success or structured failure (check `data.failure_reason`)
- `400` -- `install_unsupported_kind` (catalog entry isn't `mcp_server`)
- `404` -- `catalog_entry_not_found`
- `422` -- target is not one of the 4 supported targets

### POST `/marketplace/install-plan/{entry_id}/apply`

**Performs the actual write.** Sequence:

1. Re-runs preview internally to confirm `apply_allowed`.
2. Reads the target file (or treats missing as empty when
   `allow_create=true`).
3. If existing file has malformed JSON: returns `failed` +
   `config_parse_error`. **The file is NEVER overwritten.**
4. Builds `new_data = {**existing, "mcpServers": {**existing_block,
   server_name: proposed_block}}` -- preserves every unrelated key.
5. If file existed: copies original bytes to
   `<path>.daena-backup-<TS>.json`.
6. Writes new JSON to a temp file in the SAME directory + `os.replace`
   (atomic on POSIX + Windows since Python 3.3).
7. Imports / updates the matching `ConnectionV2(kind=mcp_server)` row
   (idempotent on `(tenant_id, mcp_server, slug=mcp-{server_name})`).
8. If `probe_after_apply=true` AND the catalog entry's
   `probe_type=="mcp_initialize"`: runs `McpServerProbe` against the
   imported row immediately and returns the outcome inline.

Response shape:

```json
{
  "success": true,
  "data": {
    "target": "claude_code",
    "target_display_name": "Claude Code (CLI)",
    "config_path": "/home/op/.claude.json",
    "server_name": "time",
    "action": "create_file",
    "backup_path": null,
    "failure_reason": null,
    "required_env_vars": [],
    "v2_row_id": "abc-...",
    "v2_label": "configured",
    "post_apply_probe": {
      "success": true,
      "label_after": "callable",
      "failure_dim": null,
      "failure_reason": null
    }
  }
}
```

---

## Backup + atomic write behavior

| Stage | What happens |
|---|---|
| Preview | NO IO. Returns the BACKUP filename Daena would use (`<path>.daena-backup-<TS>.json`) so the operator sees it in the diff before clicking Confirm. |
| Apply (file exists) | Copies current bytes to `<path>.daena-backup-<UTC-TIMESTAMP>.json`, then writes via temp + `os.replace`. Backup is left in place after success -- operator manually restores if needed. |
| Apply (file missing, allow_create=true) | Creates parent directory, writes via temp + `os.replace`. NO backup (nothing to back up). |
| Apply (file exists but identical block) | Returns `skipped`. NO backup. NO write. |
| Apply (write raises OSError) | Temp file is unlinked. Original file is untouched (replace failed). Backup stays in place. Returns `write_failed: <ExcType>`. |

The writer NEVER touches files outside the target's candidate list,
NEVER follows symlinks to escape the parent directory, NEVER reads or
writes secret material.

---

## Idempotency behavior

Re-running apply with the same (target, entry) is safe:

| Run | Existing block | Result |
|---|---|---|
| 1 | absent | `created` (or `create_file` if file was new) + backup if file existed |
| 2 | identical to proposed | `skipped` + no backup + no write |
| 3 (after manual edit to differ) | differs from proposed | `updated` + backup + write |

Pinned by `TestApplyIdempotent.test_second_apply_skips`.

---

## Secret-handling proof

Founder rule 14: env values stay in environment / vault / Settings.
Daena never writes them to the CLI config.

**Implementation:**

- `build_mcp_block(entry)` produces ONLY `{command, args}`. No `env`
  field is ever populated. The MCP server inherits whatever env the
  CLI process has -- the operator sets required env vars in their
  shell BEFORE launching the CLI.
- The preview response carries `required_env_vars` as a list of NAMES
  (e.g. `["GITHUB_PERSONAL_ACCESS_TOKEN"]`) drawn from the catalog.
- The drawer shows a yellow advisory listing the names and instructs
  the operator to set them in their shell. Daena never asks the
  operator to paste a value into a form.

**Audit test** (`TestEnvVarsSurfaceAsNames`):

- Plants a sentinel value (`ghp_test_sentinel_should_not_leak_8765`)
  in the parent process env.
- Calls preview for `mcp-github` (which has `GITHUB_PERSONAL_ACCESS_TOKEN`
  in `required_env_vars`).
- Asserts:
  - `data.required_env_vars` contains the NAME.
  - The full JSON response payload does NOT contain the sentinel value.
  - `data.proposed_block` has no `env` key at all.

Both assertions pass.

**Defense in depth:**

- `parse_command_template` rejects shell metacharacters (`;|&><\`$()`),
  so a malicious catalog entry cannot smuggle a shell pipeline through
  the writer into someone's `claude_desktop_config.json`.
- `find_unresolved_placeholders` rejects entries with `<TOKEN>`
  placeholders (e.g. `mcp-filesystem`'s `<ALLOWED_ROOT>`). The operator
  must replace the placeholder in the catalog entry's
  `command_template` before apply -- defended at both preview and apply.
- Atomic write uses `tempfile.mkstemp(dir=parent)` + `os.replace`,
  guaranteeing the on-disk file is either the OLD content or the NEW
  content -- never partial.

---

## Frontend install flow

**No new tabs.** The Brain / Plugins / Advanced layout is unchanged.
The change is local to the plugin card's primary action:

```
Plugin card "Install" button (MCP entries with command_template only)
  -> opens MCPInstallDrawer
       Step 1: Choose target CLI (Claude Desktop / Claude Code / Codex / Gemini)
       Step 2: Preview diff (existing block vs proposed block + warnings)
                 - shows risk warnings when entry.risk_level == "high"
                 - shows env var NAMES when required_env_vars non-empty
                 - "Create config file" toggle when no candidate path exists
                 - parse-error message when target file is malformed
                 - Confirm button disabled until apply_allowed=true
       Step 3: Confirm + apply (backup + atomic write + V2 import + probe)
       Step 4: Test result
                 - Connected (green) only when post-apply probe succeeded
                 - Honest failure copy + env-var hint when probe failed
       Done -> dispatches `daena:retry-pending` so marketplace cards refresh
```

**Status pill rules:**

- "Connected" appears ONLY when `v2_truth.callable.value === true` AND
  no recent failure -- this is the existing PluginCard adapter; the
  install drawer doesn't override it.
- After a successful apply + probe, the V2 row's `callable` flips to
  true and the next marketplace-cards poll re-renders the card with
  the green pill. No frontend lying.

For non-MCP entries (CLI runtimes, providers, OAuth apps, skill packs)
the existing Setup Guide / Configure / Connect flows remain unchanged.

---

## Tests run

### New: `test_cli_mcp_writer.py` (28 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestParseCommandTemplate` | 6 | npx happy path; reject empty / shell pipelines; preserve `<TOKEN>` for placeholder check |
| `TestBuildMcpBlock` | 2 | env block omitted (founder rule 14); invalid template returns None |
| `TestServerNameFor` | 1 | strips `mcp-` prefix |
| `TestPreviewLifecycle` | 4 | create_file when file missing + allow_create; skip when matches; update when differs; create when block missing |
| `TestMalformedConfigFailsClosed` | 2 | preview returns `config_parse_error`; apply leaves malformed file untouched |
| `TestApplyPreservesUnrelatedKeys` | 1 | top-level keys + sibling MCP entries kept |
| `TestApplyBackup` | 2 | backup file created with original bytes; no backup on skipped apply |
| `TestAtomicWrite` | 1 | OSError during replace cleans temp file; original preserved |
| `TestAllowCreateGuard` | 2 | preview + apply refuse missing file without flag |
| `TestCodexTarget` | 1 | codex writes to `~/.codex/config.json` |
| `TestGeminiTarget` | 1 | gemini writes to `~/.gemini/settings.json` |
| `TestIdempotentApply` | 1 | second run = `skipped` + no backup |
| `TestEnvVarsSurfaceAsWarnings` | 1 | sentinel env value never leaks; preview warns operator with NAMES |
| `TestPlaceholderRejection` | 1 | `<ALLOWED_ROOT>` blocks both preview and apply |
| `TestTargetSpecTable` | 2 | all 4 targets have specs; unknown target returns None |

```
.venv/Scripts/python.exe -m pytest tests/test_cli_mcp_writer.py -q
# -> 28 passed in 0.29s
```

### New: `test_marketplace_install_endpoints.py` (9 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestPreviewHappyPath` | 1 | preview returns proposed_block + apply_allowed=true |
| `TestPreviewRejectsUnsupportedTarget` | 1 | invalid target -> 422 (Pydantic Literal) |
| `TestPreviewUnknownEntry` | 1 | bad entry_id -> 404 |
| `TestPreviewRejectsNonMcpKind` | 1 | cli_runtime / oauth_app -> 400 |
| `TestApplyHappyPath` | 1 | writes config + imports V2 row + returns label |
| `TestApplyIdempotent` | 1 | second call = `skipped` |
| `TestApplyWithProbe` | 1 | probe_after_apply runs McpServerProbe + returns outcome |
| `TestApplyMalformedConfig` | 1 | malformed JSON -> failed + file untouched |
| `TestEnvVarsSurfaceAsNames` | 1 | env sentinel never appears in response |

```
.venv/Scripts/python.exe -m pytest tests/test_marketplace_install_endpoints.py -q
# -> 9 passed
```

### Regression: V2 marketplace + all probes + writer

```
.venv/Scripts/python.exe -m pytest tests/test_connection_v2_marketplace.py
  tests/test_mcp_server_probe.py tests/test_cli_runtime_probe.py
  tests/test_cli_mcp_writer.py tests/test_marketplace_install_endpoints.py -q
# -> 163 passed in 12.59s
```

No pre-existing test failed after the new code landed. The MCP probe's
14-test suite, CLI probe's 19-test suite, and V2 marketplace's 93-test
suite all remain green.

### Frontend

```
cd frontend && npx tsc --noEmit
# -> exit 0 (clean)
```

`MCPInstallDrawer.tsx` (470 lines), updated `pluginCard.ts`,
`PluginCardView.tsx`, and `useMarketplace.ts` all type-check under
strict TypeScript.

---

## Files changed

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/services/connection_v2/cli_mcp_writer.py` | +565 | NEW: writer module (parse_command_template, build_mcp_block, preview_install, apply_install, atomic_write_json) |
| `backend/app/api/v1/connections_v2.py` | +172 / -2 | preview + apply endpoints; V2 row import + optional probe |
| `backend/app/schemas/connection_v2.py` | +21 | NEW: McpInstallTarget request body |
| `backend/tests/test_cli_mcp_writer.py` | +462 | NEW: 28 unit tests |
| `backend/tests/test_marketplace_install_endpoints.py` | +250 | NEW: 9 endpoint integration tests |
| `frontend/src/hooks/useMarketplace.ts` | +95 | NEW: previewMcpInstall + applyMcpInstall hooks + types |
| `frontend/src/pages/connections/MCPInstallDrawer.tsx` | +470 | NEW: 4-step install drawer (Choose / Preview / Confirm / Test) |
| `frontend/src/pages/connections/PluginCardView.tsx` | +20 / -2 | route MCP `install` action to MCPInstallDrawer |
| `frontend/src/pages/connections/pluginCard.ts` | +9 / -2 | surface `install` action for MCP entries with command_template |
| `docs/Ultraview/PR_CONN_MCP_INSTALL_INTO_CLI_REPORT.md` | NEW | this report |

Total: ~2000 lines added, ~10 lines deleted, 0 V1 file touched.

---

## Remaining blockers (deferred to future PRs)

| Future PR | Goal | Why deferred |
|---|---|---|
| `PR-CONN-OAUTH-CONNECT` | Wire the OAuth Connect flow inline (paste client_id/secret -> launch authorize URL -> capture callback -> import V2 row) | OAuth needs per-provider URL templates + state-token handling + redirect-uri validation. Out of scope for MCP install. |
| `PR-CONN-OAUTH-PROBE` | Real probe for `kind=oauth_app` rows (token introspection / refresh) | Per-provider introspection endpoints + refresh handling needed. |
| `PR-CONN-BROWSER-PROBE` | Real probe for `kind=browser_tool` rows | Needs sandboxed Playwright launch test; today browser cards reuse the MCP probe path because most browser tools ship as MCP servers (Playwright MCP, Chrome DevTools MCP). |
| `PR-CONN-MCP-INSTALL-PACKAGE` | After config write, auto-run `npm install` / `pip install` for the package the catalog declares | Founder rule 9 explicitly forbids auto-install in this PR. The operator copies the install command from the Setup notes. |
| `PR-CONN-MCP-WSL-WRITE` | Allow writing into `/mnt/c/Users/<win>/.../claude_desktop_config.json` from a WSL-side backend | Today the writer only OFFERS the WSL bridge candidate when no Linux-side candidate exists. Real bidirectional WSL writes need permission elevation handling. |
| `PR-CONN-MCP-CODEX-TOML` | Codex MCP config in TOML format (`~/.codex/config.toml`) | Today we write JSON only; Codex's TOML support depends on which CLI version the operator has. JSON is the safe lowest-common-denominator. |
| `PR-CONN-MCP-INSTALL-RESTORE` | UI button to restore from a `.daena-backup-<TS>.json` | Backups are written but the UI doesn't expose a one-click restore yet. Operator manually copies the backup file over for now. |

These are blockers for the "OAuth Connect" + "browser-tool live test"
flows. Each is small and well-scoped; none requires the V2 flag flip.

---

## Why this is the right shape

1. **Honest by construction.** Preview NEVER mutates. Apply ALWAYS
   backs up before overwriting AND uses atomic rename. Skipped applies
   produce no backup and no write. Failed applies leave the original
   file byte-identical. Pinned by 6 tests that read the file back
   after every code path.
2. **No model calls + no auto-install.** Writer is pure config IO. No
   subprocess invocations, no npm/pip/docker. Founder rule 9 is the
   default behavior, not a flag.
3. **Defense in depth.** Shell metachar rejection at parse time.
   Placeholder rejection at both preview AND apply. Malformed config
   refuses the write at both preview AND apply. Three independent
   guards against the same accident.
4. **Single dispatch point.** `_runtime_id` keys nothing -- per-target
   writer behavior is keyed by the `target` query parameter and the
   `TargetSpec` table. Adding a 5th CLI is one entry in
   `_build_targets()`; nothing else changes.
5. **Idempotent by design.** `apply_install` re-runs preview internally
   and returns `skipped` when the existing block matches. This means
   a button-mash, a flaky network retry, and a deliberate re-run all
   produce the same outcome.
6. **V2 truth still gates "Connected".** The drawer never lies. The
   green pill in Plugins ONLY appears after the post-apply probe
   round-trips MCP `initialize` + `tools/list` -- the same probe the
   manual Test button calls. Founder rule 17 (honesty) is respected
   from button click through to status display.

---

## Commit

```
canonicalization: safely install MCP plugins into CLI configs
```

Stops here. Awaiting next direction.
