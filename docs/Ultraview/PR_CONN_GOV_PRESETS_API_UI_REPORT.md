# PR-CONN-GOV-PRESETS-API-UI -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-5 (PR-5 of 6)

---

## 1. Goal

Expose the Sprint-4 PR-5 plugin governance presets through:

* A read-only HTTP route returning `list_presets_for_api()` directly
* Drawer-side badges in `PluginDetailDrawer` showing the
  vendor-recommended ALLOW / ASK / DENY tier per skill class

The preset table existed but was DORMANT (only test code consumed it).
This PR makes the operator see what the vendor recommends without
ever changing enforcement: the consent gate + read_only defense
remain the actual layers.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Metadata only | YES -- the route is a passthrough of `list_presets_for_api()`; no per-tenant overlay; explicit "Metadata only -- enforcement still runs through the consent gate + Phase 2 read_only defense" copy in the drawer |
| Do not change enforcement | YES -- Phase 2 / consent gate untouched. Tests still confirm consent does not unlock writes |
| Show ALLOW / ASK / DENY baseline | YES -- per skill class with color-coded badges (emerald / amber / rose) |
| High-risk plugins show warning copy | YES -- when any tier in the preset is `deny`, the drawer renders a "High-risk plugin: at least one skill class is recommended DENY by default" rose banner |
| No new primary tabs | YES -- new section lives inside the existing `PluginDetailDrawer` between Permissions and Provider key deep-link |

---

## 3. Surface area

### Backend

#### `backend/app/api/v1/plugin_governance_presets_api.py` (NEW)

* `GET /api/v1/connections/v2/governance/plugin-presets`
  * Auth-required.
  * Returns `{data: {presets: [...]}}` -- direct passthrough of the
    Sprint-4 PR-5 `list_presets_for_api()`.
  * Includes the DEFAULT fallback marker as the last entry.
* No POST / PUT / DELETE -- presets are vendor opinion, edited only
  by code change for now (per-tenant overrides are a follow-up PR).

#### `backend/app/api/v1/__init__.py`

* New router import + mount at `/connections/v2/governance`.

### Frontend

#### `frontend/src/pages/connections/PluginDetailDrawer.tsx`

* New "Governance recommendations" section between Permissions and
  Provider key deep-link.
* `GovernancePresetsBlock(pluginId)`:
  * Lazy-loads `/v2/governance/plugin-presets` once per session
    (module-level cache + in-flight promise dedup).
  * Renders the matching preset's rationale + per-class badges
    using the founder's color palette (`emerald` / `amber` / `rose`
    for ALLOW / ASK / DENY).
  * Shows a rose warning banner when any class is recommended DENY
    so the operator can't miss "high-risk plugin".
  * Falls back to the DEFAULT_PRESET's "no specific recommendation"
    copy for unknown plugins.
  * Footer notice: "Metadata only -- enforcement still runs through
    the consent gate + Phase 2 read_only defense" so the operator
    never confuses a recommendation with enforcement.

### Tests

#### `backend/tests/test_plugin_governance_presets_api.py` (NEW, 5 tests)

1. **Auth required (1)**: anonymous -> 401/403.
2. **Full table + fallback marker (1)**: 8 founder + 1 DEFAULT = 9
   entries; `_is_fallback=true` exactly once.
3. **Founder coverage (1)**: all 8 plugins (mcp-filesystem,
   mcp-github, app-gmail, app-google-drive, mcp-slack, mcp-stripe,
   mcp-playwright, mcp-chrome-devtools) present.
4. **Conservative defaults preserved (1)**: Stripe PAYMENT=DENY,
   Filesystem WRITE=DENY, Gmail SEND=DENY, GitHub READ=ALLOW.
5. **No token leak in payload (1)**: defense-in-depth substring
   check against access_token / refresh_token / Bearer /
   client_secret / vault / credentials.

#### Frontend type-check

`npx tsc --noEmit` -> `EXIT=0`.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_plugin_governance_presets_api.py -q
5 passed in 4.17s

$ .venv/Scripts/python.exe -m pytest <full sprint scope> -q
221 passed in 27.12s
```

Test growth Sprint-5 PR-5:
* End of PR-4: 216 in scope
* PR-5 adds: 5 new preset-API tests = **221 in scope**

---

## 5. What did NOT change

* No allowlist entry modified.
* No executor enforcement change.
* No new primary tab.
* The consent gate + read_only defense + OAuth invoker + account
  picker + Phase 2 floor -- all unchanged.
* Phase 3 writes -- still impossible.

---

## 6. Follow-up PRs

1. **`PR-CONN-PER-TENANT-POLICY-OVERRIDES`** (future): DB-backed
   override of the baseline. Operator's policy editor writes here;
   reads fall back to the baseline. The drawer should prefer the
   override when present.
2. **`PR-CONN-GOV-PRESETS-IN-APPROVAL-QUEUE`** (future): the
   approval queue should render the preset tier as a sidecar
   "vendor recommends X" pill so reviewers see the recommended
   action without leaving the queue.
3. **`PR-LOCAL-USABILITY-SPRINT5-SMOKE` (Sprint-5 PR-6)** -- the
   final smoke status across all 5 PRs of this sprint.
