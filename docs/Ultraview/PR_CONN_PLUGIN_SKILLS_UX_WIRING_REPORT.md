# PR-CONN-PLUGIN-SKILLS-UX-WIRING — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Founder request:** wire plugin bundle metadata into Connections UI/UX
so the operator FEELS the bundle model (MCP + auth + default skills +
setup flow) without faking execution.
**Hard rules honored:** no deploy / no V2 flag flip / no vault apply /
no V1 deletion / no secrets touched / no external scans / no auto-install
/ no falsely-callable status / no new primary tabs / no skill execution
without callable plugin / no spiral-sunflower takeover.

---

## Summary

Previous PR (`PR-CONN-MCP-CATALOG-SKILL-BUNDLES`, commit `7f6127b`)
shipped the **data**: 7-tier officiality + `default_skills` +
`suggested_prompts` + `permissions_summary` + `source_refs` on 23+
catalog entries. This PR ships the **experience** that uses it:

1. A new **SkillBundleSection** component renders bundled skills as
   honeycomb-style chips that lock until the plugin is callable.
2. **PluginDetailDrawer** redesigned with four new sections that read
   the bundle metadata: *What Daena can do*, *Connection steps*,
   *Skills*, *Source & trust* — plus a beefed-up *Permissions* block.
3. A new **`skillReadiness`** helper in `pluginCard.ts` is the single
   source of truth for "is this skill executable?" — both the card
   and drawer consult it so they can never disagree.
4. A 22-test backend regression file pins the bundle-UX contract
   (suggested_prompts coverage, controlled-vocabulary permissions,
   no prompt/skill collisions, high-risk plugins declare permissions,
   skill-pack entries always advertise prompts or skills).

Total backend tests after PR: **506 passed / 1 skipped / 0 failed**
(+22 from the new file; previous baseline 484). Frontend `tsc -b`
clean for every file I touched (one pre-existing OAuth error in
`OAuthConnectDrawer.tsx` from commit `3af8601` remains, scope-quarantined
per founder rule).

Live verified in Chrome DevTools MCP against `localhost:5173/connections`
on the GitHub plugin drawer.

---

## UI before / after

### Before (commit `7f6127b`)
- Drawer led with a generic *"What this plugin lets Daena do"*
  paragraph using the catalog short_description.
- *Included capabilities* rendered as a flat 2-column list with
  a green checkmark per row — looked like already-callable tools.
- Permissions section ONLY existed if `required_env_vars` was set
  (so plugins like Slack with no env vars showed no Permissions block).
- No connection-state ladder; the operator had to read the probe-status
  grid + figure out the install/auth/test/skills mental model on their
  own.
- No officiality badge inside the drawer header (only on the card).
- No `source_refs` surface anywhere.
- No collapsible source-attribution block.

### After (this PR)
- Drawer leads with a new **"What Daena can do"** section that uses
  `suggested_prompts` when present (Codex-style concrete intents like
  "Triage the open issues in this repo by priority") and falls back to
  the short_description otherwise. Footer caption clearly states
  "Skill execution wiring lands in the next PR" — honest about what
  isn't wired.
- New **"Connection steps"** section: a 4-rung visual ladder (MCP
  install / Auth / Test / Skills ready) tinted by V2 truth. Each rung
  shows a checkmark when the corresponding lifecycle dimension is
  satisfied, an icon otherwise. Auth rung is suppressed for plugins
  with `auth_type=none`.
- New **"Skills"** section replaces the old flat capabilities list
  with the **SkillBundleSection** component — honeycomb chips with
  padlock icons until callable; click reveals an inline reason rather
  than executing.
- New **"Permissions"** section now renders for any plugin with
  `permissions_summary` OR `required_env_vars`. High-risk plugins get
  an explicit Asset Shield reminder under their scope chips.
- New **"Source & trust"** collapsible block: officiality badge +
  `last_verified_at` date + clickable `source_refs` URLs. Open by
  default for community/archived entries (operator caveat); collapsed
  for vendor-official/verified (trust badge already carries the
  signal).
- Officiality badge added to the drawer **header** alongside status +
  risk pills, so the operator sees source tier without scrolling.

---

## How plugin bundle fields are displayed

| Catalog field | Where it surfaces | Behavior |
|---|---|---|
| `default_skills` | Drawer **Skills** section | Honeycomb chips. `humanize()` turns `triage_issues` → "Triage issues". Locked until lifecycle reaches `callable`/`enabled`. Click reveals inline tooltip below the chip. |
| `suggested_prompts` | Drawer **What Daena can do** section | Quoted intent sentences with chat icon. Up to 5 shown. Falls back to `short_description` when empty. |
| `permissions_summary` | Drawer **Permissions** > Scope row | Chips with controlled vocabulary (Read/Write/Network/Browser/etc). Backed by a test enforcing the controlled set. |
| `officiality` | Drawer **header pill** + **Source & trust** badge | 7-tier: green (official, vendor-official), cyan (vendor-blessed, verified), amber (community), slate (archived, coming-soon). |
| `source_refs` | Drawer **Source & trust** > URL list | Clickable external links opening in a new tab. Collapsed by default for high-trust tiers; expanded for community. |
| `last_verified_at` | Drawer **Source & trust** date stamp | Plain text next to the officiality pill. |
| `mcp_servers` | Reserved — not yet surfaced | Future PR will use this in the Connection-Steps "MCP server installed" rung tooltip. |

The card view (PluginCardView) deliberately stays simple — chips show
the first 4 skills as flat pills (existing behavior), badges reflect
status + officiality. The card's job is "scan to find a plugin"; the
drawer's job is "understand what it does."

---

## How skills are locked / unlocked

The `skillReadiness(plugin)` helper in `pluginCard.ts` returns one of
seven values:

| Readiness | When | Chip appearance | Click behavior |
|---|---|---|---|
| `ready` | `status === 'connected'` (V2 callable) | Emerald, no padlock, sparkles header | Reveals "Skill execution wiring pending. The next PR connects this skill name to a prompt template + tool call against `<plugin>`." |
| `ready_metadata_only` | Skill-pack entries | Violet, no padlock, sparkles header | Reveals "This is a skill-pack prompt. Pair with a runtime, MCP, or app that exposes the matching tool to actually run it." |
| `locked_needs_auth` | `status === 'needs_auth'` | Amber muted, padlock | Reveals "Connect `<plugin>` first to enable this skill." |
| `locked_needs_setup` | `status === 'available'` or `'installed'` | Cyan muted, padlock | Reveals "Install or set up `<plugin>` first to enable this skill." |
| `locked_failed` | `status === 'failed'` | Rose muted, padlock | Reveals "`<plugin>` probe is failing. Re-test from the drawer, then this skill becomes ready." |
| `locked_unsupported` | OS gate failed | Slate muted, padlock | Reveals "`<plugin>` is not supported on this operating system." |
| `locked` | Catch-all fallback | Slate muted, padlock | Reveals "Skill locked: connect `<plugin>` first." |

The header above the chip cluster restates the same reason, so the
operator gets it twice (badge + chip header) and never has to guess.

**No chip ever invokes a tool**. Click toggles a small popover under
the chip that displays the plain-English readiness reason. This is the
honest version of "skill chips look real but execution wiring lands
in the next PR."

---

## What is wired vs still pending

### Wired in this PR
- ✅ `default_skills` → drawer chips with lock state
- ✅ `suggested_prompts` → drawer "What Daena can do" section
- ✅ `permissions_summary` → drawer Permissions > Scope
- ✅ `officiality` → drawer header pill + Source & trust badge
- ✅ `source_refs` → drawer Source & trust collapsible URL list
- ✅ `last_verified_at` → drawer Source & trust date stamp
- ✅ Lock-state truth single-sourced via `skillReadiness()`
- ✅ Connection-Steps ladder driven by V2 truth dimensions
- ✅ High-risk plugins get the Asset Shield reminder copy
- ✅ Community/archived plugins get the "Review source before install" caveat
- ✅ Click-to-reveal for chip readiness (no execution)
- ✅ Card chips still render (flat) — drawer chips are honeycomb-styled

### Pending (next PRs, none queued — founder picks order)
- **PR-CONN-PLUGIN-SKILLS-EXECUTION**: connect each `default_skill`
  identifier to a prompt template + tool call against the plugin's
  MCP / OAuth / API surface. Honest invocation through `chat_orchestrator`
  with full audit trail. Asset Shield consent dialog for high-risk
  plugins. Per-skill execution audit log row.
- **PR-CONN-MCP-REGISTRY-AUTOSYNC**: poll
  `registry.modelcontextprotocol.io` daily and bump
  `last_verified_at` automatically. Surface stale-entry warning if
  >30 days.
- **PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS**: Vercel/Linear
  OAuth-DCR client allowlisting input.
- **PR-CONN-LOCAL-MODEL-PROBE**: Ollama / vLLM probe button parity
  with provider Test (PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT shipped
  this for paid providers).
- **PR-CONN-PROVIDER-KEY-VAULT-MIGRATION**: replace the JSON
  override store with `vault_v2.encrypt_secret`.
- **PR-CONN-MCP-SUGGESTED-PROMPT-RUN-IN-COMPOSER**: clicking a
  quoted prompt in "What Daena can do" sends it to the chat composer
  as a draft (zero-cost interaction; never auto-sends).

---

## How Daena visual language / math was used

The brief calls out: "skills = honeycomb chips" and "do not create
spiral/sunflower layout here." Translation: nod to the
sunflower-honeycomb topology codename without dominating the page.
What I shipped:

- **Hex glyph as chip leading icon**: each skill chip carries a small
  flat-top hexagon rendered via CSS `clip-path: polygon(...)`. No SVG
  asset, no extra DOM, just a colored block clipped to a hex. The
  hex color matches the readiness tone (emerald when ready, slate when
  locked, etc.) so the geometric signature reinforces the state.
- **Flex-wrap chip cluster, no spiral coordinates**: chips wrap as
  a normal `flex flex-wrap gap-1.5` grid. I avoided custom hex packing
  math because it would over-constrain layout at narrow widths and
  collide with the drawer's natural line-flow.
- **Color tones are coherent across the page**: skill chip color =
  status pill color = ladder rung color. The operator's eye groups
  "Connected (emerald) → Skills ready (emerald) → Skill chips
  (emerald)" without thinking. Same for the failure path
  (rose → rose → rose).
- **Officiality badge palette**: green/cyan/amber/slate — same
  palette as elsewhere in the app, no new tokens introduced.
- **Drawer rhythm**: every section uses the existing `Section` helper
  with `tracking-[0.16em]` uppercase headers. New sections inherit it,
  so the drawer stays visually unified despite the +5 sections.

The page layout was untouched: tabs are still Brain / Plugins /
Advanced (per Part A). The Plugins grid still uses the existing
3-column responsive layout. No new primary tabs added. No spiral
sunflower introduced. The honeycomb math lives where it earns its
keep — at the chip glyph level.

---

## Tests run

### New test file
`backend/tests/test_plugin_skills_ux_wiring.py` — **22 tests**,
all passing. Covers:

1. At least 15 entries have `suggested_prompts`
2. 15 high-confidence plugins have ≥1 prompt each (parametrized)
3. Suggested prompts are HUMAN sentences, not snake_case identifiers
4. Permissions use the controlled vocabulary (Read/Write/Network/etc)
5. Card payload round-trips suggested_prompts + permissions
6. No prompt collides with a default_skill identifier (categories
   stay clean)
7. High-risk + high-trust entries declare permissions_summary so
   PermissionsBlock can show the Asset Shield reminder
8. Skill-pack entries advertise prompts OR skills (their core value
   prop)

### Regression sweep
```
.venv/Scripts/python.exe -m pytest tests/ -q -k "marketplace or
connection_v2 or probe or provider_key or dynamic_model or
account_provider or plugin_bundle or plugin_skills"
506 passed, 1 skipped, 3953 deselected, 13 warnings in 29.54s
```

Up from the prior PR baseline of 484 passing. Net +22 from the new
test file; zero regressions in the 484 prior tests.

### Frontend tsc
`npx tsc -b` after deleting `tsbuildinfo` — exits 0 errors for every
file I touched (`SkillBundleSection.tsx`, `PluginDetailDrawer.tsx`,
`pluginCard.ts`). One pre-existing error remains in
`OAuthConnectDrawer.tsx` line 98 (`msg.connector` is `string |
undefined` but `onComplete?` expects `string`); last touched in
commit `3af8601`, no diff in this PR — scope-quarantined per
founder rule "don't fix unrelated drift in scope-limited PRs."

### Live browser smoke (Chrome DevTools MCP)
Verified `localhost:5173/connections` end-to-end:

- Plugin grid: 57 cards rendering with status pills + officiality
  badges + first-4 skill chips.
- Counts: `0 connected · 3 needs auth · 1 installed · 53 available`
  matches V2 truth.
- GitHub drawer (vendor-official, MEDIUM risk): rendered all 5 new
  sections in order — *What Daena can do* (3 quoted prompts +
  attribution caption), *Connection steps* (4 rungs with icons), *Skills*
  (5 locked chips with padlocks + "Install or set up GitHub first to
  enable this skill." header), *Permissions* (Scope: Read/Write/Network
  + env-var NAMES block), *Source & trust* (collapsed "Vendor official"
  pill + Verified 2026-05-03 timestamp).
- Click on locked chip "Triage issues": no execution, no network call,
  inline tooltip reveal in drawer.
- Install/setup steps preserved with the existing yellow "Daena does
  not execute install commands automatically" banner.
- Compatibility row preserved (auth=token, risk=medium, install=npm,
  OS=windows/wsl/mac/linux).

Screenshot evidence: GitHub drawer top-half shows new sections + chip
locks + suggested-prompt quotes; bottom-half shows Source & trust
collapsed badge + Compatibility grid.

---

## Remaining blockers for real skill execution

The next PR (`PR-CONN-PLUGIN-SKILLS-EXECUTION`) needs:

1. **Skill → tool mapping table**. Each `default_skill` identifier
   must resolve to either:
   - A prompt template (for skill packs / OSS prompts)
   - An MCP tool invocation (for `mcp_server` plugins)
   - An OAuth-mediated API call (for `oauth_app` plugins)
   - A composer-prefill action (for "draft this for me" intents)

2. **Asset Shield consent dialog** for high-risk skills (Cloudflare,
   Stripe, Desktop Commander, Browser tools). Per-skill consent token
   with TTL.

3. **Per-skill audit log row**. Currently `audit_service` logs
   per-tool-call; we need a parent `skill_invocation` event tying
   N child tool calls back to the operator's one-click intent.

4. **Composer integration**: clicking a `suggested_prompt` quote
   should fill the chat composer (zero-cost, never auto-sends). This
   is the simplest first execution path and could go in a tiny PR
   ahead of the full execution wiring.

5. **Per-plugin governance policy presets**. Each bundle ships with
   a recommended `BehaviorGuard` policy (e.g., Stripe: never
   auto-charge above $X; Cloudflare: never edit production zones
   without approval). Operator opts in at install time.

6. **Live MCP registry sync** (`PR-CONN-MCP-REGISTRY-AUTOSYNC`) so
   `last_verified_at` actually means something.

None of these are blockers for *this* PR — the UI honestly says
"Skill execution wiring lands in the next PR" everywhere it shows a
chip, so there is no false promise to clean up.

---

## Files changed

```
A  backend/tests/test_plugin_skills_ux_wiring.py             (240 lines)
A  frontend/src/pages/connections/SkillBundleSection.tsx     (174 lines)
M  frontend/src/pages/connections/PluginDetailDrawer.tsx     (~+220 / -50 lines)
M  frontend/src/pages/connections/pluginCard.ts              (~+135 lines)
A  docs/Ultraview/PR_CONN_PLUGIN_SKILLS_UX_WIRING_REPORT.md  (this file)
```

Net: +769 lines added, -50 removed across 3 src files + 1 new
component + 1 test file + this report.

---

## Hard rules verification

| Rule | Compliance |
|---|---|
| 1. No deploy production | ✅ no Cloud Run touch, no docker push |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` | ✅ flag unchanged |
| 3. No `vault --apply` | ✅ vault untouched |
| 4. No V1 file deletion | ✅ legacy panels still mounted in Advanced |
| 5. No secrets printed/grepped/logged/committed | ✅ env-var NAMES only, never values; PR-CONN-PROVIDER-KEY-INPUT vault contract preserved |
| 6. No external scans | ✅ no scanner invocations |
| 7. No emails/DMs/webhooks/messages sent | ✅ pure UI work |
| 8. No auto-install of npm/pip/docker | ✅ install banner preserved + reinforced |
| 9. No falsely-callable status | ✅ `skillReadiness()` is the gate; "ready" only when V2 callable=true |
| 10. No new primary tabs | ✅ tabs still Brain/Plugins/Advanced |
| 11. No skill execution unless plugin connected/callable | ✅ click → reveal text only; no tool dispatch path exists |
| 12. No heavy sunflower dashboard | ✅ honeycomb signature lives in the chip glyph only |

Stop and report.
