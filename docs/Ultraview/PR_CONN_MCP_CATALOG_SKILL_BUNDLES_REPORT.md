# PR-CONN-MCP-CATALOG-SKILL-BUNDLES — Curate the marketplace into plugin bundles

**Date:** 2026-05-03
**Branch:** rebuild-connections-mcp-runtime
**Base commit:** 79f38e8 (provider key input)
**Status:** Shipped + live-verified

---

## Founder intent

> A plugin is not just an MCP row. A plugin is: MCP server + app connector/auth +
> default skills + setup/probe/install flow.

Before this PR, every catalog entry had only a `kind` (mcp_server / oauth_app /
api_provider / etc.) and a flat `capabilities` list. Officiality was implicit
(the `vendor` field said "Anthropic" for everything in `modelcontextprotocol/
servers`, even when the actual vendor had since shipped their own first-party
MCP). Skills weren't separated from generic capability strings. There was no
trust signal on the card to distinguish "this is the GitHub-shipped MCP" from
"this is some random `@unverified/foo` package."

This PR adds the bundle composition layer + trust signal + skill bundles per
the founder's brief.

---

## Research sources checked

Four parallel research agents covered:

1. **Official MCP Registry + reference servers** — `registry.modelcontextprotocol.io`,
   `modelcontextprotocol/servers`, `modelcontextprotocol/servers-archived`,
   `modelcontextprotocol.io` spec, Cloudflare Agents docs, individual vendor
   MCP repos (GitHub, Cloudflare, Stripe, Sentry, Notion, Linear, etc.).
2. **MCPB / Codex plugin design** — Anthropic Claude Desktop Extensions
   (`.mcpb` ZIP + `manifest.json` + `user_config{sensitive:true}` keychain
   storage); OpenAI Codex Plugins three-primitive composition (skills + apps +
   MCP) with `interface{display_name, capabilities, brand_color, default_prompts}`.
3. **Vendor-shipped first-party MCPs** — confirmed shipping for GitHub,
   Atlassian (Rovo), Linear, Notion, Slack, Stripe, Sentry, Cloudflare (6
   endpoints), Vercel, HuggingFace, Figma (Dev Mode beta), Chrome DevTools,
   Microsoft Playwright.
4. **Community directories** — PulseMCP, Glama (~22.7k servers), Smithery,
   awesome-mcp-servers (`🎖️` flag for vendor-official). Picked vendor-blessed
   community entries (Supabase, MongoDB, Neon) and explicitly REJECTED
   sensitive-surface unofficial MCPs (Salesforce, HubSpot, Datadog, etc.).

Full inventory in `docs/Ultraview/CONNECTIONS_MCP_PLUGIN_ECOSYSTEM_RESEARCH.md`
(450 lines, structured per-vendor).

---

## Schema additions (Part B)

`backend/app/services/connection_v2/marketplace_catalog.py` — added a new
`Officiality` literal type and seven optional fields on `CatalogEntry`. All
fields default to safe values (empty tuples, `"community"` officiality) so
the existing 55 entries work unmodified; entries that were bumped this PR
opt into the new metadata explicitly.

```python
Officiality = Literal[
    "official",          # MCP steering group reference servers
    "vendor-official",   # First-party MCP shipped by the app's vendor
    "vendor-blessed",    # Community but vendor-affiliated org
    "verified",          # Manually reviewed by Daena
    "community",         # Third-party, surfaced with caveat (default)
    "archived",          # Was reference, no longer maintained
    "coming-soon",       # No MCP shipping yet
]

# New CatalogEntry fields
officiality: Officiality = "community"
default_skills: tuple[str, ...] = ()
suggested_prompts: tuple[str, ...] = ()
permissions_summary: tuple[str, ...] = ()
mcp_servers: tuple[str, ...] = ()
source_refs: tuple[str, ...] = ()
last_verified_at: str = ""
```

The `to_dict()` extension serializes all new tuple fields as JSON lists so the
marketplace card payload exposes them end-to-end — no marketplace_service
changes needed.

---

## Plugin count before / after

|  | Before (cf47244) | After (this PR) | Δ |
|---|---:|---:|---:|
| Total entries | 55 | **57** | +2 (Supabase, Neon) |
| Has officiality field | 0 | **57** | new |
| Has default_skills | 0 | **23** | new |
| Has source_refs | 0 | **29** | new |
| `official` (reference) | n/a | 6 | — |
| `vendor-official` | n/a | 15 | — |
| `vendor-blessed` | n/a | 2 | — |
| `verified` | n/a | 3 | — |
| `archived` (was-reference) | n/a | 3 | — |
| `community` (default) | 55 (implicit) | 28 | — |
| Total **high-trust** (off+vo+vb+ver) | 0 | **26** | +26 |

---

## High-confidence plugins added or upgraded

### Upgraded existing entries → vendor-official + skill bundles

| Plugin | Was | Now | Skills |
|---|---|---|---|
| **GitHub** | community (vendor=Anthropic) | vendor-official (vendor=GitHub) | triage_issues, review_pull_request, summarize_repo, draft_release_notes, inspect_ci_failure |
| **Cloudflare** | community | vendor-official (6 endpoints) | inspect_dns, review_workers, check_security_headers, summarize_zone_config |
| **Sentry** | community | vendor-official | summarize_errors, trace_release_regression, create_bug_task |
| **Notion** | community | vendor-official | find_page, summarize_database, extract_action_items, update_page |
| **Linear** | community | vendor-official | triage_issues, summarize_cycle, draft_status_update, find_blockers |
| **Slack** | community | vendor-official | summarize_channel, draft_reply, find_decisions, extract_tasks |
| **Stripe** | community | vendor-official | summarize_payments, inspect_customer, reconcile_subscriptions |
| **Figma** | community | vendor-official (Dev Mode beta) | inspect_design, summarize_components, generate_frontend_plan |
| **Playwright** | community | vendor-official | open_page, inspect_ui, fill_form_safe, capture_screenshot, run_smoke_test |
| **Chrome DevTools** | community | vendor-official | inspect_dom, read_network, analyze_perf, capture_screenshot |
| **Brave Search** | community | vendor-official | (search) |
| **HuggingFace** | coming-soon | vendor-official | find_model, summarize_dataset, compare_models, inspect_paper |
| **Vercel** | coming-soon | vendor-official | summarize_deployment, inspect_logs, review_env_config |
| **Atlassian (Jira+Confluence)** | coming-soon | vendor-official (Rovo) | triage_tickets, summarize_sprint, draft_release_notes, find_blockers |

### New entries added

| Plugin | Officiality | Skills |
|---|---|---|
| **Supabase** | vendor-blessed | describe_schema, safe_query, summarize_storage |
| **Neon** | vendor-official | describe_schema, safe_query, list_branches |

### Reference servers → official + skills

Filesystem, Fetch, Memory, Time, Git, Sequential Thinking — all bumped to
`officiality="official"` with vendor="MCP Steering Group" to reflect the actual
publisher (the steering group, not Anthropic specifically).

### Archived references → archived tier

Postgres, SQLite, Google Drive (MCP) — flipped to `officiality="archived"`
with source_refs pointing at `servers-archived` repo and a note in setup_notes
explaining the status.

### OAuth integrations → verified + skills

Gmail, Google Calendar, Google Drive (OAuth) — flipped to `officiality="verified"`
since Daena's OAuth wiring is the canonical path for these (Google has not
shipped first-party MCPs).

---

## Default skills added

Per the founder brief Part C — skill **NAMES** (snake_case identifiers), not
prose. Skills describe what each plugin can do once `lifecycle == callable`;
they are NOT executable from the catalog row. Per project rule, they only
become "available" when the plugin is connected; until then UI can render them
with the caption "Skill ready. Requires <plugin> connection."

Skill bundles attached this PR:

```
GitHub          → triage_issues, review_pull_request, summarize_repo,
                  draft_release_notes, inspect_ci_failure
Gmail           → summarize_unread, draft_reply, extract_action_items,
                  search_email_context
Google Calendar → list_today, find_free_time, schedule_meeting,
                  summarize_week
Google Drive    → find_documents, summarize_file, compare_docs, extract_tables
Slack           → summarize_channel, draft_reply, find_decisions, extract_tasks
Notion          → find_page, summarize_database, extract_action_items, update_page
Linear          → triage_issues, summarize_cycle, draft_status_update, find_blockers
Atlassian       → triage_tickets, summarize_sprint, draft_release_notes, find_blockers
Figma           → inspect_design, summarize_components, generate_frontend_plan
Cloudflare      → inspect_dns, review_workers, check_security_headers,
                  summarize_zone_config
Sentry          → summarize_errors, trace_release_regression, create_bug_task
Stripe          → summarize_payments, inspect_customer, reconcile_subscriptions
Vercel          → summarize_deployment, inspect_logs, review_env_config
HuggingFace     → find_model, summarize_dataset, compare_models, inspect_paper
Playwright      → open_page, inspect_ui, fill_form_safe, capture_screenshot,
                  run_smoke_test
Chrome DevTools → inspect_dom, read_network, analyze_perf, capture_screenshot
Postgres/SQLite → describe_schema, safe_query, explain_query
Filesystem      → find_files, read_file, summarize_directory
Supabase / Neon / MongoDB → describe_schema/collections, safe_query
                            (+ list_branches for Neon, summarize_storage for Supabase)
```

---

## Frontend changes (Part D)

`frontend/src/hooks/useMarketplace.ts`:
- New `Officiality` literal union type with the seven tiers + JSDoc.
- New optional fields on `CatalogEntry`: `officiality`, `default_skills`,
  `suggested_prompts`, `permissions_summary`, `mcp_servers`, `source_refs`,
  `last_verified_at`. All optional with safe defaults.

`frontend/src/pages/connections/pluginCard.ts`:
- Threaded the new fields onto `PluginCard`.
- `included_skills` now PREFERS `default_skills` over `capabilities` (the
  Codex skill model wins; capabilities is the fallback for unbumped entries).
- New `OFFICIALITY_TONE` color map + `officialityTone()` / `officialityLabel()`
  helpers.

`frontend/src/pages/connections/PluginCardView.tsx`:
- Added the **officiality badge** to the status pill row. Always rendered so
  every card carries its trust signal.
- Tone:
  - **green** — `official`, `vendor-official` (vendor-shipped or reference)
  - **cyan** — `vendor-blessed`, `verified` (Daena-reviewed)
  - **amber** — `community` (review source before install)
  - **slate** — `archived`, `coming-soon`

Per Part D, no new primary tabs added. The default Plugins page renders the
new metadata; the Advanced tab still exposes raw V2 / discovery / debug.

---

## Action rules (Part E) — already enforced from prior PRs

This PR does not change the action-derivation logic, but the existing rules
already match the brief:

- **MCP install writer support** → "Install" (PR-CONN-MCP-INSTALL-INTO-CLI)
- **OAuth flow support** → "Connect" (PR-CONN-OAUTH-CONNECT)
- **API key (provider) support** → "Configure" → /account/api-keys#provider-keys
  (PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT)
- **No safe automation** → "Setup guide"
- **`coming-soon`** → "Setup guide" (with coming-soon pill)

The new `officiality` field is a TRUST signal that drives badge rendering;
it does NOT bypass any existing safety gate. A `community` MCP with an
install_method="npm" still gets the same "Install" action — the operator just
sees the amber "Community" badge alongside.

---

## Tests run (Part F)

| File | Suite | Result |
|---|---|---|
| `tests/test_marketplace_plugin_bundles.py` | NEW (62 tests) | **62 passed** |
| `tests/test_provider_key_visibility.py` | regression | 25 passed |
| `tests/test_marketplace_parity_repair.py` | regression | 6 passed |
| `tests/test_connection_v2_marketplace.py` | regression (1 vendor-attribution test updated) | 93 passed |
| `tests/test_provider_keys_store.py` | regression | 21 passed |
| `tests/test_account_provider_keys_endpoint.py` | regression | 11 passed |
| Wider sweep: `marketplace or connection_v2 or probe or provider_key or dynamic_model or account_provider or plugin_bundle` | sweep | **484 passed, 1 skipped, 0 failed in 30.26s** |
| Frontend `tsc -b` | typecheck | exits 0 (pre-existing OAuthConnectDrawer warning untouched) |

### Test coverage highlights (`test_marketplace_plugin_bundles.py`)

- **Schema shape** — every entry has officiality + default_skills + source_refs
- **Officiality contract** — high-trust entries (official/vendor-*/verified)
  MUST cite source_refs; default is community
- **High-confidence pin** — 30 parametrized assertions confirming GitHub /
  Cloudflare / Sentry / etc. are tagged with the correct officiality
- **Skill name shape** — every default_skill is a snake_case identifier
  (catches accidental human prose paste)
- **Skill dependency** — no skill name marked "executable" in the catalog
  row (executability is enforced by lifecycle, not the catalog)
- **Leak safety** — defense-in-depth grep for real key prefixes in serialized
  catalog payload
- **End-to-end card payload** — `MarketplaceCard.to_dict().catalog` exposes
  all new fields with correct types
- **Catalog growth floor** — `len(CATALOG) >= 55`, high-trust count `>= 25`

---

## Hard-rule compliance

| Rule | Status |
|---|---|
| 1. No production deploy | never invoked |
| 2. Don't flip USE_CONNECTION_REGISTRY_V2 | untouched |
| 3. Don't run vault --apply | never invoked |
| 4. Don't delete V1 files | none deleted |
| 5. No print/grep/log/commit secrets | length-only logging persists from prior PR; no new secret paths |
| 6. No external scans | none |
| 7. No emails/DMs/webhooks | none |
| 8. **No auto-install of npm/pip/docker** | catalog edits ONLY; install paths unchanged |
| 9. Don't mark connected/callable without probe | unchanged — bundles add metadata, not lifecycle bumps |
| 10. Don't add new primary tabs | unchanged (Brain / Plugins / Advanced only) |
| 11. **No aggressive scraping** | 4 research agents made ~60 WebFetch calls TOTAL across 4 days of ecosystem coverage; no scraping daemons |
| 12. **Don't copy third-party code** | catalog cites URLs, embeds zero external code |
| 13. **Don't vendor external repos** | none vendored |
| 14. **Unofficial MCPs labeled** | community / archived / vendor-blessed all have distinct badges; sensitive-surface unofficial MCPs (Salesforce, HubSpot, Datadog, etc.) are explicitly REJECTED |

---

## What is now installable / connectable / testable

After this PR, the marketplace ships honest metadata for these high-confidence
plugins. The action lights up only when the underlying flow exists:

**Has remote OAuth → Connect (today via existing OAuth drawer):**
GitHub, Atlassian (Jira), Linear, Notion, Slack, Stripe, Sentry, Vercel,
Cloudflare, Figma, HuggingFace.

**Has npm install_method → Install (today via PR-CONN-MCP-INSTALL-INTO-CLI):**
Filesystem, Fetch, Memory, Time, Sequential Thinking, Brave Search, Playwright,
Chrome DevTools, Sentry (local), Stripe (local), Supabase, Neon, MongoDB, Postgres
(archived), GitHub (npm path), Slack (legacy ref).

**Has API key path → Configure (today via PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT):**
All 7 LLM providers (Anthropic, OpenAI, Gemini, Groq, Perplexity, OpenRouter,
Together).

**Setup-guide-only (no safe automation yet):**
GitLab (archived community fork), Vercel (allowlisted-clients-only — Daena
needs registration), the rest of the coming-soon entries.

---

## Coming soon / why deferred

- **Skills execution layer** — `PR-CONN-PLUGIN-SKILLS-EXECUTION` will wire
  skill names to actual prompt templates / tool invocations. This PR makes
  them visible; they don't yet act.
- **Live registry ingest** — `PR-CONN-MCP-REGISTRY-AUTOSYNC` would poll
  `registry.modelcontextprotocol.io` daily. Curation stays manual until then.
- **Cloudflare 6-endpoint fan-out** — currently rendered as a single tile.
  Future PR can expose per-endpoint sub-products.
- **Vendor freshness re-check** — `last_verified_at` is set at PR-merge time;
  no automatic re-verification loop.
- **OAuth client config in-product entry** — `PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS`
  still pending (Gmail/Drive/Calendar still need GOOGLE_CLIENT_ID/SECRET via
  `.env`).
- **Local model probe** — `PR-CONN-LOCAL-MODEL-PROBE` for Ollama/vLLM
  http_get probe.
- **Per-skill execution audit log** — once skills act, each invocation
  should emit `plugin.<id>.skill.<name>` audit events.

---

## Remaining blockers for one-click full sync

The brief's ultimate target ("Search plugin → Click GitHub → Install MCP →
Connect account → Test → Use built-in GitHub skills") is **80% there** after
this PR. The remaining 20%:

1. **Skills execution wiring** (above) — clicking a skill should surface a
   prompt template / tool call, not just be a metadata chip.
2. **Per-vendor client registration** for OAuth-DCR providers (Vercel,
   Linear) where Daena needs to be allowlisted as an MCP client.
3. **Asset Shield consent dialog** for high-risk plugins (Cloudflare,
   Stripe) so the install flow surfaces "This plugin will read your zones,
   modify DNS, and run Workers" before consent.
4. **Per-plugin governance policy presets** — a "GitHub plugin needs
   approval for write actions" preset should ship with the plugin so the
   founder doesn't have to author it manually.
5. **Live MCP registry sync** to keep officiality fresh as new vendors
   ship their first-party MCPs.

---

## Files changed

**Backend (3):**
- `backend/app/services/connection_v2/marketplace_catalog.py` — schema fields
  + 23 entries upgraded with officiality/skills/source_refs + 2 new entries
  (Supabase, Neon) — net +400 lines
- `backend/tests/test_marketplace_plugin_bundles.py` — NEW 62 tests, ~280
  lines
- `backend/tests/test_connection_v2_marketplace.py` — 1 line: GitHub vendor
  attribution updated from "Anthropic" → "GitHub"

**Frontend (3):**
- `frontend/src/hooks/useMarketplace.ts` — Officiality type + 7 optional
  CatalogEntry fields
- `frontend/src/pages/connections/pluginCard.ts` — bundle fields on
  PluginCard, OFFICIALITY_TONE map + helpers
- `frontend/src/pages/connections/PluginCardView.tsx` — render officiality
  badge in status row

**Docs (2):**
- `docs/Ultraview/CONNECTIONS_MCP_PLUGIN_ECOSYSTEM_RESEARCH.md` — NEW (450
  lines, the 4-agent synthesis)
- `docs/Ultraview/PR_CONN_MCP_CATALOG_SKILL_BUNDLES_REPORT.md` — this report
