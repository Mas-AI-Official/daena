# PR-CONN-PROVIDER-KEY-VISIBILITY -- Surface provider key truth in connections marketplace

**Date:** 2026-05-03
**Branch:** rebuild-connections-mcp-runtime
**Base commit:** cf47244 (parity repair)
**Status:** ✅ Shipped + live-verified

---

## Founder complaint (the bug this PR fixes)

API provider cards in /connections appeared as useless "Setup guide" buttons
even when Daena's own settings already had `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `GEMINI_API_KEY`, etc. pasted in. The card UI had no idea
whether the credential was present, so every provider rendered identically as
"Available - click Setup guide" with no path to "Test" or "Connected" without
the operator first running discovery and then a probe.

The marketplace was lying by omission: the truth ladder existed in the
backend (`ModelRegistry.is_configured(provider)`) but was never threaded into
the marketplace card payload.

---

## Surgical changes (5 files)

### 1. `backend/app/services/connection_v2/marketplace_service.py` (+57 lines)

* Added `MarketplaceCard.provider_key_present: bool | None` field.
  Tri-state: `True` when the settings attribute holds a non-empty value,
  `False` when empty/unset, `None` for kinds that do not use a settings
  credential (oauth_app, mcp_server, browser_tool, computer_use, cli_runtime,
  skill_pack -- their truth lives in the V2 probe).

* Added `_PROVIDER_KEY_BY_ENTRY_ID` map (catalog id -> settings attribute):
  ```
  provider-anthropic     -> anthropic_api_key
  provider-openai        -> openai_api_key
  provider-google-gemini -> gemini_api_key
  provider-perplexity    -> perplexity_api_key
  provider-groq          -> groq_api_key
  provider-openrouter    -> openrouter_api_key
  provider-together      -> together_api_key
  local-ollama           -> ollama_base_url   (with OLLAMA_ENABLED guard)
  local-vllm             -> vllm_base_url
  ```

* Added `_resolve_provider_key_present(entry)`. Reads the bool by
  `getattr(settings, attr, "")` -- the credential value is NEVER read
  beyond `bool(value)`. The bit is the only thing that leaves the module.

* Special case for Ollama: even with a default `ollama_base_url`,
  `OLLAMA_ENABLED=false` reports `key_present=False` so the marketplace
  doesn't fake-green an endpoint Daena's own model_registry refuses to
  register.

* Extended `_derive_lifecycle(entry, row, *, provider_key_present=None)`:
  * `provider_key_present is True` and no V2 row -> bump
    `lifecycle="configured"`, `primary_action="test"`, label `"Test"`.
  * `provider_key_present is False` and `entry.kind == "api_provider"` ->
    `primary_action="configure"`, label `"Configure"`. Only api_provider
    routes here -- local_model entries need an env var, not a paste-in
    key, so they keep the Setup Guide path with env-var instructions.

* Wired `_resolve_provider_key_present` into `MarketplaceService.list_cards`
  and threaded the value into `_derive_lifecycle`.

### 2. `frontend/src/hooks/useMarketplace.ts` (+13 lines)

* Added `'configure'` to the `PrimaryAction` union.
* Added `provider_key_present: boolean | null` field to the
  `MarketplaceCard` interface with a docblock pinning the tri-state
  contract and the leak-safety guarantee.

### 3. `frontend/src/pages/connections/pluginCard.ts` (+27 lines)

* New `deriveAction` branch: when `entry.kind === 'api_provider'` and
  `card.provider_key_present === false`, return `{ action: 'configure',
  enabled: true }` (was `'setup_guide'`).
* New guards in the `'needs_auth'` and `'installed'` branches: when an
  api_provider / local_model card has `provider_key_present === true`,
  return `'test'` instead of `'configure'`. This was the missing piece
  -- without it, the lifecycle="configured" backend bump was being
  re-collapsed by the adapter's `auth_type==='api_key' -> 'configure'`
  fallthrough, defeating the point of the lifecycle bump.

### 4. `backend/tests/test_provider_key_visibility.py` (NEW, 251 lines, 13 tests)

* `test_card_dict_carries_provider_key_present_bool_only` -- shape contract
* `test_card_dict_never_contains_secret_substrings` -- defense in depth
* `test_resolve_returns_bool_for_credentialed_kinds[9 entries]` -- parametric
* `test_resolve_returns_none_for_non_credentialed_kinds[5 entries]` --
  parametric guard against accidentally False-ing OAuth / CLI / MCP cards
* `test_resolve_returns_false_for_empty_setting` -- empty-string handling
* `test_resolve_ollama_respects_disabled_flag` -- pins the OLLAMA_ENABLED
  special case so a future PR doesn't silently revert it
* `test_lifecycle_promotes_to_configured_when_key_present_no_v2_row` --
  the core lifecycle bump
* `test_lifecycle_uses_configure_action_when_key_missing` -- new vocabulary
* `test_lifecycle_keeps_local_model_on_setup_guide_when_key_missing` -- the
  api_provider/local_model split
* `test_lifecycle_falls_back_to_setup_guide_when_key_state_unknown` --
  legacy path still works for non-credentialed kinds
* `test_lifecycle_coming_soon_beats_provider_key_present` -- coming-soon
  catalog state still wins
* `test_every_provider_key_map_id_exists_in_catalog` -- map/catalog drift
* `test_every_api_provider_in_catalog_has_a_key_mapping` -- inverse drift
  (catch a future api_provider that lands without a mapping)

### 5. `backend/tests/test_connection_v2_marketplace.py` (1 test updated)

* `test_no_v2_row_yields_available_lifecycle` updated to allow the new
  `"configured"` lifecycle and `("setup_guide", "configure", "test")`
  action vocabulary, plus a tri-state shape assertion on
  `provider_key_present`. Comment cites this PR by name.

---

## Hard-rule compliance

| Rule | Status |
|---|---|
| No production deploy | ✅ never invoked |
| Don't flip USE_CONNECTION_REGISTRY_V2 | ✅ untouched |
| Don't run vault --apply | ✅ never invoked |
| Don't delete V1 | ✅ V1 paths untouched |
| Don't print/grep/commit secrets | ✅ never read key VALUES; only `bool(getattr(...))` |
| Don't run external scans | ✅ none |
| Don't send emails/DMs/webhooks | ✅ none |
| Don't add new primary tabs | ✅ no new tabs (Brain / Plugins / Advanced unchanged) |
| Don't mark connected/callable without probe truth | ✅ key_present=True only bumps to "configured" + Test, never to "callable" or "connected" |

---

## Live smoke (browser-verified)

Ran via Chrome DevTools MCP against http://localhost:5173/connections after
the backend restart that picked up the new module. Reading
`/api/v1/connections/v2/marketplace/cards` and the on-page button labels.

| Card | Backing | Key state | Backend lifecycle | Backend action | Live UI button |
|---|---|---|---|---|---|
| Anthropic API | api_provider | absent | `available` | `configure` | **Configure** ✅ |
| OpenAI API | api_provider | absent | `available` | `configure` | **Configure** ✅ |
| OpenRouter | api_provider | absent | `available` | `configure` | **Configure** ✅ |
| Together AI | api_provider | absent | `available` | `configure` | **Configure** ✅ |
| Google Gemini API | api_provider | present | `configured` | `test` | **Test** ✅ |
| Perplexity API | api_provider | present | `configured` | `test` | **Test** ✅ |
| Groq API | api_provider | present | `configured` | `test` | **Test** ✅ |
| Ollama | local_model | OLLAMA_ENABLED=false | `available` | `setup_guide` | **Setup guide** ✅ |
| vLLM / llama-server | local_model | URL set | `configured` | `test` | **Test** ✅ |
| Gemini CLI | cli_runtime | n/a | `available` | `setup_guide` | **Setup guide** ✅ |

Click test: clicking **Configure** on Anthropic API navigates to
`/account/api-keys` (the existing API key surface), exactly as the brief
specified.

---

## Test results

**Backend** (relevant suites):
* `tests/test_provider_key_visibility.py` -- 25 passed
* `tests/test_marketplace_parity_repair.py` -- 6 passed
* `tests/test_connection_v2_marketplace.py` -- 93 passed
* **Total: 124 passed in 7.42s**

Wider regression: `pytest tests/ -k "marketplace or connection_v2 or probe or
provider_key"` -- **370 passed, 1 skipped, 0 failed in 25.73s**.

**Frontend**:
* `tsc -b` exits 0 with one pre-existing warning in
  `OAuthConnectDrawer.tsx:98` (unrelated to this PR; file untouched).

---

## What this PR does NOT do (scope discipline)

* Does NOT add an in-product surface for entering provider API keys --
  the deep-link to `/account/api-keys` is the existing UX. Surfacing the
  per-provider env-var entry inside that page is a follow-up
  (PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT, deferred).
* Does NOT change anything for cli_runtime, oauth_app, mcp_server,
  browser_tool, computer_use, skill_pack -- their truth still flows
  through their respective probes / OAuth tokens / discovery.
* Does NOT alter the discovery flow, V2 row creation, or vault wiring.
* Does NOT add a real probe call when key_present=true -- the lifecycle
  bump is "I know the credential is present, the next click triggers
  the test." The bump is honest because failing the probe will move the
  card to lifecycle="failed" with a real `_failure_reason`.

---

## Deferred follow-ups (each gated on founder authorization)

* **PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT** -- /account/api-keys today
  manages Daena's outbound `dna_` keys; extend it (or split into a
  sibling tab) so the operator can paste provider keys without editing
  `.env` directly.
* **PR-CONN-LOCAL-MODEL-PROBE** -- register a real http_get probe for
  local-vllm / local-ollama so the Test button's outcome is recorded as
  V2 truth instead of falling back to NoopProbe.
* **PR-CONN-AUTO-PROBE-ON-KEY-CHANGE** -- when the operator pastes a
  new provider key, kick off a discovery + first probe so the card moves
  from `configured` to `callable` automatically.
* **PR-CONN-PROVIDER-KEY-AGE** -- surface "key set 3 days ago" or
  "rotated 2 weeks ago" so the operator can spot stale keys (would
  require a settings-mtime read; never the value).

---

## Author note

The operator-side win here is small in line count but large in cognitive
load: previously every provider card screamed "Setup guide" regardless of
whether the operator had already configured it. Now the card honestly
mirrors what `ModelRegistry.is_configured(provider)` already knew. Three
providers in this dev environment (Gemini / Perplexity / Groq) light up
green-ready immediately, four (Anthropic / OpenAI / OpenRouter / Together)
explicitly say "you need to configure me," and the local stack
correctly distinguishes vLLM (URL-configured, ready to test) from Ollama
(disabled by env, setup-guide).

The PR uses the existing tri-state pattern from the V2 truth dimensions
(`{value, at, failure_at}`), keeping the contract consistent across the
codebase. Tests pin every edge case I could think of, including the two
drift sentinels that catch a future PR landing a new api_provider entry
without a key mapping (or removing one mapping that other code relies on).
