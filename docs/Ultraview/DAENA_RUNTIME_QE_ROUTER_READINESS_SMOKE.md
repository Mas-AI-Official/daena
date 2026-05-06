# Sprint-12A — Runtime / QE / Router readiness smoke report

**Sprint:** DAENA-RUNTIME-QE-ROUTER-READINESS-SPRINT-12A
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## What's now true

Daena has a **single, honest source of truth** for which brain she
will use right now. Built on top of the existing
`runtime_truth_registry` (no duplicate stores, CLAUDE.md Rule 2).
Three new endpoints:

```
GET /api/v1/system/runtime-readiness   # full inventory + summary
GET /api/v1/system/router-readiness    # just the summary slice
GET /api/v1/system/router-policy       # static policy matrix (no I/O)
GET /api/v1/system/qe-readiness        # QE/Council slot assignment
```

Plus a `BrainReadinessPanel` mounted at the top of
`SettingsModelsRuntimes` that renders all of it with honest pills.

## What brains are wired

The readiness inventory covers **14 runtime IDs** across three classes:

| Cost class | Runtimes |
|---|---|
| `free_local` | `vllm_configured`, `ollama_backend`, `ollama_windows`, `cli_ollama` |
| `subscription` | `cli_claude`, `cli_codex`, `cli_gemini` |
| `metered_api` | `provider_perplexity`, `provider_anthropic`, `provider_openai`, `provider_gemini`, `provider_groq`, `provider_openrouter`, `provider_together` |

Each is classified with `primary_role`, `secondary_roles`, and a
plain-English `rationale`. A coverage test asserts every
truth-registry id has a classification entry — adding a new provider
without classifying it is a CI failure.

## What "ready" means now (the readiness ladder)

| cost_class | `ready` requires | Why |
|---|---|---|
| `free_local` | `callable=true` (HTTP probe succeeded) | Local probes are zero-cost |
| `subscription` | CLI binary on PATH | Probing CLI auth would spend tokens |
| `metered_api` | `configured AND authenticated=True` | Key presence alone is **never** ready |

Critical guard: a `metered_api` runtime stays at `configured_untested`
until an explicit zero-cost test endpoint runs (per-provider test
endpoints are a follow-up). This is the spend-prevention floor.

## What provider Daena will use for enrichment

The router decision depends on what's ready on the operator's machine
**right now**. Walk the operator through the panel:

- If `vllm_configured.readiness_state == 'ready'`:
  → `main_brain_id == 'vllm_configured'` (free / local / private).
- Else if `ollama_backend.readiness_state == 'ready'`:
  → `main_brain_id == 'ollama_backend'` (free / local).
- Else if `cli_claude.readiness_state == 'ready'`:
  → `main_brain_id == 'cli_claude'` (subscription).
- Else: `main_brain_id == null` and `next_action == "Start the local
  llama-server / vLLM endpoint at VLLM_BASE_URL or Ollama at
  OLLAMA_BASE_URL. No main brain is ready, so brain-enrichment work is
  blocked."`

**There is no scenario where a metered API provider is silently
selected as the default main brain.** The router policy enforces
free_local-first for `main_brain`. Perplexity is reserved for
`web_grounding` only — never appears in any other role's
preference_order.

## Whether QE/Council is full or degraded

| Mode | When | Operator-visible message |
|---|---|---|
| `full` | ≥2 distinct ready runtimes filling ≥3 slots | "QE can run with peer cross-check" |
| `degraded` | <2 distinct runtimes, but at least one slot filled | "QE runs degraded — there is no real peer cross-check when reviewers are the same model" |
| `unavailable` | Zero ready runtimes | "Configure at least one local model or one CLI/API provider before running Council" |

A single-runtime council is **never** reported as full, even when all
five reviewer slots have a value. That's the brief's "no fake council
complete" rule, encoded in the mode logic and asserted by tests.

## Whether Perplexity is configured

The endpoint returns `provider_perplexity.configured == bool(settings.perplexity_api_key)`. The boolean is the
ONLY information about Perplexity that ever leaves the process; the
key itself never appears in any response. A regex sweep over the
readiness JSON in `test_runtime_readiness_smoke.py` enforces this —
no `pplx-`, `sk-`, `xai-`, `gsk_`, or `AIzaSy...` shape ever passes
through.

## Whether Sprint-12 LLM enrichment can safely start

**Yes** — once `main_brain_id` is non-null in the panel.

The Sprint-12 enrichment pipeline (LLM-fill the `_llm_pending` fields
on ResearchDraft + FormDraft) MUST:

1. Read `/system/runtime-readiness` first.
2. Refuse to run when `main_brain_id is None` (return
   `no_ready_main_brain` with `next_action` from the panel).
3. Use whatever runtime the router picked, NOT a hardcoded
   `llama-server` / Ollama / Anthropic call.
4. For QE/Council passes, read `/system/qe-readiness` first; refuse
   to claim "council complete" when `mode != 'full'`. Run in
   degraded mode with the honest mode_reason surfaced to the
   operator.

The enrichment service does not yet exist — that's Sprint-12 PR-1.
The readiness layer is ready for it.

## Hard-rule audit (full Sprint-12A)

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push (other than the explicit Sprint-11 push earlier this session) | ✅ |
| No secrets read/printed/committed | ✅ — regex sweep enforces |
| No expensive model calls | ✅ — only HTTP probes against local ports + PATH lookups |
| API keys boolean only in response | ✅ — type-level enforcement |
| CLI auth probe doesn't spend tokens | ✅ — only checks PATH presence |
| No paid API call without ready=true | ✅ — `_classify_item` demotes role to "none" when not ready |
| QE requires ≥2 distinct ready runtimes for full mode | ✅ — `assign_qe_slots` enforces |
| No silent metered_api default | ✅ — main_brain preference_order is local-first |
| No duplicate router/provider stores | ✅ — wraps `runtime_truth_registry` |
| Phase 3 writes still blocked | ✅ — `INTEGRATIONS_PHASE2_READONLY=true` |

## Test results

| Suite | Tests | Status |
|---|---|---|
| `test_runtime_readiness.py` (PR-1+2) | 25 | ✅ pass |
| `test_qe_council_assignment.py` (PR-3) | 11 | ✅ pass |
| `test_runtime_readiness_smoke.py` (PR-5) | 18 | ✅ pass |
| Sprint-11 regression (PR-1..PR-5 + research + integrations) | 188 | ✅ pass |
| **Sprint-11 + Sprint-12A combined** | **242** | **✅ all green** |

Frontend: `npx tsc --noEmit` exit 0.

## Five commits in Sprint-12A

| Commit | PR | Headline |
|---|---|---|
| `21569fa` | PR-1 + PR-2 | Runtime + router readiness inventory |
| `e2213ab` | PR-3 | QE/Council runtime slot assignment |
| `f01a534` | PR-4 | Surface runtime + QE readiness in UI |
| `<this>` | PR-5 | Sprint-12A smoke report |

## Exact next action for Masoud

Pick **one** based on what your machine looks like:

**A. If you already have llama.cpp `llama-server` or Ollama running:**
→ Open Daena Settings → Models & Runtimes → the new "Brain readiness"
panel at the top. Confirm `main_brain` shows your local runtime as
`Ready`. Then say *"start Sprint-12 using the readiness layer"* and
PR-1 of Sprint-12 will be the LLM enrichment pass that fills the
`_llm_pending` fields on every existing ResearchDraft / FormDraft.

**B. If your local runtime is offline:**
→ Start `D:\Ideas\llama.cpp\llama-server.exe` with a GGUF in
`MODELS_ROOT\gguf\`, OR start Ollama. The panel's `next_action`
string is the exact instruction. Once the panel says `Ready`, return
to (A).

**C. If you want Perplexity for web-grounded research:**
→ Settings → Account → Provider Keys → paste a Perplexity API key.
The readiness panel will flip Perplexity to `Configured, untested`.
A future per-provider zero-cost test endpoint will flip it to
`Ready` (Sprint-12 follow-up); for now, key presence is enough for
Daena to know Perplexity is available for the `web_grounder` QE
slot.

**D. If you want to push Sprint-12A:**
→ Say *"push Sprint-12A"* and I'll fast-forward the four new commits
(`21569fa..<PR-5>`) to `origin/master`. No deploy. No migration.

## Honest status snapshot

| Layer | Status |
|---|---|
| Daena as supervised work operator (Sprint-11) | ✅ done + pushed |
| Daena as runtime-aware brain selector (Sprint-12A) | ✅ done, awaiting push |
| Daena as autonomous external actor | ❌ NOT YET (Phase 3 still blocked) |
| Daena as VP brain doing real work intelligence | ⚠️ partial — readiness layer ready; LLM enrichment is Sprint-12 |
| Production deploy | ❌ NOT YET (production migrations pending) |

Sprint-12A is the foundation for "Daena uses the right brain at the
right cost for the right job." It does NOT itself spend a single
LLM token. It tells you, honestly, what you have to work with.
