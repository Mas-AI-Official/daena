# PR-1 — Runtime readiness inventory (Sprint-12A)

**Sprint:** DAENA-RUNTIME-QE-ROUTER-READINESS-SPRINT-12A
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

One backend source of truth for "which brain is ready right now" —
spanning local LLM endpoints, subscription CLIs, and metered API
providers. Built **on top of** the existing `runtime_truth_registry`
(per CLAUDE.md Rule 2 — extend, don't duplicate). Adds the
*operational* overlay (cost_class, recommended_role, readiness_state)
the supervised-work brain needs to choose correctly without
hardcoding llama-server.

## What changed

### 1. `runtime_truth_registry` extended for the three missing API providers

`_discover_items` now also surfaces:

- `provider_groq`
- `provider_openrouter`
- `provider_together`

Same ladder as the existing four (Perplexity / Gemini / OpenAI /
Anthropic): API keys flagged as boolean only, no value ever leaves
the process, `imported_state="configured_untested"` until an explicit
zero-cost test runs.

### 2. New service: `app/services/runtime_readiness.py`

Three concepts:

#### (a) `RUNTIME_CLASSIFICATION` map

Per-runtime classification with `cost_class`, `primary_role`,
`secondary_roles`, `rationale`:

| Runtime ID | cost_class | primary_role | secondary_roles |
|---|---|---|---|
| `vllm_configured` | `free_local` | `main_brain` | `qe_reviewer`, `coder` |
| `ollama_backend` | `free_local` | `main_brain` | `qe_reviewer` |
| `ollama_windows` | `free_local` | `fallback` | `main_brain` |
| `cli_claude` | `subscription` | `coder` | `qe_reviewer`, `main_brain` |
| `cli_codex` | `subscription` | `coder` | `qe_reviewer` |
| `cli_gemini` | `subscription` | `researcher` | `main_brain` |
| `cli_ollama` | `free_local` | `fallback` | (none) |
| `provider_perplexity` | `metered_api` | `web_grounding` | `researcher` |
| `provider_anthropic` | `metered_api` | `qe_reviewer` | `main_brain`, `coder` |
| `provider_openai` | `metered_api` | `qe_reviewer` | `main_brain` |
| `provider_gemini` | `metered_api` | `researcher` | `main_brain` |
| `provider_groq` | `metered_api` | `fallback` | `coder` |
| `provider_openrouter` | `metered_api` | `fallback` | (none) |
| `provider_together` | `metered_api` | `fallback` | (none) |

**A coverage test asserts every truth-registry id is classified.**
Adding a new provider to the truth registry without classifying it
is a CI failure. No silent orphans.

#### (b) Readiness ladder — `_readiness_state(item, cost_class)`

| cost_class | `ready` when | `configured_untested` when | `not_configured` when |
|---|---|---|---|
| `free_local` | `callable=true OR reachable=true` | (n/a — local should be probed via HTTP) | not detected/configured |
| `subscription` | CLI binary on PATH (`callable=true`) | detected but not callable | binary not found |
| `metered_api` | `configured AND authenticated=True` | configured (no zero-cost probe yet) | no API key |

Critical: **`metered_api` items NEVER report `ready` from key
presence alone.** `authenticated=True` only flips after an explicit
zero-cost test endpoint runs. This is the spend-prevention guard.

#### (c) `_classify_item` demotes role when not ready

A runtime that's classified as `main_brain` but is offline reports
`recommended_role="none"`, not `"main_brain"`. The router sees only
*ready* candidates.

### 3. `RouterSummary` aggregator

Picks one runtime per role:

- `main_brain_id` — preferred ready main brain
- `web_grounding_id` — Perplexity if ready
- `coder_id` — preferred ready coder
- `researcher_id` — preferred ready researcher
- `qe_reviewers_ready` — ALL ready reviewers
- `qe_mode` — `full` (≥2 distinct ready reviewers) / `degraded` (1) / `unavailable` (0)
- `next_action` — plain-English string the UI can render

When no main brain is ready, `next_action` says "blocked, start a local
endpoint." That's the brief's "never fail silently" rule.

### 4. New endpoints

| Verb | Path | Purpose |
|---|---|---|
| GET | `/api/v1/system/runtime-readiness` | Full inventory + summary |
| GET | `/api/v1/system/router-readiness` | Just the router summary |
| GET | `/api/v1/system/router-policy` | Static policy matrix (no I/O) |

All three require auth. None return secret values.

## Tests

`backend/tests/test_runtime_readiness.py` — **25 passing.**

| Group | Cases |
|---|---|
| `TestClassificationCoverage` | 2 (every truth-registry id classified, every entry has required fields) |
| `TestReadinessLadder` | 6 (free_local ready / offline, subscription ready / untested, metered_api untested / not_configured) |
| `TestRoleDemotion` | 2 (offline runtime → role=none, ready → real role) |
| `TestRouterSummary` | 5 (free_local main_brain pick, qe full/degraded/unavailable, next_action blocked) |
| `TestRouterPolicyMatrix` | 3 (all roles present, Perplexity only in web_grounding, hard rules documented) |
| `TestEndToEnd` | 3 (no secret leak via regex scan, endpoints registered, phase-2 still on) |
| `TestKindMapping` | 4 (local_model→local_llm, cli→cli_runtime, api→api_provider, runtime kept separate) |

**No paid API call made during tests.** All probes are mocked or use
the existing zero-cost truth-registry path.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets read/printed/committed | ✅ |
| No expensive model calls | ✅ — readiness is metadata only |
| API keys are boolean only in response | ✅ — regex test enforces |
| CLI auth probe doesn't spend tokens | ✅ — only checks PATH presence |
| No duplicate router/provider stores | ✅ — wraps `runtime_truth_registry` |
| Phase 3 writes still blocked | ✅ |

## Files touched

```
modified:   backend/app/services/runtime_truth_registry.py  (3 provider rows added)
new:        backend/app/services/runtime_readiness.py       (overlay service)
modified:   backend/app/api/v1/system_self_diagnostic.py    (3 endpoints)
new:        backend/tests/test_runtime_readiness.py
new:        docs/Ultraview/PR_RUNTIME_READINESS_INVENTORY_REPORT.md
```

## What this PR does *not* do (deferred)

- Per-provider zero-cost test endpoints (Anthropic / OpenAI / etc).
  These need a "ping the / endpoint" implementation per provider —
  follow-up PR.
- UI surface — that's PR-4.
- QE/Council slot-level assignment — that's PR-3.

## Next step

PR-3 — QE/Council runtime slot assignment (5 named slots:
local_reasoner, code_reviewer, web_grounder, risk_reviewer,
final_synthesizer). Builds on the readiness summary; emits a
slot-level assignment report.
