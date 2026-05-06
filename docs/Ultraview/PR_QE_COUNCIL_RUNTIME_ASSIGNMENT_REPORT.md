# PR-3 — QE/Council runtime slot assignment (Sprint-12A)

**Sprint:** DAENA-RUNTIME-QE-ROUTER-READINESS-SPRINT-12A
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Make Daena's QE/Council brain know **which specific runtimes fill
which reviewer roles right now** — and refuse to claim "council
complete" when it's actually one model talking to itself.

## What changed

### 1. `QE_SLOTS` constant (`runtime_readiness.py`)

Five named reviewer slots, each with `intent` + `preferred` runtime
ids + `fallback_role`:

| Slot | Intent (one-liner) | Preferred | Fallback role |
|---|---|---|---|
| `local_reasoner` | Cheap, private, deterministic first-pass review | `vllm_configured`, `ollama_backend` | `main_brain` |
| `code_reviewer` | Cross-file impact + refactor quality | `cli_claude`, `cli_codex`, `vllm_configured` | `coder` |
| `web_grounder` | Verifies live-data claims | `provider_perplexity` | `web_grounding` |
| `risk_reviewer` | Hallucination / missing-evidence / scope-creep | `provider_anthropic`, `provider_openai`, `cli_claude` | `qe_reviewer` |
| `final_synthesizer` | Reads peers, writes the operator-facing summary | `vllm_configured`, `ollama_backend`, `cli_claude`, `provider_anthropic` | `main_brain` |

**Critical guard: `web_grounder.preferred = ["provider_perplexity"]`
ONLY.** When Perplexity isn't configured, the slot stays unfilled —
it does not silently borrow the local model. A test enforces this.

### 2. `assign_qe_slots(items)` resolver

Three-tier resolution per slot:

1. **Preferred + unused** — first-choice runtime not yet assigned
   to another slot. Gives council actual diversity.
2. **Fallback role + unused** — any ready runtime whose
   `recommended_role` (primary or secondary) matches `fallback_role`
   AND isn't already assigned.
3. **Re-use** — last resort, take a preferred runtime even if it's
   already in another slot. The QE mode flips to `degraded` when
   this happens for any slot.

Result: `QEReadiness` with `mode`, `distinct_runtime_ids`,
`slot_assignments[]`, `mode_reason`.

### 3. Mode taxonomy

| Mode | When | Honest message |
|---|---|---|
| `full` | ≥2 distinct runtimes filling ≥3 slots | "QE can run with peer cross-check" |
| `degraded` | <2 distinct runtimes, but at least one slot filled | "QE runs degraded — there is no real peer cross-check when reviewers are the same model" |
| `unavailable` | Zero ready runtimes | "Configure at least one local model or one CLI/API provider before running Council" |

A single-runtime council is **never** reported as "full," even when
all five slots have a value. That's the brief's "no fake council
complete" rule, encoded in code.

### 4. New endpoint

`GET /api/v1/system/qe-readiness` returns the slot assignment +
mode + reason. Auth-required, no secrets.

## Tests

`backend/tests/test_qe_council_assignment.py` — **11 tests passing.**

| Group | Cases |
|---|---|
| `TestSlotsConstant` | 3 (5 slots present, every slot has intent/preferred/fallback, web_grounder = perplexity-only) |
| `TestAssignment` | 6 (full mode requires 2+ distinct + 3+ slots, degraded for single-runtime, unavailable when none, web_grounder unfilled when Perplexity absent, distinct runtimes used when available, single-runtime re-uses across all slots) |
| `TestEndpoint` | 2 (route registered, returns mode + slots) |

Combined Sprint-12A regression: **36 passing** across PR-1+2 + PR-3
suites.

## Hard-rule audit

| Rule | Status |
|---|---|
| No paid API call during tests | ✅ |
| No fake "council complete" with one model | ✅ — encoded in mode logic + asserted |
| Web grounding never silently borrows from main brain | ✅ — encoded in QE_SLOTS + asserted |
| No hidden chain-of-thought exposure | ✅ — readiness service only emits metadata; reviewer prompts are out of scope here |
| Phase 3 writes still blocked | ✅ |

## Files touched

```
modified:   backend/app/services/runtime_readiness.py     (QE_SLOTS, assign_qe_slots, get_qe_readiness)
modified:   backend/app/api/v1/system_self_diagnostic.py  (qe-readiness endpoint)
new:        backend/tests/test_qe_council_assignment.py
new:        docs/Ultraview/PR_QE_COUNCIL_RUNTIME_ASSIGNMENT_REPORT.md
```

## What this PR does *not* do (deferred)

- The actual reviewer-prompt construction. PR-3 only assigns
  runtimes to slots; the chat-orchestrator code that builds peer-
  review prompts and runs the synthesis remains in scope for the
  follow-up "QE/Council brain" PR.
- UI surface — that's PR-4.

## Next step

PR-4 — UI polish: surface readiness + QE mode in the existing
`RuntimeSwapper` (Connections / Brain status) so the operator sees
what's ready, what's degraded, and what needs setup.
