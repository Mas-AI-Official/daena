# PR-CONN-UI-GHOSTS-AND-PROMPT-WIRING — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Founder request:** clean up the remaining frontend ghosts in
Connections, then wire plugin `suggested_prompts` into the chat
composer as **safe drafts**. Do not execute skills yet.
**Hard rules honored:** no deploy / no V2 flag flip / no vault apply /
no V1 deletion / no secrets touched / no external scans / no
auto-install / no skill execution / no auto-sent chat messages /
no new primary tabs / no falsely-callable status / no spiral-sunflower
takeover.

---

## Summary

Previous PR (`PR-CONN-PLUGIN-SKILLS-UX-WIRING`, commit `55e836c`) made
the plugin drawer *show* `suggested_prompts` as quoted intent
sentences but they were inert. This PR turns each prompt into a
**clickable button** that hands a safe draft to the chat composer
(no auto-send, no tools), AND fixes the pre-existing
`OAuthConnectDrawer.tsx` strict-null TypeScript ghost.

What lands:
1. **OAuth ghost fixed**: `msg.connector` strict-null narrowing via
   a hoisted local. `tsc -b` is now clean (was 1 error since commit
   `3af8601`).
2. **Composer-draft bridge**: a new `composerDraftStore` (Zustand,
   in-memory only) + `composerBridge.ts` write-side helper +
   `daena:composer-draft` CustomEvent. Survives navigation; never
   persisted to localStorage.
3. **ChatPage subscribes** via a useEffect that drains the store on
   mount AND listens to the event. Drafts arrive as `prefillValue`
   on the existing `ChatInput` prop -- the same path
   `/chat?project=<id>` uses today.
4. **Suggested prompts are now buttons** in `PluginDetailDrawer`'s
   "What Daena can do" section. Click composes
   `Use the <plugin> plugin to <prompt>.`, drafts via the bridge,
   closes the drawer, navigates to `/chat`. Fires a toast confirming
   the draft.
5. **Skill chip ready-state copy updated**: the popover for
   callable plugins now redirects to the suggested-prompt path
   ("Use a suggested prompt above (one click drafts it into the
   chat composer) or open chat and ask <plugin> directly.")
   instead of the prior "next PR connects this" copy.
6. **3 new backend tests** (composer-draft template safety): no
   newlines in prompts, max 200 chars, no template metacharacters.

Total backend tests after PR: **509 passed / 1 skipped / 0 failed**
(+3 from this PR; previous baseline 506).
Frontend `tsc -b`: **0 errors** (was 1 pre-existing).
Live Chrome DevTools verified end-to-end: drawer click → composer
filled → no auto-send (session list still "No conversations yet").

---

## Frontend ghosts found / fixed

| Ghost | Status | Fix |
|---|---|---|
| `OAuthConnectDrawer.tsx(98,22)` -- `msg.connector` is `string \| undefined` but `onComplete` expects `string` | **FIXED** | Hoist `msg.connector` into a local variable + early-return on `typeof !== 'string'`. Equality check (`=== start?.provider`) does not narrow undefined out, so the prior `onComplete?.(msg.connector)` failed strict-null. The fix is one-line refactor + comment explaining why. |
| Drawer backdrop click handlers | Audited, OK | All 5 drawers (`PluginDetailDrawer`, `MCPInstallDrawer`, `MCPRestoreDrawer`, `OAuthConnectDrawer`, `MarketplaceCard`) use the same pattern: `fixed inset-0 z-50` outer with `onClick={onClose}`, `onClick={(e) => e.stopPropagation()}` on inner. Consistent. |
| Stale drawer state on re-open | Audited, OK | Each drawer is unmounted by parent (`setDrawerOpen(false)` removes from DOM) and remounts fresh on next click. Internal `useState` is reinitialized. |
| Black overlay after navigation | Audited, OK | The connections page does not retain drawer DOM after navigate; the navigate-to-chat path I added explicitly calls `onClose()` before `navigate('/chat')`. |
| Z-index stuck | Audited, OK | All drawers use `z-50` consistently. ChatPage doesn't introduce any conflicting stack. |

The remaining "ghost" risk is in legacy V1 panels (`PluginsCatalogBrowser`,
`McpServersPanel` etc) hidden behind the Advanced tab. Out of scope
per founder rule 4 ("Do not delete V1 files yet").

---

## How suggested prompts wire to the composer

```
┌──────────────────────────────┐
│ /connections plugin drawer  │
│  [WHAT DAENA CAN DO]         │
│  "Triage the open issues..."│
│  ↓ click                     │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────┐
│ composerBridge.draftFromSuggestedPrompt()    │
│   text = "Use the GitHub plugin to triage   │
│   the open issues in this repo by priority."│
│   ↓                                          │
│ composerDraftStore.setDraft(text, source)   │
│   ↓                                          │
│ window.dispatchEvent(                        │
│   new CustomEvent("daena:composer-draft",   │
│     { detail: { text, source } })           │
│ )                                            │
└────────┬─────────────────────────────────────┘
         │
         ├─── (same-page) → ChatPage event listener fires →
         │                  fills composer
         │
         └─── (cross-page) → onClose() + navigate("/chat") →
                             ChatPage mounts → useEffect drains
                             store → fills composer
```

Hand-off path:
1. **`PluginDetailDrawer.DaenaIntent`** -- each `suggested_prompts[i]`
   is now a `<button>` with hover-revealed "Use in chat →" affordance.
2. **`lib/composerBridge.ts`** -- `draftFromSuggestedPrompt(prompt,
   pluginName, source)` does three things atomically:
   - Builds the safe template `Use the <plugin> plugin to <prompt>.`
     with case-fixed first letter and stripped trailing punctuation.
   - Writes to `composerDraftStore` (in-memory Zustand, never
     persisted to localStorage).
   - Dispatches `daena:composer-draft` on `window` so an already-
     mounted ChatPage picks it up immediately.
3. **`ChatPage`** -- post-mount `useEffect` drains the store ONCE
   (covers cross-page navigation) and registers a window event
   listener (covers same-page draft updates). Drafts feed
   `ChatInput` via the existing `prefillValue` prop, the SAME path
   `/chat?project=<id>` uses today. `onPrefillConsumed` clears
   the buffer + schedules a 5-second lingering "Drafted from
   `<plugin>`" caption above the composer.
4. **`ChatInput`** (unchanged) -- existing `prefillValue` effect
   writes to its internal `value` state when textarea is empty,
   focuses the textarea, calls `onPrefillConsumed` once.

### Why both store AND event?
- **Store** survives the cross-page navigation (most common case).
- **Event** delivers same-tick when ChatPage is already mounted
  (operator returned to /chat without remounting). The event also
  gives ChatPage a single integration point to fan out to future
  listeners (e.g. a "draft" badge on the sidebar) without each new
  consumer having to subscribe to the store directly.

---

## Safety proof: nothing auto-sends or executes

| Hard rule | Where enforced | Evidence |
|---|---|---|
| 8. No auto-install | Bridge does not invoke MCP / npm / docker | `composerBridge.ts` is 100 LOC of string composition + a `setState` + a `dispatchEvent`. No HTTP, no shell, no install. |
| 9. No skill execution | Drafted text is a string | Composer only calls `setValue()`. The user must press Enter / click Send to actually invoke the chat orchestrator. |
| 10. No auto-sent chat | `ChatInput.handleSubmit` requires explicit click/Enter | Verified in live smoke: after the bridge fired, session list still showed "No conversations yet. Start a new chat!" -- the user has not pressed Send. |
| 5. No secrets touched | Bridge composes plain English | No env-var read, no API call, no token storage. The store has no localStorage backing -- closing the tab discards the draft. |
| 7. No external messages | Bridge only writes local state | No fetch, no WebSocket, no postMessage. Only `window.dispatchEvent` to a handler in the SAME tab. |

### Live smoke verification (Chrome DevTools)
- Click GitHub plugin Details → drawer opens with 3 quoted prompts
  + "Use in chat" hover affordance.
- Click "Triage the open issues in this repo by priority." prompt.
- Drawer closes; URL changes to `/chat`.
- Composer textarea contains exactly:
  `Use the GitHub plugin to triage the open issues in this repo by priority.`
- Token estimate `~19 tokens · ~$0.0001` rendered (proof the
  textarea sees the text).
- **Session list shows "No conversations yet. Start a new chat!"**
  -- no message was created. Send button is enabled but has not
  been clicked.

### Skill chip click behavior
- **Locked chip click**: still shows the per-readiness "Connect
  first" / "Install first" / "Re-test" message. No execution.
- **Ready chip click** (when V2 callable=true): popover now reads
  "Skill execution wiring pending. Use a suggested prompt above
  (one click drafts it into the chat composer) or open chat and
  ask `<plugin>` directly." -- redirects the operator to the safe
  draft path. Still no execution.

---

## UI / UX changes

| Change | File | Visual impact |
|---|---|---|
| Suggested-prompt rows are now buttons | `PluginDetailDrawer.tsx` (`DaenaIntent`) | Hover lights cyan border + reveals "Use in chat →" pill. Footer caption updated to "Click any prompt to draft it in the chat composer. Daena does NOT auto-send -- review first, then send when ready. Tool execution still lands in a later PR." |
| Lingering "Drafted from `<plugin>`" hint | `ChatPage.tsx` | Thin cyan caption above composer for ~5s after a plugin draft lands. Pure presentation. |
| Toast on draft hand-off | `ChatPage.tsx` event listener | "Drafted from `<plugin>`" success toast fires when ChatPage receives the draft. |
| Skill chip ready popover redirect | `SkillBundleSection.tsx` | Copy points to the new composer path instead of "next PR". |
| OAuth ghost fixed | `OAuthConnectDrawer.tsx` | None visible; `tsc` is clean. |

No new tabs added. Brain / Plugins / Advanced unchanged. Honeycomb
chip glyph kept subtle. No spiral / sunflower layout introduced.

---

## Tests run

### New backend tests (3)
Added to `backend/tests/test_plugin_skills_ux_wiring.py`:

1. `test_suggested_prompts_are_single_line` -- composer template is
   a one-liner; newlines in prompts would break the textarea.
2. `test_suggested_prompts_are_short_enough_for_composer` -- max
   200 chars; longer prompts trigger ChatInput's long-paste
   collapse heuristic which is meant for *user* paste, not our
   drafts.
3. `test_suggested_prompts_have_no_template_metacharacters` --
   defense-in-depth against `${...}`, `\b`, `$0` style strings
   that could change meaning if the templating ever moves to
   template literals or `.replace(callback)`.

### Regression sweep
```
.venv/Scripts/python.exe -m pytest tests/ -q -k "marketplace or
connection_v2 or probe or provider_key or dynamic_model or
account_provider or plugin_bundle or plugin_skills"
509 passed, 1 skipped, 3953 deselected, 13 warnings in 30.63s
```
Up from 506 in the prior PR. Net +3 from the new tests. Zero
regressions in the 506 prior tests.

### Frontend tsc
```
npx tsc -b → 0 errors
```
Was 1 pre-existing error (`OAuthConnectDrawer.tsx(98,22)`) before
this PR; now clean.

### Live Chrome DevTools smoke
- `/connections` loads (57 plugin cards, status pills, officiality
  badges).
- GitHub drawer opens, suggested-prompt buttons visible with
  hover affordance.
- Click "Triage the open issues..." → drawer closes → navigate to
  `/chat` → composer textarea filled with safe template string.
- Session list still empty → no auto-send.
- No black overlay after drawer close.
- Token estimate renders (textarea sees text).

---

## Remaining blockers for real skill execution

The next PR (`PR-CONN-PLUGIN-SKILLS-EXECUTION`) still needs:

1. **Skill identifier → tool dispatch table**. Each
   `default_skills[i]` snake_case identifier must resolve to:
   - A prompt template (for skill packs / OSS prompts) -- can reuse
     this PR's composer-draft path.
   - An MCP tool invocation (for `mcp_server` plugins) -- new dispatch
     in `chat_orchestrator`.
   - An OAuth-mediated API call (for `oauth_app` plugins) -- per
     plugin auth surface.
2. **Asset Shield consent dialog** for high-risk skills (Cloudflare,
   Stripe, Desktop Commander, Browser tools) before any auto-execute
   path lands.
3. **Per-skill audit log row**. Currently `audit_service` logs
   per-tool-call; needs a parent `skill_invocation` event tying
   N child tool calls back to one operator intent.
4. **Per-plugin governance policy presets**. Each bundle ships a
   recommended `BehaviorGuard` policy at install time.
5. **Live MCP registry sync** so `last_verified_at` actually means
   something.

None of these are blockers for THIS PR -- the UI honestly says
"NOT auto-send -- review first" and "Tool execution still lands in
a later PR" everywhere it surfaces a draft.

---

## Files changed

```
M  frontend/src/pages/connections/OAuthConnectDrawer.tsx     (+11 / -3 ghost fix)
M  frontend/src/pages/connections/PluginDetailDrawer.tsx     (+50 / -10 prompt buttons)
M  frontend/src/pages/connections/SkillBundleSection.tsx     (+5 / -4 ready copy)
M  frontend/src/pages/ChatPage.tsx                            (+70 / -5 store hydration + hint)
A  frontend/src/lib/composerBridge.ts                         (102 lines)
A  frontend/src/stores/composerDraftStore.ts                  (89 lines)
M  backend/tests/test_plugin_skills_ux_wiring.py              (+60 lines, 3 tests)
A  docs/Ultraview/PR_CONN_UI_GHOSTS_AND_PROMPT_WIRING_REPORT.md  (this file)
```

Net: ~+390 lines added, ~-22 removed across 4 src edits + 2 new
src files + 1 test extension + this report.

---

## Hard rules verification

| Rule | Compliance |
|---|---|
| 1. No deploy production | ✅ no Cloud Run touch |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` | ✅ flag unchanged |
| 3. No `vault --apply` | ✅ vault untouched |
| 4. No V1 file deletion | ✅ legacy panels still mounted |
| 5. No secrets printed/grepped/logged/committed | ✅ bridge composes plain English; no env reads |
| 6. No external scans | ✅ no scanner invocations |
| 7. No emails/DMs/webhooks/messages | ✅ bridge only writes local state + dispatches in-tab event |
| 8. No auto-install of npm/pip/docker | ✅ bridge does not invoke installers |
| 9. No skill execution from this PR | ✅ chip click → tooltip; prompt click → composer fill |
| 10. No auto-sent chat | ✅ verified in live smoke (session list empty post-draft) |
| 11. No new primary tabs | ✅ Brain/Plugins/Advanced unchanged |
| 12. No heavy sunflower dashboard | ✅ no layout changes; subtle hint caption only |
| 13. No falsely-callable status | ✅ `skillReadiness()` still gates chip lock state |

Stop and report.
