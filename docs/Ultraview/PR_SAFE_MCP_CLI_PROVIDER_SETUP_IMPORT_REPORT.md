# PR-4 — Safe MCP / CLI / provider setup detection

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 4 of 7
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Surface a single read-only morning summary so the operator sees in
one panel: CLI runtimes detected, local LLMs reachable, API keys
present (boolean only — never values), MCPs already configured in
other CLIs, and any blockers.

## What's new

**Backend:** new aggregator endpoint
`GET /api/v1/system/morning-readiness`. Pure read-only. NEVER returns
secret values. Composes:

- `cli_runtimes` — Claude Code / Codex / Gemini CLI detection (via
  existing runtime_truth_registry).
- `local_llms` — Ollama / llama-server / vLLM reachability.
- `api_providers` — OpenAI / Anthropic / Gemini / Groq / OpenRouter /
  Perplexity / Together. Each row reports `configured: bool` only —
  the actual env var value is never read or returned.
- `detected_mcps` — top 20 MCP servers found in OTHER CLIs' configs.
  **Env values are dropped** before returning. Only `name`, `from_cli`,
  `command` are exposed.
- `blockers` — operator-actionable strings. e.g. "No local LLM and no
  CLI runtime detected. Start llama-server / Ollama, or install Claude
  / Codex / Gemini CLI."
- `ready_for_morning_work` — single boolean derived from the buckets.

**Frontend:** new `MorningReadinessPanel.tsx` component, mounted in
`SettingsModelsRuntimes` directly under the existing `BrainReadinessPanel`.
One backend round-trip; renders headline pill + four sections + blockers.

## Hard rules — encoded + tested

| Rule | Status |
|---|---|
| No secret values returned | ✅ — `test_no_brain_marks_blockers` and `test_detected_mcps_drops_env` pin this |
| Env var names only (no values) | ✅ — `configured: bool` field; never a string of the value |
| Detected MCPs dropped env | ✅ — explicit deletion in aggregator + test asserts `"env" not in items[0].keys()` |
| No random package installs | ✅ — endpoint is read-only |
| No filesystem MCP auto-config | ✅ — detector is read-only; install path stays behind explicit operator action + install_scanner gate |
| No Phase 3 writes | ✅ |
| Best-effort failure handling | ✅ — detector errors caught and surfaced as `scan_error`, never raised |

## Files

```
modified:   backend/app/api/v1/system_self_diagnostic.py             (+128 lines: morning-readiness endpoint)
new:        backend/tests/test_morning_readiness_endpoint.py         (175 lines, 4 tests)
new:        frontend/src/components/common/MorningReadinessPanel.tsx (236 lines)
modified:   frontend/src/pages/settings/SettingsModelsRuntimes.tsx   (+6 lines: mount panel)
new:        docs/Ultraview/PR_SAFE_MCP_CLI_PROVIDER_SETUP_IMPORT_REPORT.md
```

## Tests

**Backend:** 120 / 120 pass on the Sprint-12 + PR-1..PR-4 fast subset.

```
tests/test_morning_readiness_endpoint.py     4 (NEW)
tests/test_morning_route_contract.py        13
tests/test_chat_vp_preflight_contract.py     5
tests/test_vp_work_commands.py              25
tests/test_draft_enrichment.py              24
tests/test_draft_qe_review.py               10
tests/test_workstream_from_draft.py         11
tests/test_sprint12_full_smoke.py           28
                                          ────
                                           120
```

The new tests pin:

1. Route mounted under `/system/morning-readiness`.
2. Response shape (six top-level keys + bucket sub-keys).
3. `ready_for_morning_work=False` when no LLM + no CLI ready.
4. **Critical safety**: detected MCP env values are dropped from the
   response. Test injects a fake MCP with `env={"GMAIL_TOKEN": "secret-shouldnt-leak"}` and asserts the literal string `"secret-shouldnt-leak"` does not appear in any string value of the response.

**Frontend:** `npx tsc --noEmit` exit 0.

## What this PR does NOT do

* Does NOT install anything. The detection is purely read-only. The
  one-click MCP import path stays where it already lives (the
  Connections page → `install_scanner` governance gate). The new
  panel includes a hint pointing the operator there.
* Does NOT auto-fill the Filesystem MCP root. Per the brief, this
  remains a manual operator action.
* Does NOT probe paid API endpoints. Provider readiness is "key
  present?" only — no test calls fire.

## Live UX

In Settings → Models & Runtimes, below the existing BrainReadinessPanel:

```
┌─ Ecosystem Readiness                              [Refresh ↻] ─┐
│ CLI runtimes, local LLMs, API keys, detected MCPs.            │
│                                                                │
│   [✓] Ready for VP work                                        │
│                                                                │
│ CLI Runtimes                                3 / 4 ready        │
│   ● Claude Code CLI               (subscription)   Ready       │
│   ● Codex CLI                     (subscription)   Ready       │
│   ● Gemini CLI                    (subscription)   Ready       │
│   ○ Ollama CLI                    (free_local)     Detected    │
│                                                                │
│ Local LLMs                                  1 / 2 ready        │
│   ● Ollama (backend)              (free_local)     Ready       │
│   ○ llama-server                  (free_local)     Offline     │
│                                                                │
│ API Providers                               0 / 7 ready        │
│   ○ OpenAI                        no key           Not config  │
│   ○ Anthropic                     no key           Not config  │
│   ...                                                          │
│                                                                │
│ Detected MCPs (other CLIs)                       4 found       │
│   claude_code  gmail              npx                          │
│   claude_code  google-calendar    npx                          │
│   codex        memory             npx                          │
│   gemini_cli   fetch              uvx                          │
│   Visit the Connections page to import these into Daena.       │
└────────────────────────────────────────────────────────────────┘
```

## Next: PR-5 — Runtime autofix proposals (no auto OS install)
