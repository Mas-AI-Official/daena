# PR-CONN-PER-PLUGIN-GOV-PRESETS -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-4 (PR-5 of 6)

---

## 1. Goal

Static metadata table mapping `(plugin_id, skill_class)` -> default
governance tier (`ALLOW` / `ASK` / `DENY`). Pure metadata --
**no enforcement change** vs. Sprint-4 PR-3 + PR-4 floor. The
table will be consumed by:

* The future approval-queue UI to render the right "ask / allow /
  deny" badge on each pending request.
* The future per-tenant policy editor as a starting baseline
  (operator can override; baseline lives here).
* External integrations / docs that want to show vendor-recommended
  governance posture per plugin.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Metadata only or enforcement only if safe | YES -- metadata only. Phase 2 read_only defense + consent gate (PR-4) remain the actual floors |
| Do not enable writes | YES -- presets cannot make a write skill executable; they can only RECOMMEND tiers. Today's read_only=True universe still applies |
| Do not change global governance mode | YES -- no policy rule modified |
| No new primary tabs | YES -- presets are a backend artifact; future UI consumes via API in a follow-up PR |

---

## 3. Surface area

### `backend/app/services/connection_v2/plugin_governance_presets.py` (NEW)

* `GovernanceTier` enum: ALLOW / ASK / DENY
* `SkillClass` enum: READ / READ_SENSITIVE / WRITE_EXTERNAL /
  SEND_MESSAGE / PAYMENT / BROWSER_ACTION / SECURITY_SCAN
* `_CONSENT_TO_CLASS` mapping: bridges the consent gate's
  `SkillConsentCategory` (PR-4) to this PR's `SkillClass` so
  classification stays consistent across modules
* `PluginGovernancePreset` dataclass: per-plugin (plugin_id,
  rationale, tiers dict)
* `PLUGIN_PRESETS` table covering the founder's full example list:
  - **mcp-filesystem**: READ=ASK, WRITE_EXTERNAL=DENY
  - **mcp-github**: READ=ALLOW, WRITE_EXTERNAL=ASK
  - **app-gmail**: READ=ALLOW, READ_SENSITIVE=ASK,
    SEND_MESSAGE=DENY
  - **app-google-drive**: READ=ALLOW, READ_SENSITIVE=ASK,
    WRITE_EXTERNAL=ASK
  - **mcp-slack**: READ=ALLOW, SEND_MESSAGE=ASK
  - **mcp-stripe**: READ_SENSITIVE=ASK, PAYMENT=DENY
  - **mcp-playwright**: BROWSER_ACTION=ASK
  - **mcp-chrome-devtools**: BROWSER_ACTION=ASK
* `DEFAULT_PRESET` fallback: READ=ALLOW, anything else defaults to
  ASK via `tier_for` (conservative for unknown plugins)
* `get_preset(plugin_id)` -> preset or DEFAULT
* `classify_skill(entry)` -> SkillClass (composes
  `skill_consent.categorize_skill`)
* `recommended_tier(entry)` -> GovernanceTier (composes get_preset
  + classify_skill)
* `list_presets_for_api()` -> JSON-safe list for future endpoint

### `backend/tests/test_plugin_governance_presets.py` (NEW)

25 tests across 8 logical sections:

1. **Schema validity (3)**: every preset uses valid enums, no duplicate
   plugin_id
2. **Founder coverage (1)**: all 8 founder-listed plugins have entries
3. **Conservative defaults (4)**: Stripe PAYMENT=DENY, Filesystem
   WRITE=DENY, Gmail SEND=DENY, unspecified->ASK
4. **Permissive reads (5 parametrized + 1)**: GitHub/Gmail/Drive/Slack
   READ=ALLOW; Filesystem READ=ASK explicitly
5. **classify_skill mapping (3)**: read_only=True->READ; Stripe
   write->PAYMENT; unknown write->WRITE_EXTERNAL
6. **recommended_tier composition (4)**: filesystem read=ASK;
   github read=ALLOW; stripe payment=DENY; unknown plugin falls
   through to DEFAULT
7. **JSON serialization (2)**: dict shape + json.dumps round-trip
8. **Foundation invariant (3)**: every Phase 2 entry classifies as
   READ; every Phase 2 entry's recommended_tier is ALLOW or ASK
   (NEVER DENY -- Phase 2 floor stays usable); every
   SkillConsentCategory has a SkillClass mapping (no silent drift)

---

## 4. What ships, what doesn't

### Ships

* The static preset table.
* The classify + recommend helpers.
* JSON-safe serializer for future API.
* 25 tests pinning the contract.

### Does NOT ship

* No HTTP endpoint (`GET /v2/governance/plugin-presets` is a
  follow-up PR after the UI design lands).
* No frontend rendering of preset badges (consumes the future API).
* No per-tenant policy override storage (separate PR; this module
  only ships the BASELINE).
* No executor enforcement change. The presets do NOT block anything
  the consent gate + read_only defense don't already block.

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_plugin_governance_presets.py
25 passed in 0.09s

$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py \
                                     tests/test_oauth_invoker.py \
                                     tests/test_skill_executor_oauth_wireup.py \
                                     tests/test_oauth_account_profiles.py \
                                     tests/test_skill_consent.py \
                                     tests/test_plugin_governance_presets.py
162 passed in 5.81s
```

Test growth Sprint-4 PR-5:
* End of PR-4: 64 phase2 + 21 oauth_invoker + 13 wireup + 12
  account_profiles + 24 consent = 134 (+3 net retargeted in PR-2 = 137)
* PR-5 adds: 25 new presets = **162 in scope**

---

## 6. What did NOT change

* No allowlist entry modified.
* No executor branch added.
* No runtime behavior change for any current Phase 2 call.
* No new dependencies, no install, no production deploy.
* No vault, no V2 flag, no secret read.
* The Phase 2 read_only defense and the Sprint-4 PR-4 consent gate
  remain the only enforcement layers. Presets are advisory.

---

## 7. Follow-up PRs

1. **`PR-CONN-GOV-PRESETS-API`** -- HTTP endpoint:
   `GET /v2/governance/plugin-presets`. Returns
   `list_presets_for_api()` dict.
2. **`PR-CONN-GOV-PRESETS-UI`** -- drawer + approval-queue badge:
   "vendor recommends ASK" / "vendor recommends DENY" pills.
3. **`PR-CONN-PER-TENANT-POLICY-OVERRIDES`** -- DB-backed per-tenant
   override of the baseline. Operator's policy editor writes here;
   reads fall back to the baseline if no override.
