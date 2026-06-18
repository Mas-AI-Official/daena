# PR — Connections Hot-Fix Verification Report

**Date:** 2026-05-06
**Scope:** Verification of the 3-commit Connections hot-fix push (b7e2fb7 → 3ddc509 → 7e92851).
**Author:** Daena VP under operator brief: "Push hotfix → restart → inspect Connections → either finish OAuth or start V3."
**Brutal-truth verdict:** 6/8 PASS, 1 PARTIAL, 1 DEFERRED, 1 FOUND-GAP that the hot-fix introduced and did not close.

---

## 1. Push verification

| Field | Value |
|---|---|
| Local HEAD before push | `7e92851f9c7332b224bb75893a4998383b320202` |
| origin/master before push | `6d58c2c0eee73c9e97dc98802dc2d825617b196a` |
| FF-only check | `git merge-base --is-ancestor origin/master HEAD` → `FF_OK` |
| `git push origin master` output | `6d58c2c..7e92851  master -> master` |
| Local HEAD after push | `7e92851f9c7332b224bb75893a4998383b320202` |
| origin/master after push | `7e92851f9c7332b224bb75893a4998383b320202` |
| SHAs equal | **yes** |
| Force flag | **not used** |
| Deploy | **not done** (no Cloud Run / GCP changes) |
| Secrets in commits | **none** (3 commits inspected by file list) |

**Commits published:**

```
7e92851  fix(connections): subscription-first AI provider cards + status sort + #brain deep-link
3ddc509  fix(connections): hot-fixes for operator-visible UX issues + V3 plan
b7e2fb7  docs(google-oauth-live-proof-run): operator interactive checklist seeded
```

Result: **PASS** — fast-forward only, no force, no deploy, no secrets, scope limited to Connections + Google OAuth proof doc.

---

## 2. Restart status

| Field | Value |
|---|---|
| Cleanup script | `scripts\cleanup-stale-dev.ps1` (PowerShell) |
| Start script | `scripts\start-daena-local.bat` (batch) |
| Can Daena execute these herself | **No** |
| Reason | Workspace policy denies `powershell.exe` invocation via Bash (would circumvent the user's PowerShell deny rule). |
| Current backend uptime | 2h 31m — operator has not restarted since the hot-fix landed on disk. |
| Current backend version | `2.0.0`, status `healthy`, db `healthy`, redis `unavailable` (expected). |

**Operator action required:** run `scripts\cleanup-stale-dev.ps1` then `scripts\start-daena-local.bat` from PowerShell. Then refresh `/connections`.

Result: **DEFERRED** — push verified; restart sits with the operator.

---

## 3. Eight observable verification items

### 3.1 `/connections` loads

| Method | Result |
|---|---|
| TypeScript build (proxy for "the page renders") | `npx tsc --noEmit` → **clean, 0 errors** |
| Vite dev server live? | **No** (port 5173 unreachable) |
| Backend live? | **Yes** (`/api/v1/health` HTTP 200) |
| Operator-side browser verification | **Pending** — operator must start Vite (`scripts\start-daena-local.bat` does both) and refresh. |

**Verdict:** PASS for code-correctness; **PENDING** for browser-rendered confirmation.

---

### 3.2 Text says "Plugins tab", not "Apps tab"

```text
frontend/src/pages/connections/AcceptanceStatusPanel.tsx:313:
  ? 'Open the Plugins tab and follow the Google Account Setup Guide. ...'
frontend/src/pages/connections/GoogleAccountSetupGuide.tsx:128:
  Not connected yet. Open the Plugins tab below and click Connect on
```

Both occurrences switched. Grep for legacy "Apps tab" in those files returns zero hits.

**Verdict:** **PASS**.

---

### 3.3 Roadmap cards hidden by default

```text
frontend/src/pages/connections/PluginsPanel.tsx:105:
  const [showRoadmap, setShowRoadmap] = useState(false)
PluginsPanel.tsx:163:
  const filtered = showRoadmap ? all : all.filter((p) => p.status !== 'coming_soon')
PluginsPanel.tsx:316,320:
  <input checked={showRoadmap} ... />
  Show roadmap ({hiddenRoadmapCount})
```

Default state is `false`, filter excludes `coming_soon`, header offers an opt-in checkbox with the hidden-count badge.

**Verdict:** **PASS**.

---

### 3.4 CLI cards no longer show stale `probe_unavailable`

Live snapshot from `/api/v1/connections/v2?kind=cli_runtime` (3 rows):

| Slug | Label | Callable | Stale `probe_unavailable:` failures |
|---|---|---|---|
| `cli-claude_code` | `healthy_stale` | **true** | none |
| `cli-codex` | `failed` | false | none — real reason `auth_failed: token expired` (codex login expired; not a stale probe) |
| `cli-gemini_cli` | `healthy_stale` | **true** | none |

Provider-side snapshot (`kind=provider`, 5 rows):

| Slug | Label | Callable | Stale `probe_unavailable:` failures |
|---|---|---|---|
| `ollama` | healthy_stale | true | none |
| `vllm` | healthy_stale | true | none |
| `gemini` | healthy_stale | true | none |
| `perplexity` | healthy_stale | true | none |
| `groq` | healthy_stale | true | none |

Zero rows carry a `probe_unavailable:` failure_reason in any of the 6 ladder dimensions.

**Verdict:** **PASS** for the observable claim. Note: this state was already clean before today's restart — meaning either an earlier restart fired the heal step, or periodic re-probe naturally cleared the rows. The wire-up of `_heal_stale_probes` (`backend/app/main.py:669-700`, `backend/app/services/connection_v2/_self_heal.py:51`) is correct on disk and will re-fire idempotently on the operator's next restart. There are no rows for it to heal right now (zero work to do), which is the desired steady state.

Codex remains correctly marked `failed` because the underlying cause is real auth expiry, not a stale probe. Operator action: `codex login`.

---

### 3.5 Anthropic / OpenAI / Gemini cards prefer CLI subscription path when CLI is callable

The hot-fix wires `cliSubscriptionByProviderId` in `PluginsPanel.tsx:118-142`:

| Catalog id | Maps to runtime_id | Live CLI row label | Resulting `cliPrimary` |
|---|---|---|---|
| `provider-anthropic` | `claude_code` | `healthy_stale` (callable=true) | **true** → emerald "Reachable via Claude Code subscription · Use as Main Brain" → `/connections#brain` |
| `provider-openai` | `codex` | `failed` (callable=false) | **false** → falls back to "Configure" → `/account#provider-keys` (honest: Codex CLI auth expired) |
| `provider-google-gemini` | `gemini_cli` | `healthy_stale` (callable=true) | **true** → emerald "Reachable via Gemini CLI subscription · Use as Main Brain" → `/connections#brain` |

Cli-primary precondition (`PluginCardView.tsx:103-107`):

```ts
const cliPrimary =
  cliAlternative
  && cliAlternative.callable
  && plugin.source.catalog.kind === 'api_provider'
  && plugin.status !== 'connected'
```

The "don't demote a real connected status" guard is intentional — if the operator pasted a real Anthropic API key and connected via that path, Daena will not flip them to the CLI banner.

**Verdict:** **PARTIAL** PASS — Anthropic and Google Gemini cards now point at the right path; OpenAI correctly falls back because Codex CLI auth is expired (this is a feature, not a regression — the page will not advertise a path that doesn't work). Operator-side browser confirmation pending Vite + reload.

---

### 3.6 Provider Keys page shows CLI subscription hint

```text
frontend/src/pages/account/AccountProviderKeys.tsx:73-139:
  CliSubscriptionHint() {
    claude_code: 'Claude Code subscription (Pro / Max)',
    codex: 'Codex CLI (ChatGPT Plus / Pro)',
    gemini_cli: 'Gemini CLI',
    ...
    "You already have a callable CLI subscription — no API key needed."
  }
```

Component is exported and rendered at the top of the API-keys page when `useConnectionsV2('cli_runtime')` returns at least one callable row.

**Verdict:** **PASS** for code; **PENDING** for browser confirmation.

---

### 3.7 Google Account Setup Guide is findable from Plugins

**This is the gap.** The Fix-1 text edit changed "Apps tab" → "Plugins tab" in both:

- `AcceptanceStatusPanel.tsx:313`
- `GoogleAccountSetupGuide.tsx:128`

But `<GoogleAccountSetupGuide />` is **not actually mounted in `PluginsPanel.tsx`**. It is mounted in:

- `frontend/src/pages/connections/AppsPanel.tsx:115` — but `AppsPanel.tsx` is **dead code** (no imports referencing it).
- `frontend/src/pages/connections/AppsStorePanel.tsx:110` — mounted inside `AdvancedPanel` → "apps" section, which requires the operator to toggle "Show advanced", click Advanced tab, then drill into the apps section.

Outcome: when the operator follows the new text and opens the Plugins tab, they will **not** see the Google Account Setup Guide there. They will have to discover the Advanced tab → apps drill-down on their own — exactly the kind of maze the operator complained about.

**Verdict:** **FOUND-GAP**. The text fix landed without moving the underlying mount point. This is a real flaw introduced by today's hot-fix.

**Proposed minimal follow-up (one PR, ~5 lines, no new feature):**

```tsx
// PluginsPanel.tsx (top of returned JSX)
import GoogleAccountSetupGuide from './GoogleAccountSetupGuide'
...
return (
  <div>
    <GoogleAccountSetupGuide />
    {/* existing plugin grid */}
  </div>
)
```

This duplicates the guide into the Plugins tab so the operator sees it where the new text says it lives. Sister copy in AppsStorePanel can stay (until V3 deletes Advanced > apps section), or be removed in the same PR.

I have **not** landed this follow-up. Per the operator brief ("Push only the scoped Connections hotfix commit … No new feature work"), I am surfacing the gap and waiting for an explicit go.

---

### 3.8 `/connections/google-activation-summary` shows exact OAuth blockers

Live response:

```json
{
  "ready": false,
  "client_configured": false,
  "blockers": [
    { "role": "client", "email": null,
      "missing": ["client_id", "client_secret"] },
    { "role": "founder", "email": "masoud.masoori@mas-ai.co",
      "missing": ["gmail", "drive", "calendar"] },
    { "role": "agent", "email": "daena@mas-ai.co",
      "missing": ["gmail", "drive", "calendar"] }
  ]
}
```

Three blockers, identical shape to the pre-push live capture in `DAENA_GOOGLE_OAUTH_LIVE_PROOF_RUN.md`. The hot-fix did not touch this surface, which is correct.

**Verdict:** **PASS**.

---

## 4. Findings & risk

### Findings

| # | Severity | What | Where |
|---|---|---|---|
| F1 | P1 | Google Account Setup Guide is mounted in Advanced > apps, not in the Plugins tab where the new text now sends the operator. | `AppsStorePanel.tsx:110` mounts; `PluginsPanel.tsx` does not. Proposed 5-line fix in section 3.7. |
| F2 | P2 | `AppsPanel.tsx` is dead code (no import referencing it). Carries an unused mount of the same guide. | `frontend/src/pages/connections/AppsPanel.tsx`. Safe to delete. Defer to V3 cleanup. |
| F3 | Info | `cli-codex` is `failed` with `auth_failed: token expired`. Heal step won't fix this — it's a real auth state. | Operator action: `codex login` from PowerShell. |
| F4 | Info | The heal step (Fix-2) is wired correctly but currently has zero stale rows to heal. Idempotent no-op on next restart. | `_self_heal.py:51`, `main.py:700`. |

### Things still un-verifiable from inside Claude Code

- Browser-rendered behavior of `/connections` (Vite dev server is not running; operator must start it).
- Operator hand-test of: clicking Anthropic card → going to `#brain` (instead of `#provider-keys`); the emerald banner copy; the `Show roadmap (N)` toggle behavior; the deep-link from `/connections#brain` from elsewhere in the app.

These have to land on the operator's own screen.

---

## 5. Decision tree (operator only)

```
operator restarts Daena (cleanup-stale-dev.ps1 + start-daena-local.bat)
  → operator opens /connections in the browser

  if Connections is now understandable AND the Google Setup Guide is findable
    → ship F1 follow-up (5-line PluginsPanel mount) → confirm
    → continue Google OAuth Live Proof Run from D.1

  if Connections is still confusing despite this hotfix
    → start DAENA-CONNECTIONS-V3-CURATED-CATALOG (Sprint-22 plan in
      docs/Ultraview/DAENA_CONNECTIONS_V3_PLAN.md)
    → answer the 3 V3 decision points first:
        1. catalog list (~30 apps) — confirm or trim
        2. roadmap visibility — keep "Show roadmap" toggle, or remove?
        3. API-key path retention — keep /account#provider-keys for
           CLI-paired providers, or strip it entirely?
```

---

## 6. Brutal truth

The hot-fix shipped what was scoped. It does **not** rebuild the Connections page; it makes today's surface less wrong. Three of the operator's complaints are now genuinely fixed (wrong tab name, roadmap noise, wrong CTA on subscription providers). One — "where do I find the Google setup wizard" — was fixed in copy but not in routing, which is a real F1 gap and the most useful next move.

V3 is the right long-term answer. Don't start V3 today; finish OAuth proof first so we know what real-world OAuth wiring teaches us about V3's curated-catalog shape. V3 built without that signal will just be a prettier version of the same wrong assumptions.

**Stop and report.**
