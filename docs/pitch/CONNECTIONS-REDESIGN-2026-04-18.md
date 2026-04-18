# Connections Redesign — 2026-04-18 · TICKET-S16

**Scope**: fix the core UX defect (per-skill "Ask" as main CTA), promote MCP servers to a first-class surface, align the vocabulary with real integration centers (Zapier, Slack apps, Notion integrations). Land as a layered refactor; what can ship cleanly in one turn ships; what needs per-provider end-to-end testing is scoped as the next tickets with honest reasons.

## Root cause

Three architectural confusions were visible in the UI:

1. **Skills treated as top-level install units.** Each tool (`netlify_deploy`, `netlify_logs`, etc.) got its own `Ask / Allow / Block` dropdown as primary CTA. That made sense when every tool was a high-risk primitive (`file.delete_file`, `terminal.run_command`), but for a *connected app* the account-level auth is already the gate. Per-tool dropdowns on `Netlify Deploy` and `Netlify Logs` just produce visual noise + false confidence.

2. **Three different integration concepts stuffed into two tabs.** The previous layout had `Extensions` (MCP-style local primitives) + `Connectors` (cloud apps with OAuth/API key) but no dedicated surface for `MCP Servers imported from claude_desktop_config.json`. The bootstrap already scanned them; the UI just never showed them in their own context.

3. **Account identity buried in subtitle text.** A user who just connected Google Drive saw `Connected as masoud@mas-ai.co` as a muted gray subtitle line, easy to miss. Real integration centers put the account email/avatar in a dedicated pill next to a green "Signed in" indicator.

## Architecture

```
                     ┌─────────────────────────────┐
                     │      Connections Page       │
                     └────────────┬────────────────┘
                                  │
       ┌──────────┬────────────┬──┴──────────┐
       │          │            │             │
   Runtimes  Extensions    Plugins       MCP Servers   ← new tab
   (AI CLIs) (local prim.) (cloud apps)  (imported)
       │          │            │             │
   claude_code   file.*    google-drive   github MCP
   codex        terminal.*  notion         sentry MCP
   gemini-cli   browser.*   slack          ...
       │          │            │             │
       └──────── per-tool ─────┤  account-level auth
                 Allow/Ask/    │  (tool surface exposed
                 Block CTA     │   as capabilities, not
                 (unchanged)   │   per-tool Ask dropdowns)
                               │
                       Advanced drawer
                       per-tool A/A/B
                       (opt-in, defense
                        in depth)
```

Key principle: **the tool-gate vocabulary is the MCP-primitive tab** (filesystem, terminal, etc.) because those are where genuinely risky single-call primitives live. For a connected *app*, the primary gate is the account — tools are a capability surface, not a permission surface.

## What shipped in this ticket

### Layer 1 · Connections UI refactor (primary UX defect)

Files modified: `frontend/src/pages/ConnectionsPage.tsx`

- Per-skill `PermissionSelect` dropdown **removed as default CTA** in `ConnectorRow`. Capability rows are now informational (name + description + tool id) with no action button.
- New `showAdvanced` toggle per connector card. Clicking `Advanced` reveals the per-tool Allow/Ask/Block controls for users who want defense-in-depth. Off by default.
- Skill pill renamed from `Skill` to `Tool`, demoted from primary (`bg-primary-500/10`) to neutral (`bg-white/5`) — visually aligns with its new information-only role.
- Section header renamed `Skills (N)` → `Capabilities (N)`. Subtitle added: `available to Daena + agents in scope` when connected.
- Connected-account identity strip promoted from muted subtitle to dedicated pill with `UserCircle` glyph + green accent: `Signed in as <email>`.
- Tab labels cleaned: `Extensions` (was "MCP Servers" — too narrow); `Plugins` (kept) with new `Plug` icon instead of duplicate `Puzzle`.

### Layer 3 · MCP Servers as a first-class tab

Files modified: `frontend/src/pages/ConnectionsPage.tsx` (new tab + render block)

- New `mcp` tab driven by the existing `useMcpRegistry` hook (which polls `/connections/mcp-registry`).
- Entry cards show: display name, live-dot pill, package identifier, description, command + first few args (so operators can see `uvx something` vs `npx @scope/server` at a glance).
- "Legacy MCP import hint" panel surfaces MCPs found in other CLI configs (the existing `mcpSync` detection infra).
- Empty state explains the config path: `~/AppData/Roaming/Claude/claude_desktop_config.json` + points to the Plugins tab for one-click install.
- Refresh button re-runs the bootstrap scan without a backend restart.

## What was NOT shipped (deferred with reasons)

### OAuth end-to-end per provider — next ticket per provider

The OAuth launcher (`startOAuthConnect`), popup flow, and callback route already exist from Session 10/11. What's missing is *per-provider* profile-endpoint wiring so the "Signed in as <email>" pill shows for all 116 connectors, not just the 3-4 that already work (Google family + Notion + GitHub).

**Why not in this ticket**: each provider has its own profile endpoint, token-exchange quirks, and consent-screen edge cases. Doing 116 providers in a single commit would be 2-3 shallow implementations per provider and a guaranteed regression wave. The right cadence is one ticket per category (Google / Microsoft / Notion / Atlassian / Slack etc.), each with its own test matrix.

**Unblock for now**: the identity strip I just built *renders* the accountIdentity when it's populated; the provider-by-provider work in later tickets is purely backend-side. No frontend rework needed when the per-provider work lands.

### Agent permission UI — cross-cutting, needs DB schema work

The brief specifies `founder only / Daena core only / selected departments / selected agents / global` as a permission scope per connector. That's a real need, but it requires:

- new `connection_agent_permission` table
- tenant/workspace/user-scope FK plumbing
- a dedicated UI (probably inside the connector's expanded card, not the main scan)
- migration from the current all-or-nothing model

**Why not in this ticket**: schema work mid-refactor multiplies blast radius. Shipping the UX cleanup first without changing the DB gives a safe base to add the permission model onto.

### Icon normalization across all 116 connectors — design sprint

The brief asks for accurate brand icons for every provider. The current `CONNECTOR_ICONS` map has ~40 of them, with the remaining falling back to the generic `Plug` icon. Doing all 116 is legitimately a design-system sprint (SVG sourcing, dark-mode contrast tuning, radius + padding normalization).

**Why not in this ticket**: Icon work is grindy and visual-QA-heavy; bundling it with the UX refactor risks scope creep and visual inconsistency. The cleaner pattern is one dedicated "icon pass" ticket where all 116 get reviewed together.

## Files changed

| File | Change |
|---|---|
| `frontend/src/pages/ConnectionsPage.tsx` | `ConnectorRow` skill section now info-only + advanced drawer; tabs +MCP; identity strip; MCP tab render block; Lucide icon imports (Wrench, Server, Activity, UserCircle) |
| `docs/pitch/CONNECTIONS-REDESIGN-2026-04-18.md` | this file |

## Test checklist

- [x] Frontend `tsc -b --noEmit` clean
- [x] Existing ConnectorRow behavior preserved (auth flow, Save API key, OAuth connect, disconnect dropdown)
- [x] `showAdvanced=false` hides the per-tool `PermissionSelect` -- capabilities list is read-only
- [x] `showAdvanced=true` restores the legacy per-tool controls (no regression for power-users who want them)
- [x] MCP tab renders with empty state when registry is empty + config-path hint
- [x] MCP tab renders populated entries with live-dot pill + package + command preview
- [x] Refresh button re-polls `useMcpRegistry`
- [ ] Manual: connect Google Drive, confirm "Signed in as <email>" pill appears (requires live OAuth round-trip against backend)
- [ ] Manual: install an MCP server from Plugins tab, switch to MCP tab, confirm it shows up within the 10s poll window

## Acceptance criteria status

| # | Brief requirement | Status |
|---|---|---|
| 1 | Clicking Connect opens a real auth flow / secure credential modal | Already shipped (Session 10/11); UX clarified |
| 2 | User can sign into external account and Daena stores the connection | Already shipped; account identity pill added |
| 3 | Connected account identity visible on the card | **Shipped** (dedicated pill with UserCircle glyph) |
| 4 | Skills no longer treated as separate top-level install items | **Shipped** (capability rows, no per-skill CTA) |
| 5 | Capabilities auto-attached to connector | Was always true in data model; UI now reflects it |
| 6 | "Ask" no longer the main CTA per skill | **Shipped** (moved to Advanced drawer) |
| 7 | MCP servers restored/imported/manageable | **Shipped** (dedicated MCP tab, bootstrap scan) |
| 8 | Brand icons visually correct | **Deferred** — see "Icon normalization" |
| 9 | Daena and agents can use connected tools after auth | Was always true at call-graph level |
| 10 | Switch account / disconnect / refresh / debug | Already shipped (`Switch account`, `Disconnect`, new `Refresh` in MCP tab) |
| 11 | No duplicate files or parallel implementations | **Held** — all edits to existing canonical ConnectionsPage |
| 12 | Everything integrated cleanly | **Held** |

## Manual credentials the user still needs to provide

None for the shipped features. The per-provider OAuth completion (deferred) will need real client IDs + secrets for each provider — those land in `backend/.daena_oauth_overrides.json` via the existing setup modal when each provider's ticket runs.
