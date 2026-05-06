# PR-2 — Router policy matrix (Sprint-12A)

**Sprint:** DAENA-RUNTIME-QE-ROUTER-READINESS-SPRINT-12A
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)
**Note:** Shipped with PR-1 in the same commit because the policy matrix
lives in the same `runtime_readiness.py` service file. Splitting would
have meant committing partial code.

## Goal

Make Daena's router decisions **inspectable as data**, not buried in
chat-orchestrator logic. The operator (and the supervised-work tests)
can ask "where would Daena route X right now?" without firing a
single LLM call.

## What changed

### `get_router_policy()` static matrix

Six roles, each with `intent`, `preference_order`, and a `guard`
clause:

```python
{
  "main_brain": {
    "intent": "default brain-enrichment + chat reasoning",
    "preference_order": [
      "vllm_configured", "ollama_backend", "ollama_windows",
      "cli_claude", "cli_codex", "cli_gemini",
      "provider_anthropic", "provider_openai", "provider_groq",
    ],
    "guard": "Default to free_local; metered_api requires explicit operator opt-in.",
  },
  "qe_reviewer": {
    "intent": "Council / QE peer review of drafts and decisions",
    "preference_order": [
      "vllm_configured", "ollama_backend",
      "cli_claude", "provider_anthropic", "provider_openai",
    ],
    "guard": "Need >=2 distinct ready runtimes for full mode; otherwise degraded.",
  },
  "coder": {
    "intent": "code review / refactor / scaffolding",
    "preference_order": [
      "cli_claude", "cli_codex", "vllm_configured",
      "ollama_backend", "provider_anthropic",
    ],
    "guard": "Prefer subscription CLIs over metered APIs.",
  },
  "researcher": {
    "intent": "long-context summarisation, doc synthesis",
    "preference_order": [
      "cli_gemini", "vllm_configured", "provider_gemini", "ollama_backend",
    ],
    "guard": "Local first; Gemini API only for long-context that local cannot handle.",
  },
  "web_grounding": {
    "intent": "queries that require live web information",
    "preference_order": ["provider_perplexity"],
    "guard": (
      "Perplexity ONLY when the query genuinely needs live web; "
      "never as a silent default."
    ),
  },
  "fallback": {
    "intent": "last-resort brain when nothing else is ready",
    "preference_order": [
      "ollama_windows", "provider_groq",
      "provider_openrouter", "provider_together",
    ],
    "guard": "Reach for fallbacks ONLY when primary lanes are unavailable.",
  },
}
```

### `hard_rules`

Surfaced as a list the UI renders verbatim:

1. No paid API call without `ready=true` on the chosen provider.
2. No silent metered_api usage when a free_local option is ready.
3. QE/Council requires ≥2 distinct ready runtimes for full mode.
4. Audit every router decision via `integration.tool_invocation`
   pattern.

### Endpoint

`GET /api/v1/system/router-policy` returns the matrix verbatim. Pure
function — no I/O — so the UI can render this in the absence of any
runtime, providing operator guidance even when nothing is configured.

## Critical guard tests

Two guards are explicitly enforced in `test_runtime_readiness.py`:

1. **Perplexity isolation**: `provider_perplexity` appears in the
   `web_grounding` role only — NEVER in `main_brain` / `qe_reviewer`
   / etc. Otherwise Daena could silently bill the operator on every
   chat turn.
2. **Hard rules documented**: a regex grep over `hard_rules` confirms
   "no paid api" and "qe ... >=2" are both present.

## Hard-rule audit

| Rule | Status |
|---|---|
| No paid API calls during tests | ✅ |
| Router checks readiness before selecting provider | ✅ — `_pick_for_role` filters by `readiness_state=="ready"` |
| Audit provider choice metadata, not prompts | ✅ — readiness service emits no audit; that's the consumer's job |

## Files touched

Same files as PR-1 (combined commit):

```
modified:   backend/app/services/runtime_readiness.py        (`get_router_policy`)
modified:   backend/app/api/v1/system_self_diagnostic.py     (router-policy endpoint)
modified:   backend/tests/test_runtime_readiness.py          (`TestRouterPolicyMatrix`)
new:        docs/Ultraview/PR_ROUTER_POLICY_MATRIX_REPORT.md
```

## Next step

PR-3 — QE/Council runtime slot assignment.
