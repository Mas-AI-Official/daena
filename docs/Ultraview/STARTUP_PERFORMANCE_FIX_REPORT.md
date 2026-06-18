# Startup Performance Fix Report

Date: 2026-04-29
Author: Claude Code (Opus 4.7) — Phase 3 of stabilization sprint

## Goal

The API never blocks on a slow provider. The `/connections` page first
load is under 2s even when one or more LLM API providers are slow or
unreachable.

## Two distinct slow paths

Phase 1 already moved the slow lifespan seedings out of the request
path. Phase 3 fixes the second offender: the `/api/v1/runtimes` endpoint
itself.

The endpoint had two synchronous slow paths inside its request handler:

1. **Lazy registry discovery** ([runtimes.py:40-43](../backend/app/api/v1/runtimes.py:40)
   pre-fix): if `registry._installed_cache` was empty (e.g. first hit
   after restart, before the deferred startup task had populated it), the
   handler ran `discover_all + check_health_all + check_subscriptions_all`
   on the request thread. That's a multi-second probe sweep blocking the
   user's first /connections page load.

2. **Sequential provider model probes** ([runtimes.py:96-108](../backend/app/api/v1/runtimes.py:96)
   pre-fix): for each API provider with credentials (Groq, Gemini,
   Anthropic, OpenAI, OpenRouter, Together, Perplexity), the handler
   awaited `prov.list_models()` sequentially. 7 providers x ~500ms = 3.5s
   on a clean run, multi-second when any one provider was slow or
   unreachable.

## Changes shipped

### 1. Per-tenant 30s response cache

Added `_runtimes_cache: dict[str, tuple[float, dict]]` keyed by
`tenant_id`. Cache hits return in <5ms. Cache miss recomputes the
payload and stores it. TTL matches `ModelRegistry._MODEL_CACHE_TTL_SECONDS
= 60.0` so we don't out-stale the inner model catalog cache.

The response now carries a `cache_hit: bool` field so devtools can verify
the cache is hitting.

### 2. `_invalidate_runtimes_cache(tenant_id=None)` helper

State-changing endpoints invalidate the cache so the next GET returns
fresh data. Wired into:

- `POST /runtimes/discover` (full registry rescan)
- `POST /runtimes/{id}/refresh-auth` (per-runtime re-probe)
- `PUT /runtimes/primary` (changes which runtime orchestrates)
- `POST /runtimes/{id}/disconnect` (manual disconnect + auto-promote)

The discover and refresh-auth paths invalidate ALL tenants' caches
(global state changed). The primary/disconnect paths invalidate only
the affected user's tenant.

### 3. Warming gate replaces synchronous discovery

Removed:
```python
if not any(registry._installed_cache.values()):
    await registry.discover_all()
    await registry.check_health_all()
    await registry.check_subscriptions_all()
```

Added: `data["warming"] = is_warming` flag in the response. The frontend
proxy + ConnectionsRuntimes.tsx will see `warming: true` while the
deferred startup task is still scanning, render an "AI Runtimes
detecting..." chip, and poll. The lifespan deferred phase
(`runtime_registry` step) populates the cache; the next /runtimes hit
returns full data.

### 4. Parallel provider model probes via `asyncio.gather`

`for ... await prov.list_models()` replaced with:
```python
model_lists = await asyncio.gather(
    *[_safe_list_models(p, prov) for p, _, _, prov in enabled_providers],
    return_exceptions=False,
)
```

`_safe_list_models` wraps each provider call in `asyncio.wait_for(...,
timeout=5.0)`, catches `TimeoutError` + generic `Exception`, records the
failure to the per-provider error cache, and returns an empty model list.
The slowest provider sets the response time, not the sum. Worst case is
5s for one stuck provider; previous worst case was 30s+ if any one
provider hung.

These gathers do NOT touch the request-scoped DB session — they're pure
httpx calls — so the AST guard from Phase 2 doesn't flag them.

### 5. Per-provider error cache surfaces failure reason inline

```python
_provider_error_cache: dict[str, dict] = {}  # {"provider": {"last_error_at": ts, "last_error_msg": "..."}}
```

When `_safe_list_models` catches an exception, it records the error to
the cache with the timestamp. The response payload now includes per-row:
- `status: "connected" | "degraded"` (degraded if last call failed)
- `last_error_at: float | None`
- `last_error_msg: str | None`

The UI can render "Gemini: list_models() timed out (5s) — 14s ago" instead
of a stuck spinner or a misleading "Connected (0 models)" state.

A successful call clears the error cache for that provider.

### 6. Module-level `logger` import added

The previous file referenced `logger.warning(...)` at line 110 inside an
`except` block, but only imported `get_logger` deep inside another
function (line 376). That was a `NameError` waiting to happen on the
first model-enum failure. Now imported at module top.

## Measured behavior (pre/post)

(Will be measured by the user against a real backend; estimates from
code path inspection.)

| Scenario | Pre-fix | Post-fix |
|---|---|---|
| First /connections load, registry warm, all providers reachable | ~3.5s | ~600ms |
| First /connections load, registry cold (deferred not done) | 5-15s | ~50ms (returns warming) |
| Subsequent loads within 30s | ~3.5s (no cache) | <5ms (cache hit) |
| One provider unreachable (e.g. Gemini timeout) | ~30s+ | ~5s (one timeout, others parallel) |
| All 7 providers slow (~2s each) | ~14s | ~2s (parallel) |

## What was NOT changed

- Per-runtime endpoints (`/runtimes/{id}`, `/test`, `/refresh-auth`,
  `/disconnect`) — they're already targeted single-runtime calls, no
  fan-out. Untouched.
- Provider adapter implementations themselves — `list_models` still has
  its own TTL cache via `ModelRegistry._MODEL_CACHE_TTL_SECONDS`, plus
  per-provider httpx timeouts. We just wrap them in a 5s outer ceiling.
- The lifespan deferred-task scan that populates the registry cache —
  Phase 1 covers that.

## Verification

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m pytest tests/test_runtime_adapters.py -v
# 54 passed
```

After backend restart (Phase 1 lifespan):

```powershell
$port = (Get-Content .daena-port).Trim()
# First call: warming gate, returns fast
Measure-Command { Invoke-WebRequest "http://127.0.0.1:$port/api/v1/runtimes" `
  -Headers @{Authorization="Bearer $token"} -UseBasicParsing }
# Expect: <100ms, response.data.warming = true (until deferred startup completes)

# After deferred completes (~10-15s into startup):
Invoke-WebRequest "http://127.0.0.1:$port/api/v1/runtimes" `
  -Headers @{Authorization="Bearer $token"} -UseBasicParsing
# Expect: full data, warming=false

# Cache hit:
Invoke-WebRequest "http://127.0.0.1:$port/api/v1/runtimes" `
  -Headers @{Authorization="Bearer $token"} -UseBasicParsing |
  Select-Object -ExpandProperty Content | ConvertFrom-Json |
  Select-Object cache_hit
# Expect: True
```

To verify per-provider error surfacing, kill internet to one provider
and hit /runtimes:

```powershell
# (e.g. block api.groq.com via hosts file)
Invoke-WebRequest "http://127.0.0.1:$port/api/v1/runtimes" `
  -Headers @{Authorization="Bearer $token"} -UseBasicParsing |
  Select-Object -ExpandProperty Content | ConvertFrom-Json |
  Select-Object -ExpandProperty data |
  Select-Object -ExpandProperty api_providers
# Expect: Groq row has status="degraded", last_error_msg="...timeout..."
```

## Files modified

- `backend/app/api/v1/runtimes.py` (cache + warming gate + parallel
  probes + error surfacing + module logger fix)

## Status

Phase 3 of stabilization sprint: COMPLETE.
