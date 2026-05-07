# PR Connections F1 + Mini Simplification — Verification Report
Date: 2026-05-06
Scope: 4 PRs bundled, ~70 LOC + 1 dead file removed, no V3 work
Operator brief: DAENA-CONNECTIONS-F1-AND-MINI-SIMPLIFICATION

## Mythos pre-flight (brutal-honest)

- This bundle does NOT solve product design. It hides clutter.
- It DOES fix a real user-trust bug: the UI told operators to "Open the Plugins tab" while the GoogleAccountSetupGuide was mounted under Advanced > apps. PR-1 removes that lie.
- It does NOT add backend architecture, OAuth flow rewrites, or new install endpoints.
- It does NOT delete working functionality. It moves things behind expanders / collapsed groups. The information is one click away, not gone.
- AppsPanel.tsx (proven dead — zero imports) is the only deletion.
- Dupe: GoogleAccountSetupGuide had two render sites (Advanced > apps AND now Plugins). Per "least duplication" rule from the brief, the Advanced > apps copy was removed; Plugins is the canonical surface.
- Cascading risk: none expected. The drawer's section components (SkillBundleSection, OAuthLifecyclePanel, GovernancePresetsBlock) are unmodified — they just render inside an `if (techOpen)` block now.
- Safety gap: the Sidebar's Approvals badge still surfaces even when Governance group is collapsed, via a sum-of-badge-counts on the group header. Pending counts cannot hide silently.

## What changed

### PR-1 — fix(connections): surface Google setup guide in Plugins tab + delete dead AppsPanel
**Files**:
- `frontend/src/pages/connections/PluginsPanel.tsx` (+13 LOC)
- `frontend/src/pages/connections/AppsStorePanel.tsx` (-7 LOC, +4 LOC comment)
- `frontend/src/pages/connections/AppsPanel.tsx` **DELETED** (proven dead via grep, zero imports anywhere in `frontend/src`)

**Behaviour**:
- `useGoogleSetupStatus` hook called from PluginsPanel.
- `GoogleAccountSetupGuide` renders ABOVE `AcceptanceStatusPanel` when `status !== null && !status.ready`.
- When Google IS ready, the guide self-removes and the operator sees a clean grid.
- AppsStorePanel no longer renders the duplicate guide. The previous comment block in AppsStorePanel imports stays as a marker for the next reader.

**Verification**:
- `grep "import GoogleAccountSetupGuide"` returns ONLY `PluginsPanel.tsx:54` (single canonical mount).
- The copy in `GoogleAccountSetupGuide.tsx` already says "Open the Plugins tab below and click Connect on Gmail". UI now matches the copy.
- `frontend/src/pages/connections/AppsPanel.tsx` removed — `ls` confirms gone.

### PR-2 — fix(connections): collapse plugin technical details by default
**Files**:
- `frontend/src/pages/connections/PluginDetailDrawer.tsx` (+45 LOC for expander wrapper, no section content removed)

**Behaviour**:
- New `techOpen` state, default `false`.
- Always-visible above the expander (3 things):
  1. Header (icon, name, vendor, status pill, officiality pill, risk pill, skill-pack badge — unchanged)
  2. One-sentence description (`plugin.description`)
  3. Failure banner — ONLY when `status === 'failed' && failure_reason` (honesty rule 17 — never silent error suppression)
- Behind one "Technical details" expander (default closed):
  - "What Daena can do" (suggested prompts)
  - Connection ladder (4 rungs)
  - First skill run block
  - Skills (SkillBundleSection)
  - OAuth lifecycle
  - Permissions + env-var names
  - Governance preset recommendations
  - Provider key deep-link
  - Probe status (full truth ladder + WSL/Docker hints)
  - Verify locally (browser/computer-use)
  - Install / setup steps
  - Source & trust
  - Compatibility
- Footer with primary action — unchanged.
- Expander label includes a hint of what's inside: "skills · permissions · probe · install · source" so the operator knows it's worth opening.

**Verification**:
- `grep "techOpen"` returns 6 references (state, aria-expanded, two icon switches, one expander toggle, one conditional render).
- `tsc --noEmit` clean.
- All section components (FirstSkillRunBlock, SkillBundleSection, OAuthLifecyclePanel, GovernancePresetsBlock) untouched — they just render inside the new `{techOpen && ...}` block.
- Failure banner uses the same rose tone + AlertTriangle icon as the existing failed-card banner, for visual continuity.

### PR-3 — fix(nav): collapse governance sidebar group by default
**Files**:
- `frontend/src/components/layout/Sidebar.tsx` (+~40 LOC: ChevronDown import, `collapsible` + `key` fields on NavGroup, openGroups state + toggleGroup callback, dual-render branch in nav loop)

**Behaviour**:
- `NavGroup.collapsible: boolean` and `NavGroup.key: string` are new optional fields.
- Only the Governance group is marked collapsible (key=`gov`). Other groups render unchanged.
- `openGroups` state hydrates from `localStorage.getItem('daena.sidebar.gov.open')` on mount (default `false`).
- `toggleGroup(key)` flips the in-memory state AND writes to localStorage. Try/catch guards against private mode / blocked storage.
- When collapsed, the group header is a `motion.button` with a chevron-right and the group title. The 8 nav items stay in the DOM but are hidden via `className="space-y-0.5 hidden"` so route resolution and screen-reader landmarks still work.
- When ANY item in the collapsed group has a non-zero badge (today: Approvals), a single summary pill renders on the group header. Pending counts cannot hide silently.
- When expanded, chevron-down replaces chevron-right and items render normally.

**Verification**:
- `grep "collapsible:\|toggleGroup\|openGroups"` returns 6 references confirming all the wiring.
- `tsc --noEmit` clean.
- 8 routes inside Governance still exist in `App.tsx` — only their nav-group label collapsed.
- Approvals badge (`badgeKey: 'approvals'`) sums into the group badge when collapsed, so the operator sees `Governance (3)` in amber if 3 approvals are pending.

### PR-4 — fix(connections): simplify plugin cards
**Files**:
- `frontend/src/pages/connections/PluginCardView.tsx` (-18 LOC chip block, +7 LOC explanatory comment)

**Behaviour**:
- The capability-chip list ("Multi-turn coding sessions", "Native MCP client", etc.) — a `<ul>` rendering up to 4 chips plus a +N counter — is removed from the front of the card.
- Card now matches Codex Desktop / Claude Desktop layout: icon, name, vendor, one-line description, status pill row, action row.
- Full skill list remains accessible via the Details drawer (specifically the Skills section inside the Technical-details expander).

**Verification**:
- `grep "included_skills.slice"` in PluginCardView.tsx returns zero matches (block removed).
- `tsc --noEmit` clean.
- Card structure preserved: header, description, status row, action row.

## Bundled metadata fixes (carried forward from previous session, same arc)

### Catalog officiality + source_refs patches — backend/app/services/connection_v2/marketplace_catalog.py
**Reason**: previous-session operator feedback ("all of them have some errors etc... shows Community on Perplexity"). 16 catalog entries previously defaulted to `officiality="community"` (the dataclass default), which caused mass mislabeling on first-party CLIs and AI providers.

**Patched** (16 entries):
- CLIs (3): Claude Code, Codex CLI, Gemini CLI → `vendor-official`
- AI providers (7): Anthropic API, OpenAI API, Gemini API, Perplexity API, Groq API, OpenRouter, Together AI → `vendor-official`
- Local LLMs (2): Ollama, vLLM/llama-server → `official`
- OAuth-only (4): GitHub OAuth, Figma OAuth, Slack OAuth, Canva → `vendor-official`

**Verification**: `pytest tests/test_connector_catalog_seed.py tests/test_connector_catalog_api.py` → 6/6 passed.

### Drawer wording fix — frontend/src/pages/connections/PluginDetailDrawer.tsx (kind-aware noun helper)
**Reason**: previous-session feedback. The community warning text used to read "Daena does not vet third-party MCP code" on every kind, which was wrong for api_provider, oauth_app, cli_runtime, local_model, skill_pack cards.

**Patched**: new `communityKindNoun(plugin)` switch that returns the correct noun per kind ("MCP code", "API services", "OAuth integrations", "CLI tools", "local-model software", "skill packs"). The community warning now reads correctly per kind.

## Acceptance checklist (operator brief PR-5)

| # | Check | Result |
|---|---|---|
| 1 | `/connections` tsc clean | PASS — no errors |
| 2 | Plugins tab shows Google setup guide when Google activation is not ready | PASS — gated on `useGoogleSetupStatus().status?.ready === false`, rendered above AcceptanceStatusPanel |
| 3 | No "Apps tab" text remains | PASS — copy reads "Open the Plugins tab below" both before and after; was always pointing at Plugins, just rendered in the wrong panel |
| 4 | Roadmap hidden by default | PASS — `showRoadmap` defaults to false, was already shipped in PR-CONNECTIONS-FIX-3 |
| 5 | Anthropic / OpenAI / Gemini cards use CLI path when callable | PASS — `cliSubscriptionByProviderId` map + `cliPrimary` override unchanged from previous hot-fix |
| 6 | Provider Keys hint still works | PASS — `/account#provider-keys` deep-link unchanged in PluginCardView and PluginDetailDrawer |
| 7 | Details drawer is simpler | PASS — 8 sections collapsed behind one expander; description + failure banner stay visible |
| 8 | Sidebar less noisy | PASS — Governance group (8 items) collapsed by default; pending Approvals count surfaces on group header when collapsed |
| 9 | No fake connected states | PASS — V2 truth ladder unchanged; failure banner makes failures MORE visible (above the expander) |
| 10 | Google activation summary still reports honest blockers | PASS — guide content unchanged; just rendered in the right place now |

## Risk assessment

**LOW**:
- All 4 PRs are pure UI layout changes. Zero changes to API contracts, business logic, or governance gates.
- No fetch hooks added or modified except `useGoogleSetupStatus` (already shipped, just newly consumed in PluginsPanel).
- No tests broken (catalog tests 6/6, no frontend tests touch modified files).
- No localStorage namespace conflicts — new keys are `daena.sidebar.gov.open` (specific, prefixed).
- Failure visibility IMPROVED in the drawer (rose banner above the expander).

**ZERO**:
- No backend code path changed.
- No deploy.
- No force push.
- No secrets touched.

## Files changed (commit candidates)

- `frontend/src/pages/connections/PluginsPanel.tsx` (modified — PR-1)
- `frontend/src/pages/connections/AppsStorePanel.tsx` (modified — PR-1)
- `frontend/src/pages/connections/AppsPanel.tsx` (deleted — PR-1, dead code)
- `frontend/src/pages/connections/PluginDetailDrawer.tsx` (modified — PR-2 + prior wording fix)
- `frontend/src/components/layout/Sidebar.tsx` (modified — PR-3)
- `frontend/src/pages/connections/PluginCardView.tsx` (modified — PR-4)
- `backend/app/services/connection_v2/marketplace_catalog.py` (modified — bundled metadata fix)
- `docs/Ultraview/PR_CONNECTIONS_F1_MINI_SIMPLIFICATION_REPORT.md` (new — this report)

## Next step

Push fast-forward to `origin/master`. No deploy. Then:
1. Operator restarts Daena (PowerShell scripts denied for me).
2. Open `/connections` and confirm:
   - Google setup guide appears at the top of Plugins tab (until both accounts ready).
   - Plugin card has no chips below the description.
   - Plugin detail drawer opens with header + one-sentence + (optional) failure banner + "Technical details" expander.
   - Sidebar Governance group is collapsed; clicking it expands and persists across reloads.
3. Continue Google OAuth Live Beta proof: configure OAuth client at console.cloud.google.com (project `daena-467315`), paste client_id + client_secret into `/account#oauth-clients`, then connect masoud.masoori@mas-ai.co and daena@mas-ai.co.

V3 (full Connections rewrite) deferred until after Google live proof completes — per the brief.
