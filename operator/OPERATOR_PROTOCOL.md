# DAENA OPERATOR PROTOCOL

Authoritative behavior contract for the Daena Operator Runner. The runner (daena_operator.py / .ps1) implements
this. If code and this doc disagree, this doc wins -- fix the code.

## 1. Purpose
The Daena Operator Runner exists to CONTINUE safe Daena sprints automatically: read the active next-prompt, invoke
an available agent CLI (when explicitly enabled + verified), monitor its output, record everything, and keep going
through safe local work. It stops only for hard gates. It never exposes secrets and never fakes automation.

## 2. Input files (next-prompt priority order)
1. D:\Ideas\Daena\Doc\production-readiness\DAENA_NEXT_PROMPT.md
2. D:\Ideas\Daena\Doc\company-ops\MAS_AI_NEXT_PROMPT.md
3. D:\Ideas\Daena\Doc\production-readiness\DAENA_RESUME_PROMPT.md
The runner uses the first file that exists. On context-high or sprint-boundary, the agent is expected to refresh
DAENA_RESUME_PROMPT.md + DAENA_NEXT_PROMPT.md so the NEXT iteration resumes correctly.

## 3. Output files (all under operator/logs/)
- session_<timestamp>.log -- full redacted run transcript (heartbeats + agent stream).
- state.json -- current state-machine snapshot (state, mode, agent, loop count, timestamps).
- last_result.md -- summary of the last iteration (dry-run plan, or agent exit + tail).
- hard_gate.md -- written ONLY when a hard gate is detected; names the gate + the founder action.
- NEEDS_USER_LOOP.md -- written when no usable+enabled agent CLI exists; says manual /loop is required.

## 4. State machine
IDLE -> LOAD_PROMPT -> RUN_AGENT -> MONITOR -> PARSE_RESULT -> UPDATE_DOCS -> CONTINUE -> (loop) / DONE
Exits: HARD_GATE (gate detected, stop) and ERROR (no prompt / launch failure / unexpected).
- dry-run path: IDLE -> LOAD_PROMPT -> (plan) -> DONE. No agent. No side effects beyond logs.

## 5. Stop only for TRUE hard gates (decide + proceed on everything else)
Hard gates: secrets / backend/.env / keys / passwords, paid deploy or spend, real external sends, unsafe scans,
production deploy / DNS, destructive prod DB migration, legal/business/tax/patent decisions, public posting/
submission, deleting founder work, anything irreversible. For ALL other (safe local) work: DECIDE and PROCEED --
never ask the founder which safe step to do next (see section 13).

Gate classification -- the runner stops ONLY on TRUE_HARD_GATE, and CONTINUES on MENTION_ONLY:
- TRUE_HARD_GATE (STOP): the agent says it cannot perform the NEXT action now without a founder-only action --
  e.g. "TRUE_HARD_GATE: ...", "BLOCKED_NEEDS_FOUNDER", "I cannot proceed without {secret/deploy/send/...}",
  "needs founder approval to ...". Agents MUST emit `TRUE_HARD_GATE: <founder action needed>` when genuinely blocked.
- MENTION_ONLY (CONTINUE): the output merely references gated items or future founder actions -- "founder-gated
  items remain", "DEP-001 later", "founder should eventually ...". Mentioning a gate is NOT hitting one. The runner
  does not stop just because a report lists gated remainders; it picks the next safe step and keeps going.
The runner classifies from the AGENT'S OUTPUT (GATE_MARKERS vs MENTION_ONLY_MARKERS in daena_operator.py); it never
treats a prompt's policy text as a gate.

## 6. Sprint boundary handling
If an agent stops at a sprint boundary (clean completion, not a gate): the runner reads the next-prompt again. If
the next safe item exists, it continues (next iteration). If only hard-gated / founder items remain, it stops and
records why.

## 7. Context-high handling
The runner cannot see an agent's context window. It relies on the PROMPT CONTRACT: each prompt instructs the agent
to, when context is high, refresh DAENA_RESUME_PROMPT.md + DAENA_NEXT_PROMPT.md before yielding. The next loop
iteration then resumes from the refreshed prompt. Per-iteration wall-clock is capped by max_minutes_per_loop.

## 8. Long-running commands (tests/build)
When an agent runs a long command, the runner monitors the agent's streamed output and writes a heartbeat to
state.json every checkpoint_minutes (default 15) -- it does NOT poll tightly. A run exceeding max_minutes_per_loop
is killed and recorded as a timeout (not a gate).

## 9. Dirty tree
The runner never runs `git add -A`. Committing is the AGENT'S job under its own rules (classify, commit scoped
verified work, hold unknown-provenance, never bypass hooks). The runner only records what the agent reported.

## 10. Agent execution safety (honesty rule -- do not fake it)
- `agent_exec.enabled` defaults to FALSE. While false, the runner plans + writes NEEDS_USER_LOOP.md and exits;
  it does NOT invoke an agent.
- Enable it ONLY after verifying, by hand, that the chosen CLI runs a prompt non-interactively AND safely. Enabling
  lets the runner spend your agent quota unattended -- treat that as a deliberate cost decision.
- Even when enabled, the runner caps work with max_loops + max_minutes_per_loop, redacts secrets from all logs,
  never reads backend/.env, and never itself runs deploy/send/secret commands.

## 11. Secret handling
Every line written to a log is passed through a redactor (api keys, tokens, bearer, password, sk-..., AKIA...,
gh pat, PEM private keys -> [REDACTED]). The runner never opens or prints backend/.env or any vault file.

## 12. Limits (from config)
max_loops (hard cap on iterations), max_minutes_per_loop (per-iteration timeout), checkpoint_minutes (heartbeat
cadence). allow_sends / allow_paid_deploy / allow_secret_access are hard-false and not overridable at runtime.

## 13. Autonomous decision policy (no "founder picks" for safe work)
When multiple SAFE next steps exist, the operator/agent CHOOSES automatically by this priority -- it does NOT ask
the founder to pick, and does NOT stop to ask whether to continue / fix P1-P2 / write docs / run tests / commit
scoped safe changes / scan local projects / draft business plans / create next prompts:
  1 P0 security/data-loss/auth/deploy blockers. 2 self-start runner reliability. 3 closed-beta readiness blockers.
  4 production readiness / observability / tracing / rollback / smoke. 5 deployment dry-run + OAuth/Gmail checklist.
  6 company revenue path. 7 hackathon/grant/customer opportunity. 8 code review + cleanup. 9 UX polish.
  10 speculative feature.
Tie-break: highest revenue impact > fastest path to closed beta > lowest risk > strongest test coverage >
reduces founder workload > improves Daena's core VP / company-OS vision.
State the decision as: "DECISION: I choose <step> because <reason>. Proceeding." NEVER "Founder picks." Founder
approval is required ONLY for the TRUE hard gates in section 5.

MYTHOS / debate (only for risky architecture/security/production/business/product-direction choices -- NOT tiny
fixture/doc fixes): run a short internal debate, written into the DOC (not chat): MYTHOS (safest codebase-grounded
path + risk/rollback) / Codex view (architecture, regression, test risk) / Gemini view (product/UX/ecosystem/
business) / Decision (selected path, why, rejected alternatives, tests, rollback). Use real Codex/Gemini/Perplexity
tools if available + safe; otherwise simulate and label SIMULATED_DEBATE.
