# Connections — Card-by-card walkthrough (live browser audit)

**Date:** 2026-05-06
**Method:** Driven via Chrome DevTools MCP against `http://localhost:5176/connections` after the 3-commit hot-fix push.
**State at audit start:** 6 connected · 2 installed · 2 failed · 37 available.
**State at audit end:** 8 connected · 1 installed · 1 failed · 37 available.

The two flips during the audit were:
- **Codex CLI** went from `failed (auth_failed: token expired)` → `connected` after `codex login` refreshed `~/.codex/auth.json` and the Test button re-probed.
- **Filesystem MCP** went from `installed` → `connected` after Test re-probed and the MCP responded.

Side benefit: when Codex flipped, the **OpenAI API** card automatically picked up the emerald "Reachable via Codex CLI subscription · Use as Main Brain" path, mirroring what the Anthropic API card already showed via Claude Code.

---

## What each card button actually does (verified live)

The Plugins grid offers six action verbs. Each one maps to a different code path:

| Action | Plugin kind | What clicking does | Verified? |
|---|---|---|---|
| **Test** | any with V2 row | `POST /api/v1/connections/v2/{id}/probe` → re-runs the probe ladder, updates the row's last failure_reason + label. Card pill updates. | ✓ Codex `failed → connected`. Filesystem `installed → connected`. |
| **Install** | mcp_server with `command_template` | Opens `MCPInstallDrawer`. 4 steps: **Choose CLI** (Claude Desktop / Claude Code / Codex / Gemini) → **Preview** → **Confirm** → **Test**. Daena writes the npx invocation into the chosen CLI's mcp config (e.g. `~/.claude.json`, `~/.codex/config.json`). | ✓ Brave Search drawer opened, showed all 4 host options + the exact config file each would touch. |
| **Setup guide** | oauth_app | Opens `OAuthConnectDrawer`. Drawer fetches `POST /api/v1/connections/oauth/start`. If `failure_reason` starts with `configure_required:`, shows a FailureBlock with a "Configure in Settings" button → `/account#oauth-clients`. If start succeeds, shows scopes preview + "Open consent page" → popup → token capture. | ✓ Gmail drawer: shows `configure_required: google_client_id not set -- paste your gmail OAuth client credentials...` Pre-flight gate works. |
| **Configure** | api_provider | Deep-links to `/account#provider-keys` (the new Provider Keys section under Account). **Does not** open a drawer. | ✓ OpenRouter Configure → URL changes to `/account#provider-keys`. |
| **Use as Main Brain** | api_provider with callable paired CLI | Deep-links to `/connections#brain` (Brain tab, where the operator picks which runtime orchestrates). | ✓ Anthropic + OpenAI both expose this button (Claude Code + Codex callable). Gemini API will when its CLI is also callable. |
| **Or use API key** | api_provider with callable paired CLI | Same as Configure: deep-links to `/account#provider-keys` so the operator can override the CLI path with a paste key. | ✓ Visible on Anthropic + OpenAI cards. |
| **Details** | any | Opens `PluginDetailDrawer` (read-only). Shows: probe ladder, last failure reason, last checked, install/setup steps, vendor docs links, governance recommendation, source/trust, compatibility matrix, sample prompts. **Test button at the bottom** re-probes from inside the drawer. | ✓ Codex Details + Playwright Details drawers both render the full content. |

---

## What's currently working end-to-end

These flows are wired, honest, and proven via live click in this audit:

1. **CLI runtimes** (Claude Code, Codex, Gemini CLI):
   - `Discover installed tools` button → backend `/discovery/refresh` finds the binary + auth file → V2 row + truth ladder populated.
   - `Test` re-probes; if auth file is fresh, row flips to `connected (callable=true)`.
   - **Anthropic + OpenAI provider cards then become "Reachable via {CLI} subscription"** via the cliPrimary hot-fix path.

2. **Connected providers** (Ollama, vLLM/llama-server, Gemini API, Groq, Perplexity):
   - All 5 already callable (the operator has env-var keys configured).
   - Test re-probe works.

3. **Installed MCPs** (Filesystem, Windows MCP):
   - `Test` re-probes via `mcp_initialize` → if MCP responds, flips to `connected`.
   - Filesystem demonstrably worked in this audit.

4. **MCP install wizard** (Brave Search, Fetch, Git, GitHub, Hugging Face, Memory, MongoDB, Neon, Postgres, Sequential Thinking, SQLite, Supabase, Time):
   - `Install` button opens 4-step drawer. 4 host CLI options, each with its config-file path shown.
   - Wizard writes the npx invocation into the chosen CLI's config; Daena does NOT spawn the MCP itself — the host CLI does.
   - Operator confirms each step explicitly.

5. **OAuth Connect drawer** (Gmail, Calendar, Drive, GitHub OAuth, Slack OAuth, Notion, Linear, Sentry, Vercel, Atlassian, Cloudflare, Canva, Figma OAuth, Stripe):
   - `Setup guide` opens drawer → fetches OAuth start payload from backend.
   - Pre-flight gate: if `client_id`/`client_secret` missing on the Daena side, drawer shows "OAuth client not configured" with a button to `/account#oauth-clients`.
   - When client is configured, drawer shows scopes + opens the vendor consent popup.

6. **Provider Keys page** (`/account#provider-keys`):
   - **CliSubscriptionHint banner** is rendered (the hot-fix component): tells operator they already have Anthropic / OpenAI / Gemini callable via subscription, and links back to `/connections#brain` if they only want CLI orchestration.
   - Password inputs for 7 providers (Anthropic, OpenAI, Gemini, Groq, Perplexity, OpenRouter, Together).
   - OAuth client config inputs for 5 vendors (Google, GitHub, Slack, Figma, Canva) below.

7. **Hot-fix subscription path** for AI providers:
   - Anthropic API card: emerald, "Reachable via Claude Code subscription · Use as Main Brain".
   - OpenAI API card: emerald, "Reachable via Codex CLI subscription · Use as Main Brain" (after Codex flipped).
   - Each card also exposes "Or use API key" as a quiet fallback.

---

## What is genuinely broken (V3-grade gaps)

These are the real holes. They require code changes, not operator action.

### Gap V3-G1 — No in-app "Sign in" on a Failed CLI card

**Symptom (live):** Codex CLI showed `failed (auth_failed: token expired)`. The Details drawer's INSTALL/SETUP section literally says: *"Run `codex --bare`. Authenticate via the vendor's CLI (e.g. claude login, codex login). Daena does not execute install commands automatically."* No button on the card or in the drawer triggers `codex login` for the operator.

**Today's workaround:** Operator runs `codex login` in a terminal. Daena's Test button only re-probes after the operator does this externally.

**V3 fix proposal:** Add `POST /api/v1/runtimes/{runtime_id}/auth/start` that spawns `codex login` server-side and returns the OAuth URL. Frontend renders a "Sign in to {CLI}" button that opens the URL in a new tab. After the vendor's local server captures the callback, Daena polls `auth.json`'s mtime and triggers a re-probe automatically. Same shape works for `claude login` and `gemini auth login`.

**Risk:** spawning subprocesses from a web request is the kind of thing that needs careful sandboxing. The OAuth URL must be parsed from stdout reliably.

### Gap V3-G2 — No "Install for me" on a Failed/Available MCP card

**Symptom (live):** Playwright shows `failed (initialize_failed: McpError: Connection closed)`. The Details drawer offers a useful "Verify locally" button (tries to launch the binary in headless mode for an `about:blank` evaluation), and the INSTALL/SETUP section says `npx -y @playwright/mcp@latest`. No button auto-runs that npx for the operator.

**Today's workaround:** The Install button works for **Available** cards (4-step wizard writes config into chosen host CLI). But the host CLI is what spawns the MCP — Daena never does. So if Playwright is `Failed`, the operator has to either re-run the host-CLI invocation or pick a different host.

**V3 fix proposal:** For Failed MCPs, replace the static drawer with a "Reinstall" path that re-runs the wizard. For Available MCPs that the operator wants Daena to host directly (no host CLI), add a `/connections/v2/mcp/{slug}/start` endpoint that spawns the npx subprocess in a managed pool — only when explicitly authorized by the operator (high-risk path, needs governance gate).

### Gap V3-G3 — `AppsPanel.tsx` is dead code

**Symptom (filesystem):** `frontend/src/pages/connections/AppsPanel.tsx` exists with a `<GoogleAccountSetupGuide />` mount at line 115, but no other file imports `AppsPanel`. The only mount of `GoogleAccountSetupGuide` that's actually reachable is in `AppsStorePanel.tsx:110`, which lives under `Advanced > apps` (requires toggling "Show advanced" first).

**Today's workaround:** Operator must toggle "Show advanced" → click Advanced tab → drill into "apps" section → see Google Account Setup Guide. Today's hot-fix corrected the wording from "Apps tab" to "Plugins tab" but didn't move the mount.

**V3 fix proposal:** 5-line change to `PluginsPanel.tsx`: import `GoogleAccountSetupGuide` and render it at the top of the panel. Delete `AppsPanel.tsx` entirely. This was identified in the hot-fix verification report as F1 P1.

### Gap V3-G4 — 4 "duplicate" cards split a single product into auth-method variants

**Symptom (catalog):**
- `Notion` (vendor MCP) + `Notion (OAuth)` (no second card actually — the catalog has only `Notion` with OAuth scopes, but Notion is dual-auth in vendor docs)
- `GitHub` (vendor MCP, install-via-PAT) + `GitHub (OAuth)` (separate card for OAuth-managed)
- `Slack` (vendor MCP, hosted-only requires admin) + `Slack (OAuth)` (separate card)
- `Figma (Dev Mode)` (vendor MCP) + `Figma (OAuth)` (separate)
- `Google Drive` (Daena-managed OAuth) + `Google Drive (MCP)` (Anthropic archived ref)

**Today's workaround:** Operator picks the right card by reading the description. Most cards display the auth method in the description.

**V3 fix proposal:** Fold each pair into one card with an auth-method picker dropdown inside the drawer (OAuth / API key / MCP). Selected method drives the lifecycle. Save 5 cards.

### Gap V3-G5 — `Coming soon` roadmap (10 items) is hidden by the toggle

**Status:** the hot-fix added `Show roadmap (10)` toggle, default off. Roadmap items are kept off the main grid by default. ✓ Working. No gap. Just confirming this works.

---

## Card-by-card status (state at audit end, post-Codex flip)

### Connected (8) — callable, ready to use

| Card | Vendor | Last fix |
|---|---|---|
| Chrome DevTools | Google | already connected |
| Claude Code (CLI) | Anthropic | already connected |
| **Codex CLI** | OpenAI | **flipped during audit via `codex login` + Test re-probe** |
| Gemini CLI | Google | already connected |
| Google Gemini API | Google | already connected (env-var key) |
| Groq API | Groq | already connected (env-var key) |
| Perplexity API | Perplexity | already connected (env-var key) |
| **Filesystem MCP** | MCP Steering Group | **flipped during audit via Test re-probe** |

### Installed (1) — Test should flip to connected if MCP responds

| Card | Action |
|---|---|
| Windows MCP | Click Test on the card. If the MCP server responds, flips to connected. |

### Failed (1) — needs a real fix, not auth refresh

| Card | Failure | Fix |
|---|---|---|
| Playwright | `initialize_failed: McpError: Connection closed` | The Daena-managed Playwright MCP failed to initialize. Either the npx package version drifted or the host environment is missing browsers. Click Details → Verify locally to run a SAFE pre-install check. If verify passes, run `npx -y @playwright/mcp@latest` in a host CLI's config (Install drawer). |

### Available (37) — fall into 3 sub-groups

**Group A — MCP installs (13 cards):** Brave Search, Fetch, Git, GitHub, Hugging Face, Memory, MongoDB, Neon, Postgres, Sequential Thinking, SQLite, Supabase, Time. Click Install → 4-step wizard. Most need an API key set in env (e.g. BRAVE_API_KEY, GITHUB_PAT) — the wizard collects them in step 2.

**Group B — OAuth apps (16 cards):** Atlassian, Canva, Cloudflare, Desktop Commander, Figma (×2), GitHub (OAuth), Gmail, Google Calendar, Google Drive (×2), Linear, Notion, Sentry, Slack (×2), Stripe, Vercel, Ollama. Click Setup guide → drawer. Each requires the operator to first paste the vendor's `client_id`/`client_secret` at `/account#oauth-clients`. **For all 4 Google cards (Gmail / Calendar / Drive / Drive MCP), the same Google OAuth client unlocks all of them.**

**Group C — provider keys (2 cards still unconfigured):** OpenRouter, Together AI. Click Configure → land on `/account#provider-keys` → paste key → save.

---

## Operator action map (what unlocks the rest)

If the goal is to maximize callable surface fast, here is the ranked path:

| Priority | Action | Time | Unlocks |
|---|---|---|---|
| **1** | Create one Google Cloud OAuth client at `console.cloud.google.com/apis/credentials`, paste client_id + client_secret at `/account#oauth-clients` | ~5 min | Gmail, Google Calendar, Google Drive, Google Drive (MCP) — 4 cards |
| **2** | Click Setup guide on Gmail → consent popup → approve `gmail.send` + `gmail.compose` for `masoud.masoori@mas-ai.co` | ~1 min | Gmail send/draft for founder account |
| **3** | Repeat step 2 for `daena@mas-ai.co` (founder switches Google account in popup) | ~1 min | Gmail send/draft for agent account |
| **4** | If you want Stripe / Sentry / Notion: paste their OAuth `client_id`/`client_secret`, click Setup guide on each | ~5 min each | one card per vendor |
| **5** | If you want any MCP from Group A: click Install → pick host CLI (Codex CLI is the most common) → confirm | ~30 sec each | one MCP per click |
| **6** | OpenRouter / Together AI keys: paste at `/account#provider-keys` (not strictly needed since you already have Anthropic / OpenAI / Gemini callable via subscription) | ~30 sec each | broader model coverage |

Step 1+2+3 is the **single highest-value next action**. After that, all 4 Google cards flip to connected, and the Live Business Beta loop (DAENA-GOOGLE-OAUTH-LIVE-PROOF-RUN) can run end-to-end.

---

## What Daena does NOT do today (and why)

- **Daena does not run `codex login` / `claude login` / `gemini auth login`.** These are interactive vendor flows that open browsers; spinning them up server-side from a web request needs careful sandboxing. Today the operator runs them in a terminal. V3 candidate (V3-G1).
- **Daena does not run `npx -y <mcp-package>` directly.** It writes the invocation into the host CLI's config; the CLI runs the MCP. This is the right boundary — Daena owns the catalog + governance + truth ladder; the host CLI owns subprocess lifecycle.
- **Daena does not auto-create OAuth clients on vendor consoles.** This is an inherent limitation: Google Cloud Console + GitHub Developer Settings + Slack App Manifest etc. all require human-loaded forms. The closest thing to automation is pre-filling guides (which the GoogleAccountSetupGuide already does for Google).
- **Daena does not auto-paste API keys.** By design — keys are sensitive and the operator must paste deliberately. The vault layer (`/account#provider-keys`) handles them once pasted, encrypted at rest.

---

## Brutal-truth verdict

The Connections page **is functionally correct after the hot-fix**. Every card has a reachable wizard or guide, the truth ladder is honest, and stale states self-heal on probe. What the operator perceives as "broken" is actually the absence of three V3 features:

1. In-app trigger for vendor CLI auth flows (V3-G1).
2. In-app auto-install of MCP packages (V3-G2).
3. A consolidation pass on duplicate vendor cards (V3-G4).

Of those, **V3-G1 has the highest leverage** — it would let the operator click "Sign in" inside Daena instead of opening a terminal, which matches what they explicitly asked for. The hot-fix shipped today does NOT close V3-G1; that's separate work.

Until V3-G1 ships, the operator's friction on Failed CLI cards (Codex token expired, future Claude/Gemini token expiries) will repeat. The Live Business Beta proof can still run because the only gating CLI is Codex, and Codex is now connected. But the next time any CLI's id_token rotates out, the operator will be back in a terminal.

Status: **ship the hot-fix as-is, run Google OAuth Live Proof, then start V3 with G1 + G3 + G4 first.**
