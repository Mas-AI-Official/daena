# PR-CONN-MCP-READINESS-AUDIT-AND-INSTALL-POLISH · Sprint-9 PR-2

**Branch:** `master` (committed directly to the merged Sprint-8 line)
**Date:** 2026-05-05
**Author:** Claude (under bounded-autopilot brief)

---

## Verdict

Catalog audited deterministically. Every one of the **57 entries** classified into one of the brief's 6 statuses with a rationale string the UI can quote verbatim. Filesystem MCP regression locked. Probe failure messages now actionable on the two paths the operator hits first (npx not on PATH, first-probe timeout). UI labels remain honest because the existing routing already gates Install on `command_template.length > 0` + `install_method != 'coming-soon'`; the audit pins those invariants.

**Status mix (57 total):**

| status | count | what it means |
|---|---:|---|
| `ready_to_install` | 4 | One-click installable. No env vars, no placeholders. |
| `needs_placeholder` | 4 | Operator provides a path / URL via the MCP install drawer (Sprint-8 PR-1). |
| `needs_token` | 15 | Install command wired, operator must set required env var(s) before launching the host CLI. |
| `setup_guide_only` | 24 | Hosted MCP / OAuth / external runtime. Setup Guide instead of Install. |
| `coming_soon` | 10 | Catalog parity placeholder. Render Setup Guide only. |
| `broken` | **0** | Clean catalog — no malformed install commands. |

---

## Files

```
backend/app/services/connection_v2/readiness_audit.py        (+220 lines, new)
backend/app/services/connection_v2/cli_mcp_writer.py         (+10 / -7 — placeholder detector accepts both <UPPER> and <lower>)
backend/app/services/connection_v2/probes/mcp_server_probe.py (+22 / -1 — actionable failure messages)
backend/tests/test_readiness_audit.py                        (+216 lines, 11 tests)
backend/tests/test_cli_mcp_writer_placeholder_input.py       (+5 / -3 — updated detector test)
docs/Ultraview/PR_CONN_MCP_READINESS_AUDIT_AND_INSTALL_POLISH_REPORT.md  (this file)
```

No frontend code changes were needed: PluginCardView.tsx already routes
`command_template.length > 0 && install_method !== 'coming-soon'` MCPs to
the new MCPInstallDrawer (Sprint-8 PR-1), and everything else falls
through to the read-only Setup Guide. The audit pins those routing
invariants from the catalog side so the UI gating stays honest.

---

## Audit table (57 catalog entries, sorted by kind then plugin_id)

| plugin_id | name | kind | category | install? | placeholders | env vars | probe | exec | status |
|---|---|---|---|---|---|---|---|---|---|
| `provider-anthropic` | Anthropic API | api_provider | ai_provider | no | - | ANTHROPIC_API_KEY | yes | no | **needs_token** |
| `provider-google-gemini` | Google Gemini API | api_provider | ai_provider | no | - | GEMINI_API_KEY | yes | no | **needs_token** |
| `provider-groq` | Groq API | api_provider | ai_provider | no | - | GROQ_API_KEY | yes | no | **needs_token** |
| `provider-openai` | OpenAI API | api_provider | ai_provider | no | - | OPENAI_API_KEY | yes | no | **needs_token** |
| `provider-openrouter` | OpenRouter | api_provider | ai_provider | no | - | OPENROUTER_API_KEY | yes | no | **needs_token** |
| `provider-perplexity` | Perplexity API | api_provider | ai_provider | no | - | PERPLEXITY_API_KEY | yes | no | **needs_token** |
| `provider-together` | Together AI | api_provider | ai_provider | no | - | TOGETHER_API_KEY | yes | no | **needs_token** |
| `mcp-browserbase` | Browserbase | browser_tool | browser | no | - | BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID | no | no | **coming_soon** |
| `mcp-chrome-devtools` | Chrome DevTools | browser_tool | browser | yes | - | - | yes | no | **setup_guide_only** |
| `mcp-playwright` | Playwright | browser_tool | browser | yes | - | - | yes | no | **setup_guide_only** |
| `cli-claude-code` | Claude Code | cli_runtime | cli_runtime | yes | - | - | yes | no | **setup_guide_only** |
| `cli-codex` | Codex CLI | cli_runtime | cli_runtime | yes | - | - | yes | no | **setup_guide_only** |
| `cli-gemini` | Gemini CLI | cli_runtime | cli_runtime | yes | - | - | yes | no | **setup_guide_only** |
| `mcp-desktop-commander` | Desktop Commander | computer_use | computer_use | yes | - | - | yes | no | **setup_guide_only** |
| `mcp-windows` | Windows MCP | computer_use | computer_use | no | - | - | yes | no | **setup_guide_only** |
| `local-ollama` | Ollama | local_model | local_llm | no | - | OLLAMA_BASE_URL | yes | no | **setup_guide_only** |
| `local-vllm` | vLLM / llama-server | local_model | local_llm | no | - | VLLM_BASE_URL | yes | no | **setup_guide_only** |
| `mcp-brave-search` | Brave Search | mcp_server | dev_tools | yes | - | BRAVE_API_KEY | yes | no | **needs_token** |
| `mcp-cloudflare` | Cloudflare | mcp_server | code_platform | yes | - | CLOUDFLARE_API_TOKEN | yes | no | **setup_guide_only** |
| `mcp-fetch` | Fetch | mcp_server | dev_tools | yes | - | - | yes | no | **ready_to_install** |
| `mcp-figma` | Figma (Dev Mode) | mcp_server | design | yes | - | - | yes | no | **setup_guide_only** |
| `mcp-filesystem` | Filesystem | mcp_server | filesystem | yes | <ALLOWED_ROOT> | - | yes | yes | **needs_placeholder** |
| `mcp-git` | Git | mcp_server | dev_tools | yes | <path> | - | yes | no | **needs_placeholder** |
| `mcp-github` | GitHub | mcp_server | code_platform | yes | - | GITHUB_PERSONAL_ACCESS_TOKEN | yes | yes | **needs_token** |
| `mcp-gitlab` | GitLab | mcp_server | code_platform | no | - | GITLAB_PERSONAL_ACCESS_TOKEN, GITLAB_API_URL | no | no | **coming_soon** |
| `mcp-google-drive` | Google Drive (MCP) | mcp_server | productivity | yes | - | GDRIVE_OAUTH_CLIENT_ID, GDRIVE_OAUTH_CLIENT_SECRET | yes | no | **needs_token** |
| `mcp-huggingface` | Hugging Face | mcp_server | research | yes | - | HF_TOKEN | yes | yes | **setup_guide_only** |
| `mcp-jira` | Atlassian (Jira + Confluence) | mcp_server | code_platform | yes | - | - | yes | no | **setup_guide_only** |
| `mcp-linear` | Linear | mcp_server | productivity | yes | - | - | yes | no | **setup_guide_only** |
| `mcp-memory` | Memory | mcp_server | dev_tools | yes | - | - | yes | no | **ready_to_install** |
| `mcp-mongodb` | MongoDB | mcp_server | data_storage | yes | - | MONGODB_URI | yes | yes | **needs_token** |
| `mcp-neon` | Neon | mcp_server | data_storage | yes | - | NEON_API_KEY | yes | yes | **needs_token** |
| `mcp-netlify` | Netlify | mcp_server | code_platform | no | - | NETLIFY_AUTH_TOKEN | no | no | **coming_soon** |
| `mcp-notion` | Notion | mcp_server | productivity | no | - | - | yes | no | **setup_guide_only** |
| `mcp-perplexity` | Perplexity Search | mcp_server | research | no | - | PERPLEXITY_API_KEY | no | no | **coming_soon** |
| `mcp-postgres` | Postgres | mcp_server | data_storage | yes | <DATABASE_URL> | POSTGRES_URL | yes | no | **needs_placeholder** |
| `mcp-redis` | Redis | mcp_server | data_storage | no | - | REDIS_URL | no | no | **coming_soon** |
| `mcp-sentry` | Sentry | mcp_server | code_platform | yes | - | SENTRY_AUTH_TOKEN, SENTRY_HOST | yes | yes | **needs_token** |
| `mcp-sequential-thinking` | Sequential Thinking | mcp_server | dev_tools | yes | - | - | yes | no | **ready_to_install** |
| `mcp-shopify` | Shopify | mcp_server | payment | no | - | SHOPIFY_ADMIN_TOKEN, SHOPIFY_SHOP_DOMAIN | no | no | **coming_soon** |
| `mcp-slack` | Slack | mcp_server | communication | yes | - | SLACK_CLIENT_ID, SLACK_CLIENT_SECRET | yes | yes | **setup_guide_only** |
| `mcp-sqlite` | SQLite | mcp_server | data_storage | yes | <PATH> | - | yes | yes | **needs_placeholder** |
| `mcp-stripe` | Stripe | mcp_server | payment | yes | - | STRIPE_SECRET_KEY | yes | no | **needs_token** |
| `mcp-supabase` | Supabase | mcp_server | data_storage | yes | - | SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY | yes | yes | **needs_token** |
| `mcp-time` | Time | mcp_server | dev_tools | yes | - | - | yes | no | **ready_to_install** |
| `mcp-vercel` | Vercel | mcp_server | code_platform | yes | - | - | yes | no | **setup_guide_only** |
| `app-canva` | Canva | oauth_app | design | no | - | CANVA_CLIENT_ID, CANVA_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-cloudflare-oauth` | Cloudflare (OAuth) | oauth_app | code_platform | no | - | CLOUDFLARE_CLIENT_ID, CLOUDFLARE_CLIENT_SECRET | no | no | **coming_soon** |
| `app-figma` | Figma (OAuth) | oauth_app | design | no | - | FIGMA_CLIENT_ID, FIGMA_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-github` | GitHub (OAuth) | oauth_app | code_platform | no | - | GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-gmail` | Gmail | oauth_app | productivity | no | - | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-google-calendar` | Google Calendar | oauth_app | productivity | no | - | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-google-drive` | Google Drive | oauth_app | productivity | no | - | GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-notion-oauth` | Notion (OAuth) | oauth_app | productivity | no | - | NOTION_CLIENT_ID, NOTION_CLIENT_SECRET | no | no | **coming_soon** |
| `app-sentry-oauth` | Sentry (OAuth) | oauth_app | code_platform | no | - | SENTRY_CLIENT_ID, SENTRY_CLIENT_SECRET | no | no | **coming_soon** |
| `app-slack` | Slack (OAuth) | oauth_app | communication | no | - | SLACK_CLIENT_ID, SLACK_CLIENT_SECRET | yes | no | **setup_guide_only** |
| `app-stripe-oauth` | Stripe (Connect) | oauth_app | payment | no | - | STRIPE_CONNECT_CLIENT_ID | no | no | **coming_soon** |

---

## Honest takeaways

**The 4 cards an operator can install with zero inputs:**
`mcp-fetch`, `mcp-memory`, `mcp-sequential-thinking`, `mcp-time`. After Filesystem becomes callable (placeholder fix from PR-1), the next operator click should land on one of these for the smoothest first-real-tool experience. None of them is in `PHASE2_ALLOWLIST` with `mcp_tool` execution mode yet — they install fine but carry no Daena-armed skills today. Sprint-9 PR-3 candidate: arm one read-only skill on each so the local-beta has more than just Filesystem to demonstrate.

**The 4 cards that need an operator-supplied path / URL** (Sprint-8 PR-1's placeholder flow handles all of them):
- `mcp-filesystem` — `<ALLOWED_ROOT>` ← already shipped, find_files armed.
- `mcp-git` — `<path>` ← lowercase placeholder, detector widened to catch it (cli_mcp_writer change in this PR).
- `mcp-postgres` — `<DATABASE_URL>` ← needs both placeholder AND POSTGRES_URL env. Honesty: we mark it `needs_placeholder` because that's the first hurdle; once placeholder filled, the operator still has to set POSTGRES_URL.
- `mcp-sqlite` — `<PATH>` ← already in PHASE2_ALLOWLIST with `mcp_tool` execution mode for `describe_schema`.

**The 7 MCPs already wired for real read-only execution** (PHASE2_ALLOWLIST `execution_mode="mcp_tool"`):
`mcp-filesystem`, `mcp-github`, `mcp-mongodb`, `mcp-neon`, `mcp-sentry`, `mcp-sqlite`, `mcp-supabase` — but **only Filesystem is actually demonstrable today** because the other six need real tokens (PAT, connection strings, Sentry auth, etc.) that the operator hasn't provided. That's why Sprint-8 picked Filesystem as the local-beta anchor.

**Hosted-MCP gotcha clarified:** entries like `mcp-cloudflare`, `mcp-vercel`, `mcp-jira`, `mcp-linear`, `mcp-figma`, `mcp-slack`, `mcp-huggingface` carry HTTPS URLs in `command_template` (e.g. `https://mcp.cloudflare.com/mcp`). Daena does NOT write URLs into the local Claude Desktop `mcpServers` list (those entries expect `command + args`, not URLs). The audit correctly classifies these as `setup_guide_only` so the UI doesn't dangle a fake Install button. The vendor's hosted MCP UI is the right authorize path.

**No `broken` rows.** The 1 entry the first audit run flagged (`mcp-notion` — empty `command_template`) was already intentional (Notion's hosted-OAuth MCP). The classifier was widened to recognize `install_method=manual` + empty template + hosted-URL templates as `setup_guide_only`, not `broken`.

---

## Actionable failure messages (probe layer)

`backend/app/services/connection_v2/probes/mcp_server_probe.py` — two paths got operator-friendly hints:

**Binary not found on PATH** — was: `command 'npx' not found on PATH`. Now adds:

| missing binary | hint |
|---|---|
| `npx` / `npm` / `node` | `Install Node.js (https://nodejs.org) or ensure npx is on PATH.` |
| `uvx` / `uv` | `Install uv (https://docs.astral.sh/uv) or ensure uvx is on PATH.` |
| `docker` | `Install Docker Desktop or ensure docker is on PATH.` |
| `python` / `python3` / `pip` / `pipx` | `Ensure Python is on PATH.` |

**Initialize timeout** — was: `initialize did not complete in 8.0s`. Now: `… Package may still be downloading/warming on first run. Retry probe in ~10s.` This matches what we hit on the live Sprint-8 smoke (first probe of the freshly-installed Filesystem MCP timed out at 8s; second probe succeeded immediately because npx had cached the package).

Tests (`test_probe_binary_not_found_message_actions_npx_and_uvx`, `test_probe_initialize_timeout_message_suggests_retry`) pin both copy strings so a future refactor can't silently revert them.

---

## Hard rules verified

| # | Rule | Status |
|---|---|---|
| 1 | No push to origin | Local commit only |
| 2 | No production deploy | No GCP / Cloud Run touch |
| 3 | No `USE_CONNECTION_REGISTRY_V2` flip | Untouched |
| 4 | No secrets read/printed | Audit treats `required_env_vars` as NAMES ONLY; report contains zero secret values |
| 5 | No auto-install | Audit is read-only over the catalog; never spawns npx/uvx/docker |
| 6 | No external scans | This PR adds zero outbound HTTP |
| 7 | No writes enabled | Phase 3 floor pinned by `test_phase3_writes_floor_holds_through_audit` (PHASE2_ALLOWLIST has 0 non-read-only entries) |

---

## Tests

11 new in `backend/tests/test_readiness_audit.py`. Sweep across full Sprint-7 + Sprint-8 + Sprint-9 PR-1 + writer suites:

```
175 passed in 105.40s
```

Frontend `tsc --noEmit` clean (exit 0).

### What the audit tests pin

| # | Test | What it catches |
|---|---|---|
| 1 | `test_audit_covers_every_catalog_entry` | A future catalog edit that adds an entry without a classification path |
| 2 | `test_audit_has_no_broken_or_unknown_status_rows` | Malformed install commands sneaking into the catalog |
| 3 | `test_filesystem_remains_needs_placeholder_with_executable_path` | **Local-beta acceptance anchor.** If Filesystem regresses, find_files breaks |
| 4 | `test_phase3_writes_floor_holds_through_audit` | Phase 3 leak via PHASE2_ALLOWLIST |
| 5 | `test_audit_has_at_least_one_ready_to_install_entry` | Catalog with zero one-clickables (would make local-beta unfair) |
| 6 | `test_audit_includes_known_zero_input_mcps` | Catalog edit that accidentally adds env vars / placeholders to mcp-time / mcp-fetch / mcp-memory / mcp-sequential-thinking |
| 7 | `test_audit_renders_markdown_table_with_every_entry` | Renderer drift |
| 8 | `test_every_ready_to_install_entry_previews_cleanly` | **Classifier-vs-writer sync.** A "ready_to_install" classification that fails preview = worst-possible UX (operator clicks Install, gets 422) |
| 9 | `test_classify_entry_is_deterministic` | Side-effects sneaking into the classifier |
| 10 | `test_probe_binary_not_found_message_actions_npx_and_uvx` | Sprint-9 PR-2 actionable copy |
| 11 | `test_probe_initialize_timeout_message_suggests_retry` | Sprint-9 PR-2 actionable copy |

---

## What the operator should expect

| Card status | What the UI shows | What the operator does |
|---|---|---|
| `ready_to_install` | "Setup guide" button → opens MCPInstallDrawer (Sprint-8 PR-1) | Pick CLI target, click Confirm. No inputs. |
| `needs_placeholder` | Same button, drawer renders the placeholder input form | Type the path / URL, click Update preview, click Confirm. |
| `needs_token` | Same button, drawer surfaces required env-var NAMES | Set the env var in your shell BEFORE launching the host CLI, then click Confirm. |
| `setup_guide_only` | "Setup guide" button → opens read-only SetupDrawer | Read the steps. Run install command in your terminal. Or for hosted MCPs, click through to the vendor's authorize URL. |
| `coming_soon` | "Setup guide" button + "coming soon" pill | Daena cataloged this for roadmap parity. Not locally probeable yet. |

The card UI was already correct on these mappings (Sprint-6 `_derive_lifecycle` + Sprint-8 PluginCardView routing). PR-2 locks the catalog side so the routing invariants stay honest.

---

## Sprint-9 queue, updated

| # | Status |
|---|---|
| 1 | `PR-SCAN-ADD-TO-SCOPE-INLINE-CTA` — DONE (`1083715`) |
| **2** | **`PR-CONN-MCP-READINESS-AUDIT-AND-INSTALL-POLISH` — DONE (this PR)** |
| 3 | `PR-CONN-FS-PROBE-AUTO-INSTALL-NOTICE` — partly addressed by this PR's actionable failure copy. Remaining: surface the same hint inline on the marketplace card (not just the probe response) so the operator sees it without having to drill in. |
| 4 | `PR-CONN-CONSENT-EXECUTOR-DB-CUTOVER` — Sprint-6 carryover |
| 5 | Audit-log viewer plugin filter |
| 6 | Google OAuth manual setup helpers |
| 7 | **NEW** — `PR-CONN-PHASE2-ARM-ZERO-INPUT-MCPS` — pick one read-only skill on each of mcp-time / mcp-fetch / mcp-memory / mcp-sequential-thinking and arm `execution_mode="mcp_tool"`. Today, `find_files` is the only demonstrable Daena-armed skill on a callable plugin. Adding 4 more after install gives the local-beta a richer first-impression surface without adding token / placeholder friction. |

Recommend #7 next: it's the cheapest path to "Daena does more than file search."

**Stop and report.**
