# Soul Wiring + Token Settings — Status / Handoff

Last updated: 2026-06-16. Owner: founder (Masoud). Survives session compaction.

## What this covers
Wiring the upgraded Daena soul (Director posture, anti-sycophancy, Fable-5
cognition) to ALL agent paths, plus best token settings. Deploy is BLOCKED on
one thing only: gcloud 2FA (see "The one unblock").

## DONE (edits applied, compile-verified via py_compile — NOT yet committed, NOT deployed)
5 surgical edits, all additive + degrade-on-exception, all confirmed to compile:

1. `backend/app/services/soul_engine.py`
   New `SoulEngine.build_agent_system_prompt(governance_mode, *, department,
   sub_capability, company_context)` — single composition point:
   soul + tagged role prompt. Backward-compatible. (No `is_founder` param yet —
   see DEFERRED.)

2. `backend/app/services/swarm/executor.py`  ← the real "wire to ALL agents" win
   `_collect_output` now prepends the full souled system prompt
   (via build_agent_system_prompt) to each swarm sub-agent task. This is the
   live autonomous swarm path, so the soul + Fable-5 cognition + anti-sycophancy
   now reach swarm sub-agents and every model the swarm routes to. Nested
   try/except degrades to the prior bare get_agent_prompt on any failure.

3. `backend/app/services/departments/department_agent.py`
   Docstring-only truthing of `build_role_prompt` (it does NOT include the soul).
   Behavior intentionally unchanged: gitnexus proved this method test-only;
   changing behavior would risk the test for zero live gain.

4. `backend/app/services/providers/anthropic.py`  ← the big token-burn win
   `_build_payload` now emits `system` as a cached block:
   `[{"type":"text","text":<soul>,"cache_control":{"type":"ephemeral"}}]`.
   The soul prefix is large + identical across same-dept/same-governance
   requests, so repeats bill at the ~10% cache-read rate. Ephemeral caching is
   GA (grounded via Context7 against anthropic-sdk-python) — no beta header,
   block form accepted anywhere the string is, under-min blocks served uncached
   (never errors). gitnexus impact on `_build_payload`: LOW, 0 callers.

5. `backend/app/services/providers/anthropic.py`  <- the "highest level" model + cognition upgrade (2026-06-16)
   Catalog + payload rewritten to the grounded current Anthropic catalog and
   top-tier cognition. All additive, py_compile OK.
   - `_DEFAULT_MODEL` "claude-sonnet-4-7-max" -> "claude-opus-4-8". The OLD
     default was an INVALID API model id (no such model in the grounded Anthropic
     catalog) -- the real API would 400 it. So this is a latent-bug FIX, not just
     an upgrade. Corroborated by claude_cli.py:112 ("rolled back from explicit
     claude-sonnet-4-7-max").
   - `_MODELS` rebuilt to valid current ids, real pricing, no date suffixes:
     opus-4-8 (priority tag), fable-5 (detection/security/frontier), opus-4-7,
     sonnet-4-6, haiku-4-5. This feeds the layer-1 cost path (real ModelInfo
     pricing), so opus-4-8/fable-5 bill correctly with NO shadow-map edit.
   - Adaptive-thinking tier `_ADAPTIVE_THINKING_MODELS = {opus-4-8, opus-4-7,
     fable-5}`. For these, `_build_payload` sends thinking={"type":"adaptive"} +
     output_config.effort and DROPS temperature/top_p (the API 400s on sampling
     params for this tier). Cheaper/legacy models keep explicit sampling.
   - Effort per model (`_EFFORT_BY_MODEL`): opus = "xhigh" (Claude Code's own
     default; deliberately NOT "max" until routing reliably delegates cheap work
     -- the open orchestration gap below); fable-5 = "max" (founder direction:
     do NOT downgrade Fable; it is the detection/security model). Flip opus to
     "max" once delegation is proven.
   RESOLVED (this window): added `_ADAPTIVE_THINKING_MIN_MAX_TOKENS = 16384`. For
   the adaptive tier ONLY, `_build_payload` floors max_tokens at 16384 via
   max(request.max_tokens, 16384) so thinking tokens cannot starve the visible
   answer (worst case ~$0.41/call at Opus 4.8 out pricing). Cheaper/legacy models
   keep the caller's value verbatim -- zero blast radius outside the apex tier.
   RUNTIME-VERIFIED (not just py_compile): called _build_payload directly --
   opus-4-8 -> thinking=adaptive, output_config.effort=xhigh, max_tokens=16384, NO
   temperature/top_p; fable-5 -> same but effort=max; sonnet-4-6 -> classic
   sampling (temperature+top_p, max_tokens=2048, no thinking). The apex tier no
   longer sends the sampling params that 400, and the default model is now valid.

## Two deploy lanes (they are NOT the same image)
- LANE A — "soul-only clean": build from HEAD 443ec52 + overlay soul MARKDOWN
  only. Delivers the upgraded persona/cognition to the EXISTING chat-path soul
  injection (chat_orchestrator.stream_reply ~L708). Ready; blocked on 2FA.
  DOES NOT carry edits 1/2/4 (those are Python, not markdown).
- LANE B — code wiring + caching + MODEL UPGRADE: edits 1+2+3+4 above. Ship as a
  FOCUSED commit of exactly those 4 files, OR apply deploy/lane-b-settings-upgrade.patch
  (staged 2026-06-16: 331 lines, exactly 4 files, ZERO of the 197 dirty-tree files,
  excludes HANDS-OFF scan_workflow.py) onto a clean HEAD worktree. Needs a QA pass
  (swarm path + provider generate() smoke test) before commit; payloads already
  runtime-verified (see DONE #5).

GROUNDED 2026-06-16 (corrects the earlier plan): `git show HEAD:anthropic.py`
proves the DEPLOYED code has _DEFAULT_MODEL="claude-sonnet-4-7-max" (INVALID id)
and a FULLY STALE catalog (sonnet-4-7-max, opus-4-20250514, sonnet-4-20250514,
haiku-4-5-20251001) -- ZERO current models. So the "highest-level" model upgrade
the founder asked for lives ENTIRELY in Lane B (Python). LANE A ALONE WOULD NOT
DELIVER IT -- it ships persona only. REVISED RECOMMENDATION: do NOT ship Lane A
alone. Ship a single clean-HEAD build that overlays soul markdown AND applies the
Lane B patch (one image, both persona + model upgrade), or ship Lane B then Lane A.
Working tree is 197 dirty (NOT 110); never blind-deploy it.

## The one unblock (everything deploy waits on this)
RECONFIRMED 2026-06-16: `gcloud auth print-access-token` ERRORS (token mint fails)
-> the 2SV wall is still up. Active account IS masoud.masoori@mas-ai.co but active
project is `mas-ai-kya` (config daena-train-gcp), NOT daena-467315 -- deploy MUST
pin --project=daena-467315.
gcloud user auth hits a 2SV reauth wall every few hours -> non-interactive
`gcloud builds submit` fails. Fix, run ONCE interactively:
    gcloud auth login masoud.masoori@mas-ai.co
    powershell -ExecutionPolicy Bypass -File .\deploy\setup-deploy-sa.ps1
Then deploys are hands-off (service account, no 2FA). Rollback: deploy/ROLLBACK.md
(instant: daena-v2-00003-7zx=100). I will NOT enter your Google credentials/2FA,
and will NOT claim deploy success until a NEW daena-v2 revision is proven live.

## DEFERRED (own design pass — do NOT half-do)
- Founder-scoped vs universal SPLIT: foundation.md L13-17/L48-68 bakes founder
  identity (Masoud by name, MAS-AI loyalty) into the FIRST always-loaded soul
  file. Soul is GLOBAL (lru_cache) -> brutal/call-out-Masoud + MAS-AI loyalty
  LEAK to customer tenants. Split a UNIVERSAL anti-sycophancy/cognitive core
  (all tenants, Director posture toward THE USER) from a FOUNDER-gated pack;
  add `is_founder` to build_agent_system_prompt only when implementing this.
- Stale model catalog in anthropic.py: RESOLVED this session (see DONE #5).
  Grounded against the in-context claude-api skill catalog, not a live call.
  Belt-and-suspenders: hit GET /v1/models once to confirm opus-4-8 / fable-5 /
  opus-4-7 / sonnet-4-6 / haiku-4-5 are all live for THIS key. RESIDUAL:
  - Shadow cost map (chat_orchestrator.py:185 `_SHADOW_COSTS`) still prices the
    claude-code CLI runtime at Sonnet-4.7-max-equiv ($3/$15). That map is layer-2
    (CLI/local pseudo-ids only); the httpx API path bills via layer-1 (real
    `_MODELS`), so opus-4-8/fable-5 ARE correct. But if the CLI runtime now
    orchestrates at the opus-4-8 tier, bump `claude-code`/`claude_code` to
    ($5/$25) for an honest "what it would cost" meter. Flagged, NOT changed
    (separate money-meter call; my edit did not break it).
  - Other providers' `_DEFAULT_MODEL` (openai/google/etc.) may still be stale --
    out of scope for the Anthropic upgrade; sweep separately.
- Hardcoded temp=0.7 / max_tokens=2048 (chat_orchestrator L2287-88 + council);
  no thinking/effort param. Tuning + cost call -> recommend, did not silently
  change a production money path. Plumbing thinking/effort needs a GenerateRequest
  schema change (ripples) -> its own commit.
- Front-end rules: verify (don't rewrite) D:\agents\rules\rules.src.md has
  Director/Fable/anti-sycophancy/token-discipline, then rules-sync.py --build
  (never write global CLAUDE.md directly).

## Orchestration audit -- PARTIAL (workflow died on session limit; resume after 2:10pm Toronto)
The founder's core question: does "the higher-level model orchestrate the rest +
drive to done"? The audit workflow MAPPED the components but the VERIFY +
SYNTHESIZE stages died on the session usage limit, so these 11 are CANDIDATE
gaps, NOT confirmed (confirmed_count:0 = unverified, NOT "no gaps found"):
  1. SwarmPlanner._decompose_with_llm / decompose_and_route -- weak higher-level
     model orchestration of the plan.
  2. SwarmExecutor._try_runtime -- no completion verification of a subtask.
  3. RuntimeRegistry.select_runtime -- model selection looks like flat scoring,
     not hierarchical (apex delegates to cheaper workers).
  4. chat_orchestrator swarm caller / SwarmExecutor.execute_plan -- no result
     aggregation / final synthesis step.
  5. AutopilotController._continuation_loop -- "drive to completion" gap.
  6. SwarmExecutor.execute_plan / _collect_output -- subtask results never feed
     downstream subtasks.
  7. SwarmExecutor governance.evaluate + _solicit_required_approvers -- approver
     gates (HANDS-OFF: do not refactor governance).
  8. DaenaVP wiring in chat_orchestrator (~Stage 2.8) -- the one component that
     COULD be the supervisor.
  9. SwarmExecutor._execute_subtask / SwarmPlanner fallback -- escalation on
     failure is a single step, not a ladder.
  10. cost recording / AutopilotController ceiling / RuntimeRegistry cost filter
      -- cross-subtask cost ceiling missing.
  11. chat_orchestrator -- TWO parallel divergent orchestration paths (DaenaVP
      block vs agent-loop SwarmPlanner block).
Read so far: Daena HAS a would-be supervisor (DaenaVP) but routing is likely
flat, there are two divergent paths, and the swarm lacks aggregation /
completion-verification / cost-ceiling -- i.e. the pattern the founder asked for
is PARTIAL, not fully realized. UNVERIFIED until the resume below.
RESUME: Workflow({scriptPath: "C:\Users\masou\.claude\projects\D--Ideas\200b3e84-7e06-4eb6-8adf-af2e512ae390\workflows\scripts\daena-orchestration-audit-wf_34db74d7-07c.js", resumeFromRunId: "wf_34db74d7-07c"})
after 2:10pm America/Toronto. Cached map/gap agents return instantly; only the
limit-failed agents re-run. THEN strengthen with safe-additive edits only
(supervisor delegates to cheaper workers + aggregation + completion-verification
+ cost ceiling). HANDS-OFF governance/security/scan.

## Guardrails in force
HANDS OFF security/governance/scan/asset-shield (scan_workflow.py is in the
dirty tree — must not ride any deploy). Never --no-verify. Never commit on red.
Editing soul_engine needs gitnexus impact first (done, LOW). Soul is gitignored
by design.
