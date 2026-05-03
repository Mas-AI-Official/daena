# PR-CONN-MCP-INSTALL-RESTORE -- Restore MCP backups created by the install flow

**Branch:** rebuild-connections-mcp-runtime
**Date:** 2026-05-02
**Founder brief:** Add a safe restore flow for MCP install backups
created by PR-CONN-MCP-INSTALL-INTO-CLI. The plugin marketplace
should feel powerful but recoverable.

---

## TL;DR

The MCP install flow lays down `<config>.daena-backup-<TS>.json`
files before each overwrite. This PR adds the counterpart:

- **Backend** -- one new module (`cli_mcp_backups.py`) with strict
  filename validation, in-directory enforcement, JSON parse-check,
  and pre-restore-backup-of-current safety. Re-uses the writer's
  `atomic_write_json` helper (one source of truth for "how Daena
  writes a JSON file safely").
- **Two new endpoints**:
  - `GET /api/v1/connections/v2/marketplace/install-backups?target=...`
  - `POST /api/v1/connections/v2/marketplace/install-backups/restore`
- **Frontend** -- new `MCPRestoreDrawer.tsx` component (3-step:
  list / confirm / done) wired into the existing
  `MCPInstallDrawer` via a discrete "Restore previous backup..."
  link. No new tabs.
- **24 new tests** for the backup module + endpoints, all pass; **339
  V2 + probe + writer regression** all pass; frontend tsc clean.
- Zero em-dashes added. Zero V1 file deleted. Zero new top-level tabs.

**Hard rules honored:** no production deploy, no V2 flag flip, no
vault apply, no V1 deletion, no secret printing, no external scans/
messages, no auto-install, no overwrite without a fresh pre-restore
backup, no exposing secret values from restored config.

**Test results:**
- `test_cli_mcp_backups.py`: 24/24 passed.
- Combined V2 + probe + writer + backups regression: 339/339 passed.
- Frontend `tsc --noEmit`: 0 errors.

---

## Backup discovery behavior

For a given target (`claude_desktop` / `claude_code` / `codex` /
`gemini_cli`):

1. Resolve the target's config path the same way the writer does:
   prefer the FIRST candidate that exists; if none exist, use the
   FIRST candidate's path (so backups left behind after the operator
   manually deleted the live config are still discoverable).
2. List every file in the config's parent directory whose name
   matches the strict pattern:
   ```
   <config_basename>.daena-backup-YYYYMMDDTHHMMSSZ.json
   ```
3. Skip:
   - Files with path components in their name (defense against
     directory traversal entries that somehow ended up in the dir).
   - Files whose timestamp segment doesn't match the strict shape.
   - Files for a DIFFERENT config basename (so listing claude_code's
     backups doesn't surface codex's).
   - Anything that's not `.json`.
4. For each kept entry: read the file, measure size, attempt JSON
   parse. The list payload returns ONLY:
   ```json
   {
     "filename": ".claude.json.daena-backup-20260502T203134Z.json",
     "timestamp": "2026-05-02T20:31:34+00:00",
     "size_bytes": 1234,
     "valid_json": true
   }
   ```
   File contents NEVER appear. Only the metadata above does.
5. Sort newest-first.

**Empty-list state.** If no backups exist (fresh install), the list
returns successfully with `backups: []` and the drawer renders
"Daena hasn't written any backup files for X yet." Honest signal,
no fake entries.

---

## Restore safety rules

Every step fail-closed; any rule violation aborts the write before
the live config is touched.

| Step | Rule | Failure prefix |
|---|---|---|
| 1 | Target must be one of the 4 supported CLIs | `target_unsupported` |
| 2 | Backup filename must match `<config>.daena-backup-<TS>.json` exactly | `backup_invalid_filename` |
| 3 | Backup filename must NOT contain `/`, `\`, `.`, or `..` (rejects path traversal) | `backup_invalid_filename` |
| 4 | Resolved backup path's parent must equal the resolved config dir (defense against symlink trickery) | `backup_outside_config_dir` |
| 5 | Backup file must exist on disk | `backup_not_found` |
| 6 | Backup file must parse as valid JSON | `backup_parse_error` |
| 7 | Parsed root must be a JSON object (not a list/string/null) | `backup_invalid` |
| 8 | Pre-restore backup of CURRENT config must succeed | `restore_write_failed` (rare; OS-level) |
| 9 | Atomic rename of new content into place must succeed | `restore_write_failed` |

The validation helpers (`_is_valid_backup_filename`,
`_parse_backup_timestamp`) are pure functions with no I/O so they
can be re-used by future PRs (e.g. an audit-log entry generator,
a "purge old backups" job).

---

## Pre-restore backup behavior

Founder rule 11: "Do not restore over a config without creating a
pre-restore backup."

**Implementation:** `restore_backup` calls
`atomic_write_json(target_path, payload, backup=target_path.exists())`
-- the same helper the install flow uses. That means:

- The current live config (if any) is copied to
  `<config>.daena-backup-<UTC-NOW>.json` BEFORE the temp file is
  written.
- The pre-restore backup uses the SAME naming scheme as the install
  flow's backups, so it appears in the next call to
  `list_backups(target=...)` -- the operator can roll forward by
  re-restoring it.
- The write is atomic: temp file in same directory, then `os.replace`
  (atomic on POSIX + Windows since Python 3.3).
- The restore's response payload returns the absolute path of the
  pre-restore backup so the drawer can display it for operator
  reference.

If `atomic_write_json` raises (OS-level filesystem error), the
restore returns `restore_write_failed` and the live config is
untouched. The pre-restore backup may exist (it was written first) --
the operator can manually copy it back if needed.

**Idempotent restores are safe.** Restoring the SAME backup twice
both succeed; the second call still creates a pre-restore backup
of what's now the same content (a small disk cost for a clear audit
trail).

---

## Frontend restore flow

**No new tabs.** The change is local to `MCPInstallDrawer.tsx`: a
discrete "Restore previous backup..." link appears at the bottom of
every install step (after the operator has picked a target so we
know which CLI's backups to list).

```
MCPInstallDrawer (existing 4-step flow)
  -> "Restore previous backup..." link at bottom of each step
       -> opens MCPRestoreDrawer
            Step 1 (list):    list of backups, newest first
                              each row: timestamp + filename + size + JSON-valid pill
                              malformed backups are listed but Restore is disabled
                              Cancel | Restore selected
            Step 2 (confirm): amber warning + selected backup metadata
                              Back | Restore now
            Step 3 (restoring): spinner ("Writing pre-restore backup +
                                atomic rename...")
            Step 4 (done):    success block with restored_from + the
                              pre_restore_backup path so the operator
                              can roll forward by re-restoring
       -> on success: dispatches `daena:retry-pending` so marketplace
          cards refresh, closes restore drawer, bounces install flow
          back to "preview" so the operator sees the new (restored)
          state
```

**Honesty in the drawer:**

- File contents are NEVER fetched. The list shows metadata only.
- Pre-restore-backup safety is announced in the confirm copy:
  "A fresh pre-restore backup of the live state is created first
  (atomic rename), so you can roll forward by re-restoring this
  drawer."
- Malformed backups appear with a red "JSON invalid" pill and
  the row is `disabled` -- the operator can SEE the file is there
  but can't accidentally restore garbage.
- The pre-restore-backup absolute path is shown in the success
  state (`<pre>` tag) so the operator can copy it for safekeeping.

---

## Tests run

### New: `test_cli_mcp_backups.py` (24 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestFilenameValidation` | 5 | Valid pattern accepted; path traversal rejected; wrong basename rejected; bad timestamp rejected; non-JSON suffix rejected |
| `TestListBackups` | 5 | Empty-list when none exist; sorted newest-first; ignores non-backup files; marks malformed JSON as `valid_json=false`; payload never carries file contents (sentinel test) |
| `TestRestoreSafety` | 6 | Unsupported target; path components rejected; wrong pattern rejected; missing file; malformed backup; non-object root |
| `TestRestoreHappyPath` | 3 | Pre-restore backup created with LIVE state; live config now matches backup; payload never leaks contents; idempotent re-restore |
| `TestEndpoint` | 5 | List endpoint returns backups; list 400 on bad target; restore endpoint happy path; restore endpoint blocks path traversal; restore endpoint 422 on Pydantic Literal mismatch |

```
.venv/Scripts/python.exe -m pytest tests/test_cli_mcp_backups.py -q
# -> 24 passed in 2.63s
```

### Regression: V2 + probes + writer + backups

```
.venv/Scripts/python.exe -m pytest tests/ -k "connection_v2 or
  connection_registry or mcp_server_probe or cli_runtime_probe or
  cli_mcp_writer or cli_mcp_backups or marketplace_install or
  skill_pack or provider_probe or oauth_app_probe or
  oauth_marketplace or browser_probe" -q
# -> 339 passed, 3974 deselected in 24.53s
```

No pre-existing test failed after the backup module landed. The
fixture for the new endpoint tests deliberately uses flush-only (no
commit) so it doesn't pollute test isolation downstream.

### Frontend

```
cd frontend && npx tsc --noEmit
# -> exit 0 (clean)
```

`MCPRestoreDrawer.tsx` (430 lines) and the updated
`MCPInstallDrawer.tsx` + `useMarketplace.ts` all type-check under
strict TypeScript.

---

## Files changed

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/services/connection_v2/cli_mcp_backups.py` | +369 | NEW: list_backups + restore_backup + filename validation |
| `backend/app/api/v1/connections_v2.py` | +85 | NEW: GET /install-backups + POST /install-backups/restore endpoints |
| `backend/app/schemas/connection_v2.py` | +13 | NEW: McpBackupRestoreRequest model |
| `backend/tests/test_cli_mcp_backups.py` | +405 | NEW: 24 unit + endpoint tests |
| `frontend/src/hooks/useMarketplace.ts` | +60 | NEW: listMcpBackups + restoreMcpBackup hooks + types |
| `frontend/src/pages/connections/MCPRestoreDrawer.tsx` | +430 | NEW: 3-step restore drawer (list/confirm/done) |
| `frontend/src/pages/connections/MCPInstallDrawer.tsx` | +50 / -2 | "Restore previous backup..." link + drawer wiring |
| `docs/Ultraview/PR_CONN_MCP_INSTALL_RESTORE_REPORT.md` | NEW | this report |

Total: ~1400 lines added, ~2 lines deleted, 0 V1 file touched.

---

## Remaining config-management debt (deferred)

| Future PR | Goal | Why deferred |
|---|---|---|
| `PR-CONN-MCP-BACKUP-PURGE` | Auto-purge backups older than N days (e.g. 30) with operator confirmation | Today the directory accumulates backups indefinitely. Purge needs a "keep latest 5 / keep last 30 days" policy + a UI slot for the operator to set it; out of scope for restore. |
| `PR-CONN-MCP-BACKUP-DIFF` | Diff view in the drawer: "Restoring this backup will UNINSTALL these MCPs / REINSTALL these / RESTORE these settings" | Real diff requires loading + comparing JSON in the UI; today the operator just sees the timestamp + size. |
| `PR-CONN-MCP-BACKUP-EXPORT` | Download a backup as a `.json` file via the browser | Frontend would need a streaming endpoint; today the operator can copy the file from disk. |
| `PR-CONN-MCP-BACKUP-AUDIT` | Audit-log entry per restore (who / when / which backup / which target) | Today the structured `cli_mcp_backups.restored` log has the data; an audit-log row that surfaces in the Founder dashboard is a separate UX surface. |
| `PR-CONN-MCP-BACKUP-CROSS-CLI` | Restore a backup written for one CLI into a DIFFERENT CLI's config (e.g. Claude Desktop -> Codex) | Today restore is per-target. Cross-target restore needs schema validation per CLI; out of scope. |

---

## Why this is the right shape

1. **One source of truth for "safe write."** The restore endpoint
   re-uses `atomic_write_json` from the writer module -- the same
   temp-file + os.replace + backup pattern the install flow uses.
   Adding a future write-needing endpoint means importing the same
   helper, not re-inventing safe write semantics.
2. **Pure validation functions.** `_is_valid_backup_filename` and
   `_parse_backup_timestamp` are pure (no I/O, no globals). They're
   exported as private symbols so a future audit/purge job can re-use
   the exact validator the restore uses.
3. **Path traversal is a structural fix, not a sanitize.** The
   filename validator REJECTS path components outright (`/`, `\`,
   `..`, `.`). Even if a hostile actor pasted the perfect Daena
   filename pattern with a path prefix, the validator drops it
   BEFORE the I/O layer sees it.
4. **Defense-in-depth on directory.** Beyond filename validation,
   we ALSO `Path.resolve()` both the backup path and the config
   parent and assert they match. A symlink in the config directory
   pointing at `/etc/passwd` can't trick us into restoring there
   because the resolved parent wouldn't match.
5. **Pre-restore backup is the rollback ramp.** Even if the operator
   restores the wrong file by accident, the pre-restore backup
   captures the state they had a second ago. Recovery is one more
   click in the same drawer.
6. **Honest empty + malformed states.** Empty backup list = "no
   backups yet" copy with the resolved path so the operator knows
   where Daena was looking. Malformed backups are LISTED (so the
   operator sees they exist) but with the Restore button disabled.

---

## Commit

```
canonicalization: add MCP config backup restore flow
```

Stops here. Awaiting next direction.
