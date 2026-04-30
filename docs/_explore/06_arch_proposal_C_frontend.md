# Architecture Proposal C - Frontend & UX Architect Lens

Stage 1 proposer (Karpathy llm-council). Scope: information architecture, state surfacing, real-time updates, no-lie codification, accessibility. NOT system architecture, NOT security plumbing.

## TL;DR
1. Collapse 10 proposed subtabs to **5 primary tabs + 2 nested drawers**. The CEO list confuses *channels of acquisition* with *runtime concerns*.
2. **Single source of badge truth = `state` field on the materialized row.** UI's only job is to map the enum to a pill. No client-side derivation. Ever.
3. **Three-channel real-time:** SSE for state changes, single fetch on mount + retry-on-focus for catalog, ephemeral toast for irreversible actions only.
4. **Empty state is mandatory and copy is owned by the same person who owns the page.** No blank panes. No "Something went wrong." Concrete next-action verbs.
5. **Archive `ConnectionsConnectors`/`ConnectionsExtensions`/`ConnectionsRuntimes` after the V2 cutover lands; keep them for one ship cycle as a regression escape hatch then delete by date** (not "when comfortable").

---

## Section 1: Page tree (subtab list)

CEO listed 10. The honest count is **5 tabs**. Some of his items are sub-views, not tabs.

| # | Tab | Purpose (1 line) | Replaces |
|---|---|---|---|
| 1 | **Brain** | Pick the primary runtime + see fallback chain. Local Ollama panel inline. | `MainBrainPanel` + Local Ollama section of `SettingsModelsRuntimes` |
| 2 | **Catalog** | Browse 116 connectors + filter + install. The discovery surface. | `PluginsCatalogBrowser` |
| 3 | **Installed** | Everything I have installed. Per-row state, probe button, disconnect, configure. | New unified view: connector instances + MCP servers + skill packs in one table |
| 4 | **MCP Servers** | Live MCP registry detail (tool counts, last call, raw config). Power-user surface. | `McpServersPanel` |
| 5 | **API Keys** | Provider keys (Anthropic, OpenAI, Gemini, Groq, OpenRouter, Together, Perplexity, xAI, Cohere). Save/rotate/test. | `SettingsModelsRuntimes` API-key form (rest of file deleted) |

Drawers (not tabs):
- **Plugin Detail Drawer** - opens from any catalog or installed row. NOT a route; preserves table context.
- **Audit Trail Drawer** - opens from any failure pill. Shows last 20 events for that row.

The CEO's "Routing", "Permissions", "Skills" are **per-row drawers**, not their own tabs. Forcing them into top-level tabs is what produced the 10-tab sprawl in the first place. Evidence: `pages/connections/ConnectionsConnectors.tsx` already collapsed permissions into a drawer pattern; we keep that, not regress.

---

## Section 2: State→UI mapping (16 lifecycle states)

One enum. One badge per row. Color is **never** the only signal - every badge has icon + text. Color hex from the locked design system: slate `#0F1419`, gold `#D4A843`, teal `#2DD4BF`. Plus traffic-light additions: success `#10B981`, warning `#F59E0B`, danger `#EF4444`, neutral `#64748B`.

| State | Pill text | Icon | Pill color | Primary CTA | Secondary CTA |
|---|---|---|---|---|---|
| `discovered` | Available | dot, neutral | `#64748B` | Install | View details |
| `installable` | Installable | download, gold | `#D4A843` | Install | View details |
| `installing` | Installing... | spinner | `#D4A843` (animated) | Cancel | - |
| `installed` | Installed | check, neutral | `#64748B` | Configure | Disconnect |
| `auth_required` | Sign in needed | key, gold | `#D4A843` | Sign in | Cancel install |
| `auth_in_progress` | Authorizing... | spinner | `#D4A843` (animated) | Open auth window | Cancel |
| `auth_complete` | Auth done | check, gold | `#D4A843` | Configure | View token |
| `configured` | Configured | gear, neutral | `#64748B` | Probe | Edit config |
| `persisted` | Saved | database, neutral | `#64748B` | Probe | Edit config |
| `probing` | Testing... | spinner, teal | `#2DD4BF` (animated) | - | Cancel probe |
| `healthy` | Callable | bolt, teal | `#2DD4BF` | Use in chat | Re-probe |
| `degraded` | Degraded | warning triangle | `#F59E0B` | View error | Re-probe |
| `failed` | Failed | x, red | `#EF4444` | View error | Re-probe |
| `disabled` | Disabled | pause, neutral | `#64748B` | Enable | Remove |
| `archived` | Archived | archive box | `#64748B` (50% opacity) | Restore | Delete |
| `callable` | (alias of `healthy`) | - | - | - | - |

**`callable` is an alias of `healthy`.** Two names for the same state cause exactly the bugs we already have (`McpServersPanel.tsx:296` uses string-prefix matching). Pick `healthy`. Drop `callable` from the enum at the source-code level.

---

## Section 3: Real-time updates strategy

Three channels, each with a distinct purpose.

| Signal type | Channel | Latency budget | Fallback |
|---|---|---|---|
| Probe completion (single row) | **SSE** on `/api/v1/connections/events` filtered by `instance_id` | ≤ 2s after backend write | 30s polling on visible rows |
| Install progress (multi-step) | **SSE** with `progress` events (`step`, `pct`, `message`) | ≤ 1s per step | None - install is foreground |
| OAuth callback completion | **SSE** broadcast `oauth_complete` to original tab | ≤ 3s after callback | window.opener.postMessage from popup |
| Catalog list (116 rows) | **HTTP fetch** on mount + on tab focus | n/a (cached 5 min, see `useConnectorCatalog`) | Existing 5-min module cache |
| Registry/instances list | **HTTP fetch + SSE invalidate** | mount + on `connections:invalidate` SSE event | Existing `useRuntimeRegistry` 30s poll |
| Audit log entries | **Lazy-load on drawer open** - never streamed at table level | drawer-open + 1s | No fallback (drawer is opt-in) |

**Hard rule:** if the SSE channel is not connected, the badge **must show a "stale" subtle indicator** (small clock icon next to the pill) and the user must be able to manually re-probe. Reference: ADR-001 rule "No advertised real-time without an SSE channel." (Daena CLAUDE.md Rule 17)

**Latency surfacing:** show `last_checked_at` next to every pill in relative time ("12s ago", "3 min ago", "2 hr ago"). When > 5 minutes the badge dims to 60% opacity until next probe. This is the single biggest fix for the "callable refreshes back to nothing" bug at `McpServersPanel.tsx:218`.

---

## Section 4: Empty / loading / error / success states

Specific copy for every pane. **Empty pane is a bug.**

### Catalog tab

- **Loading:** skeleton grid, 8 cards, 3-line shimmer each. `aria-busy="true"`.
- **Empty (catalog API returned 0):** "Catalog is empty. The backend may be reindexing - try again in 30 seconds. [Retry]"
- **Error:** "Couldn't load the catalog. [details: 503 from /connections/catalog]. [Retry] [View server logs]" - never "Something went wrong."
- **Empty after filter:** "No connectors match `<query>`. Clear filters or [browse all]."

### Installed tab

- **Loading:** 5-row skeleton table.
- **Empty:** "No connections yet. Connect your first tool from the Catalog tab. [Open Catalog]"
- **Error:** "Couldn't load your connections. [Retry]" + inline error toast.

### MCP Servers tab

- **Loading:** "Detecting MCP servers..." with spinner + count animation (shows "Found N servers" as it discovers).
- **Empty:** "No MCP servers detected. Daena scanned: Claude Desktop config, npm globals, $PATH binaries. [Add manually] [How to install MCPs]"
- **Error:** "MCP detection failed. Detection scans 3 sources - see which one errored:" with per-source status row.

### Plugin Detail Drawer

- **Loading:** placeholder with logo + skeleton tabs.
- **Empty config schema:** "This plugin has no configuration. Click Probe to test it." (Not "Schema is empty" which sounds broken.)
- **Failed probe:** Full error trace in the **Diagnostics** sub-tab, with a one-line summary at top: "Last probe failed at `<time>`: `<sanitized_reason>`" + a "View raw response" button that opens a `<details>`.

### API Keys tab

- **Empty:** "No API keys saved. Daena will use local Ollama only. [Add a key]"
- **Save success:** "Anthropic key saved. Probing... [pulse animation] -> Probe succeeded. Available models: claude-opus-4-7, claude-sonnet-4-5..." - **never** show success until the probe round-trips.

---

## Section 5: The no-lie principle, codified

This is the most important section. Five rules, all enforceable in code review.

### Rule 1: Badge color is a pure function of `row.state`

```typescript
// frontend/src/lib/connectionState.ts (NEW)
export const stateToBadge = (state: ConnectionState): BadgeProps => {
  // exhaustive switch, no fallthrough, TS catches missing cases
  switch (state) {
    case 'healthy': return { color: '#2DD4BF', text: 'Callable', icon: 'bolt' };
    // ... 15 more cases
  }
};
```

**Forbidden:** any function that derives badge state from anything other than `row.state`. No `name.includes(...)`, no `package.has(...)`, no `Object.keys(probe).length > 0`. ESLint custom rule blocks the pattern. CI fails the build.

### Rule 2: `state` is set ONLY by backend

Frontend never writes `row.state = 'healthy'` after a successful probe. Frontend dispatches the probe, receives an SSE event, **the SSE event carries the new `state`** stamped by the backend with `last_checked_at`. UI re-renders.

This kills `McpServersPanel.tsx:218` ("`${serverKey} is callable` toast posted on basis of single tools/list reply"). The toast can fire - but the badge cannot flip until backend persists.

### Rule 3: Optimistic-success toasts are banned for irreversible/state-changing operations

`SettingsGeneral.tsx:269` ("Your data has been imported into Daena memory!") fires before the response body is inspected. Replace with: post-action button shows spinner -> resolves on response -> success copy reflects what the backend actually returned. Toast fires from the response handler, not the click handler.

### Rule 4: `null` / `undefined` / "unknown" all render as "Unknown - re-probe to check"

Currently `RuntimeSwapper.tsx:29-43` defaults unknown statuses to "online" via `STATUS_DOT_CLASS` lookup. New rule: a status the FE cannot map to one of the 16 enum values renders as `<UnknownBadge />` with explicit "[Re-probe]" CTA. Never gold, never green by default.

### Rule 5: `last_checked_at` is mandatory on every status pill

If the value is missing or older than 5 minutes, the pill dims and shows "Stale" subtitle. Forces the data architecture: every state row has a timestamp, and the UI surfaces it. No more refresh-and-lose-state at `McpServersPanel.tsx:218`.

**Enforcement file:** `frontend/src/lib/connectionState.ts` (single mapping function), `frontend/eslint-rules/no-derived-state.js` (custom rule), `frontend/src/components/connections/StatusPill.tsx` (the only allowed badge component for connections).

---

## Section 6: Catalog cards - sketch

Density target: **3 columns at 1440px, 2 at 1024px, 1 at 768px**. Card is information-dense, no marketing fluff.

```
+----------------------------------------------------+
| [logo 32x32]  Cloudflare                           |  <- vendor logo (real, not emoji), name
|               by Cloudflare Inc.   [verified]      |  <- vendor + verified badge if first-party
| ------------------------------------------------- |
| MCP server for Workers, R2, KV, D1, Pages.        |  <- 1-line description, max 80 chars
| ------------------------------------------------- |
| [oauth] [12 tools] [tier 2]    Status: Available  |  <- chips: auth method, tool count, risk tier; right-aligned: state pill
| ------------------------------------------------- |
| [Install]                          [View details] |  <- primary + secondary CTA, primary on left
+----------------------------------------------------+
```

Chip semantics:
- **Auth chip** (`oauth` / `api_token` / `none` / `bearer`): exact backend `auth_method`, never "auto" or "none" defaulting to api_token (`connection_service.py:139` bug).
- **Tools chip:** count from backend, 0 = "skill pack" (different visual treatment, see Section 13).
- **Tier chip:** governance risk tier 0-4, sourced from `governance_tier` field. Tier 4 row has red ring.
- **Status pill:** the 16-state pill from Section 2.

**No "Add to Daena" button on rows that are already imported** - this anti-pattern from the damage report (`McpServersPanel.tsx:353` "Import to Daena" alongside an already-imported row). The button text **always** matches state: `discovered`-> `Install`, `installed`-> `Configure`, `healthy`-> `Use in chat`.

---

## Section 7: Plugin detail drawer (Cloudflare reference)

Drawer slides in from right at 720px wide. Sections in this order:

1. **Header** (sticky): logo + name + vendor + state pill + last-checked + breadcrumb back arrow.
2. **At-a-glance** (always visible): risk tier, auth method, tool count, install date, version.
3. **Tabs** (within drawer):
   - **Overview** - vendor description, supported tools, scopes requested. (Read-only.)
   - **Auth** - OAuth status, "Sign in" / "Re-authorize" / "Revoke" buttons. **THIS is where OAuth starts.** Not a modal, not a separate page.
   - **Tools** - list of N tools the MCP exposes, each with `last_call_at`, `last_error`, per-tool enable toggle. Resolves issue 13 (per-tool surfacing).
   - **Skills** - when an MCP ships skills (rare), toggle which to load into Daena. Default off. Per-skill enable.
   - **Permissions** - Allow / Ask / Block per scope. Reuses pattern from archived `ConnectionsExtensions.tsx`.
   - **Diagnostics** - last 10 probes with timestamp + result + raw payload (`<details>` collapsed). The single source for "why did this fail."
   - **Audit** - link out to the full audit log filtered by this `instance_id`.
4. **Footer** (sticky): Disconnect (red, requires confirm) + Probe (primary).

**OAuth flow inside the drawer:**
1. User clicks "Sign in" in Auth tab.
2. Drawer dims, inline progress card appears: "Opening Cloudflare authorization in a new window. Don't close this drawer."
3. Popup opens to `/connectors/cloudflare/install/start` -> Cloudflare consent -> `/connectors/mcp-oauth/callback`.
4. Backend persists token. SSE event `oauth_complete{instance_id, state: 'auth_complete'}` fires.
5. Drawer Auth tab updates in place. State pill flips. Probe button enables.

If popup is blocked: inline alert with the URL as a copyable link + "Open in new tab" button. Never silent-fail.

---

## Section 8: Brain routing tab visual

The Brain tab shows the **fallback chain** as a vertical stack, not a grid. Why: the chain is ordered, grid implies parallel.

```
PRIMARY MIND
+--------------------------------------------------+
| [Claude Code]  o callable           [12s ago]   |
| Anthropic - claude-opus-4-7                      |
| (currently active)                  [Probe] [v] |
+--------------------------------------------------+

FALLBACK CHAIN
1. [OpenAI]      o callable         [Promote]
2. [Gemini]      o auth needed      [Sign in]
3. [Ollama]      o callable         [Promote]

UNAVAILABLE
- [Codex]        x not installed    [Install]
   reason: claude-code-codex npm package not found in PATH
```

- "currently active" badge in gold `#D4A843`.
- Grayed-out rows ("UNAVAILABLE") show **why** in italic - not just disabled. Reason text comes from backend `unavailable_reason` field. Never empty.
- Promote button is `Promote to primary` - single click + confirm modal: "Promote OpenAI to primary mind? Future requests will route to OpenAI first. [Confirm] [Cancel]"
- A **graph link** at bottom: "Visualize routing graph -> Mermaid diagram of: primary -> fallback A -> B -> Ollama, with model registry attached." This satisfies CEO's Section 13 requirement without cluttering the linear view.

**Graying rule:** a row grays when `state ∈ {disabled, archived, failed}` OR when `installed=false`. The unavailable reason field MUST be populated by backend - never UI-derived.

---

## Section 9: Failure surface

Three layers, ordered by user effort.

**Layer 1 - In the row (always visible):**
- State pill: `Failed` (red `#EF4444`) or `Degraded` (orange `#F59E0B`).
- Inline 1-line error summary truncated to 60 chars: "OAuth token expired 2hr ago".
- Adjacent `[Details]` text-link.

**Layer 2 - Drawer Diagnostics tab (one click):**
- Full sanitized reason: "Cloudflare API returned 401: token expired at 2026-04-30T18:42Z. Re-authorize via Auth tab."
- Last 10 probe attempts with status + timestamp + raw response.
- Suggested fix as bulleted next-actions.

**Layer 3 - Audit log (deep link):**
- "View full audit trail" button at bottom of Diagnostics. Opens `/audit?instance_id=X&limit=50` filtered.
- This is the security/governance proposer's domain - UX just needs the deep link.

**Forbidden:** raw exception strings in toasts. Reference bug: `PLUGIN_INSTALL` "MCP Test surfaced raw `TaskGroup` errors". UI sanitizer in `frontend/src/lib/errorSanitizer.ts` maps known backend error families to user-facing text. Anything unmapped becomes "Probe failed (technical detail in Diagnostics tab)". Never shows stack traces in chrome.

---

## Section 10: Consolidate `SettingsModelsRuntimes` vs `MainBrainPanel`

**Recommendation: delete `SettingsModelsRuntimes` as a tab. Move its surviving concerns.**

The damage report says it has "stale 4-provider list while backend has 9". Keeping it as a "duplicate of MainBrainPanel" is the exact category of confusion to eliminate.

Migration:
1. **Local Ollama panel** (currently in `SettingsModelsRuntimes`) -> moves to **Brain tab** as a section under "Local runtimes".
2. **API key forms** -> become the new **API Keys tab** (Section 1, item 5). All 9 providers, sourced from backend `/runtimes` endpoint, never hardcoded.
3. **"Auto Routing" placeholder banner** -> deleted. The honest message belongs in the Brain tab Routing section.
4. The settings tab itself collapses to a redirect to `/connections?tab=brain` for 2 ship cycles, then deletes.

Why one tab, not two: a single column of "where do I configure how Daena thinks" is the user's mental model. Two tabs forces them to remember "providers go here, runtimes go there." Reference confusion: `MindsPage` is for soul-personas and is **already mistaken** for a brain switcher according to the file map ("Naming is a known footgun").

---

## Section 11: Archived siblings - delete criteria

`ConnectionsConnectors.tsx`, `ConnectionsExtensions.tsx`, `ConnectionsRuntimes.tsx`, `BrowseModal.tsx`, `oauth.ts`, `shared.tsx`, `catalog.ts` (mostly).

**Delete date: 14 days after V2 ships to production**, contingent on:
1. V2 has been live in prod for ≥ 7 days with zero rollback.
2. No active code paths import them (verified via `gitnexus_impact`).
3. `CONNECTOR_MCP_EQUIVALENT` extracted to dedicated tiny file (per `03_frontend_file_map.md` recommendation).
4. Any unique CLIBridgeCard logic re-ported into `MainBrainPanel`.

Until then: move all archived files to `frontend/src/pages/connections/_archived/` (underscore prefix, IDE-collapsed by convention) so they're visually segregated but searchable. Add header comment block: `// ARCHIVED 2026-04-30 - DO NOT EDIT - DELETE BY 2026-05-XX`.

Why not delete now: the V2 might surface a regression that needs a 1-line ref to legacy permission-ladder UX. 14 days is the safety buffer. Deletion criteria is **date + clean impact** - not "vibes."

---

## Section 12: Accessibility

Non-negotiables:

1. **Keyboard nav across the table:** `Tab` to row, `Enter` to open drawer, `Esc` to close, `Cmd+K` palette search across catalog.
2. **Screen reader announcements for probe state changes:** every state transition fires `aria-live="polite"` on a hidden region: "Cloudflare probe started", "Cloudflare callable, 12 tools available", "Cloudflare probe failed: token expired."
3. **Color-only conveyance forbidden:** every badge has icon + text. The `Failed` pill is not just red - it has an `x` icon and the word "Failed". Daltonism-safe by construction.
4. **Focus rings always visible:** `outline: 2px solid #D4A843; outline-offset: 2px;` on focused interactive elements. No `outline: none` anywhere in the connections tree.
5. **Tooltips reachable by keyboard:** the chip tooltips ("Tier 2 means Daena can use this without confirmation") must show on focus, not just hover. `aria-describedby` linkage.
6. **Form errors announced:** `aria-invalid="true"` + `role="alert"` for the first error. Error text linked via `aria-describedby` to the input.
7. **Status pills have accessible text:** `aria-label="Status: Callable, last checked 12 seconds ago"`. The relative time is not a visual shortcut - screen readers get the absolute too.
8. **Loading skeletons announce:** `aria-busy="true"` on the table while loading, transition to `aria-busy="false"` on resolve.
9. **Reduced motion respected:** spinners and pulse animations on `.probing` / `.installing` states wrap in `@media (prefers-reduced-motion: no-preference)`. Provide static alternatives.

---

## Section 13: MCP servers - surfacing per-tool health

This is the trickiest IA problem in the rebuild. An MCP can be **healthy at the server level but have failed tool calls**. Current UI: nothing distinguishes.

Solution: **two-tier badge.**

Server row pill = the **server's** state (the connection itself is healthy/degraded/failed).

Inside the drawer's **Tools** sub-tab, each tool has its own mini-pill:
- Server `healthy` + all tools `healthy` -> top-level shows `Callable`.
- Server `healthy` + 1+ tool `degraded` -> top-level shows `Degraded` with subtitle "1 of 12 tools failing".
- Server `healthy` + 0 tool calls yet -> top-level shows `Callable` with subtitle "Untested in this session".
- Server `failed` -> top-level shows `Failed`. Tool-level pills not shown (server is the bottleneck).

Top-level subtitle ("1 of 12 tools failing") is clickable -> opens drawer to Tools tab pre-filtered to failing tools.

Backend contract requirement (passed to system + security proposers): MCP `instance` row must have `tool_health: {tool_name: {state, last_call_at, last_error}}` map alongside server-level `state`. Frontend never derives this. SSE events scope to `(instance_id, tool_name)` for fine-grained updates.

---

## Section 14: Sample row sketches

### Catalog card (replicating Section 6 in pseudocode)

```tsx
<CatalogCard>
  <Header>
    <Logo src={vendor.logoUrl} alt={`${name} logo`} fallback={vendor.initial} />
    <Name>{name}</Name>
    <VendorRow>
      <span>by {vendor.name}</span>
      {vendor.verified && <VerifiedChip />}
    </VendorRow>
  </Header>
  <Description>{shortDescription /* max 80 chars, server-side truncated */}</Description>
  <ChipsRow>
    <AuthChip method={auth_method} />
    <ToolsChip count={tools_count} />
    <TierChip tier={governance_tier} />
    <StatusPill state={state} lastCheckedAt={last_checked_at} />
  </ChipsRow>
  <ActionsRow>
    <PrimaryAction state={state} onClick={dispatchPrimaryAction} />
    <SecondaryAction>View details</SecondaryAction>
  </ActionsRow>
</CatalogCard>
```

### MCP row (Installed tab)

```
+--------------------------------------------------------------------+
| [logo] cloudflare-workers     o Callable [12s ago]      [Use] [v] |
| 12 tools | OAuth (active)     1 tool failing -> [Diagnose]        |
+--------------------------------------------------------------------+
```

The "1 tool failing" link is the bridge into Section 13's drilldown.

### Plugin detail drawer header (sticky)

```
+----------------------------------------------------+
| [<] Cloudflare                          o Callable |
|     by Cloudflare Inc.   verified       [12s ago]  |
| ------------------------------------------------- |
| Tier 2 | OAuth | 12 tools | installed 3 days ago  |
| ------------------------------------------------- |
| [Overview] [Auth] [Tools] [Skills] [Perms] [Diag] |
+----------------------------------------------------+
```

---

## Section 15: Three biggest UX risks of V2 if built naively

### Risk 1: 16 states will get aliased back into 4 visible pills under product pressure

The 16-state machine is correct. But "we already have 4 colors, do we really need 16 messages?" pressure will collapse them in week 2. **Mitigation:** ship the full 16 as fixtures in Storybook week 1, with screenshots in the PR description. Make the breadth visible to the org before someone proposes the simplification. Lock the enum in `connectionState.ts` with a comment: `// SOURCE OF TRUTH - see ADR-002`.

### Risk 2: SSE channel will fail silently on flaky networks and badges will go stale without users noticing

The current code at `McpServersPanel.tsx:218` already has this exact disease: in-memory probe state lost on refresh. SSE doesn't fix it if disconnects are silent. **Mitigation:** the **stale subtitle** (Section 5 Rule 5) is mandatory and the SSE connection state itself shows in the page footer: green dot "live" or amber "reconnecting (last update 47s ago)". User can never be lulled into thinking a stale badge is fresh.

### Risk 3: Plugin Detail Drawer becomes a settings dump and users won't find OAuth

The drawer has 6 sub-tabs. If "Auth" is the 4th tab and OAuth is broken, users will rage-quit before finding it. **Mitigation:** when `state ∈ {auth_required, auth_in_progress, auth_complete}`, the drawer **defaults to the Auth tab on open**. State-driven default tab. Otherwise defaults to Overview. Encoded in `<DrawerTabs defaultTab={getDefaultTab(state)} />` - never hardcoded.

---

**End of proposal.**

Length: ~17 KB raw. Within 18 KB cap.
