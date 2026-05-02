# Connections Marketplace -- Research notes

**Date:** 2026-05-02
**Author:** Claude Code (Opus 4.7) under founder direction (PR-CONNECTIONS-MARKETPLACE-UX, Phase J)
**Scope:** background research informing the curated catalog only. NO repo
vendoring. NO dependencies installed. NO automatic execution. Source links
are pointers to public install instructions; the operator follows them
manually until a real probe lands.

---

## 1. Why a curated catalog (instead of an auto-fetched registry)

The MCP ecosystem ships through several distribution surfaces today:

1. **Anthropic's official Model Context Protocol servers repo** (Apache-2.0):
   `github.com/modelcontextprotocol/servers` -- the canonical reference set
   (filesystem, github, gdrive, slack, postgres, sqlite, brave-search,
   memory, fetch, time, sequentialthinking, ...). Distributed via npm
   under `@modelcontextprotocol/server-*` and via PyPI under
   `mcp-server-*`.
2. **Vendor-official MCP servers** -- Google (chrome-devtools-mcp),
   Cloudflare (mcp-server-cloudflare), Sentry (@sentry/mcp-server),
   Stripe (@stripe/mcp-server), Linear (linear-mcp), Notion
   (notion-mcp), Figma (figma-mcp). Each one ships under the vendor's
   own org / package and follows the vendor's auth flow.
3. **Community MCP catalogs** -- e.g. mcpservers.org, smithery.ai,
   opentools.com. Useful as discovery surfaces for end users; not
   suitable as Daena's runtime source-of-truth because:
   - Quality and security review varies by community moderator;
   - They redirect to npm / GitHub for actual install (Daena would
     still need the install plan locally);
   - They drift -- entries appear / disappear without notice.
4. **DXT extensions** -- Anthropic's Desktop Extensions format
   (`.dxt` zips installed under `Claude Extensions/`). Daena's
   detector reads these once installed but does not fetch the
   gallery itself.

**Decision:** ship a hand-curated catalog inside Daena's source tree
(`backend/app/services/connection_v2/marketplace_catalog.py`). Each
entry is reviewed against the official source URL, carries
`required_env_vars` as NAMES ONLY, and never executes install commands.
The frontend renders the catalog as a marketplace; the V2 row truth
ladder overlays the actual install/configure/probe state.

A future PR can add an external-fetch source IF we adopt one of the
community catalogs as upstream and add a signature / review pipeline.
Today: shipped catalog = source of truth.

---

## 2. Coverage decision -- which MCP servers ship in v0

The catalog targets ~30 entries spanning the founder-listed categories:

| Category | Entries (v0) | Source / vendor |
|---|---|---|
| Filesystem | `filesystem`, `desktop-commander` | Anthropic + Wonderwhy-er |
| Browser / Computer Use | `playwright`, `chrome-devtools`, `windows-mcp`, `browserbase` (coming-soon) | Microsoft + Google + community + Browserbase |
| Code platform | `github`, `gitlab`, `cloudflare`, `sentry`, `vercel`, `netlify` | Anthropic + GitLab + vendors |
| Communication | `slack`, `discord` | Anthropic + community |
| Productivity | `notion`, `linear`, `gcal`, `gmail`, `gdrive` | Anthropic + Linear + Google |
| Design | `figma`, `canva` (no MCP yet -- API only) | Figma + Canva |
| Data / Storage | `postgres`, `sqlite`, `mongodb`, `redis` | Anthropic + community |
| Payment | `stripe`, `shopify` (coming-soon) | Stripe + Shopify |
| Local LLM | `ollama`, `vllm` | Daena-native (HTTP probe) |
| Dev tools | `fetch`, `brave-search`, `time`, `git`, `memory`, `sequentialthinking`, `exa-search` (coming-soon) | Anthropic + community |
| AI services | `perplexity-mcp` (coming-soon), `huggingface-mcp` (coming-soon) | Vendor |

**Out of scope for v0:**
- Any entry whose install requires Daena to run an arbitrary script
  outside `npx` / `docker run` / `pip install`.
- Any entry whose auth flow needs a custom OAuth client (Daena will
  surface a "Setup guide" link instead of a built-in install).
- Any entry that requires GPU / model weights (those go through
  Local Models, not MCP).

---

## 3. Lifecycle states (used by every catalog card)

Adopted from the founder's Phase B brief:

```
Available  ->  Installed  ->  Configured  ->  Reachable  ->  Callable  ->  Enabled
                                                      \                /
                                                       v              v
                                                Failed / Needs setup
```

Mapping to V2 truth ladder:
- `Available` = catalog entry exists, no V2 row yet
- `Installed` = V2 row exists with `imported=True` (we know about it locally)
- `Configured` = V2 row has `configured=True` (auth/env present)
- `Reachable` = V2 truth `reachable=True` (network handshake worked)
- `Callable` = V2 truth `callable=True` (real functional probe passed)
- `Enabled` = V2 row not disabled and not archived
- `Failed` = any truth dim has a recent failure (`failure_at` after `at`)

**Honesty rule:** the lifecycle pill on a card NEVER advances past the
truth ladder. If the catalog says "Reachable" but the V2 row's last
probe failed, the card shows "Failed" with the failure reason.

---

## 4. Auth conventions

Each catalog entry declares one auth type:

| Auth type | Daena behavior | UI |
|---|---|---|
| `none` | No setup needed | Probe button enabled immediately |
| `subscription` | CLI uses provider's own auth (e.g. claude login) | "Authenticate via CLI" link |
| `api_key` | Operator pastes API key into Settings | "Add API key in Settings" link |
| `token` | Operator pastes token (PAT / personal token) into Settings | "Add token in Settings" link |
| `oauth` | OAuth 2.0 dance via existing oauth_service | "Connect via OAuth" button (existing flow) |

`required_env_vars` carries NAMES only. The operator sees "Needs:
GITHUB_TOKEN, GITHUB_OWNER" and configures them in the Daena Settings
page or the source CLI's own env. Daena never reads the values until
a real probe is invoked, and even then the probe NEVER returns the
value back to the UI.

---

## 5. Risk levels (for governance display)

- `low` -- read-only, no side effects (filesystem-read, fetch, search,
  list_models, get_user)
- `medium` -- writes within scoped resources (create issue, send
  message, update calendar event, post to slack)
- `high` -- destructive or irreversible (delete file, drop table,
  charge customer, transfer money, force-push, send DM, follow
  account)

Founder rule: catalog entries default to `medium`; entries that
explicitly enumerate `high` capabilities get the `high` badge so the
operator knows what they are signing up for. Asset Shield + governance
mode still gate the actual call; the catalog risk is just a heuristic
for the UI.

---

## 6. Probe types (mapped to V2 probe registry)

| `probe_type` | What runs | Notes |
|---|---|---|
| `mcp_initialize` | JSON-RPC `initialize` + `tools/list` | Future PR-CONN-MCP-PROBE; today `probe_unavailable` |
| `oauth_token` | Read access_token from vault, call `userinfo` / `whoami` endpoint | Future PR-CONN-OAUTH-PROBE; today `probe_unavailable` |
| `http_get` | GET against a known healthcheck URL | Existing `ProviderProbe` covers this for local_model |
| `binary_check` | `shutil.which` + version-check subprocess | Future PR-CONN-CLI-PROBE; today `probe_unavailable` |
| `skill_pack_only` | Always returns `not callable` | Existing `SkillPackProbe` |
| `none` | No probe | Catalog-only entry (e.g. coming-soon) |

The catalog ships the `probe_type` so the V2 row's probe registry
knows which probe class to invoke once the real probes land. Until
then, every probe of type `mcp_initialize` / `oauth_token` /
`binary_check` returns `probe_unavailable` and the UI honestly
displays "Probe not yet implemented" rather than fake-green.

---

## 7. Browser / Computer-use research

The Phase D founder brief asked for honest treatment of this category.
Findings:

- **Playwright MCP** (`@microsoft/playwright-mcp` from Microsoft) --
  full browser automation via the Playwright API, runs locally,
  permission-prompted. Works on Windows / macOS / Linux. NPM install.
- **Chrome DevTools MCP** (`chrome-devtools-mcp` from Google) -- talks
  to Chrome over the DevTools protocol; needs Chrome / Chromium
  running. Useful for "open this page, take screenshot, inspect
  network".
- **Desktop Commander** (`desktop-commander` by Wonderwhy-er) -- full
  desktop control (terminal, file ops, process management). High risk;
  requires explicit operator opt-in.
- **Windows MCP** (community) -- Windows-specific automation
  (PowerShell, registry, services). Windows-only.
- **Browserbase / Stagehand** (paid) -- cloud-hosted browser sessions
  with stealth. Daena marks this as `coming-soon` because the install
  plan needs an account + API key the operator must obtain themselves
  AND Daena does not endorse anti-bot evasion for adversarial use.

Honest copy in the UI:

> "Browser tools let Daena open pages, inspect UI, click, fill forms,
> test flows, and observe results. They require explicit permission
> and run in your local / runtime environment. Daena does not bypass
> anti-bot systems and never claims to evade detection."

This PR ships the catalog cards and Setup Guide links. It does NOT run
live browser automation -- that lands when PR-BROWSER-RUNTIME-WIRING
authorizes the Playwright adapter for general use.

---

## 8. Primary sources consulted

(Public install docs only, never executed.)

- modelcontextprotocol/servers README + per-server READMEs
- modelcontextprotocol.io/clients (DXT extension catalog)
- microsoft/playwright-mcp README
- ChromeDevTools/chrome-devtools-mcp README
- Cloudflare developer docs on `mcp-server-cloudflare`
- Sentry MCP integration docs
- Stripe `agent-toolkit` README (covers `@stripe/mcp-server`)
- Linear API docs + linear-mcp community README
- Notion API docs + notion-mcp community README
- Figma developer docs
- Anthropic OAuth + API key configuration docs
- Google Workspace OAuth scope docs
- GitHub OAuth app + PAT scope docs
- Slack OAuth + bot-token scope docs

No code was copied, no packages installed, no remote scripts run. The
catalog dataclass entries are 100% hand-typed from public READMEs and
captured as a static Python module so the catalog itself can be diffed
+ reviewed before merge.

---

## 9. Future research (not in this PR)

- DXT extension auto-discovery: read `Claude Extensions/<name>/manifest.json`
  and surface them as catalog entries. Defer to PR-CONN-DXT-IMPORT.
- External MCP catalog mirror: subscribe to mcpservers.org (or build
  Daena's own community submission flow). Defer to PR-CONN-CATALOG-EXTERNAL.
- Marketplace ratings / install counts: needs an external opt-in
  telemetry service; out of scope.
- Auto-install via `npx -y` / `docker pull`: requires a real
  install-and-rollback story. Today the catalog returns an
  `install_plan` document for the operator to execute manually.

---

**End of research notes.**
