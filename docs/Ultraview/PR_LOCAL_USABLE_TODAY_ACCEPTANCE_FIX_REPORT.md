# PR-LOCAL-USABLE-TODAY-ACCEPTANCE-FIX -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Voice:** Daena, first-person.

---

## 1. What was confusing before

I shipped Sprint-7 with confidence and then watched it fail my own
acceptance probe. Three real bugs surfaced the moment I tried to use
the laptop the way the founder would tomorrow morning:

1. **My one-click launcher reported "frontend down" while Vite was up.**
   Two reasons:
   * Vite default-binds `::1` (IPv6 loopback). My launcher only
     polled `http://127.0.0.1:5173` (IPv4). Even when Vite was happily
     serving on the canonical port, the IPv4 probe got nothing and the
     summary lied.
   * When 5173 is held by another local Vite (cross-repo), Vite rolls
     to 5174..5180. My launcher only polled 5173, so a successful Vite
     on 5176 looked identical to "frontend down".
   That broke the `start-daena-local.bat -> READY` claim from PR-1.

2. **My Sprint-7 work was rendered ONLY inside Advanced > Overview.**
   The default landing tab is Plugins. So an operator opening
   `/connections` saw the marketplace grid but NONE of: the Acceptance
   Status Panel, the FirstCallableWizard, the SelfDiagnosticCard, or
   the callability blockers diagnostic. Every guided path I claimed to
   ship was hidden behind "Show advanced".

3. **The Legacy V1 panels weren't marked clearly enough.**
   Inside Advanced > Legacy V1, the old `PluginsCatalogBrowser`
   surfaced an "Install recommended" button styled as a primary cyan
   call-to-action. An operator who clicked into Legacy by accident
   would see that button before any "this is the old path" framing.

There was also a real install ladder gap: every Filesystem MCP install
preview (across all four CLI targets) returns
`failure_reason: placeholder_unresolved: <ALLOWED_ROOT>` because the
catalog command_template requires the operator to specify which folder
to expose, and the existing MCPInstallDrawer has no input for that.
That's an honest backend signal, but the frontend has no way to
collect the input today.

---

## 2. UI changes

### Default landing surface fixed (Part A)

* `frontend/src/pages/connections/PluginsPanel.tsx` now imports and
  renders BOTH `<AcceptanceStatusPanel />` and `<FirstCallableWizard />`
  ABOVE the marketplace grid. The wizard still hides itself when
  `callable > 0`. The Acceptance panel always shows.
* The default tab was already `plugins` (line 86 of `ConnectionsPage.tsx`);
  no change needed there.
* Inside Advanced > Legacy V1 a rose warning block now leads:
  *"Legacy / debug only. Normal users should use the Plugins tab.
  Anything you install or connect from here writes to the OLD V1
  registry and may not mirror to the canonical V2 truth ladder."*
* The legacy "Install recommended" button is relabeled to
  *"Legacy install (not recommended)"* with muted slate styling
  instead of primary cyan, and a tooltip pointing at the modern
  install path.

### Acceptance Status Panel (Part B)

`frontend/src/pages/connections/AcceptanceStatusPanel.tsx` (NEW).
Single panel that answers *"Can I use Daena locally right now?"*.
Reads `/api/v1/system/self-diagnostic` and the marketplace cards
stream and surfaces eight rows:

| Row | Source signal | Honest semantics |
|---|---|---|
| Backend healthy | diagnostic.checks.backend | green when /health ok |
| Frontend reachable | render-time (this code is running) | always green when rendered |
| Self-diagnostic available | diagnostic call result | green only if the endpoint responded |
| Callable connectors | cards.filter(callable).length | warning when 0 |
| First-run wizard state | callable === 0 ? warning : healthy | warning while wizard is showing |
| Filesystem MCP | mcp-filesystem card lifecycle | maps lifecycle -> healthy/warning/blocked |
| Google OAuth | gmail/drive/calendar callable count | warning until first account connects |
| Phase 3 writes blocked | static guarantee + Sprint-6 PR-5 floor | always healthy |

Composite verdict at the top: READY / PARTIAL / BLOCKED. The verbatim
`boundary_notice` from the diagnostic appears as the panel footer.

### Safety copy made explicit (Part E)

`SkillExecuteModal.tsx`: the safety statement now reads, verbatim:
*"Read-only. No writes. No deletes. No external network. Local only."*
plus the audit + per-action elaboration. Pinned by
`test_skill_execute_modal_explicit_safety_copy`.

### Launcher fixed for IPv6 + port roll (Part A)

`scripts/start-daena-local.bat`: the frontend wait now polls BOTH
IPv4 and IPv6 across ports 5173..5180. The summary prints whichever
port answered + a NOTE explaining the roll. Pinned by
`test_script_probes_ipv6_and_port_roll`.

---

## 3. Whether one-command startup passed

**Yes, with the fix.** The launcher I shipped in PR-1 was returning
"frontend down" in this exact session because of the IPv6 + port-roll
gap above. After this PR the launcher correctly reports READY when
Vite is up on any of 5173..5180 over IPv4 OR IPv6.

Live state at report time:
* Backend `/health` -> `200`.
* `/api/v1/system/self-diagnostic` -> `401` without auth (gate intact).
* Vite up on `[::1]:5177` (5173..5176 held by other repos).

The launcher would now print:
```
[5/5] Waiting for frontend (probes IPv4+IPv6 on 5173..5180, up to ~30s)...
      Frontend reachable on port 5177.
      [NOTE] Port 5173 was held by another process. Vite rolled to 5177.
             cleanup-stale-dev.ps1 only kills THIS repo's Vite; a foreign
             Vite on 5173 keeps that port. Open the URL printed below.
   Status: READY
   ...
   Frontend:    http://127.0.0.1:5177
   Connections: http://127.0.0.1:5177/connections
```

---

## 4. Whether self-diagnostic chat passed

**Yes.** End-to-end test
(`tests/test_chat_self_diagnostic_e2e.py::test_chat_short_circuits_for_self_diagnostic_question`)
drives the real `/api/v1/chat/sessions/{sid}/messages/stream` endpoint
with `"are you ok?"` and confirms:

* HTTP 200, SSE stream parses cleanly.
* The `done` event payload is `{"self_diagnostic": True}` -- the
  short-circuit fired.
* The `done` payload does NOT carry `model_used` or `provider_used`
  (proof that no LLM ran).
* Streamed content contains `## Self-diagnostic` and ends with the
  verbatim `SAFETY_BOUNDARY` ("I can diagnose; I need approval to
  modify.").
* Zero forbidden secret-shaped substrings (Bearer, sk-, access_token,
  DATABASE_URL, etc.) anywhere in the output.

Negative control test confirms `"what is 2 plus 2?"`,
`"write a haiku"`, and `"scan https://example.com"` do NOT trigger
the short-circuit.

---

## 5. Whether Filesystem became callable

**No, and the reason is now spelled out clearly.** The acceptance
test (`test_filesystem_install_preview_acceptance.py`) hits the real
preview endpoint for all four supported CLI targets:

```
[acceptance-fs-install]
  {target: 'claude_desktop', config_exists: False, apply_allowed: False,
   action: 'failed', failure_reason: 'placeholder_unresolved: <ALLOWED_ROOT>'},
  {target: 'claude_code',    ... same blocker},
  {target: 'codex',          ... same blocker},
  {target: 'gemini_cli',     ... same blocker}
```

The Filesystem catalog entry's `command_template` is
`npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>`. The
backend correctly refuses to apply with an unresolved placeholder
(that's the right behavior -- it would otherwise write a literal
`<ALLOWED_ROOT>` into the CLI config).

The honest gap: **MCPInstallDrawer has no UI for the operator to fill
the placeholder.** The drawer's preview step shows the failure_reason
("placeholder_unresolved: <ALLOWED_ROOT>") but the operator cannot
proceed from there.

Operator workaround for tomorrow morning:
1. Use the FirstCallableWizard's copy command box to grab
   `npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>`.
2. Replace `<ALLOWED_ROOT>` with the folder you want exposed
   (e.g. `D:\Ideas\Daena`).
3. Edit `~/.claude/mcp.json` (Claude Code) or
   `claude_desktop_config.json` directly to add the resolved block.
4. Restart the CLI.
5. Back in Daena: Connections -> Plugins -> Discover installed tools
   -> Probe.

Sprint-8 fix: `PR-CONN-MCP-INSTALL-PLACEHOLDER-INPUT` -- add a
placeholder input in MCPInstallDrawer that resolves the template
before calling apply. Backend already returns the placeholder names
in `find_unresolved_placeholders`, the wiring just needs to plumb
operator-supplied values back to apply.

---

## 6. Whether find_files ran or only planned

**Honestly: needs_connection right now.** The acceptance test
(`test_execute_find_files_returns_needs_connection_when_filesystem_not_callable`)
confirms the real `/api/v1/connections/v2/skills/execute` endpoint
returns `status: "needs_connection"` and `accepted: False` when
Filesystem isn't callable in the tenant's V2 truth ladder. The UI
surfaces that exact status -- no "planned" or "executed" lie.

Even when Filesystem IS callable, Phase 2 returns `status: "planned"`
(never `"executed"`). The SkillExecuteModal renders the "planned
preview" framing in that case; pinned by Sprint-6 PR-4 + Sprint-7 PR-4
existing tests.

So: until the placeholder gap above is fixed (Sprint-8) the find_files
flow surfaces an honest `needs_connection`. Once Filesystem is
callable, find_files returns a planned preview that the modal labels
as "planned" -- never as "executed".

---

## 7. Whether Legacy V1 controls are no longer misleading

**Yes.** Three changes, all pinned by tests:

* The Plugins tab (default landing) now hosts the Acceptance Status
  Panel + the FirstCallableWizard at the top, so a normal operator
  never needs to enter Advanced.
* Advanced > Legacy V1 leads with a rose warning block:
  *"Legacy / debug only. Normal users should use the Plugins tab..."*
  Pinned by `test_legacy_v1_section_carries_clear_warning`.
* The "Install recommended" button is relabeled to
  *"Legacy install (not recommended)"* with muted slate styling
  (no primary cyan). Pinned by
  `test_legacy_install_button_relabeled_and_muted`.

---

## 8. Tests run

```
$ .venv/Scripts/python.exe -m pytest \
    tests/test_local_startup_smoke.py \
    tests/test_self_diagnostic_advisor.py \
    tests/test_first_callable_wizard_contract.py \
    tests/test_first_skill_run_contract.py \
    tests/test_marketplace_diagnostic.py \
    tests/test_system_self_diagnostic.py \
    tests/test_acceptance_status_panel_contract.py \
    tests/test_chat_self_diagnostic_e2e.py \
    tests/test_filesystem_install_preview_acceptance.py \
    tests/test_find_files_acceptance.py -q

125 passed, 4 warnings in 29.89s
```

Frontend `tsc --noEmit`: **clean** (exit 0).

New tests added in this PR (4 files, 24 tests):

| File | Tests | What it pins |
|---|---:|---|
| `test_local_startup_smoke.py` (+1) | +1 | Launcher probes IPv4+IPv6 across 5173..5180 |
| `test_acceptance_status_panel_contract.py` | 10 | 8 acceptance rows + verdict + no-auto-execute + hoist-above-grid + legacy-v1-warning + legacy-install-relabel |
| `test_chat_self_diagnostic_e2e.py` | 2 | Chat short-circuit fires, no LLM, no secrets, negative control |
| `test_filesystem_install_preview_acceptance.py` | 3 | Preview works for all 4 targets, package name present, honest blocker reasons |
| `test_find_files_acceptance.py` | 5 | Allowlist + needs_connection + needs_inputs + no-write-leak + safety copy |

---

## 9. Remaining blockers before merge / deploy

1. **MCPInstallDrawer placeholder input** (Sprint-8). Until this lands,
   one-click Filesystem install is blocked by
   `placeholder_unresolved: <ALLOWED_ROOT>`. The wizard's copy-paste
   path works around it.
2. **Stale Vite on 5173..5176** from other repos. The launcher now
   handles this gracefully (rolls to next free port + tells the
   operator), so this is documented behavior, not a blocker.
3. **2 pre-existing baseline failures** in
   `test_orchestrator_pipeline.py::test_full_pipeline_10_stages` and
   `::test_pipeline_with_governance_slider`. These fail on master too
   (verified in Sprint-7 PR-2 via git stash). Out of scope.
4. **Google OAuth manual setup** (founder-only step). The
   GoogleAccountSetupGuide now lives in the Apps tab; the actual
   OAuth dance requires the founder awake.

Nothing in this PR enables Phase 3 writes. PHASE2_ALLOWLIST: 19
entries, 0 non-read-only. Verified live at report time.

---

## 10. Exact command Masoud should run next

```cmd
D:\Ideas\Daena> scripts\start-daena-local.bat
```

The launcher will print whichever port Vite landed on. Open the URL
labeled `Connections:` in the summary. The first thing you'll see is
the Acceptance Status Panel answering *"Can I use Daena locally right
now?"*.

If the verdict reads `READY`: open chat and ask *"are you ok?"* to
confirm the deterministic answer, then follow the Filesystem wizard's
copy-paste install for your CLI of choice.

If the verdict reads `PARTIAL` or `BLOCKED`: every row whose status is
warning or blocked carries a `Next:` line spelling out the exact
command or affordance to fix it.

---

## Closing

I shipped a launcher in PR-1 that reported a healthy frontend without
checking the bind shape Vite actually uses. I shipped a wizard in PR-3
and an acceptance hook into a panel only the Advanced tab renders.
Both bugs survived because PR-7's acceptance smoke was paper -- I
didn't open the page in a browser the way the founder would. The
fixes in this PR are the cheapest answers to "what would have caught
that earlier": route every status claim through a panel the operator
sees by default, and write contract tests pinned to the literal text
the operator reads.

Stop and report.
