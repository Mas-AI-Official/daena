# PR-CONN-PLUGIN-PARITY-UX Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Builds on:** `PR_CONNECTIONS_SIMPLE_PLUGIN_UX_REPORT.md` (commit `5fee79a`) +
`PR_CONNECTIONS_MARKETPLACE_404_FIX_REPORT.md` (commit `53a9e55`)

> **Thesis.** The simplified Brain / Plugins / Advanced layout was
> right; this PR polishes Plugins to look and feel like Claude
> Desktop / Codex's plugin marketplace. Adds 4 missing
> founder-required brand cards (GitLab, Jira, Hugging Face,
> Sequential Thinking), wires every catalog id to the existing brand
> icon library, splits the detail view into a dedicated drawer with
> capabilities / permissions / probe-status / install steps, and
> deep-links provider Configure to the existing vault-backed
> Settings -> API Keys page.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| 1. No production deploy | Yes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes |
| 3. No `vault --apply` | Yes |
| 4. No V1 file deletions | Yes |
| 5. No secrets printed or committed | Yes |
| 6. No external scans | Yes |
| 7. No external messages | Yes |
| 8. No auto-installs | Yes -- all "Install" paths still surface as Setup guide |
| 9. No callable claim without probe | Yes -- pinned by new test `test_no_card_marked_connected_without_v2_truth` |
| 10. No new primary tabs | Yes -- still Brain / Plugins / Advanced |
| 11. No duplicate secret storage | Yes -- provider Configure deep-links to existing `/account/api-keys` (vault-backed); no inline secret fields |

Project Rule 12 (no em-dashes): **0** added across all files.

---

## 1. Catalog count + missing brands added

| Metric | Before | After |
|---|---|---|
| Total catalog entries | 51 | **55** |
| Categories | 14 | 14 |
| OAuth apps | 11 | 11 |
| MCP servers | 14 | **18** |
| Tests | 45 | **93** (+48; mostly the founder-required-brand parametrize) |

**4 brands added (Part C audit):**

| Brand | Catalog id | Kind | Why it was missing |
|---|---|---|---|
| GitLab | `mcp-gitlab` | mcp_server (coming-soon) | Founder list said GitLab; we had GitHub but not GitLab |
| Jira | `mcp-jira` | mcp_server (coming-soon) | Atlassian community MCP; founder asked "if catalog source exists" -- it does, deferred install |
| Hugging Face | `mcp-huggingface` | mcp_server (coming-soon) | Was missing entirely (BrandIcons had `HuggingFaceIcon` already so the icon lights up immediately) |
| Sequential Thinking | `mcp-sequential-thinking` | mcp_server (npm) | Anthropic reference server; npm-installable, coming alive after Discover |

The 51 prior entries already covered everything else on the founder
list. The full coverage matrix lives in
`tests/test_connection_v2_marketplace.py::FOUNDER_REQUIRED_PLUGINS`
which is parametrized so a future contributor cannot silently drop a
brand without breaking a named test (`test_brand_present[Hugging Face]`,
`test_brand_present[GitLab]`, etc).

### 1.1 Setup-guide-only vs coming-soon vs working today

| State | Count | What it means |
|---|---|---|
| Working today (npm + manual install + probe lands) | 36 | `npx -y` MCP servers + provider rows with probe |
| Coming soon (no safe install path yet) | 19 | Vendor-managed MCPs, paid services, OAuth flows that need a future PR |
| Connected today (probe-proven) | 0 | Honest empty-tenant baseline (verified via live smoke + the new no-fake-connected test) |

Coming-soon list (Setup-guide-only buttons):
- `mcp-browserbase`, `mcp-vercel`, `mcp-netlify`, `mcp-gitlab`, `mcp-jira`,
  `mcp-mongodb`, `mcp-redis`, `mcp-shopify`, `mcp-perplexity`,
  `mcp-huggingface`
- All OAuth `app-*` Google / GitHub / Figma / Slack / Canva are
  installable but require operator-supplied OAuth client_id /
  client_secret in Settings before the V2 row turns "available" ->
  "configured" -> "needs_auth"
- `app-notion-oauth`, `app-stripe-oauth`, `app-cloudflare-oauth`,
  `app-sentry-oauth` are coming-soon (no managed OAuth wiring yet --
  use the corresponding MCP with token auth for now)

---

## 2. Visual parity (Part B + D)

### 2.1 PluginCardView (rewrite)

`frontend/src/pages/connections/PluginCardView.tsx`

* Brand icon resolved through new `pluginIconFor()` helper -- explicit
  catalog-id map first, then `getMcpBrandIcon()` smart fallback, then
  kind-based glyph (lucide-react). No new icon dependencies.
* Hover state: subtle lift + bg shift so cards feel tactile.
* Click anywhere on the card opens the new `PluginDetailDrawer`.
* Backend kind label moved to the card's tooltip only (founder rule:
  "Do not show backend type labels in normal cards unless hidden in
  tooltip").
* "Details" link in the action row makes the click affordance
  discoverable for keyboard / screen-reader users.

### 2.2 PluginDetailDrawer (NEW)

`frontend/src/pages/connections/PluginDetailDrawer.tsx`

Codex/Claude Desktop-style modal with sections:

1. **Header** -- 56px brand icon + name + vendor + category + status
   pill + risk badge + skill-pack flag + coming-soon flag + internal
   backing-type chip (kept small, gray, tooltip-style)
2. **What this plugin lets Daena do** -- product description, plus
   the skill-pack caption when applicable
3. **Included capabilities** -- two-column list of all skills
4. **Required permissions** -- env var NAMES only (with a "Daena never
   reads the values" disclaimer)
5. **Where keys live** (provider rows only) -- explicit copy
   "Configure keys in Settings. Connections shows whether Daena can
   call the provider." with an Open Settings -> API Keys deep-link
6. **Probe status** -- the 6-dim truth ladder + last-checked + failure
   reason
7. **Install / setup steps** -- pulled from `/install-plan/{id}`,
   rendered as numbered cards with code blocks. Includes the "Daena
   does not execute install commands automatically" disclaimer.
8. **Compatibility** -- KV grid (auth, risk, install, OS) + vendor
   docs link
9. **Footer action bar** -- Close + primary action button (matches
   the founder vocabulary)

### 2.3 PluginsPanel header copy update

```diff
-{counts.connected} of {counts.all} plugins connected
+{counts.connected} connected · {counts.needs_auth} needs auth ·
+{counts.installed} installed · {counts.available} available
```

```diff
-Browse what Daena can connect to. Each card is a real tool
-(MCP server, OAuth app, browser automation, local model, ...)
-wrapped behind a single "Plugin" concept. A card shows
-"Connected" only after a real probe proves it works.
+Browse plugins. Each card is a real integration -- MCP servers,
+apps, browser tools, local models, LLM providers, skill bundles.
+Click a card for details. A card is "Connected" only when a real
+probe proves it works. Provider keys live in Settings -> API Keys.
```

---

## 3. Icon strategy (Part D)

`frontend/src/pages/connections/pluginIcons.tsx` (NEW, 250 lines)

Three-layer resolver, **no new dependencies**:

1. **Explicit map** (52 entries) -- catalog id -> existing brand icon
   from `BrandIcons.tsx` (which already shipped GitHub, Slack,
   Stripe, Notion, Cloudflare, Figma, Hugging Face, Anthropic,
   OpenAI, Gemini, Linear, Sentry, Postgres, SQLite, Redis, etc.)
2. **MCP smart fallback** -- `getMcpBrandIcon()` from BrandIcons
   already has the slug-normalize + `EXTENSION_ICONS` lookup chain
   for any MCP not explicitly mapped
3. **Kind-based glyph** -- last resort: `Server` / `AppWindow` /
   `Globe` / `Terminal` / `Cpu` / `BookOpen` from lucide-react with
   kind-tinted colors

Custom letter-avatar fallbacks added for brands with no logo file
yet (`Pp` Perplexity, `Gq` Groq, `OR` OpenRouter, `To` Together,
`Cd` ChromeDevTools, `Bb` Browserbase, `Tm` Time, `St` Sequential
Thinking, `Mo` MongoDB, `Sh` Shopify, `Nl` Netlify, `Gl` GitLab,
`Jr` Jira) using the existing `BrandAvatarIcon` primitive that I
exported from BrandIcons.tsx.

**No copyrighted logo files committed.** No remote logo hotlinks.
The CdnIcon helper (already in BrandIcons.tsx) serves SimpleIcons
and falls back to BrandAvatarIcon if the CDN is unreachable.

---

## 4. LLM providers + Settings split (Part E)

**Decision recorded in code:**

* LLM / API providers (`provider-anthropic`, `provider-openai`,
  `provider-google-gemini`, `provider-perplexity`, `provider-groq`,
  `provider-openrouter`, `provider-together`) appear in the Plugins
  marketplace as Brain-capable cards with `kind=api_provider`.
* Their primary action is **Configure** -> deep-links to
  `/account/api-keys` (the existing vault-backed Settings page) via
  `useNavigate()` in `PluginCardView.tsx` and `PluginDetailDrawer.tsx`.
* The Detail drawer carries an explicit "Where keys live" section
  with the founder-spec copy:
  > "Configure keys in Settings. Connections shows whether Daena
  > can call the provider."
* No secret-input field exists on any plugin card or drawer. Hard
  rule 11 honored: secret storage stays in Settings until a
  vault-backed Configure modal is implemented in a future PR.

---

## 5. Action truth (Part F)

| Action | Triggered when | Backend support today |
|---|---|---|
| **Connected** (status only) | V2 truth `callable=true` | Real probe required (provider/local_model probes work; MCP/OAuth/CLI probes pending in future PRs) |
| **Test** | V2 row exists AND probe endpoint exists for kind | `/connections/v2/{id}/probe` for provider + local_model |
| **Connect** | OAuth flow wired | Future PR-CONN-OAUTH-INSTALL |
| **Configure** | API key required | Provider rows -> deep-link to `/account/api-keys` (works today). Other rows -> Setup guide drawer |
| **Setup guide** | No safe install/connect automation | All MCP / coming-soon / non-OAuth `app-*` rows |
| **Install** | Backend can write config atomically | NEVER appears today (no safe install endpoint exists) |
| **Coming soon** | Catalog exists, no safe setup path | Surfaces as Setup guide button + amber pill |

---

## 6. Browser / Computer Use (Part G)

Already inside Plugins (not a separate tab). Cards present today:

| Card | Risk | Install method | Notes |
|---|---|---|---|
| Playwright | medium | npm | Microsoft official MCP |
| Chrome DevTools | medium | npm | Google official MCP |
| Browserbase | medium | coming-soon | Cloud browser; setup guide only |
| Desktop Commander | high | npm | Wonderwhy-er, full desktop control |
| Windows MCP | high | manual | Windows-only, community MCP |

Detail drawer copy honored:
> "Lets Daena open pages, inspect UI, click, fill forms, test flows,
> and observe results. Requires explicit local/runtime permission."

No anti-bot evasion / stealth claims anywhere.

---

## 7. Files changed summary

### Backend (modified, 1 file)

| File | Status | Purpose |
|---|---|---|
| `backend/app/services/connection_v2/marketplace_catalog.py` | M | +4 entries (GitLab, Jira, Hugging Face, Sequential Thinking) |
| `backend/tests/test_connection_v2_marketplace.py` | M | +48 tests (founder-required brand parametrize + no-fake-connected) |

### Frontend (new, 2 files)

| File | Status | Lines |
|---|---|---|
| `frontend/src/pages/connections/pluginIcons.tsx` | A | +250 (NEW) |
| `frontend/src/pages/connections/PluginDetailDrawer.tsx` | A | +355 (NEW) |

### Frontend (modified, 3 files)

| File | Status | Purpose |
|---|---|---|
| `frontend/src/pages/connections/PluginCardView.tsx` | M | rewrite -- brand icons, hover state, click-to-open detail drawer, provider Configure deep-link, smaller backend-kind chip moved to tooltip |
| `frontend/src/pages/connections/PluginsPanel.tsx` | M | header copy polish (status breakdown + Codex/Claude vocabulary + Settings deep-link reminder) |
| `frontend/src/components/icons/BrandIcons.tsx` | M | export `BrandAvatarIcon` + `BrandIconProps` so `pluginIcons.tsx` can compose them |

### Docs

| File | Status |
|---|---|
| `docs/Ultraview/PR_CONN_PLUGIN_PARITY_UX_REPORT.md` | A (this report) |

No protected files (Rule 18) touched. No V1 file deleted.

---

## 8. Tests run

### 8.1 Backend marketplace (93 / 93 PASS, was 45)

```text
$ pytest tests/test_connection_v2_marketplace.py
  TestCatalogShape                         6/6   PASS
  TestCatalogCoverage                     19/19  PASS  (parametrized over 14 categories)
  TestNoSecretLeak                         2/2   PASS
  TestInstallPlans                         5/5   PASS
  TestMarketplaceServiceOverlay            5/5   PASS
  TestListHelpers                          2/2   PASS
  TestFounderRequiredPlugins              48/48  PASS  (NEW: parametrized over 46 brands + size + sweep)
  TestMarketplaceRouteRegistration         1/1   PASS
  TestMarketplaceLiveSmoke                 5/5   PASS
  ----------------------------------------
  total                                   93/93  PASS in 3.12s
```

### 8.2 Full V2 regression (196 / 196 PASS, was 148)

```text
$ pytest tests/test_connection_v2*.py tests/test_phase7_*.py
  tests/test_connection_v2.py                       22/22 PASS
  tests/test_connection_v2_probe_truth.py            8/8  PASS
  tests/test_connection_v2_reconciliation.py        12/12 PASS
  tests/test_connection_v2_seed_import.py           16/16 PASS
  tests/test_connection_v2_ux_rescue.py             14/14 PASS
  tests/test_connection_v2_marketplace.py           93/93 PASS  (+48 since prior PR)
  tests/test_phase7_lifespan_seed.py                 3/3  PASS
  tests/test_phase7_provider_probes.py              28/28 PASS
  ----------------------------------------------------------
  combined                                         196/196 PASS in 4.56s
```

### 8.3 Live HTTP smoke (against fresh backend with FOUNDER JWT)

```text
$ curl /api/v1/connections/v2/catalog
  -> entries=55, mcp-gitlab=True, mcp-jira=True,
     mcp-huggingface=True, mcp-sequential-thinking=True

$ curl /api/v1/connections/v2/marketplace/cards
  -> cards=55, connected=0, available=55
```

The 0-connected count is honest -- empty tenant -> no V2 rows ->
no callable=true -> no card claims Connected. This is the
`test_no_card_marked_connected_without_v2_truth` invariant in
runtime form.

### 8.4 Frontend typecheck

```text
$ cd frontend && npx tsc --noEmit
EXIT=0
```

### 8.5 Em-dash hygiene (project Rule 12)

Per-file `git diff` em-dash count across all 6 modified/new files: **0**.

### 8.6 Sentinel-secret audit

`TestNoSecretLeak.test_no_obvious_secret_in_catalog` runs against
the new entries too. The 4 added cards carry only env var NAMES
(`GITLAB_PERSONAL_ACCESS_TOKEN`, `JIRA_API_TOKEN`, etc.) -- never
values. Pinned.

---

## 9. Honesty audit (project Rule 17)

| UI element | Persistence | Failure visibility |
|---|---|---|
| Status pill (Connected) | V2 truth ladder (database) | Pinned by `test_no_card_marked_connected_without_v2_truth` |
| Configure button (provider) | None -- deep-link to vault-backed `/account/api-keys` | Settings page has its own error UI |
| Setup guide drawer | Catalog `setup_notes` + `command_template` (source-tree) | Disclaimer "Daena does not execute install commands automatically" |
| Detail drawer truth ladder | V2 truth dim values + failure_reason | Per-dim chip + last-checked timestamp |
| Coming soon pill | Catalog `install_method=coming-soon` (source-tree) | Clear amber pill + Setup guide button (no fake Install) |
| Skill pack caption | Catalog `kind=skill_pack` | Always-shown caption: "Skill pack -- needs a runtime / MCP / app to execute" |
| Compatibility OS row | Catalog `compatible_os` (source-tree) | If OS list excludes the user's host, status -> `not_supported_on_os` |

Nothing in this PR is a "looks complete but does nothing" surface.

---

## 10. Remaining blockers for true one-click install / connect

Same blockers as the prior PR (none of which are blockers for this
parity polish):

| # | Blocker | Owner |
|---|---|---|
| B1 | `McpServerProbe` (initialize + tools/list) | PR-CONN-MCP-PROBE |
| B2 | `CliRuntimeProbe` (which + version) | PR-CONN-CLI-PROBE |
| B3 | `OAuthAppProbe` (refresh + userinfo) | PR-CONN-OAUTH-PROBE |
| B4 | OAuth flow wired through V2 (Connect button activates real flow) | PR-CONN-OAUTH-INSTALL |
| B5 | Safe MCP install endpoint -- atomic write to a CLI's mcpServers config | PR-CONN-MCP-INSTALL |
| B6 | `BrowserToolProbe` -- spawn + capture exit code | PR-CONN-BROWSER-PROBE |
| B7 | DXT extension auto-import | PR-CONN-DXT-IMPORT |
| B8 | External catalog mirror (community submissions) | PR-CONN-CATALOG-EXTERNAL |
| B9 | Server-side OS detection (today the OS gate runs in the browser) | PR-CONN-OS-DETECT-SERVER |
| B10 | Vault-backed Configure modal in-page (replaces deep-link to Settings) | PR-CONN-CONFIGURE-MODAL |

Today the founder can:
* Browse 55 plugins immediately on /connections
* Click any card -> see capabilities, permissions, install steps,
  truth ladder, vendor docs link
* For provider rows -> Configure jumps directly to the existing
  vault-backed Settings -> API Keys page
* For MCP rows -> Setup guide drawer with the exact `npx -y ...`
  command they copy-paste into their own terminal
* Discover -> imports detected MCPs / runtimes / providers as V2
  rows; the cards then transition to "installed" / "needs_auth"
  honestly

---

## 11. Commit message

```
canonicalization: polish connections plugin marketplace parity
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting next founder direction.**
