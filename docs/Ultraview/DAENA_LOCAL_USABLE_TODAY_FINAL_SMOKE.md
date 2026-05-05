# Daena · Local-Usable-Today · Sprint-8 Final Smoke

**Branch:** `rebuild-connections-mcp-runtime`
**Tag-candidate after merge:** `v3.7.2-local-usable`
**Date:** 2026-05-05
**Sprint:** PR-LOCAL-USABLE-TODAY (Sprint-8)
**Author:** Claude (under Daena-mode bounded-autopilot brief)

---

## Verdict

**MERGE-READY for local beta.**
Acceptance: **PASS** — every condition the operator listed is honest.
Phase 3 writes still blocked. No external network. No V1 deletion.
No production deploy.

| # | Brief criterion | Result |
|---|---|---|
| 1 | `scripts\start-daena-local.bat` works | ✅ Backend up `/health`, frontend up on `[::1]:5173` (IPv6 path the Sprint-7 PR-1 launcher fix handles) |
| 2 | `/connections` opens on the printed frontend port | ✅ Live snapshot at `http://localhost:5173/connections` |
| 3 | Acceptance Status Panel visible on default Plugins tab | ✅ Snapshot shows "Pick your Brain. Browse Plugins." headline + "Make your first plugin callable" wizard above the catalog grid |
| 4 | Legacy V1 no longer looks primary | ✅ Snapshot shows "Internal V2 / V1 surfaces. Normal users should use the Plugins tab" warning + muted styling |
| 5 | Filesystem placeholder input works | ✅ PR-1 ships the input form with friendly label "Allowed folder root"; 21 tests pin the contract |
| 6 | Filesystem can be installed/probed or gives exact blocker | ✅ PR-2 live smoke: install writes resolved command to disk; probe returns honest verdict (success OR `binary_not_found`/`reachable` failure_dim with reason) |
| 7 | `find_files` either executes read-only or gives exact blocker | ✅ PR-3: executor returns `status="executed"` when callable, `status="needs_connection"` otherwise; modal renders "Executed read-only" / "Connect Filesystem first" |
| 8 | "are you ok?" self-diagnostic chat works | ✅ Sprint-7 `test_chat_self_diagnostic_e2e.py` still passes; no LLM call, no secret leakage |
| 9 | Phase 3 writes still blocked | ✅ Pinned by `test_phase2_allowlist_has_no_write_entries` (PR-3); PHASE2_ALLOWLIST has zero `read_only=False` entries |
| 10 | Frontend `tsc --noEmit` clean | ✅ Exit 0 |
| 11 | Relevant backend tests pass | ✅ 103/103 across the Sprint-7 + Sprint-8 acceptance + writer suite |

---

## What Sprint-8 added

### PR-1 · `0088b1b` — MCP install placeholder input
**Closed the Sprint-7 acceptance blocker.**
Before: Filesystem preview returned `placeholder_unresolved: <ALLOWED_ROOT>`; install was disabled, no UI affordance to fix it.
After: drawer renders "Operator-supplied values" form with a labeled input ("Allowed folder root") for each `<TOKEN>` in the catalog template. Backend substitutes via `resolve_command_template` (always shlex.quote'd, rejects shell metacharacters / shell expansion / control bytes / nested angle brackets). 21 new tests pin the contract end-to-end.

### PR-2 · `7f7fb4b` — Filesystem callable live smoke
End-to-end smoke proving the PR-1 fix unblocks the full preview → apply → probe path. Sandbox: `patched_home` repoints `Path.home` + `APPDATA` + `USERPROFILE` to a tmp dir so the test never touches the operator's real Claude Desktop config. Live verification (run outside pytest):
```
config_path = D:\tmp\daena-fs-smoke-0s76k4g1\Claude\claude_desktop_config.json
args = ["-y", "@modelcontextprotocol/server-filesystem",
        "D:\\tmp\\daena-fs-smoke-0s76k4g1"]
```
The literal `<ALLOWED_ROOT>` token never appears in the on-disk config.

### PR-3 · `ba9b326` — find_files real read-only
The executor was already armed (Sprint-3 PR-CONN-PHASE2X-FILESYSTEM-HUGGINGFACE-READONLY) but the SkillExecuteModal lied about it ("Phase 2 spine: planned-only. Real tool invocation arms in follow-up PRs.") even when the call returned `status="executed"`. PR-3 swaps the modal copy:
- New STATUS_LABEL table maps every executor status to its honest label + tone + testid.
- `executed` → "Executed read-only" (emerald pill).
- `needs_connection` → "Connect Filesystem first" (or `Connect ${pluginName} first` for non-fs plugins).
- "Planned tool call (no real invocation in Phase 2)" header swaps to "Executed tool call (real read-only invocation)" when status === executed.
- Footer copy switches on `execution_mode` (planned-only entries keep the old line; mcp_tool entries surface the live-execution line).
- Draft-follow-up CTA now offered for both `planned` and `executed`.

### PR-4 · this report — Final acceptance smoke
Live launch, browser snapshot, full test sweep, this document.

---

## Tests landed

| File | Tests | Sweep result |
|---|---:|---|
| `test_cli_mcp_writer.py` (existing) | 28 | ✅ |
| `test_cli_mcp_writer_placeholder_input.py` (new, PR-1) | 21 | ✅ |
| `test_mcp_install_drawer_placeholder_contract.py` (new, PR-1) | 5 | ✅ |
| `test_filesystem_install_preview_acceptance.py` (Sprint-7) | 3 | ✅ |
| `test_filesystem_callable_live_smoke.py` (new, PR-2) | 4 | ✅ |
| `test_find_files_acceptance.py` (Sprint-7) | 5 | ✅ |
| `test_filesystem_find_files_real_readonly.py` (new, PR-3) | 7 | ✅ |
| `test_acceptance_status_panel_contract.py` (Sprint-7) | 10 | ✅ |
| `test_chat_self_diagnostic_e2e.py` (Sprint-7) | 2 | ✅ |
| `test_marketplace_install_endpoints.py` (existing) | 9 | ✅ |
| `test_local_startup_smoke.py` (Sprint-7) | 9 | ✅ |
| **Total** | **103** | **✅** |

**Frontend `tsc --noEmit`:** clean (exit 0).
**Hard stops triggered:** 0.

---

## Live `/connections` snapshot (key elements)

```
heading "Pick your Brain. Browse Plugins." level=1
button "Plugins"                          # default tab, active
heading "0 of 57 connectors callable" level=2
heading "Make your first plugin callable" level=2
StaticText "...The fastest path to 1 callable is Filesystem MCP"
button "Discover installed tools"
button "Probe"
StaticText "Internal V2 / V1 surfaces. Normal users should use the Plugins tab"
                                          # legacy clearly demoted
button "Main Brain"      ► 0 / 10 callable
button "Runtimes"        ► 0 / 10 callable
button "MCP Store"       ► 0 / 29 callable
button "Apps"            ► 0 / 11 callable
```

The Sprint-7 hoist of AcceptanceStatusPanel + FirstCallableWizard onto the
default Plugins tab is in effect; the legacy V1 surface is clearly labeled
debug-only.

---

## What is honestly still on the operator

These are **not blockers for local-beta merge**, but they are the work
between "local beta" and "everyday driver":

1. **Connect at least one Google account** as `masoud.masoori@mas-ai.co`
   and `daena@mas-ai.co` (Gmail / Drive / Calendar). The OAuth picker
   row in AcceptanceStatusPanel will flip from blocked → healthy
   automatically.
2. **Install Filesystem MCP through the new placeholder flow.**
   Drawer → Plugins → Filesystem MCP → Install → pick Claude Desktop →
   type `D:\Ideas\Daena` (or any folder you want to grant read access)
   in the "Allowed folder root" input → Confirm. The `placeholder_input`
   testid is `mcp-install-placeholder-form`; the apply button stays
   disabled until the input is non-empty.
3. **Run find_files once.** Plugins → Filesystem MCP card → Skills →
   `find_files` → fill `root_path` + `name_or_glob` → "Run read-only
   skill". Modal pill should read **"Executed read-only"** with a
   capped result preview. If it reads "Connect Filesystem first" or
   "Planned preview" instead, that's the executor's honest verdict —
   no fake success.

After steps 1–3 the AcceptanceStatusPanel verdict should read
`PARTIAL → READY` for the rows you've covered.

---

## Sprint-9 candidates (from observation, not in scope here)

In rough priority order:

1. **`PR-CONN-FS-PROBE-AUTO-INSTALL-NOTICE`** — when the post-apply
   probe fails with `binary_not_found` (npx missing), surface a single
   line: "npx not on PATH — install Node.js to enable Filesystem MCP."
   Today the failure_reason is honest but generic.
2. **`PR-CONN-WIZARD-AUTO-HIDES-FOR-CONNECTED-OPERATORS`** — once 2+
   Google accounts are connected and Filesystem is callable, hide
   FirstCallableWizard (it's noise once the operator is past first-run).
3. **`PR-CONN-CONSENT-EXECUTOR-DB-CUTOVER`** — flip the executor's
   read path to DBConsentStore (carry from Sprint-6 recommendations).
4. **`PR-CONN-AUDIT-LOG-VIEWER-PLUGIN-FILTER`** — operator visibility
   into every find_files call: "show me everything Filesystem MCP did
   in the last hour" — the audit row is already written by the
   executor; it just needs a viewer.

None of these are blockers for the local-beta merge.

---

## Hard-stop log

| Hard stop | Triggered? | Notes |
|---|---|---|
| Production deploy / Cloud Run write | ❌ | Branch local only, no `gcloud` calls |
| `USE_CONNECTION_REGISTRY_V2=true` flip | ❌ | Untouched |
| `vault --apply` | ❌ | Vault file unchanged |
| Secret read/print/grep/log/commit | ❌ | No `.env` reads, no token logging |
| External email / DM / webhook / Slack | ❌ | No outbound network |
| Payment / refund / financial write | ❌ | N/A |
| Browser automation on external sites | ❌ | Only `localhost:5173` snapshot |
| Delete V1 / legacy files | ❌ | Untouched |
| `npm` / `pip` / `docker` install | ❌ | Used existing project venv only |
| Operator OAuth login required | ❌ | All tests use mocked accounts |
| Phase 3 write enablement | ❌ | PHASE2_ALLOWLIST still has 0 non-read-only entries |
| Unexpected secret-risk file in `git status` | ❌ | Verified clean |
| Pre-existing test failure ignored | ✅ Documented | `test_connection_v2_marketplace.py` cross-file fixture leak when batched with `test_marketplace_install_endpoints.py`; both files pass alone (98/98 + 9/9). Pre-existing test_engine session-scope state interaction; not introduced by Sprint-8. |

---

## Exact commands for the operator tomorrow

Run these in order from `D:\Ideas\Daena`:

```cmd
scripts\cleanup-stale-dev.ps1
scripts\start-daena-local.bat
```

When the launcher prints the URL, open it in a browser. The default
landing page after the navbar is `/connections`. The
AcceptanceStatusPanel + FirstCallableWizard sit at the top of the
Plugins tab. To make Filesystem callable:

1. Click "Make Filesystem callable" / Install on the Filesystem MCP card.
2. Pick "Claude Desktop" as target CLI.
3. In the "Allowed folder root" input, type `D:\Ideas\Daena`.
4. Click "Update preview" → "Confirm install".
5. Restart Claude Desktop so it re-reads the MCP config.
6. Back in `/connections`, click Discover installed tools, then Probe.
7. Filesystem card lifecycle pill should flip to **callable**.

To run find_files:

1. On the Filesystem MCP card, click the find_files skill chip.
2. Fill `root_path` = `D:\Ideas\Daena`, `name_or_glob` = `*.py`.
3. Click "Run read-only skill".
4. Pill should read **"Executed read-only"** with a capped result preview.

If any step deviates, the modal/panel surfaces the exact reason —
no fake success.

---

## Commits in Sprint-8

```
ba9b326  canonicalization: execute Filesystem find_files read-only   (PR-3)
7f7fb4b  docs/test: verify Filesystem callable path                   (PR-2)
0088b1b  fix: add MCP install placeholder input                       (PR-1)
```

Branch ahead of master by 11 commits since pre-Sprint-7 baseline
(`f863a3a`).

---

## Decision

Per founder brief: "Once that passes, Daena is acceptable as your local
working beta. Then we can decide whether to merge, clean docs, or start
the next self-improvement sprint."

The verdict is **PASS**. Recommend the operator:

1. Manually verify the workflow above tomorrow morning.
2. If the workflow holds, **merge** `rebuild-connections-mcp-runtime`
   → `master` (after squashing the 11 commits or keeping them — your call;
   the 3 Sprint-8 commits are independently revertable).
3. After merge, queue Sprint-9 PR-1 (`PR-CONN-FS-PROBE-AUTO-INSTALL-NOTICE`)
   to harden the npx-missing path, then move to the Google-OAuth /
   Phase 3 conversation.

**Stop and report.**
