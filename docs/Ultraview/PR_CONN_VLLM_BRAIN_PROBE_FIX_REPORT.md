# PR-CONN-VLLM-BRAIN-PROBE-FIX -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-3 (PR-1 of 5)

---

## 1. Goal (and the pivot)

**Brief said:** "Fix Brain tab vLLM probe so it uses the same truthful
local-model probe path as Connections."

**Investigation found the opposite**:

* `curl http://127.0.0.1:8080/v1/models` returns **Connection refused**.
* `Get-NetTCPConnection -LocalPort 8080` returns nothing -- llama-server
  IS NOT running. (`LLAMA_SERVER_MANAGED=respect_external` means Daena
  spawns it on demand when a chat routes to vLLM, but no chat has done
  that yet.)
* The Brain tab is therefore **honest** when it says "Not installed /
  offline." It uses the runtime registry's `check_health()` which probes
  port 8080 and correctly reports it dead.
* The marketplace card showing **"Installed"** is the **lie**. Lifecycle
  derived "configured" from the seeded `base_url` env, then the FE
  adapter (`pluginCard.ts:213`) mapped `lifecycle=configured` +
  `auth_type=none` to status="Installed" -- the exact "fake online pill"
  pattern Rule 17 forbids.

**PR-1 pivot**: kill the marketplace lie at its source, not the Brain
tab (which was already truthful).

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No model inference call | YES -- only the existing LocalModelProbe (GET /v1/models) is the truthful test path; this PR doesn't invoke it, just stops the marketplace from claiming "Installed" without it |
| Only GET /v1/models or existing local-model probe | YES -- LocalModelProbe untouched |
| Localhost allowlist only | YES -- LocalModelProbe._is_local_host already enforces this |
| No external network | YES -- pure local lifecycle derivation change |
| No secrets | YES -- no secret read, log, or commit |

---

## 3. The fix (3-line surface area, 5 new tests)

### Backend: `marketplace_service._derive_lifecycle`

Added an explicit honesty guard for `kind=local_model` rows that are
configured-but-never-probed:

```python
# A local_model row whose probe has never run is configured but NOT
# proven reachable. Falling through to the "configured" branch below
# causes the frontend's auth_type==none mapping to badge it
# "Installed" -- the exact "fake online pill" pattern Rule 17 forbids.
if (
    row.kind == "local_model"
    and row.configured
    and not row.reachable
):
    return "available", "test", "Probe"
```

Placed AFTER the `_has_recent_failure` check (so a real connection
failure still routes to "failed" / Retry probe) and BEFORE the existing
happy-path ladder (so a successful probe still climbs to "callable").

### Frontend: `pluginCard.ts:deriveAction`

Added the matching action handler so the new lifecycle="available"
local_model card surfaces a Probe button (not a redundant Setup guide):

```typescript
// A local_model card whose base_url env var IS set but lifecycle
// is "available" arrives via the local_model honesty guard. Show
// Probe so the operator runs LocalModelProbe instead of bouncing
// to Setup guide for env-var instructions they already followed.
if (entry.kind === 'local_model' && card.provider_key_present === true) {
  return { action: 'test', enabled: true }
}
```

### Tests: 5 new, all green

All in `tests/test_connection_v2_marketplace.py` under
`TestMarketplaceServiceOverlay`:

1. `test_local_model_unprobed_yields_available_not_installed` -- E2E
   through MarketplaceService.list_cards(); pins lifecycle=="available",
   primary_action_label=="Probe" for a vLLM row with
   detected=T/configured=T/reachable=F/no failure.
2. `test_local_model_probed_callable_yields_callable_lifecycle` -- after
   a successful probe (registry sets reachable+callable together), the
   row climbs to lifecycle=="callable".
3. `test_local_model_probed_and_failed_yields_failed_lifecycle` -- when
   the probe ran and recorded a `reachable_failure_at`, the existing
   "failed" branch wins over the new honesty guard.
4. `test_local_model_honesty_guard_unit` -- direct unit on
   `_derive_lifecycle` (no DB round-trip) to keep the assertion small.
5. `test_local_model_honesty_guard_does_not_apply_to_other_kinds` --
   defense-in-depth: an mcp_server row with the same dim shape stays at
   lifecycle=="configured". Only local_model gets the downgrade.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_connection_v2_marketplace.py
98 passed in 6.18s
```

Was 93 before this PR (5 new tests added).

```
$ npx tsc --noEmit
(no output)
```

---

## 5. What the operator now sees

### Before (the lie)

| Surface | Status | Reality |
|---|---|---|
| Brain tab | "Not installed / offline" | TRUE (port 8080 dead) |
| Marketplace card "vLLM / llama-server" | **"Installed"** (blue) | FALSE -- nothing is responding |

### After (the truth)

| Surface | Status | Reality |
|---|---|---|
| Brain tab | "Not installed / offline" | TRUE (unchanged) |
| Marketplace card "vLLM / llama-server" | **"Available"** (cyan) + **Probe** button | TRUE -- env is configured, probe-needed |

After clicking Probe:
* If llama-server is running -> probe succeeds -> card jumps to
  "Connected" (lifecycle=callable, FE status=connected, green)
* If llama-server is dead -> probe records `connection_failed:` ->
  card surfaces as "Failed" with the actionable failure_reason

Both outcomes are now truthful. The operator never sees an "Installed"
pill that doesn't reflect a successful probe.

---

## 6. What did NOT change

* LocalModelProbe (`probes/local_model_probe.py`) -- already correct.
* VLLMRuntimeAdapter (`runtimes/adapters/vllm_adapter.py`) -- already
  correct, used by the Brain tab.
* LlamaServerManager (`providers/llama_server_manager.py`) -- already
  correctly demand-spawns when chat routes to vLLM.
* Marketplace API endpoints, V2 truth columns, registry probe path.
* No new dependencies, no install, no production deploy.

---

## 7. Branch state after PR

The next commit will be PR-1 of Sprint-3.
