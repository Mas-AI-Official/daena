# Mythos simplification — Connections + Sidebar

**Date:** 2026-05-06
**Trigger:** operator (Masoud), reviewing the post-hot-fix Connections page:
> "make it simple as codex it is, 1 click install, or go to oauth.... i dont need that much details in the every mcp keep it simple lots of text and frontend exist there which is not necessary at all... think like mythos, go to codex desktop frontend... look at it, learn from it and bring it here"

This is a UX redirection, not a bug report. The hot-fix shipped today is correct as a stop-gap; the real ask is to **rebuild Connections at the conviction level Codex Desktop ships at: 1 click per outcome, no walls of text, no progress reports for operations the operator did not initiate.**

---

## 1. What Codex Desktop actually does (live observation)

Source: `C:\Users\masou\.codex\plugins\cache\` — every Codex plugin manifest examined.

A Codex plugin manifest is ~40 lines of JSON. The card in Codex Desktop renders:

```
┌─────────────────────────────────────────┐
│ [logo]  Browser Use                     │
│         OpenAI · Engineering            │
│                                         │
│ Control the in-app browser with Codex.  │
│                                         │
│ Read · Write · Interactive              │
│                                         │
│              [ Add to Codex ]           │
└─────────────────────────────────────────┘
```

Six things on screen. ONE button. That's it.

What Codex Desktop **does not show** by default:
- Probe ladder (detected/configured/imported/reachable/authenticated/callable)
- "Source & Trust" collapsible (not relevant to the choice the operator is making)
- "Governance recommendations" with READ/ALLOW/Metadata-only blurb
- "INSTALL / SETUP (NPM)" with copy-paste shell commands
- "Last failure: X" / "Last checked: timestamp"
- 4-step host-CLI picker wizard
- Compatibility matrix with AUTH / RISK / INSTALL / OS rows
- Sample prompts to "use in chat"
- The ENV var names callout
- "Daena does not vet third-party MCP code" community warning

All of those are **legitimate engineering artifacts**. None of them belong on the operator's first read of a card.

What Codex Desktop does on click:
1. **API key plugin** → drawer with one input ("Paste {vendor} API key") → Save → card shows the email/account or "Connected".
2. **OAuth plugin** → opens vendor OAuth page in new tab → operator approves → callback fires → card flips to "Connected as user@email".
3. **MCP plugin** (npx) → "Add to Codex" writes the npx invocation into Codex's own config → done.

That's the whole UX. Nothing else.

---

## 2. Daena Connections today (count of moving parts)

| Surface | Count |
|---|---|
| Sidebar nav items | **21** (audit below) |
| Plugin grid cards visible by default | **47** (after roadmap toggle hides 10) |
| Buttons per card on the grid | 2 (Details + action) |
| Sections in the Details drawer (PluginDetailDrawer) | **8** — header, WHAT DAENA CAN DO, CONNECTION STEPS, SKILLS, PERMISSIONS, GOVERNANCE RECOMMENDATIONS, WHERE KEYS LIVE, PROBE STATUS, INSTALL/SETUP, SOURCE & TRUST, COMPATIBILITY |
| Steps in the MCP install wizard | **4** — Choose CLI / Preview / Confirm / Test |
| Distinct drawers a card can open | 3 — Details, MCPInstallDrawer, OAuthConnectDrawer |
| "Apps tab" / "Plugins tab" / "Advanced > apps" overlapping mounts of same content | yes |

Operator's complaint translates: **8 drawer sections is 7 too many; 4-step wizard is 3 too many; the right number of buttons on a card is one.**

---

## 3. Sidebar audit — 21 items

```
CORE (2)
  Chat                       ← daily
  Dashboard                  ← daily

INTELLIGENCE (4)
  Security Scan              ← weekly
  Departments                ← rare
  Minds                      ← rare
  Skills                     ← rare

GO-TO-MARKET (1)
  Company Mode               ← rare

EXECUTION (5)
  Workstreams                ← daily
  Tasks                      ← daily
  Projects                   ← weekly
  Pipeline                   ← rare
  Files                      ← weekly

CONNECTIONS (1)
  Connections                ← daily

GOVERNANCE (8)
  Security Ops               ← weekly
  Scan Scope                 ← rare
  Approvals                  ← daily (only if pending)
  Policy Rules               ← rare
  Audit Log                  ← weekly
  Trust Ladder               ← rare
  Opportunities              ← unclear (operator's word)
  Analytics                  ← weekly
```

**Mythos cut — 7 daily/active items at top, 14 collapsed:**

```
TOP-LEVEL (7, always visible)
  Chat
  Dashboard
  Connections
  Tasks
  Workstreams
  Approvals (with badge)
  Files

GOVERNANCE (collapsible — 8)
  Security Scan
  Security Ops
  Scan Scope
  Policy Rules
  Audit Log
  Trust Ladder
  Analytics
  (Opportunities — kill or move to Pipeline)

WORKBENCH (collapsible — 5)
  Departments
  Minds
  Skills
  Projects
  Pipeline
  Company Mode
```

That's 7 items the operator sees by default, 13 behind one click each. Without removing functionality. The top-level 7 are the ones the operator told me they touch every day; the rest are admin / setup / weekly.

---

## 4. Connections page — Codex-style rewrite (V3)

### 4.1 Default card (what shows in the grid)

```
┌─────────────────────────────────────────┐
│ [logo]  Anthropic API                   │
│         Anthropic · AI Provider         │
│                                         │
│ Direct API access to Claude models.     │
│                                         │
│ ✓ Reachable via Claude Code subscription│
│                                         │
│         [ Use as Main Brain ]           │
└─────────────────────────────────────────┘
```

ONE primary action. ONE status pill (or none). NO sub-buttons. NO probe ladder.

### 4.2 Click behavior — single-action by kind

| Card kind | Click | Result |
|---|---|---|
| **api_provider** with callable CLI | → `/connections#brain` | Operator picks runtime for orchestration |
| **api_provider** without CLI | → mini-drawer: one password input + Save | Saved → card flips to Connected as <provider> |
| **cli_runtime**, Failed | → backend spawns `codex login` / `claude login` / `gemini auth login`, streams the OAuth URL to a new tab | Operator signs in → backend polls auth file mtime → card flips |
| **cli_runtime**, Connected | → `Test` (re-probe inline) | Confirmation toast |
| **mcp_server** | → mini-drawer: 1 dropdown ("Install for: Claude Code / Codex / Gemini / Claude Desktop"), 1 input if `required_env_vars` non-empty | Confirm → write CLI config → Test → done |
| **oauth_app** | → if client_id missing: small banner "Configure once at /account#oauth-clients" + button. If configured: opens vendor consent in new tab | Callback returns → card flips to Connected as user@email |
| **local_model** | → mini-drawer: 1 input for `*_BASE_URL` if missing, else Test | Saved + Test → done |

**No multi-step wizards.** A drawer with 1 input is fine. A 4-step stepper is not.

### 4.3 Click "ⓘ" ICON (NOT a "Details" button) for the technical side

Move ALL of today's PluginDetailDrawer behind a single small `ⓘ` icon that's discoverable but invisible until hovered. The drawer that opens stays as-is for operators who DO want to see the probe ladder + governance + source links. **It is no longer the default.**

### 4.4 What gets removed from the default card

- The "Test" button on the card (only Connected/healthy_stale cards show one). For not-yet-connected cards, the action button IS the test.
- The "Or use API key" sub-button on api_provider cards. Move it inside the drawer as a quiet link.
- The risk pill (LOW / MEDIUM / HIGH) on the card front. Move into the `ⓘ` drawer.
- The capability chips (e.g. "Multi-turn coding sessions", "Native MCP client") under the description. Keep one short description sentence; that's it.
- The "Vendor official" / "Community" pill on the front. Move into `ⓘ`.

### 4.5 Roadmap items — fully gone from the grid

Today's hot-fix added a `Show roadmap (10)` toggle. V3 removes the toggle entirely; roadmap items live at `/connections#roadmap` (different deep-link, intentional friction).

### 4.6 Folded duplicates

- `GitHub` + `GitHub (OAuth)` → ONE card with auth-method picker inside the drawer.
- `Slack` + `Slack (OAuth)` → ONE card.
- `Figma (Dev Mode)` + `Figma (OAuth)` → ONE card.
- `Google Drive` + `Google Drive (MCP)` → ONE card (MCP variant is archived ref anyway).
- `Notion` (vendor) + `Notion (OAuth)` (coming-soon) → ONE card; the variant is hidden until the OAuth flow is wired.
- `Stripe` (vendor) + `Stripe (Connect)` (coming-soon) → ONE card.

47 → ~36 cards by folding alone.

### 4.7 OAuth client config — one-time onboarding card

Today the operator must visit `/account#oauth-clients`, paste 5 different vendor `client_id`/`client_secret` pairs into separate forms, then come back. V3 moves this into a single onboarding step the operator does **once**, surfaced when needed:

```
First time you click on an OAuth-using card whose client isn't configured:

┌──────────────────────────────────────────────────┐
│ One-time setup: paste your Google OAuth client.  │
│                                                  │
│ 1. Open Google Cloud Console, create credentials │
│    [ Open console.cloud.google.com ]             │
│ 2. Paste:                                        │
│    client_id     [_____________________]         │
│    client_secret [_____________________]         │
│                                                  │
│              [ Save and continue ]               │
└──────────────────────────────────────────────────┘
```

Same shape repeats for GitHub / Slack / Figma / Canva. Configured-once, used by every Gmail/Drive/Calendar/etc card thereafter.

---

## 5. PluginDetailDrawer — slim from 8 sections to 3

Default open view:

1. **Header** — name + vendor + 1 sentence
2. **Status** — single sentence ("Connected as masoud@mas-ai.co" / "Probe expected to pass; click Test to verify" / "Not configured: paste your API key below")
3. **Action** — the same primary button the card had

Behind a single "Show technical details" expander:
- PROBE STATUS (the 6-rung ladder)
- INSTALL / SETUP commands
- ENV VAR names
- SKILLS list
- GOVERNANCE recommendations
- SOURCE & TRUST
- COMPATIBILITY
- Last failure / last checked

The expander is collapsed by default. Operator who wants engineering detail clicks once. Operator who wants to use the tool never sees it.

---

## 6. What will NOT change in V3

- **Probe ladder backend.** The 6-rung honesty model (`ConnectionV2` truth) stays. It powers the slim status sentence; the operator just doesn't see all 6 rungs unless they click Show technical details.
- **Vault for API keys.** Keys still live in vault-backed `/account#provider-keys`, encrypted. The drawer just gets a quicker write path.
- **OAuth client config in Settings.** The "paste once per vendor" model stays. We just wrap it in a friendlier first-time onboarding card.
- **Catalog metadata.** The 28 entries are correct (after today's hot-fix patches). No rewrite of catalog needed.
- **Governance pipeline.** Tier 0-4 + Shield + Asset Shield all intact. Just not surfaced as text on every card.

---

## 7. PR sequence — Sprint-22 candidate

| PR | Scope | LOC | Risk |
|---|---|---|---|
| **V3-PR-1** | Sidebar: 7 top-level + 2 collapsibles (Governance, Workbench). Sticky open/close in localStorage. Behind feature flag `connections_v3=true` while testing. | ~150 | low |
| **V3-PR-2** | New PluginCardView2 component (default; old kept under feature flag for rollback). Single primary button, no sub-actions on grid. | ~250 | low |
| **V3-PR-3** | New PluginDetailDrawer2: 3 sections + collapsible "technical details". Old drawer behind flag. | ~400 | low |
| **V3-PR-4** | Mini-drawers per click type: api_provider paste, mcp_server pick-host, oauth_app first-time-config. | ~500 | medium |
| **V3-PR-5** | Backend `/runtimes/{id}/auth/start` endpoint (V3-G1): spawns `codex login` / `claude login` / `gemini auth login`, streams OAuth URL. | ~300 | medium-high |
| **V3-PR-6** | Fold 6 duplicate cards into auth-method-picker pattern. | ~150 | low |
| **V3-PR-7** | Move GoogleAccountSetupGuide into a one-time-onboarding card the first time an OAuth flow needs Google client config. Delete `AppsPanel.tsx` dead code. | ~120 | low |
| **V3-PR-8** | Source-grep tests pinning honesty contracts (no card claims connected without probe; no drawer hides probe ladder behind 4 expanders; etc). Push. | ~100 | low |

Total: ~2000 LOC, ~3-5 working days. Each PR ships behind `connections_v3` feature flag. Rollback = flip flag.

---

## 8. Tonight's mini-fix (NOT V3)

The operator is overwhelmed RIGHT NOW. Three small wins that don't need V3:

### Mini-fix 1 — Slim the Details drawer to one expander

Move 6 of the 8 sections (PROBE STATUS, INSTALL/SETUP, ENV VARS, SKILLS, GOVERNANCE, SOURCE & TRUST, COMPATIBILITY) behind a single `▸ Technical details` expander. Keep header + WHAT DAENA CAN DO + primary action above the fold. ~15 LOC change to `PluginDetailDrawer.tsx`.

### Mini-fix 2 — Sidebar: collapse Governance into one expandable group

Don't redesign the sidebar. Just wrap the 8 Governance items inside a collapsible group with state in localStorage. Default collapsed. ~20 LOC.

### Mini-fix 3 — Card grid: hide capability chips by default

Remove the 3-4 "capability" chips under the description. They burn vertical space and add noise. Keep the description sentence; that's enough. ~5 LOC.

These three deliver 80% of the perceived simplification at 1% of the V3 code volume. They go in tonight if the operator says so.

---

## 9. Brutal-truth verdict

The hot-fix shipped today fixes **what was wrong**. The operator is now asking me to fix **what is too much**. Different problem.

The Codex Desktop comparison is fair. Codex hides engineering complexity by default; Daena exposes it. That's a positioning choice — Daena's V2 truth ladder + governance is real engineering value, but it's leaking onto every card by default and the operator is paying the cognitive cost.

V3 is the right framing. **The work is not "rebuild Connections" — it's "demote engineering detail behind one click everywhere and rebuild the default to be one button per card."** That's a 3-5 day rewrite, not a 30-minute fix.

Tonight: ship the 3 mini-fixes if the operator says go. Tomorrow: start V3-PR-1 (sidebar collapse + feature flag).

The Google OAuth Live Beta proof can run today as-is. V3 is for after the proof completes.
