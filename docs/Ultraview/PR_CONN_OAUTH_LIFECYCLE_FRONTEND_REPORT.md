# PR-CONN-OAUTH-LIFECYCLE-FRONTEND — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** _to be filled in after squash_
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-2 (PR-1 of 4)

---

## 1. Goal

Wire the three backend endpoints shipped in `PR-CONN-OAUTH-REFRESH-DISCONNECT`
(`da23dd7`) into the Connections UI so an operator can refresh /
disconnect / archive an OAuth-backed connection without curl.

---

## 2. Hard rules — all honored

| Rule | Enforced? |
|---|---|
| Disconnect + Archive require confirmation modal | YES — explicit operator click + backend `confirm: true` body (two-layer defense) |
| Refresh must not expose tokens | YES — response carries only `success`/`expires_at`/`reason`; component never renders or stores token values |
| No external message sending | YES — only refresh + revoke endpoints (RFC-7009 control plane) |
| No secret values in UI/logs | YES — toast messages quote outcome reasons + (refresh-only) the new `expires_at`, never tokens |
| Reuse backend endpoints | YES — calls `/instances/{id}/refresh-token`, `/instances/{id}/disconnect`, `/instances/{id}/archive` from PR-3 |
| Run frontend tsc | YES — `npx tsc --noEmit` clean (zero output) |
| Run targeted backend tests | YES — `pytest test_connections.py test_skill_executor_phase2.py` 76/76 pass |

---

## 3. Files changed

### `frontend/src/pages/connections/OAuthLifecyclePanel.tsx` (NEW, 270 lines)

Standalone React component that:

1. **Visibility gate** — renders nothing unless `plugin.auth_type === 'oauth'` AND `plugin.id` maps to one of the 7 OAuth providers (gmail, google-calendar, google-drive, github, figma, slack, canva).
2. **Instance lookup** — on mount, GETs `/connections/instances` and finds the CONNECTED instance whose `connector_id` matches the resolved provider key. The list endpoint already excludes ARCHIVED rows by default (PR-da23dd7), so a hit means "currently connected, refreshable".
3. **No-instance branch** — if no CONNECTED instance is found, returns `null` (no buttons shown). Avoids implying there's something to manage when there isn't.
4. **Three buttons:**
   - **Refresh token** — single click, calls `POST /refresh-token`, shows toast with new `expires_at` on success or `reason` on failure
   - **Disconnect** — opens `ConfirmDialog` modal with consequence copy explaining provider revoke is best-effort + local creds will clear
   - **Archive** — opens `ConfirmDialog` modal with consequence copy explaining archive is hidden-but-preserved
5. **`ConfirmDialog`** — same UX shape as `SkillExecuteModal`. Cancel button + verb button (color-coded: amber for Disconnect, neutral for Archive).
6. **State refresh** — after successful disconnect/archive, refetches instance list. Since the row is no longer CONNECTED, the panel hides itself.

### `frontend/src/pages/connections/PluginDetailDrawer.tsx`

- Added import: `OAuthLifecyclePanel`
- Slotted `<OAuthLifecyclePanel plugin={plugin} />` immediately after the `Skills` section. The component handles its own visibility gating, so no parent-side conditional needed.

---

## 4. Plugin-id → provider mapping (defensive)

```typescript
function pluginIdToProviderKey(pluginId: string): string | null {
  const stripped = pluginId.replace(/^(app|mcp)-/, '')
  const allowed = new Set([
    'gmail', 'google-calendar', 'google-drive',
    'github', 'figma', 'slack', 'canva',
  ])
  return allowed.has(stripped) ? stripped : null
}
```

Explicit allowlist keeps the panel from surfacing on arbitrary `app-*` plugins. If a future plugin is added without an OAuth provider entry, the panel correctly returns `null` instead of trying to refresh a non-existent instance.

---

## 5. Honesty + persistence guarantees (project Rule 17)

Per the codebase's honesty rule (`CLAUDE.md` rule 17, locked 2026-04-29):

- **No silent error suppression**: refresh failures call `toast.error(reason)`; instance-load failures hide the panel rather than show a fake state.
- **No advertised real-time without backing**: refresh button shows a spinner during the call; on success, displays the actual `expires_at` returned by the backend (proves the action persisted).
- **No fake success**: if the backend returns `{success: false, reason: "no_refresh_token"}`, the panel surfaces that reason in a toast — no green checkmark on a no-op.
- **Confirmation gate is genuinely two-layer**: even if a future bug skipped the modal, the backend rejects unconfirmed disconnect/archive with HTTP 400 + `code: confirmation_required`.

---

## 6. Test result

```
$ npx tsc --noEmit
(no output -- clean)

$ .venv/Scripts/python.exe -m pytest tests/test_connections.py tests/test_skill_executor_phase2.py
76 passed in 29.07s
```

No new backend tests (this PR is frontend-only). The PR-3 backend tests already cover the contract this UI calls.

---

## 7. Manual smoke (deferred to operator with real OAuth instance)

The component compiles + types-cleanly + the backend it calls is fully test-covered. Live UI verification requires:
1. An OAuth provider configured (Account → OAuth Client Config; from `1da1eae`)
2. A completed OAuth flow that wrote a CONNECTED ConnectorInstance row
3. Open `/connections` → click the OAuth-backed plugin card → see the new "OAuth lifecycle" panel below "Skills"
4. Click Refresh → see toast with new expires_at
5. Click Disconnect → see modal → click Disconnect again → see "Local credentials cleared" toast → panel hides itself

Operator verification covers the visual rendering + confirmation UX the test suite cannot.

---

## 8. What did NOT change

- No backend changes (all 3 endpoints already shipped in `da23dd7`)
- No production deploy
- No `USE_CONNECTION_REGISTRY_V2` flip
- No `vault --apply`
- No npm/pip/docker install
- No browser automation
- No external messaging (revoke is OAuth control plane)
- No secret read/print/grep/log/commit
- The existing `OAuthConnectDrawer` (the Connect flow) is unchanged — this PR adds the post-connection lifecycle controls only

---

## 9. Branch state after PR

```
<this commit>  fix: wire OAuth lifecycle actions into Connections UI
a4cfc61        docs: finalize sprint log with PR-4 row + sprint summary
c0906cd        docs: add local production smoke checklist
46b55f8        docs: pin PR-3 commit hash and update sprint log
da23dd7        fix: add OAuth refresh and disconnect for plugin cards
```

Sprint-2 state: PR-1 SHIPPED. Continuing autopilot to PR-2 (MCP install operator guide).
