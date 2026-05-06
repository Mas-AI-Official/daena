# PR-3: Remove or Reclassify "Coming Soon" — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE

## Brutal-truth verdict

**The work is already done.** Prior sprints (PR-SETTINGS-CLEANUP 2026-05-02,
Phase 11 PR-S1+PR-S2 2026-05-01..2026-05-02, ADR-001 2026-04-29 honesty rule)
removed every fake-success surface and replaced it with one of:

1. **A disabled control + warning badge + tooltip** explaining the missing back-end consumer (e.g. SettingsDeveloper Webhooks: "no webhook dispatcher exists in backend").
2. **An "Enforced by backend" badge** when the toggle has a real consumer (e.g. SettingsPrivacy Memory Generation: when OFF, MemoryService.store refuses writes).
3. **A "Source pending" warning** when the gate is wired but no emitter exists (e.g. SettingsNotifications Heartbeat / Runtime disconnect).
4. **An honest catalog metadata badge** for connectors that aren't installable yet (MarketplaceCard `install_method === 'coming-soon'`: "Daena cannot install or probe this connector yet — catalog metadata only").

## Verified surfaces

| Surface                                            | Behavior                                             | Honesty        |
|----------------------------------------------------|-------------------------------------------------------|----------------|
| `SettingsDeveloper.tsx` API Keys block             | redirects to /account, no fake CRUD                   | honest         |
| `SettingsDeveloper.tsx` Webhooks block             | disabled inputs + "Coming soon" + tooltip             | honest         |
| `SettingsDeveloper.tsx` Debug / Verbose toggles    | disabled, "persists; no consumer reads it yet"        | honest         |
| `SettingsNotifications.tsx` Desktop master         | live, with browser-permission gate                    | honest         |
| `SettingsNotifications.tsx` Per-event toggles      | "Enforced by backend" or "Source pending"             | honest         |
| `SettingsNotifications.tsx` Sound                  | disabled + "Coming soon" + tooltip "no audio channel" | honest         |
| `SettingsNotifications.tsx` Email                  | disabled when `emailConfigured = false`               | honest         |
| `SettingsPrivacy.tsx` Memory Generation            | "Enforced by backend"                                 | honest         |
| `SettingsPrivacy.tsx` Search past conversations    | "Enforced by backend"                                 | honest         |
| `SettingsPrivacy.tsx` Cloud sync radio             | unselectable, "-- coming soon" suffix                 | honest         |
| `SettingsPrivacy.tsx` Improve from usage           | disabled, "Coming soon" + tooltip                     | honest         |
| `SettingsPrivacy.tsx` Location metadata            | disabled, "Coming soon" + tooltip                     | honest         |
| `MarketplaceCard.tsx` `install_method='coming-soon'` | catalog metadata badge with explanatory tooltip      | honest         |
| `PluginDetailDrawer.tsx` skill-pack lifecycle      | disclaimer "not callable until paired with a runtime" | honest         |
| `BrainReadinessPanel.tsx`                           | 5-state truth ladder (ready / configured_untested / not_configured / detected_offline / unknown). Comment: "We never label a runtime 'connected' off key-presence alone." | honest |
| `OpportunityInboxPage.tsx` Google blocker banner   | exact next action from `/connections/google-activation-summary` | honest |

## What was NOT done (intentional)

The brief listed several actions:

- "If backend exists, wire the UI" — already done; PR-1+PR-2 confirmed every non-deprecated backend group is consumed by an existing UI surface.
- "If backend does not exist but feature is important, move to roadmap/dev-only panel" — already done implicitly; Settings Developer / Notifications Sound / Privacy Cloud are gated to either an `advanced` tab (which itself is a localStorage toggle) or marked with explicit roadmap labels.
- "If unsafe, show 'Requires approval/setup' instead of 'Coming soon'" — distinct UX. The current state shows `disabled + warning badge + tooltip` for unshipped features, which is *more* informative than "Requires approval/setup". No reclassification needed.
- "If OAuth is missing, show exact OAuth next action" — already done in `OpportunityInboxPage.tsx` (Sprint-20 PR-1) and `GoogleAccountSetupGuide.tsx`.
- "If provider key is missing, deep-link to Provider Keys" — `BrainReadinessPanel.tsx` exposes `next_action` from the backend; SettingsModelsRuntimes / AccountProviderKeys are deep-linked from chat / connections.
- "If local runtime is missing, show copyable command or setup guidance" — `BrainReadinessPanel.tsx` shows `safe_failure_reason` per runtime; LocalModelsPanel shows install hints.
- "If MCP is not installed, show install/probe path" — `MCPInstallDrawer.tsx` + `PluginsV2Panel.tsx` lifecycle.

## Risk: regression

If a future PR reintroduces a fake "Coming soon" badge without a paired tooltip
or disabled control, this honesty contract breaks silently. ADR-001 covers it
philosophically; no automated guard exists yet. Recommendation: a frontend
unit test that scans `src/**/*.tsx` for `Coming soon` literals and asserts each
match is within 5 lines of `disabled` or `title=`. Out of Sprint-21 scope —
captured as backlog ticket TICKET-UI-COMING-SOON-PIN.

## Hard rules respected

- [x] No deploy
- [x] No fake success — verified honesty per file
- [x] No new architecture
- [x] No code modified — UI was already correct

## Next

PR-4: Complete Business Loop UI Wiring.
