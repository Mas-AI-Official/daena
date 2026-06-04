# Daena Operator Runner

A local, file-based supervisor that continues safe Daena sprints by reading the active next-prompt, optionally
invoking an available agent CLI, recording everything to logs, and stopping only for hard gates. It exists because
prompts alone cannot keep an agent working after a session ends, and `/loop` / ScheduleWakeup are user/session
bound. The runner is the missing self-startable continuation layer -- as far as it can SAFELY be one.

## TL;DR self-start status (this machine, 2026-06-04)
PARTIAL. `claude`, `codex`, `gemini` and `python` are all installed, so the supervisor runs. BUT no agent CLI is
yet verified for safe autonomous TOOL execution, so `agent_exec.enabled` defaults to **false**: the runner plans
and writes `logs/NEEDS_USER_LOOP.md` instead of invoking an agent. Flip the flag only after you verify a CLI by
hand (see below). It will never fake automation. Details: `AVAILABLE_TOOLS.md`.

## Run it
```
cd D:\Ideas\Daena\operator

# safe plan, never invokes an agent (default):
python daena_operator.py --dry-run
.\daena_operator.ps1 -DryRun

# one iteration / bounded loop (only invokes an agent if agent_exec.enabled = true):
python daena_operator.py --once
python daena_operator.py --loop 3
.\daena_operator.ps1 -Loop 3
```
The `.ps1` launcher delegates to the Python supervisor when Python is present; if not, it runs a native
PowerShell dry-run that also never invokes an agent.

## Files
- `daena_operator.py` -- the supervisor (engine). stdlib only, no deps.
- `daena_operator.ps1` -- Windows launcher (delegates to Python; native dry-run fallback).
- `operator_config.example.json` -- template config. Copy to `operator_config.json` (gitignored) for real values.
- `OPERATOR_PROTOCOL.md` -- the authoritative behavior contract (state machine, gates, secret handling).
- `AVAILABLE_TOOLS.md` -- Phase-1 tool detection + self-start classification.
- `logs/` -- runtime output (gitignored): `session_<ts>.log`, `state.json`, `last_result.md`, `hard_gate.md`,
  `NEEDS_USER_LOOP.md`.

## How it decides
Next-prompt priority: `DAENA_NEXT_PROMPT.md` -> `MAS_AI_NEXT_PROMPT.md` -> `DAENA_RESUME_PROMPT.md` (first that
exists). State machine: IDLE -> LOAD_PROMPT -> RUN_AGENT -> MONITOR -> PARSE_RESULT -> UPDATE_DOCS -> CONTINUE ->
DONE, with HARD_GATE / ERROR exits. It stops ONLY on a TRUE_HARD_GATE (the agent says it cannot do the next action
without a founder-only action); it CONTINUES when output merely mentions gated items (MENTION_ONLY -- e.g. "DEP-001
later", "founder-gated items remain"). For safe work it chooses the next step automatically by the priority order
in OPERATOR_PROTOCOL.md section 13 -- it never asks the founder to pick a safe next step. After an agent run it
SELF-VERIFIES (post_agent_verify, section 14): runs the right tests/build/smoke for whatever the agent changed and
commits the scoped files if green (headless agents can edit but can't run pytest) -- so --loop advances without an
interactive turn. Red verification holds the changes (no commit) and stops.

## Enabling real autonomous runs (deliberate cost decision)
1. Verify by hand that your chosen CLI runs a prompt non-interactively and safely, e.g.
   `claude -p "say hello"` or `codex exec "say hello" --skip-git-repo-check`. Confirm it does not require
   interactive permission prompts to do useful work, and that auth is valid.
2. Copy `operator_config.example.json` -> `operator_config.json`, set `agent_exec.enabled: true`, keep
   `agent_order` with your verified CLI first.
3. Re-check the caps: `max_loops`, `max_minutes_per_loop`. Enabling lets the runner spend your agent quota
   unattended -- the caps are your budget guard.
4. `python daena_operator.py --loop 3`.

## Hard limits (always on)
Never exposes secrets (all log lines redacted; never reads backend/.env). Never sends, deploys, spends, submits,
or deletes founder work. `allow_sends` / `allow_paid_deploy` / `allow_secret_access` are hard-false. The runner
itself never runs deploy/send/secret commands; it only orchestrates agents + monitors + records.
