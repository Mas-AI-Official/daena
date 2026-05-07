# Daena Connections V3 — Curated Catalog Plan (Sprint-22 candidate)

**Date:** 2026-05-06
**Status:** Plan — not yet started.
**Author:** Daena VP under Auto mode, after operator feedback on Sprint-21 closure.

## Brutal-truth statement

Sprint-21 verified that *labels matched code*. It did not ask whether the
**design itself** was right. The operator's feedback on the live
`/connections` page proves it isn't:

- 57-card flat grid mashes 6 fundamentally different connection patterns
  (API key providers, CLI-subscription runtimes, OAuth apps, MCP
  servers, local LLMs, browser/computer-use) into one shape.
- 25 of the 57 cards are `install_method === 'coming-soon'` — catalog
  metadata for connectors Daena cannot install or probe yet. Pure
  noise on the operator's first read.
- "Configure" on subscription-first providers (Anthropic / OpenAI /
  Gemini) deep-links to `/account#provider-keys` — the wrong path for
  an operator who already has the corresponding CLI subscription.
- Failed pills on Claude Code / Codex / Gemini CLI carry stale
  `probe_unavailable:` reasons because rows were probed before
  `install_all_probes()` registered the real probes.
- Inconsistent "Apps tab" references in `AcceptanceStatusPanel` and
  `GoogleAccountSetupGuide` — there is no Apps tab; tabs are Brain /
  Plugins / Advanced.
- Multiple cards per vendor (Notion / Notion-OAuth, Sentry /
  Sentry-OAuth, Cloudflare / Cloudflare-OAuth) split *the same product*
  into two cards based on auth method. Confusing.

## Today's hot-fix patch (DAENA-CONNECTIONS-FIX-1..4 — landed in this commit)

| Fix | What changed |
|---|---|
| Fix-1 | "Apps tab" → "Plugins tab" in `AcceptanceStatusPanel.tsx` and `GoogleAccountSetupGuide.tsx`. |
| Fix-2 | `_self_heal.heal_stale_probes()` runs at deferred startup; re-probes any V2 row whose `*_failure_reason` starts with `probe_unavailable:`. Bounded to 50 rows, never breaks startup. |
| Fix-3 | `PluginsPanel` filters out `status === 'coming_soon'` cards by default. Operator can flip "Show roadmap (N)" toggle in the header to see them. |
| Fix-4 | `AccountProviderKeys` shows a `CliSubscriptionHint` banner at the top when a paired CLI runtime is callable. Tells the operator clearly that they already have Anthropic / OpenAI / Gemini reachable via subscription, no API key needed, and deep-links to `/connections` to pick it as Main Brain. |

These are surgical. They make the existing surface less confusing.
They do **not** rebuild the page.

## The real work — Sprint-22 Connections V3

The operator wants what Claude Desktop / Codex Desktop / OpenClaw ship:
**a curated catalog of ~30–50 first-class apps**, each with a single
"Connect" button that walks the operator through OAuth, registers
skills automatically on success, and is honest about what's wired vs.
what isn't.

### V3 scope

1. **Curated catalog (~30 apps).** Drop the long tail. Keep the apps
   the operator actually uses or can plausibly use today: Gmail,
   Drive, Calendar, Notion, Slack, GitHub, Linear, Sentry, Vercel,
   Cloudflare, Figma, Canva, Stripe, Shopify, Hugging Face, Brave
   Search, Filesystem, Memory, Time, Sequential Thinking, Playwright,
   Chrome DevTools, Desktop Commander, Windows MCP, Ollama,
   llama-server, Claude Code, Codex CLI, Gemini CLI. The exact list
   gets curated against Claude Desktop's + Codex Desktop's + OpenClaw's
   shipped catalogs.

2. **One-button "Connect" per app.** Click → if API key, drawer asks
   for it and validates by health probe. If OAuth, pop the OAuth start
   URL in a new tab → operator picks an account / signs in / grants
   scopes → callback finishes the flow → card flips to Connected as
   `user@example.com`. **No two-step "Setup guide" → "Install" →
   "Connect" maze.**

3. **Auto-skill registration.** When a card flips to Connected, the
   skills it ships with become available immediately — no manual
   "register skills" step. Skill catalog is per-app metadata in the
   curated catalog.

4. **Fold dual-auth duplicates.** Notion / Notion-OAuth → one card
   with an auth-method picker. Same for Sentry / Cloudflare / Drive
   variants. The card shows the SELECTED auth method's lifecycle.

5. **Subscription-first split.** API providers (Anthropic / OpenAI /
   Gemini) get a dedicated "AI providers" subtab inside Brain. Each
   row offers TWO mutually exclusive paths:
   - **Use my CLI subscription** (preferred when a callable CLI is detected)
   - **Use API key** (fallback)

6. **Real probes for everything left.** Already shipped per-kind for
   `cli_runtime / mcp_server / local_model / oauth_app / provider /
   skill_pack`. The V3 grid surfaces them; no guesses.

7. **No "Coming soon" cards in the main grid.** Roadmap items live in
   a separate `/connections#roadmap` deep-link or under a single
   "Roadmap" toggle. The default grid shows ONLY actionable cards.

### V3 non-goals

- **No long tail.** No 1000-app marketplace. The operator doesn't need
  Notion / Notion-OAuth / Notion-MCP / Notion-Adapter as four separate
  cards.
- **No new backend kinds.** V3 reuses `connection_v2` schema + the 6
  existing probes. The work is curation + UX, not new plumbing.
- **No auto-install of MCPs.** Existing `MCPInstallDrawer` requires
  explicit click (operator may have npx blocked, etc.). Keep it.
- **No new auth flows.** Reuse existing `OAuthConnectDrawer` /
  `ConnectorInstallDialog` / OAuth callback router.

### V3 PR breakdown (proposed)

| PR | Scope |
|---|---|
| V3-PR-1 | Author the curated catalog file (`backend/app/services/connection_v2/v3_catalog.py`): ~30 apps with name, kind, auth_method, vendor_tier, MCP package or OAuth scopes, skill list. |
| V3-PR-2 | Backend endpoint `GET /connections/v3/catalog` that merges the curated catalog with V2 row truth. |
| V3-PR-3 | New `ConnectionsV3Page` (or replace `PluginsPanel`) — clean grid, single "Connect" button per card, auth-method picker for dual-auth, no roadmap noise. Replaces the legacy V1 catalog browser. |
| V3-PR-4 | Auto-skill registration on `Connected` transition: when V2 callable=true is reached for a card, write the card's skill list into the skills registry. |
| V3-PR-5 | Subscription-first split for AI providers — banner + CLI-vs-API toggle inside the AI provider card. |
| V3-PR-6 | Migrate `AcceptanceStatusPanel`, `MainBrainPanel`, `GoogleAccountSetupGuide` to point at the V3 grid; remove duplicate cards. |
| V3-PR-7 | Source-grep tests pinning honesty contracts (no card claims callable without a probe; no card lacks an auth-method picker for dual-auth vendors; etc.). Final smoke + push. |

### Estimated scope

- ~5–7 backend files (catalog + endpoint + skill auto-register)
- ~10–15 frontend files (V3 grid + drawer wiring + AI-provider split)
- ~3–5 days of focused work

### Predecessor

The Google OAuth Live Proof Run (D.1–D.10) does **not** require V3. It
works with the current grid as long as the operator can find the
"Google Account Setup Guide" inside the Plugins tab. Today's hot-fix
1+2+3+4 unblocks that. **Run V3 after Google OAuth proof completes.**

## Operator decision points

When V3 starts, you need to decide:

1. **Catalog list** — confirm or trim my proposed ~30. If you want
   anything else (Discord, Asana, Trello, …), name it.
2. **Roadmap visibility** — keep "Show roadmap" toggle, or remove
   roadmap entirely from the operator UI?
3. **API-key path retention** — should `/account#provider-keys` stay
   reachable for operators without a CLI, or should V3 strip API-key
   entry entirely for the three CLI-paired providers?

None of those are answerable today. Park them in this doc and answer
when you're ready to start V3.

## Hard rules carried into V3

- No deploy
- No fake "Connected" pills
- No `Coming soon` in the default operator grid
- No card without a clear primary action
- No silent OAuth (every connect opens the provider's OAuth page in a
  new tab; operator sees and approves)
- No auto-install of anything outside the official MCP install path
- No reading or printing of secret values
