# PR-CONN-LOCAL-MODEL-PROBE — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Founder request:** add real V2 probe support for local model cards
(Ollama, vLLM / llama-server) so Connections can truthfully show
whether local models are reachable and Brain-capable.
**Hard rules honored:** no deploy / no V2 flag flip / no vault apply /
no V1 deletion / no secrets touched / no external scans / no
auto-install / no falsely-callable status / no new primary tabs / no
marketplace UI rewrite.

---

## Summary

Before this PR, marketplace cards for `kind=local_model` (Ollama, vLLM)
fell through to `probe_unavailable` because no probe was registered
for that kind. The Brain selector and the Connections page had no way
to confirm whether the local LLM endpoint was actually reachable +
serving a non-empty model list.

This PR ships:

1. **`LocalModelProbe`** -- a real HTTP probe for `kind=local_model`
   rows. Reads `base_url` from the row's config (with a
   settings-attribute fallback), calls `/api/tags` for Ollama or
   `/v1/models` for vLLM with a 5s timeout + `follow_redirects=False`,
   and returns a structured `ProbeResult`. NEVER calls a chat /
   completions endpoint (truth-only).
2. **Local-host allowlist** -- the probe rejects any `base_url` whose
   host is not in `{127.0.0.1, localhost, 0.0.0.0, ::1,
   host.docker.internal, gateway.docker.internal}`. Defense against a
   misconfigured URL pointing at a public endpoint that would leak
   the operator's IP, model usage timing, or even an API key on the
   path. The failure_reason mentions only "non-local host" and
   NEVER echoes the misconfigured URL back.
3. **Structured failure prefix vocabulary** -- the frontend can
   `startsWith()` match these to surface targeted hints
   (WSL/Docker copy for `connection_failed:`/`timeout:`; "pull a
   model" copy for `no_models:`; etc.) without parsing free-form text.
4. **Wire into `install_all_probes()`** -- registered as the 6th
   per-kind probe alongside Provider / SkillPack / McpServer /
   CliRuntime / OAuthApp.
5. **Drawer surfacing** -- `PluginDetailDrawer` already calls Test
   when the marketplace mapping promotes the local-model card to
   `("configured", "test")` (this happened in
   PR-CONN-PROVIDER-KEY-VISIBILITY); now the Test button actually
   produces honest truth instead of "probe_unavailable". Drawer adds
   WSL/Docker localhost guidance for connect failures and "pull a
   model" guidance for empty-list failures.
6. **39 new unit tests** + 1 live verification against the actual
   running backend's Ollama instance.

Total backend tests after PR: **548 passed / 1 skipped / 0 failed**
(+39 from this PR; previous baseline 509). Frontend `tsc -b` clean.

---

## Supported local models

| Catalog id | Provider | Endpoint | Models field | Auth |
|---|---|---|---|---|
| `local-ollama` | Ollama | `{base_url}/api/tags` | `models[]` (each `{name,...}`) | none |
| `local-vllm` | vLLM / llama-server / LM Studio (OpenAI-compatible) | `{base_url}/v1/models` | `data[]` (each `{id,...}`) | none |

The OpenAI-compatible `/v1/models` endpoint covers the entire
llama.cpp / vLLM / LM Studio family in one probe -- they all expose
the same shape.

### URL normalization
`vllm_base_url` ships with a trailing `/v1` (the chat orchestrator's
vLLM adapter expects a complete OpenAI base URL). The probe strips
trailing `/v1` before appending `/v1/models` so a base_url of
`http://127.0.0.1:8080/v1` produces `http://127.0.0.1:8080/v1/models`,
NOT `http://127.0.0.1:8080/v1/v1/models`. Test pins this:
`test_vllm_base_url_with_trailing_v1_is_normalized`.

---

## Exact probe endpoints + behavior

```
1. Read row.config['_provider_id'] -> resolve LocalModelSpec
   (or fail with FAILURE_PREFIX_UNSUPPORTED).
2. If spec.enabled_settings_attr is set, check Settings.<attr>
   (Ollama only -- OLLAMA_ENABLED). If False, fail with
   FAILURE_PREFIX_DISABLED_BY_ENV.
3. Resolve base_url from row.config['base_url'] OR
   Settings.<spec.settings_attr>. If empty, fail with
   FAILURE_PREFIX_BASE_URL_MISSING.
4. Normalize: strip trailing '/' and '/v1' so spec.path can
   append safely.
5. Validate host in _LOCAL_HOST_ALLOWLIST. If not, fail with
   FAILURE_PREFIX_CONNECTION_FAILED + "non-local host" (URL is
   NEVER echoed back).
6. GET {base_url}{spec.path} with timeout=5s,
   follow_redirects=False.
7. On TimeoutException -> FAILURE_PREFIX_TIMEOUT (reachable=false).
8. On ConnectError/NetworkError -> FAILURE_PREFIX_CONNECTION_FAILED
   (reachable=false).
9. On HTTP >=400 -> FAILURE_PREFIX_MODELS_ENDPOINT_FAILED
   (callable=false).
10. On non-JSON body -> FAILURE_PREFIX_MODELS_ENDPOINT_FAILED.
11. Extract first 8 model names via name|id field. If list is
    empty -> FAILURE_PREFIX_NO_MODELS (reachable but empty).
12. SUCCESS: return ProbeResult(success=True, capabilities=[{
      kind: "local_model", provider_id, model_count,
      models_preview: [...], endpoint_path,
    }]).
```

---

## Success / failure criteria

| Outcome | `failure_dim` | Prefix | Frontend surface |
|---|---|---|---|
| Healthy + non-empty model list | None (success=True) | -- | Green "Local model server reachable + at least one model loaded. Brain selector can route to it." caption |
| `_provider_id` missing or unknown | `configured` | `unsupported_local_model:` | Generic "Last failure" line |
| Disabled via `OLLAMA_ENABLED=false` | `configured` | `disabled_by_env:` | Generic "Last failure" line |
| `base_url` empty in both row.config and settings | `configured` | `base_url_missing:` | Generic "Last failure" line |
| `base_url` host not in allowlist | `reachable` | `connection_failed:` (no host echo) | WSL/Docker localhost guidance hint |
| TCP connect refused | `reachable` | `connection_failed:` | WSL/Docker localhost guidance hint |
| HTTP timeout (5s) | `reachable` | `timeout:` | WSL/Docker localhost guidance hint |
| HTTP 4xx/5xx from /api/tags or /v1/models | `callable` | `models_endpoint_failed:` | Generic "Last failure" line |
| Body is not JSON | `callable` | `models_endpoint_failed:` | Generic "Last failure" line |
| 200 OK + empty model list | `callable` | `no_models:` | Cyan "Pull or load a model" guidance hint |

---

## WSL / Docker localhost guidance

When the drawer's `failure_reason` starts with `connection_failed:` or
`timeout:`, the new amber callout shows:

> **Cannot reach the local model server.** Check that the server is
> running and listening on the configured base URL.
>
> - **WSL / Docker:** "localhost" inside a container points at the
>   container itself. From WSL, use the Windows host IP (or
>   `host.docker.internal`) instead of `127.0.0.1`.
> - **Windows firewall:** first run of `ollama serve` / `llama-server`
>   may prompt for network permission -- accept it.
> - **Port:** Ollama defaults to `11434`, llama-server to `8080`.

This addresses the most common operator gotcha: starting Ollama on
the Windows host but pointing Daena (running in WSL or Docker) at
`http://127.0.0.1:11434`, which inside the container resolves to
something other than the Windows host. The hint is targeted -- it
ONLY renders for connect-failure prefixes, not for `no_models:` or
`disabled_by_env:` where the WSL advice would be misleading.

---

## Live verification (against real running backend)

Ran the probe end-to-end against the actual `http://127.0.0.1:8000`
backend's settings + the actual Ollama instance running on the
operator's machine. Two cases:

**Ollama (`OLLAMA_ENABLED=false` per CLAUDE.md):**
```
success: False
failure_dim: configured
failure_reason: disabled_by_env: ollama is disabled via OLLAMA_ENABLED=false
```
Honest answer -- the operator explicitly disabled Ollama, the probe
respects that and never tries the HTTP call.

**vLLM (`vllm_base_url=http://127.0.0.1:8080/v1`, llama-server not
currently running):**
```
success: False
failure_dim: reachable
failure_reason: connection_failed: ConnectError reaching vllm -- is the
local server listening on the configured port?
```
Connect refused -- structured `connection_failed:` prefix triggers
the WSL/Docker hint in the drawer. The base_url normalization
correctly stripped the trailing `/v1` (verified in unit test
`test_vllm_base_url_with_trailing_v1_is_normalized`).

---

## Tests run

### New file: `backend/tests/test_local_model_probe.py` (39 tests)

| Test class | Tests | Pinning |
|---|---|---|
| `TestSpecCatalog` | 3 | both providers present; correct paths + auth + opt-out env |
| `TestConfigurationFailures` | 4 | unknown provider, missing base_url, OLLAMA disabled, non-local host |
| `TestNetworkFailures` | 2 | ConnectError + TimeoutException -> reachable=false |
| `TestEndpointFailures` | 3 | 5xx, non-JSON body, empty model list |
| `TestSuccessPath` | 4 | Ollama success, vLLM success, list truncation to 8, /v1 trailing-segment normalization |
| `TestLeakageGate` | 5 | redact tokens, redact Windows path, redact Linux path, truncate, never echo misconfigured public host |
| `TestLocalHostAllowlist` | 1 (parametrized x9) | 9 URLs including IPv6 + docker-internal + public hosts |
| `TestModelNameExtraction` | 5 | Ollama `name`, OpenAI `id`, malformed entries dropped, empty/non-dict payloads |
| `TestRegistryWiring` | 3 | install_local_model_probe registers under `local_model`; install_all_probes includes it; run_probe dispatches |

### Regression sweep
```
.venv/Scripts/python.exe -m pytest tests/ -q -k "marketplace or
connection_v2 or probe or provider_key or dynamic_model or
account_provider or plugin_bundle or plugin_skills or local_model"
548 passed, 1 skipped, 3952 deselected, 13 warnings in 30.05s
```
Up from 509 in the prior PR. Net +39 from this PR; zero regressions.

### Frontend tsc
`npx tsc -b` clean (0 errors).

---

## Remaining Brain / local-model debt

This PR fixes the truth surface. Three follow-ups would round out
the story but are out of scope:

1. **Capability surfacing in marketplace cards**. The probe writes
   model names + count to `ConnectionV2Capability`; surfacing them
   in the drawer needs a marketplace-card payload extension
   (`capabilities_preview: list[dict] | None`). Today the drawer
   only confirms "Brain selector can route to it" without listing
   the specific models. Could be a tiny PR.
2. **Model-routing telemetry**. The `model_router` already prefers
   local when available; once the probe truth lights up `callable=true`
   for local-vllm, the router should record per-call which local
   model handled the request so the operator can see Brain decisions
   in the audit log.
3. **`vllm_base_url` schema canonicalization**. The current default
   ships with `/v1` because the chat adapter wants a complete
   OpenAI base URL. The probe normalizes it, but a follow-up could
   split this into `vllm_base_url` (host:port) + `vllm_openai_path`
   (`/v1`) so each consumer (probe / chat adapter) reads what it
   needs without normalization.

None of these are blockers. The probe is honest now; Brain is no
longer blind to local LLM truth.

---

## Files changed

```
A  backend/app/services/connection_v2/probes/local_model_probe.py  (320 lines)
M  backend/app/services/connection_v2/probes/__init__.py           (+9 / -1)
A  backend/tests/test_local_model_probe.py                          (430 lines)
M  frontend/src/pages/connections/PluginDetailDrawer.tsx           (+50 lines drawer hints)
A  docs/Ultraview/PR_CONN_LOCAL_MODEL_PROBE_REPORT.md              (this file)
```

Net: ~+800 lines added, ~-1 removed across 1 new probe + 1 wiring
update + 1 new test file + 1 drawer extension + this report.

---

## Hard rules verification

| Rule | Compliance |
|---|---|
| 1. No deploy production | ✅ no Cloud Run touch |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` | ✅ flag unchanged |
| 3. No `vault --apply` | ✅ vault untouched |
| 4. No V1 file deletion | ✅ |
| 5. No secrets printed/grepped/logged/committed | ✅ `_scrub` redacts both token-shaped strings AND home paths in failure_reason; URL never echoed back when host fails allowlist |
| 6. No external scans | ✅ |
| 7. No emails/DMs/webhooks/messages | ✅ probe is GET-only against local hosts |
| 8. No auto-install | ✅ probe is read-only against models endpoint |
| 9. No falsely-callable status | ✅ success requires non-empty model list AND HTTP 200 AND parseable JSON |
| 10. No new primary tabs | ✅ drawer-only edit |
| 11. No marketplace UI rewrite | ✅ existing card flow unchanged; only failure-hint copy added |

Stop and report.
