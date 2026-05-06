# Sprint-12 PR-0 — Runtime ready-or-fix report

**Sprint:** DAENA-FULL-POTENTIAL-ACCELERATION-SPRINT-12
**PR:** 0 of 6
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Decide programmatically — without asking Masoud to inspect the
panel — whether Sprint-12 brain enrichment can safely run, OR what
the exact local blocker is. The answer comes from the readiness
endpoints shipped in Sprint-12A, not from a hardcoded `llama-server`
assumption.

## How verified

1. Backend started locally on `127.0.0.1:8000` via the
   `.venv`-pinned uvicorn launch (no reload, no production mode).
2. Health probed: `essentials_ready=true, seed_phase=complete`.
3. Dev JWT minted in-process from the existing seeded user (no
   secrets read from `.env`, no new credentials persisted).
4. Three readiness endpoints called with the JWT:
   * `GET /api/v1/system/runtime-readiness?refresh=true`
   * `GET /api/v1/system/router-readiness`
   * `GET /api/v1/system/qe-readiness`

No paid API call fired. No provider key value was logged.

## Result: GREEN — Sprint-12 enrichment may proceed

### Router summary

| Slot | Runtime picked | Cost class | Note |
|---|---|---|---|
| `main_brain_id` | `ollama_backend` | `free_local` | Local Ollama, 1 model loaded, callable |
| `coder_id` | `cli_claude` | `subscription` | Claude Code CLI on PATH |
| `researcher_id` | `cli_gemini` | `subscription` | Gemini CLI on PATH |
| `web_grounding_id` | `None` | — | Perplexity key configured, but `configured_untested` until per-provider zero-cost test ships (intentional honesty floor) |
| `qe_mode` | `full` | — | 3 reviewers ready: `cli_claude`, `cli_codex`, `ollama_backend` |
| `next_action` | `Brain-enrichment is unblocked. Sprint-12 PR-1 may proceed.` | — | — |

### QE/Council slot assignment

| Slot | Runtime | Source |
|---|---|---|
| `local_reasoner` | `ollama_backend` | preferred |
| `code_reviewer` | `cli_claude` | preferred |
| `web_grounder` | *(unfilled)* | — |
| `risk_reviewer` | `cli_codex` | fallback_role |
| `final_synthesizer` | `cli_gemini` | fallback_role |

`mode=full`. `distinct_runtime_ids=4`. The web_grounder slot is
honestly unfilled — Perplexity stays at `configured_untested`
until the per-provider zero-cost test endpoint is added (deferred
Sprint-12 follow-up; not a blocker for PR-1/PR-2 enrichment).

## Ready inventory (zero-cost ladder)

| Runtime | State | Cost class | Role |
|---|---|---|---|
| `cli_claude` | ready | subscription | coder |
| `cli_codex` | ready | subscription | coder |
| `cli_gemini` | ready | subscription | researcher |
| `cli_ollama` | ready | free_local | fallback |
| `ollama_backend` | ready | free_local | main_brain |
| `ollama_windows` | ready | free_local | fallback |

## Not-ready inventory (honest reasons)

| Runtime | State | Reason |
|---|---|---|
| `vllm_configured` | detected_offline | All connection attempts failed (llama-server not running on `:8080`) |
| `provider_perplexity` | configured_untested | API key configured, but no zero-cost health check has been run |
| `provider_gemini` | configured_untested | API key configured, but no zero-cost health check has been run |
| `provider_groq` | configured_untested | API key configured, but no zero-cost health check has been run |
| `provider_openai` | not_configured | API key not configured |
| `provider_anthropic` | not_configured | API key not configured |
| `provider_openrouter` | not_configured | API key not configured |
| `provider_together` | not_configured | API key not configured |

The `metered_api` providers stay in their honest states because
the readiness ladder explicitly refuses to call them. **No silent
spend can occur** during Sprint-12 enrichment based on this
snapshot.

## What this PR did NOT change

* No code edits — this PR was a pure verification step.
* No commit — nothing to commit (report-only is folded into
  Sprint-12 PR-1 commit per "commit only if code/docs changed").
* No backend behavior change.
* No provider key was read or printed.
* No paid API call was fired.

## What unblocked

PR-1 (`feat: enrich research drafts with routed brain`) may now
proceed. The enrichment service will:

1. Read `/system/runtime-readiness` first.
2. Refuse if `main_brain_id is None`.
3. Use whatever `main_brain_id` returns (`ollama_backend` today,
   `vllm_configured` tomorrow if the operator starts llama-server).
4. Audit every router decision through the existing
   `integration.tool_invocation` audit pattern.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ (PR-0 is local verify only) |
| No secrets printed/read/committed | ✅ |
| No paid API call | ✅ — only local HTTP probes + PATH lookups |
| Local LLM only if main_brain_id ready | ✅ — `ollama_backend` is the only `free_local` `ready` entry with a model |
| Phase 3 writes blocked | ✅ — `INTEGRATIONS_PHASE2_READONLY=true` confirmed at startup |
| No external action | ✅ |

## Next: PR-1 LLM enrich ResearchDraft

Field-level enrichment of `ResearchDraft.structured_payload` using
the routed `main_brain_id`. Output `confidence` + `needs_review`
on every filled field.
