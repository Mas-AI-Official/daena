# PR-CONN-PROVIDER-KEY-INPUT-IN-ACCOUNT -- Make Configure actually useful

**Date:** 2026-05-03
**Branch:** rebuild-connections-mcp-runtime
**Base commit:** f53a386 (provider key visibility)
**Status:** Shipped + live-verified

---

## Founder intent recap

> Provider card says Configure -> user pastes API key safely -> key is stored
> securely -> card refreshes to Test -> Test runs provider probe -> Connected
> only if probe succeeds.

Before this PR, clicking **Configure** on the Anthropic / OpenAI / etc. cards
deep-linked to `/account/api-keys` (Daena's outbound `dna_` key surface) which
had no place to paste a provider key. The deep-link was a dead end.

---

## Storage path used

**Mechanism: file-backed JSON override store, mirrored on
`oauth_credentials_store.py`'s proven pattern.**

* **New file:** `backend/.daena_provider_overrides.json` (gitignored, chmod
  0o600 on POSIX, atomic temp+rename writes, asyncio.Lock-guarded, in-process
  cache).
* **Why a sibling, not extending `oauth_credentials_store.py`:**
  1. CLAUDE.md Rule 18 marks `oauth_credentials_store.py` as a protected
     file (consolidating without explicit DELETE-PR is forbidden).
  2. OAuth client credentials and provider API keys have different
     lifecycles -- mixing them complicates audit + future migration.
* **Schema:** `{settings_field: {"value": str, "updated_at": iso8601}}`. Legacy
  flat-string format auto-migrated on read.
* **Hydration on startup:** `provider_keys_store.hydrate_settings(settings)`
  is called in `main.py` BEFORE `ModelRegistry.initialize()`, so the registry
  sees stored keys naturally and registers providers without a separate
  bootstrap step. Override values WIN over `.env` baseline values.
* **Asset Shield egress fingerprint:** every save calls
  `vault_adapter.register_fingerprint(asset_class="api_keys")` so the egress
  filter can scan outbound bytes for accidental leaks. The raw value never
  leaves this process; only a 16-char SHA-256 prefix is registered.
* **Future migration:** the docstring + `Secret` model (Phase 4a-2) point to
  `vault_v2.encrypt_secret` as the post-multi-tenant target. This PR
  intentionally does NOT advance that landing -- it stays inside the
  founder's hard rule "Do not run vault --apply".

---

## Providers supported (7)

| Slug | Settings field | Display | Marketplace catalog id |
|---|---|---|---|
| `anthropic` | `anthropic_api_key` | Anthropic | `provider-anthropic` |
| `openai` | `openai_api_key` | OpenAI | `provider-openai` |
| `gemini` | `gemini_api_key` | Google Gemini | `provider-google-gemini` |
| `groq` | `groq_api_key` | Groq | `provider-groq` |
| `perplexity` | `perplexity_api_key` | Perplexity | `provider-perplexity` |
| `openrouter` | `openrouter_api_key` | OpenRouter | `provider-openrouter` |
| `together` | `together_api_key` | Together | `provider-together` |

The `gemini` slug maps to `google_gemini` for `DynamicModelService` (its
naming convention). Map lives in `_slug_to_provider_name` in
`account_provider_keys.py` so neither side has to know about the other.

Local-LLM endpoints (`local-ollama`, `local-vllm`) are intentionally OUT of
scope -- their config is an env var URL, not a paste-in key, and the
marketplace already keeps them on the Setup-guide path per
PR-CONN-PROVIDER-KEY-VISIBILITY.

---

## Frontend flow

1. Operator clicks **Configure** on an `api_provider` card (Anthropic /
   OpenAI / etc.) in `/connections`.
2. PluginCardView routes to `/account/api-keys#provider-keys`. AccountPage
   renders the new **Provider Keys** section (anchored, `scroll-mt-24` so the
   header bar doesn't cover it).
3. `AccountProviderKeys.tsx` mounts, fetches `GET /account/provider-keys`,
   and renders one row per provider with: status pill (Configured /
   Not configured), settings-field hint, "Get key" external link, paste
   input (type=password, eye-toggle for reveal), Save + (when configured)
   Trash buttons.
4. Save -> `POST /account/provider-keys/{slug}` with
   `{api_key, test_after_save: true}`. The endpoint:
   * Force-removes any pre-existing provider registration so a re-key
     actually re-instantiates with the new value (workaround for
     dynamic_models' "already-registered" branch which would otherwise
     skip the new key).
   * Calls `DynamicModelService.provision_provider`, which sets
     `settings.<field>` and runs the provider's real `health_check()`.
   * **Stricter than dynamic_models**: requires `health == HEALTHY`
     (not just `!= UNAVAILABLE`). DEGRADED -> bad key (Anthropic / OpenAI
     return 401 -> classified DEGRADED, which the founder's intent reads
     as "save should reject"). Friendly message:
     `"anthropic responded but the key was not accepted (health=DEGRADED).
     Double-check the key value."`
   * Only persists to the store after the HEALTHY gate passes.
5. Component dispatches `daena:retry-pending` -> `useMarketplaceCards`
   refreshes -> the `api_provider` card flips Configure -> Test in real time
   (no manual reload).
6. Trash -> `DELETE /account/provider-keys/{slug}` -> store cleared,
   `settings.<field>` reset, provider removed from registry, marketplace
   card flips back to Configure.

---

## Secret-handling proof

The PR's central contract is **the saved key value must never leave the
backend**. Verified in three ways:

### 1. API contract (typed responses)

`SaveKeyResponse` and `ProviderKeyStatus` Pydantic models DO NOT contain a
`value` field. The closest thing is `key_hint` (an intentional UI placeholder
like `"sk-ant-..."` -- the literal `...` is not a key, it's a "your key
starts with this" hint).

### 2. Store unit tests (5 explicit leak-safety pins)

* `test_get_metadata_never_includes_value` -- canary string never appears
  in the metadata dict
* `test_list_provider_status_never_includes_value` -- canary never appears
  in the list endpoint payload
* `test_list_configured_fields_returns_names_only` -- field names only
* `test_save_returns_no_secret_value` (endpoint test) -- canary does not
  appear in the POST response body
* `test_endpoints_require_auth` -- no anon read of the configured-state
  list

### 3. Live browser audit

A 4-step flow ran in the actual browser against the live backend:

1. POST a deliberately-bad key with `test_after_save=true` -- response
   `success=false`, store untouched (`store.get_override(...) == ""`).
2. POST a different fake key with `test_after_save=false` -- response
   `success=true`, store now configured.
3. Re-read the marketplace card -- `lifecycle="configured",
   action="Test", key_present=true` (the requested behavior).
4. Serialize EVERY response payload + GET response into one JSON blob and
   `.includes('CANARY')` -> **CLEAN**.

Logging additionally caps key visibility at length-only:
`logger.info("provider_keys_store.override_set", field=field, value_len=len(value))`.

---

## Card state before / after

### Before save (Anthropic, no `.env` key, store empty)

```json
{
  "id": "provider-anthropic",
  "lifecycle": "available",
  "primary_action_label": "Configure",
  "provider_key_present": false
}
```

### After save (test_after_save=false, key persisted)

```json
{
  "id": "provider-anthropic",
  "lifecycle": "configured",
  "primary_action_label": "Test",
  "provider_key_present": true
}
```

The transition takes the same path the previous PR
(PR-CONN-PROVIDER-KEY-VISIBILITY) wired up: `provider_keys_store ->
hydrate_settings -> ModelRegistry.is_configured -> _resolve_provider_key_present
-> MarketplaceCard.provider_key_present -> _derive_lifecycle -> Test`.

---

## Tests run

| File | Suite | Result |
|---|---|---|
| `tests/test_provider_keys_store.py` | NEW (21 tests) | **21 passed** |
| `tests/test_account_provider_keys_endpoint.py` | NEW (11 tests) | **11 passed** |
| `tests/test_provider_key_visibility.py` | regression | 25 passed |
| `tests/test_marketplace_parity_repair.py` | regression | 6 passed |
| `tests/test_connection_v2_marketplace.py` | regression | 93 passed |
| Wider: `-k "marketplace or connection_v2 or probe or provider_key or dynamic_model or account_provider"` | sweep | **422 passed, 1 skipped, 0 failed in 30.46s** |
| Frontend `tsc -b` | typecheck | exits 0 (one pre-existing warning in OAuthConnectDrawer.tsx, untouched by this PR) |

---

## Hard-rule compliance

| Rule | Status |
|---|---|
| 1. No production deploy | never invoked |
| 2. Don't flip USE_CONNECTION_REGISTRY_V2 | untouched |
| 3. Don't run vault --apply | never invoked |
| 4. Don't delete V1 files | none deleted |
| 5. No print/grep/log/commit secrets | length-only logging; serialized JSON canary audit clean |
| 6. Don't expose API key after saving | response and list shapes contain no `value` field |
| 7. No emails/DMs/webhooks | none |
| 8. No external scans | none |
| 9. Don't add new primary Connections tabs | tabs unchanged |
| 10. Don't mark connected/callable without probe | save bumps to `configured` + Test, never to `callable`/`connected` -- the user must still click Test (or wait for the probe) for callable=true |
| 11. Don't duplicate secret storage | reuses the `oauth_credentials_store.py` mechanism (atomic JSON file + asyncio lock + cache + chmod 0600); new file because Rule 18 protects the OAuth file from extension |

---

## Files changed (10 files, ~1100 lines)

**Backend (5):**
* `backend/app/services/integrations/provider_keys_store.py` -- NEW (310
  lines): atomic file-backed store, leak-safe metadata, hydration helper,
  Asset Shield fingerprint registration.
* `backend/app/api/v1/account_provider_keys.py` -- NEW (215 lines): GET / POST
  / DELETE endpoints under `/api/v1/account/provider-keys`. ADMIN+ role
  required. Force-remove-then-provision workaround for dynamic_models'
  already-registered branch. HEALTHY-only acceptance gate.
* `backend/app/api/v1/__init__.py` -- registered the new router under
  `/account/provider-keys` with a docblock.
* `backend/app/main.py` -- hydrate `provider_keys_store` overrides BEFORE
  `ModelRegistry.initialize()`. Best-effort try/except so a bad override file
  never blocks startup.
* `.gitignore` -- added the new override file alongside the existing OAuth
  one.

**Backend tests (2 NEW):**
* `backend/tests/test_provider_keys_store.py` (21 tests, 250 lines): CRUD,
  atomic write, allowlist, hydration, leak safety, legacy migration, slug
  mapping consistency.
* `backend/tests/test_account_provider_keys_endpoint.py` (11 tests, 270
  lines): GET shape, POST leak-safety, store persistence, provider rejection
  path, slug 404s, DELETE idempotency, auth gate. Patches
  `DynamicModelService.provision_provider` so tests don't actually hit
  upstream APIs.

**Frontend (3):**
* `frontend/src/pages/account/AccountProviderKeys.tsx` -- NEW (240 lines):
  the input UI. Password-type input + reveal toggle, per-row Save / Clear,
  configured pill + relative `last_updated`, error inline, "Get key" links
  to vendor portals.
* `frontend/src/pages/AccountPage.tsx` -- added the `id="provider-keys"`
  anchored section + lazy import.
* `frontend/src/pages/connections/PluginCardView.tsx` -- changed Configure
  deep-link from `/account/api-keys` -> `/account/api-keys#provider-keys`.
* `frontend/src/pages/connections/PluginDetailDrawer.tsx` -- same Configure
  deep-link update.

(`OAuthConnectDrawer.tsx` was intentionally NOT updated -- its Configure
button is for OAuth client credentials, a different concept.)

---

## Remaining provider/key debt

These are explicit follow-ups, NOT started in this PR (each gated on founder
authorization):

1. **PR-CONN-PROVIDER-KEY-VAULT-MIGRATION** -- replace the JSON file
   with the `vault_v2.encrypt_secret` envelope-encrypted `Secret` table
   (per ADR-002 D-003 Phase 4b). Required for production multi-tenant.
2. **PR-CONN-PROVIDER-KEY-AUTOTEST-ON-PROBE** -- wire the existing
   marketplace `Test` button to call a provider-specific probe instead of
   the V2 NoopProbe. Today Test passes whenever the registry has a
   provider; we want it to call `provider.health_check()` and persist the
   outcome as V2 truth so the card lifecycle can climb to `callable`.
3. **PR-CONN-PROVIDER-KEY-ROTATION-CADENCE** -- surface "key set 23 days
   ago, rotation recommended every 90" with a rotate prompt. Would
   require the store to remember `created_at` separately from
   `updated_at`.
4. **PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS** (already deferred from
   PR-CONN-LIVE-PARITY-REPAIR) -- give OAuth client credentials the same
   in-product input surface, sibling section under Account.
5. **PR-CONN-LOCAL-MODEL-PROBE** (already deferred) -- register a real
   http_get probe for `local-vllm` / `local-ollama` so the Test button on
   local-model cards records V2 truth.
6. **PR-CONN-PROVIDER-KEY-AUDIT-EVENT** -- emit a structured audit log
   event on save / clear (currently only `logger.info`). Would feed into
   the existing audit-log surface so the operator can see "Anthropic key
   rotated 2 hours ago by founder".
7. **PR-CONN-PROVIDER-KEY-PARTIAL-MASK** -- show last-4-of-key after
   save so the operator can confirm "yes that's the right one." Today we
   show nothing (deliberately leak-safe). Adds a tiny disclosure
   tradeoff worth a separate review.
