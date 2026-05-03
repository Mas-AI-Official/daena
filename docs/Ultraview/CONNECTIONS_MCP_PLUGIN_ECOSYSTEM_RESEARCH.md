# Connections — MCP / Plugin Ecosystem Research (2026-05-03)

**Purpose:** Inventory the real MCP/plugin ecosystem as of 2026-Q2 and decide which apps Daena should curate into the marketplace as bundled **Plugins** (MCP server + auth + default skills + setup flow), not raw MCP rows.

**Method:** four parallel research agents covered (1) the official MCP Registry + reference servers, (2) Anthropic Claude Desktop Extensions / MCPB and OpenAI Codex Plugins design models, (3) vendor-shipped first-party MCPs, and (4) community discovery directories. Sources cited per row. No aggressive scraping.

**Hard rules respected:** no scraping beyond a handful of WebFetch calls per source; no copying third-party code; no vendoring external repos; no auto-installing packages; clear `community/unverified` labels for everything that isn't vendor-blessed.

---

## 1. Ecosystem snapshot

| Surface | Role | Verdict for Daena |
|---|---|---|
| `registry.modelcontextprotocol.io` (Apache-2.0, namespace-verified) | Canonical machine-readable registry. v0.1 API freeze (Oct 2025). | **Primary programmatic feed.** Anything in `io.github.<vendor-org>/...` namespace is `vendor-published`. |
| `modelcontextprotocol/servers` GitHub | Reference server list maintained by the MCP steering group. | Source of truth for the Anthropic-blessed reference set (Filesystem / Fetch / Memory / Sequential Thinking / Time / Git / Everything). |
| `modelcontextprotocol/servers-archived` | Previously-reference servers no longer actively maintained by the MCP org. | Surface as `archived` tag; still installable. Includes Slack ref, GDrive ref, Postgres/SQLite/Redis refs, Brave Search ref. |
| Claude Desktop Extensions (MCPB / DXT) | Anthropic's bundle format: `.mcpb` ZIP with `manifest.json` declaring tools/prompts/user_config. OS-keychain for secrets. | Mirror manifest discipline. Daena bundles stay as directories so SKILL.md edits hot-reload. |
| OpenAI Codex Plugins | Three-primitive composition (skills + apps + MCP). `plugin.json` with `interface{display_name, capabilities, brand_color, default_prompts}`. Lazy OAuth at first invocation. | Mirror Codex's high-level `capabilities` summary + `default_prompts` seeding — both missing from Daena today. |
| PulseMCP, Glama (~22.7k servers), Smithery, mcp.so | Community directories. Open submission, vetting policies generally undocumented. | Cite URLs for human discovery; do NOT scrape as data sources. |
| `awesome-mcp-servers` (86k stars) | Hand-curated list with `🎖️` flag for vendor-official servers. | Secondary feed: cache the README daily, mark `🎖️` entries as `vendor-official`. |

---

## 2. Vendor-shipped (first-party) MCPs — confirmed shipping

These thirteen vendors have **shipping** OAuth-clean (mostly) servers as of 2026-05-03:

| Vendor | Endpoint / package | Auth | Surface | Source |
|---|---|---|---|---|
| **GitHub** | `https://api.githubcopilot.com/mcp/` (remote) · `ghcr.io/github/github-mcp-server` (local) | OAuth or PAT | 24 toolsets — Repos, Issues, PRs, Actions, Code Security, Dependabot, Secret Scanning, Discussions, Gists, Projects, Notifications, Orgs, Users, Copilot | github/github-mcp-server (29.5k★) |
| **Atlassian (Jira/Confluence)** | `https://mcp.atlassian.com/v1/sse` (Streamable HTTP, "Rovo MCP") | OAuth, granular permissions, admin-controlled allowed-AI-domains | Jira tickets, Confluence pages, bulk-create | atlassian.com/platform/remote-mcp-server |
| **Linear** | `https://mcp.linear.app/mcp` | OAuth 2.1 with dynamic client registration | Issues, projects, cycles, comments | linear.app/docs/mcp |
| **Notion** | hosted, OAuth-managed | OAuth | Pages, databases, search, comments, teams (live in claude.ai) | developers.notion.com/docs/mcp |
| **Slack** | `https://mcp.slack.com/mcp` (hosted-only) | OAuth — workspace admin must approve MCP integration | search, send, history, threads, canvases | docs.slack.dev/ai/slack-mcp-server |
| **Stripe** | `https://mcp.stripe.com` (hosted) · `npx -y @stripe/mcp@latest` (local) | OAuth or restricted API key | 20+ tools — customers, invoices, subscriptions, payments, refunds, disputes, docs | docs.stripe.com/mcp |
| **Sentry** | `https://mcp.sentry.dev/mcp` (hosted) · `npx @sentry/mcp-server` (local) | OAuth device-code or PAT | Issues, errors, projects, Seer AI, NL search | docs.sentry.io/product/sentry-mcp |
| **Cloudflare** | 6 hosted endpoints (docs/bindings/observability/radar/browser/ai-gateway) | Cloudflare API tokens | Per-domain capabilities | cloudflare/mcp-server-cloudflare |
| **Vercel** | `https://mcp.vercel.com` | OAuth (MCP Authorization 2025-06-18) | Projects, deployments, logs, docs | vercel.com/docs/agent-resources/vercel-mcp |
| **HuggingFace** | `https://huggingface.co/mcp` | Bearer token | hub_repo_details, paper_search, space_search, doc_search (live in claude.ai) | huggingface/hf-mcp-server |
| **Figma (Dev Mode)** | `https://mcp.figma.com/mcp` (remote) · Desktop variant | OAuth | Code generation (React/Tailwind), image extraction, variables, Code Connect | help.figma.com Dev Mode MCP guide |
| **Chrome DevTools (Google)** | `npx -y chrome-devtools-mcp@latest` | none | 33+ tools — automation, perf trace, debugging, snapshots, lighthouse | github.com/ChromeDevTools/chrome-devtools-mcp |
| **Microsoft Playwright** | `npx -y @playwright/mcp@latest` | none | 60+ tools — accessibility-snapshot interaction, tabs, network mock, DevTools tracing | github.com/microsoft/playwright-mcp |

---

## 3. Reference servers (MCP steering group)

| Name | Install | Auth | Tier | Source |
|---|---|---|---|---|
| Filesystem | `npx -y @modelcontextprotocol/server-filesystem <root>` | none | Reference | modelcontextprotocol/servers |
| Fetch | `npx -y @modelcontextprotocol/server-fetch` | none | Reference | modelcontextprotocol/servers |
| Memory | `npx -y @modelcontextprotocol/server-memory` | none | Reference | modelcontextprotocol/servers |
| Sequential Thinking | `npx -y @modelcontextprotocol/server-sequential-thinking` | none | Reference | modelcontextprotocol/servers |
| Time | `npx -y @modelcontextprotocol/server-time` | none | Reference | modelcontextprotocol/servers |
| Git | `uvx mcp-server-git --repository <path>` | none | Reference (Python) | modelcontextprotocol/servers |
| Everything | `npx -y @modelcontextprotocol/server-everything` | none | Reference (test fixture) | modelcontextprotocol/servers |

---

## 4. Per-app verdict matrix (founder list)

Status legend: `ready_to_add` · `already_supported` · `needs_oauth_provider` · `needs_mcp_install_writer` · `coming_soon` · `reject_for_now` (community-only on a sensitive surface).

### High-confidence, official: ready or already supported

| App | Officiality | Status | Notes |
|---|---|---|---|
| GitHub | vendor-official | already_supported | Catalog entry exists; bump officiality + skills. |
| Cloudflare | vendor-official | already_supported | Bump officiality; consider 6-endpoint sub-products. |
| Stripe | vendor-official | already_supported | Bump officiality + risk_level note for restricted-key recommendation. |
| Sentry | vendor-official | already_supported | Bump officiality. |
| Notion | vendor-official | already_supported | Bump officiality. |
| Linear | vendor-official | already_supported | Bump officiality (was community in catalog). |
| Slack | vendor-official | already_supported | Bump officiality + add admin-approval-required note. |
| HuggingFace | vendor-official | ready_to_add | Currently `coming-soon` in catalog; flip to vendor-official. |
| Figma | vendor-official (beta) | already_supported | Bump officiality + beta tag. |
| Chrome DevTools | vendor-official | already_supported | Bump officiality. |
| Playwright | vendor-official | already_supported | Bump officiality. |
| **Vercel** | vendor-official | **needs_add** | Currently `coming-soon`; flip to vendor-official + remote URL install. |
| **Atlassian (Jira)** | vendor-official | **needs_add** | Currently `coming-soon`; flip to vendor-official. |

### Reference servers (MCP steering group)

| App | Officiality | Status | Notes |
|---|---|---|---|
| Filesystem | reference | already_supported | Update officiality field. |
| Fetch | reference | already_supported | Same. |
| Memory | reference | already_supported | Same. |
| Sequential Thinking | reference | already_supported | Same. |
| Time | reference | already_supported | Same. |
| Git | reference | already_supported | Same — note Python `uvx` install path. |
| Brave Search | vendor-official (now Brave-shipped) | already_supported | Was reference; Brave now ships `brave-search-mcp`. |

### Archived reference (still installable)

| App | Officiality | Status | Notes |
|---|---|---|---|
| GDrive (MCP) | archived | `mcp-google-drive` entry — surface "archived" tag |
| Postgres | archived | mark archived; surface |
| SQLite | archived | mark archived; surface |
| Redis | archived | mark archived; surface |
| GitLab | archived | currently coming-soon; bump to archived-community fork |

### OAuth apps (Google Workspace, others) — community/claude.ai-hosted

| App | Officiality | Status | Notes |
|---|---|---|---|
| Gmail | claude.ai-connector / community-MCP | already_supported (OAuth) | Daena's OAuth row uses `oauth_credentials_store`; mark officiality "claude-connector-or-community". |
| Google Calendar | same | already_supported | Same. |
| Google Drive | same | already_supported | Same; community `@modelcontextprotocol/server-gdrive` (archived) also exists as MCP path. |
| GitHub OAuth | vendor-official | already_supported | Uses GitHub's OAuth Apps; complementary to GitHub MCP. |

### Vendor-blessed community / verified

| App | Officiality | Status | Notes |
|---|---|---|---|
| Supabase | vendor-blessed (supabase-community) | needs_add | `npx supabase-mcp`. |
| Neon | vendor-published | needs_add | `npx @neondatabase/mcp-server-neon`. |
| PlanetScale | vendor-published | needs_add | Built into `pscale` CLI. |
| Qdrant | vendor-published | needs_add | `pip install mcp-server-qdrant`. |
| Weaviate | vendor-published | needs_add | `uv run mcp-server-weaviate`. |
| MongoDB | vendor-blessed community | already_supported (coming-soon) | MongoDB Inc. has shipped `mongodb-mcp-server`. |

### Community (worth listing, "Review source before install")

| App | Repo | Risk |
|---|---|---|
| Airtable | `domdomegg/airtable-mcp-server` | Medium — third-party holds API key |
| Discord | `PaSympa/discord-mcp` | Medium — bot token scope |
| Bitbucket | `aashari/mcp-server-atlassian-bitbucket` | Medium — repo write |
| Pinecone | `sirmews/mcp-pinecone` | Medium — vector DB read |
| Outlook / M365 | `softeria/ms-365-mcp-server` | Medium — Graph API scope |
| Zoom / Teams meetings | `joinly-ai/joinly` | Higher — sends bot into meetings; explicit consent flow needed |

### Skip for launch (no credible MCP, sensitive surface)

Salesforce, HubSpot, Mixpanel, Datadog, Grafana, n8n, Zapier, ClickUp, Asana, Trello, Calendly, Loom, PostHog, Render, Fly.io.

Render these as "MCP not yet available" cards with a request-vote signal so users can express demand without us shipping a hostile-third-party token grab.

---

## 5. Daena PluginBundle schema additions (informed by MCPB + Codex + Daena governance)

New fields to add to `CatalogEntry` (all optional with safe defaults so the existing 57 entries don't have to be rewritten in one PR):

```python
# --- Officiality / trust signal (from research) ---
officiality: Literal[
    "official",          # MCP steering group reference
    "vendor-official",   # First-party from the app's vendor
    "vendor-blessed",    # Community but vendor-affiliated org
    "verified",          # Manually reviewed by Daena
    "community",         # Third-party, surfaced with caveat
    "archived",          # Was reference, no longer maintained
    "coming-soon",       # No MCP shipping yet
] = "community"

# --- Plugin-bundle composition (Codex inspiration) ---
default_skills: tuple[str, ...] = ()           # Skill names this plugin provides
suggested_prompts: tuple[str, ...] = ()        # Composer seed prompts ("Try: ...")
permissions_summary: tuple[str, ...] = ()      # ["Read","Write","Network"] high-level
mcp_servers: tuple[str, ...] = ()              # For multi-MCP plugins (most have one)

# --- Source attribution (transparency) ---
source_refs: tuple[str, ...] = ()              # URLs to official docs / repos / registry
last_verified_at: str = ""                     # ISO8601 — when we last checked this
```

These are PURELY METADATA additions. No new install paths, no new auth methods, no probe changes — those land in follow-up PRs. The schema lets Daena render Codex/Claude-style plugin cards today without changing any execution path.

### What we explicitly chose NOT to copy

- **MCPB's single-`.zip` bundle**: Daena bundles stay as directories (catalog entries) so we can hot-edit metadata.
- **Codex's `.app.json` schema**: undocumented in public Codex docs (only mentioned by name), so we don't speculate.
- **Live registry ingest**: this PR does NOT pull from `registry.modelcontextprotocol.io` at runtime. The catalog stays hand-curated + reviewed in PR. A future PR can add a daily sync.

---

## 6. Default skills proposal (Part C deliverable)

Per the founder brief. Skills are NAMES + DESCRIPTIONS only — they describe what the plugin can do once connected; they do NOT execute autonomously and do NOT bypass governance.

| Plugin | Default skills (skill_name → description) |
|---|---|
| GitHub | `triage_issues`, `review_pull_request`, `summarize_repo`, `draft_release_notes`, `inspect_ci_failure` |
| Gmail | `summarize_unread`, `draft_reply`, `extract_action_items`, `search_email_context` |
| Google Drive | `find_documents`, `summarize_file`, `compare_docs`, `extract_tables` |
| Slack | `summarize_channel`, `draft_reply`, `find_decisions`, `extract_tasks` |
| Notion | `find_page`, `summarize_database`, `extract_action_items`, `update_page` |
| Linear | `triage_issues`, `summarize_cycle`, `draft_status_update`, `find_blockers` |
| Atlassian (Jira) | `triage_tickets`, `summarize_sprint`, `draft_release_notes`, `find_blockers` |
| Figma | `inspect_design`, `summarize_components`, `generate_frontend_plan` |
| Cloudflare | `inspect_dns`, `review_workers`, `check_security_headers`, `summarize_zone_config` |
| Sentry | `summarize_errors`, `trace_release_regression`, `create_bug_task` |
| Stripe | `summarize_payments`, `inspect_customer`, `reconcile_subscriptions` |
| Vercel | `summarize_deployment`, `inspect_logs`, `review_env_config` |
| HuggingFace | `find_model`, `summarize_dataset`, `compare_models`, `inspect_paper` |
| Playwright / browser | `open_page`, `inspect_ui`, `fill_form_safe`, `capture_screenshot`, `run_smoke_test` |
| Chrome DevTools | `inspect_dom`, `read_network`, `analyze_perf`, `capture_screenshot` |
| Postgres | `describe_schema`, `safe_query`, `explain_query` |
| SQLite | `describe_schema`, `safe_query`, `explain_query` |
| Filesystem | `find_files`, `read_file`, `summarize_directory` |

Skills become "available" only when the plugin's `lifecycle == callable`. Until then, surfacing them carries the badge "Skill ready. Requires <plugin> connection." (Per founder rule: "Do not make skills executable unless the required MCP/app is connected.")

---

## 7. Open gaps + remaining blockers for one-click full sync

1. **No live registry ingest.** Curation stays manual until a future PR (`PR-CONN-MCP-REGISTRY-AUTOSYNC`) wires `registry.modelcontextprotocol.io/v0/servers` polling.
2. **No vendor freshness checks.** `last_verified_at` is set at PR-merge time; we don't re-verify automatically. Future: weekly background re-check that flips officiality back to `community` if a vendor URL 404s.
3. **OAuth client config still requires manual env-var entry** for Gmail/Drive/Calendar (Google client ID/secret). Tracked separately as `PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS`.
4. **Cloudflare's six hosted endpoints** are listed as one card; we don't surface the per-domain fan-out. Decision deferred to a follow-up.
5. **MCP install writer for new vendors** — Atlassian / Vercel / Linear are remote-OAuth, no install-writer needed. But for `npx`-style local installs the `cli_mcp_writer` already exists and works (per PR-CONN-MCP-INSTALL-INTO-CLI).
6. **Skill execution layer**: this PR adds skill NAMES to the catalog. Wiring those skill names to actual prompt templates / tool invocations is `PR-CONN-PLUGIN-SKILLS-EXECUTION` — not started.

---

## 8. References

- [modelcontextprotocol/servers (reference servers + archived list)](https://github.com/modelcontextprotocol/servers)
- [modelcontextprotocol/registry (server.json schema, namespace rules)](https://github.com/modelcontextprotocol/registry)
- [registry.modelcontextprotocol.io](https://registry.modelcontextprotocol.io/)
- [github/github-mcp-server](https://github.com/github/github-mcp-server)
- [Cloudflare MCP servers list](https://developers.cloudflare.com/agents/model-context-protocol/mcp-servers-for-cloudflare/)
- [Atlassian Remote MCP](https://www.atlassian.com/blog/announcements/remote-mcp-server)
- [Linear MCP](https://linear.app/docs/mcp)
- [Notion MCP](https://developers.notion.com/docs/mcp)
- [Slack MCP](https://docs.slack.dev/ai/slack-mcp-server/)
- [Stripe MCP](https://docs.stripe.com/mcp)
- [Sentry MCP](https://docs.sentry.io/product/sentry-mcp/)
- [Vercel MCP](https://vercel.com/docs/agent-resources/vercel-mcp)
- [HuggingFace MCP](https://github.com/huggingface/hf-mcp-server)
- [Figma Dev Mode MCP](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Dev-Mode-MCP-Server)
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)
- [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [Anthropic Claude Desktop Extensions / MCPB](https://www.anthropic.com/engineering/desktop-extensions)
- [OpenAI Codex Plugins build docs](https://developers.openai.com/codex/plugins/)
- [PulseMCP](https://www.pulsemcp.com/)
- [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)
