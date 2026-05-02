# PR-CONN-CLI-PROBE -- Real CLI runtime probes for V2 connection rows

**Branch:** rebuild-connections-mcp-runtime
**Commit:** (see footer)
**Date:** 2026-05-02
**Founder brief:** Make Claude Code, Codex CLI, Gemini CLI plugin cards
testable with real local binary/auth/version probes. Prepares the
ground for safe MCP install into the right CLI config later.

---

## TL;DR

`McpServerProbe` had pinned the MCP card. CLI runtime cards still
returned the structured `probe_unavailable` outcome. This PR ships
`CliRuntimeProbe` for `kind=cli_runtime` rows: per-runtime spec table,
safe binary resolution, version + auth check with per-step timeouts,
honest failure states.

- 1 new probe class + per-runtime spec table covering claude_code,
  codex, gemini_cli, grok_cli (stretch).
- 6 new fake CLI fixtures + 19 unit tests covering every founder-listed
  failure path AND a sentinel-secret no-leak audit.
- `install_all_probes()` extended -- backend already calls this at
  startup so live rows pick up the new behavior on next probe.
- Frontend drawer emits a CLI-specific advisory when a row's
  `failure_reason` matches `auth_unknown:` -- "CLI installed, but Daena
  cannot safely verify login yet."
- Zero em-dashes added (Project Rule 12). Zero changes to V1 code paths.

**Hard rules honored:** no production deploy, no V2 flag flip, no vault
--apply, no V1 deletion, no secret printing, no external scans, no
external messaging, no auto-install, callable=true requires the probe
to prove it, no new tabs, no marketplace UI rewrites, no shell
metachar passthrough.

**Test results:**
- `test_cli_runtime_probe.py`: 19/19 passed.
- Combined V2 + probe regression: 227/227 passed.
- Frontend `tsc --noEmit`: 0 errors.

---

## Supported CLI runtimes

| runtime_id | Binary | Version check | Auth strategy | Notes |
|---|---|---|---|---|
| `claude_code` | `claude` | `claude --version` | `claude_status_cmd` (parses `loggedIn` from JSON) | Native Claude CLI; OAuth lives in `~/.claude/.credentials.json` |
| `codex` | `codex` | `codex --version` | `codex_jwt_file` (reads + decodes `~/.codex/auth.json` JWT payload) | No `auth status` subcommand exists; we read the JWT directly |
| `gemini_cli` | `gemini` | **skipped** (known to hang unauthenticated) | `gemini_oauth_file` (reads `~/.gemini/oauth_creds.json`) | Reachability proven by binary presence + auth file |
| `grok_cli` | `grok` | `grok --version` | **none** -- returns `auth_unknown` | Stretch: spec listed but no documented safe auth check yet |

Spec table lives in `cli_runtime_probe.py:SPEC_BY_RUNTIME_ID`. Adding
a fifth CLI is a one-entry addition + (optionally) a new strategy
function.

---

## Exact safe commands used

| Strategy | Command / file | Why safe |
|---|---|---|
| `claude --version` | reads CLI version, exits 0 | Documented no-side-effect introspection. No network. |
| `claude auth status` | prints JSON envelope `{loggedIn, apiProvider}` | Documented in Anthropic CLI; performs at most a token validity ping (no model call). |
| `codex --version` | reads CLI version, exits 0 | Documented no-side-effect introspection. |
| `~/.codex/auth.json` (read) | parses `tokens.id_token` JWT payload | File is written locally by `codex login`. Probe ONLY decodes JWT structure (header/payload base64) to extract plan/exp. The token string never leaves the auth-check function and never enters logs / capabilities / failure_reason. |
| `~/.gemini/oauth_creds.json` (read) | checks for presence of `access_token` / `refresh_token` keys | File written locally by `gemini auth`. Probe ONLY checks key presence -- never reads or transmits the token value. Optional friendly label is derived from `~/.gemini/google_accounts.json` (active email is masked: `op***@example.com`). |

**No prompts, no model calls, no `gemini -p ping`, no `claude -p ping`,
no `codex exec ping`.** Founder brief explicitly bans round-trip pings
in this PR. The V1 `RuntimeAdapter.probe()` methods do round-trip; the
V2 probe deliberately does not.

---

## Truth-ladder mapping

For every supported runtime:

| Dim | Set when |
|---|---|
| `detected` | `config["binary"]` is an existing file OR `shutil.which(spec.binary_name)` resolves |
| `configured` | trivially True once detected (no per-call config schema for CLI runtimes) |
| `reachable` | `<binary> --version` exits 0 within `version_timeout` (8s default) -- OR for `gemini_cli`: binary presence proves reachable (version skipped) |
| `authenticated` | per-runtime safe check returns `authenticated`. NEVER set true on `auth_unknown`. |
| `callable` | detected + reachable + authenticated all true. Per founder spec: "callable=true only if runtime is installed and usable enough for Daena routing." |

Registry's `probe_and_record` (`registry.py:229`) consumes the
`ProbeResult` and writes the truth dims atomically -- the same
contract the MCP probe already uses. No registry changes needed.

---

## Failure states (one prefix per `failure_reason`)

| Prefix | When |
|---|---|
| `binary_not_found` | `shutil.which` empty AND `config["binary"]` empty/missing/invalid |
| `version_failed` | version command exited non-zero |
| `version_timeout` | version command hung past `version_timeout` (default 8s) |
| `auth_failed` | auth check ran and proved no/expired/invalid login |
| `auth_unknown` | auth check unavailable (`spec.auth_strategy == "none"`) OR auth check raised an exception we cannot classify (e.g. malformed JSON in `auth status` output) |
| `command_timeout` | generic timeout (e.g. `claude auth status` past `auth_timeout`) -- internal helper string |
| `unsupported_runtime` | `_runtime_id` from row.config has no spec |
| `config_missing` | row.config has no `_runtime_id` (seeder never wrote CLI shape) |

All prefixes are exported as named constants from
`cli_runtime_probe.py` so the frontend can match without parsing
free-form text.

---

## Secret-handling proof

The probe NEVER returns OAuth tokens, API keys, or env values to
either the registry, the UI, or the structured logs.

**Proof points:**

1. **JWT decoding stays in-scope.** `_check_codex_jwt_file` decodes
   the JWT payload locally to extract `chatgpt_plan_type` + `exp`.
   The `id_token` string is bound only to a local variable. The
   only field that escapes the function is `AuthCheckResult.user_display`,
   which carries the plan name (`ChatGPT Pro`), never the token.

2. **OAuth token read is presence-only.** `_check_gemini_oauth_file`
   does `bool(creds.get("access_token") or creds.get("refresh_token"))`
   -- never reads the value into a variable that could be logged.

3. **Stderr is captured server-side only.** `_run_version` and
   `_check_claude_status_cmd` capture stderr via `subprocess.run(...,
   capture_output=True)`. On failure, the structured log
   (`cli_probe.version_nonzero`) carries `stderr_preview=...[:200]`.
   The `failure_reason` returned in the `ProbeResult` echoes ONLY
   the structured prefix + bounded detail (rc / type-name) -- never
   stderr content. Asset Shield Hard Law 5 (data exfiltration) honored.

4. **Capability spec is whitelisted.** `_safe_spec` builds the
   capability dict from a hand-curated set of fields:
   `runtime_id, display_name, auth_strategy, version,
   auth_user_display`. Nothing else flows in. Binary path is NOT
   surfaced (would leak username on multi-user systems).

5. **Email masking.** Gemini's `google_accounts.json` may carry the
   operator's full email. The probe masks the local-part to two
   characters before exposing it (`op***@example.com`).

**Audit test** (`TestCliProbeNoSecretLeak`):

- Plants a sentinel secret (`sk-cli-do-not-leak-...`) in the parent
  env AND on stderr of the fake CLI.
- Probes the fake CLI through the happy path.
- Asserts the sentinel does NOT appear in:
  - Returned `result.capabilities` spec JSON
  - Captured stdout/stderr (structlog sink)
- Also asserts version_failed path's `failure_reason` does NOT
  echo the fake CLI's stderr ("missing optional dependency" string).

Both assertions pass.

**Defense in depth:** `_resolve_binary` and `_extra_args` reject
shell metacharacters (`; & | > < \` $(`). A malicious catalog or
config blob cannot smuggle a shell pipeline through the probe.

---

## Tests run

### New: `test_cli_runtime_probe.py` (19 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestCliProbeHappyClaude` | 1 | claude_status_cmd happy path: version + auth status both succeed; capability spec carries plan name |
| `TestCliProbeHappyCodex` | 1 | codex_jwt_file happy path: synthesized auth.json with valid future-exp JWT yields `ChatGPT Pro` |
| `TestCliProbeHappyGemini` | 1 | gemini happy path: skips version probe, OAuth file proves auth, email is masked |
| `TestCliProbeBinaryNotFound` | 1 | grok_cli with empty binary returns binary_not_found, no path/`/etc`/`.bashrc` leak |
| `TestCliProbeVersionTimeout` | 1 | hung subprocess past 1s budget yields version_timeout |
| `TestCliProbeVersionFailed` | 1 | non-zero exit yields version_failed; CLI stderr never echoed |
| `TestCliProbeAuthFailed` | 1 | claude_status_cmd with `loggedIn=false` yields auth_failed |
| `TestCliProbeAuthFailedCodex` | 1 | codex with empty token block + empty auth_mode yields auth_failed |
| `TestCliProbeAuthUnknown` | 2 | non-JSON auth status -> auth_unknown; grok_cli (no strategy) -> auth_unknown |
| `TestCliProbeUnsupportedRuntime` | 1 | unknown `_runtime_id` -> unsupported_runtime |
| `TestCliProbeConfigMissing` | 1 | no `_runtime_id` in config -> config_missing |
| `TestCliProbeNoSecretLeak` | 2 | stderr sentinel never reaches capabilities/logs; failure_reason bounded at <400 chars |
| `TestCliProbeRegistryWiring` | 3 | `install_cli_runtime_probe` registers; `install_all_probes` includes CLI; idempotent |
| `TestCliProbeDefaults` | 2 | default timeouts bounded; spec table covers documented runtimes |

Command:
```
.venv/Scripts/python.exe -m pytest tests/test_cli_runtime_probe.py -q
# -> 19 passed in 2.38s
```

### Regression: V2 marketplace + all probes

```
.venv/Scripts/python.exe -m pytest tests/ -k "connection_v2 or
  connection_registry or mcp_server_probe or cli_runtime_probe or
  skill_pack or provider_probe" -q
# -> 227 passed, 3974 deselected in 16.02s
```

No pre-existing test failed after the new probe landed. The MCP probe's
93-test suite, V2 marketplace tests, and provider probe tests all
remain green.

### Frontend

```
cd frontend && npx tsc --noEmit
# -> exit 0 (clean)
```

PluginDetailDrawer's CLI-specific `auth_unknown` advisory compiles
cleanly under strict TypeScript.

---

## Files changed

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/services/connection_v2/probes/cli_runtime_probe.py` | +454 | NEW: probe class, per-runtime spec table, 3 auth-check strategies |
| `backend/app/services/connection_v2/probes/__init__.py` | +6 / -1 | wire `install_cli_runtime_probe()` into `install_all_probes()` |
| `backend/tests/fixtures/fake_cli_binaries/__init__.py` | +12 | NEW: fixtures package docstring |
| `backend/tests/fixtures/fake_cli_binaries/fake_cli_ok.py` | +28 | NEW: happy-path fake CLI |
| `backend/tests/fixtures/fake_cli_binaries/fake_cli_version_fail.py` | +14 | NEW: version_failed fake |
| `backend/tests/fixtures/fake_cli_binaries/fake_cli_version_hang.py` | +13 | NEW: version_timeout fake |
| `backend/tests/fixtures/fake_cli_binaries/fake_cli_auth_failed.py` | +24 | NEW: auth_failed fake |
| `backend/tests/fixtures/fake_cli_binaries/fake_cli_auth_invalid_json.py` | +21 | NEW: auth_unknown (non-JSON) fake |
| `backend/tests/fixtures/fake_cli_binaries/fake_cli_auth_leaks.py` | +33 | NEW: stderr-sentinel-leak fake |
| `backend/tests/test_cli_runtime_probe.py` | +362 | NEW: 19 unit tests |
| `frontend/src/pages/connections/PluginDetailDrawer.tsx` | +27 / -4 | CLI-specific `auth_unknown` advisory |
| `docs/Ultraview/PR_CONN_CLI_PROBE_REPORT.md` | NEW | this report |

Total: ~1000 lines added, ~5 lines deleted, 0 V1 file touched.

---

## Frontend wiring (no new tabs)

The PluginDetailDrawer already showed the truth-ladder snapshot for
every plugin. CLI-specific changes:

- When `plugin.source.catalog.kind === 'cli_runtime'` AND
  `plugin.failure_reason` starts with `auth_unknown`, render an
  amber advisory: "CLI installed, but Daena cannot safely verify
  login yet. Run the runtime's own login command in your terminal,
  then re-test from this drawer."
- Generic "Last failure: ..." red copy is suppressed when the
  CLI-auth_unknown advisory is shown (no double-warning).
- No new tabs, no new pages, no new components. Brain / Plugins /
  Advanced surface unchanged.

---

## What this PR does NOT do (deferred to future PRs)

| Future PR | Goal | Why deferred |
|---|---|---|
| `PR-CONN-CLI-VERSION-IN-DRAWER` | Surface `version`, `auth_user_display`, masked binary path in the drawer card | Marketplace endpoint does not yet pull `connection_v2_capability` rows into the response. Requires a backend join + MarketplaceCard schema extension. |
| `PR-CONN-MCP-INSTALL-INTO-CLI` | Wire safe atomic MCP install into the Brain-selected CLI's config (claude_desktop_config.json, codex MCP block, gemini ~/.gemini/settings.json) | Requires per-CLI config writers + atomic-rename + backup + audit log entry. Founder rule 8 forbids auto-install in this PR. |
| `PR-CONN-OAUTH-PROBE` | Real probe for `kind=oauth_app` rows | OAuth probe needs token-refresh handling + token-introspection endpoint per provider. |
| `PR-CONN-BROWSER-PROBE` | Real probe for `kind=browser_tool` rows | Needs a sandboxed Playwright launch test. |
| `PR-CONN-CLI-PROBE-EXTERNAL` | Add `aider`, `cline`, `cursor-cli`, `crush` to the spec table | Each needs its own version + auth strategy research. |

These are blockers for the "MCP plugin install lands in the right CLI
config" flow. Each is small and well-scoped; none requires the V2 flag
flip.

---

## Why this is the right shape

1. **Honest by construction.** The probe never sets `authenticated=true`
   speculatively. Either we proved it via a documented safe check, or
   we honestly report `auth_unknown` and the operator sees the
   advisory.
2. **No model calls.** The V1 `RuntimeAdapter.probe()` methods burn
   tokens on a "ping" round-trip; the V2 probe does not. The MarketSig
   "callable" claim is now a different (and more conservative)
   thing: "binary + version + auth proven, ready for Daena routing"
   -- without paying the round-trip tax on every probe.
3. **Defense in depth.** Shell metachar rejection in both binary path
   and extra-args. Bounded per-step timeouts. Stderr stays server-side.
   Sentinel-leak tested.
4. **Single dispatch point.** `_runtime_id` keys a single spec table.
   Adding a CLI is one entry; nothing else changes. The auth-check
   strategy is a tiny named function -- not a class hierarchy.
5. **Idempotent registration.** `install_cli_runtime_probe()` and
   `install_all_probes()` are safe to call multiple times. Live
   backend already calls `install_all_probes()` at startup; new
   installs pick up the probe with no migration.

---

## Commit

```
canonicalization: add real CLI runtime probes
```

Stops here. Awaiting next direction.
