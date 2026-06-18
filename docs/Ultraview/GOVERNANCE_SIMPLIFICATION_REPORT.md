# Governance Simplification Report

Date: 2026-04-30

## Decision

Founder-facing governance should expose only:

1. Unleashed
2. Balanced
3. Governed

T0/T1/T2/T3/T4 can exist internally for policy/audit/debugging, but they should not be the main operator control. The current UI overexplains internals and makes governance look more complex than the founder wants.

## Current Evidence

- Header already shows a 3-mode surface (`UNLEASHED`, standard/balanced, `QE` nearby for reasoning).
- Existing AGI status text was misleading because it represented autopilot preference, not backend health.
- Header text was changed to `AUTOPILOT ON/OFF` with a title clarifying backend health belongs to the connection indicator.

## Policy Rules Standard

Policy save is only real if it does all of this:

- Persist the natural-language rule.
- Compile it through the Plain-English Policy Compiler.
- Write the structured policy under backend policy config.
- Reload or affect the runtime governance loop.
- Emit an audit log event.
- Show active policy status after reload.

If any of those steps is missing, the UI must say `Not active in backend loop` instead of implying enforcement.

## Recommendation

- Keep the 3-mode governance control in normal settings.
- Move tier internals under `Advanced`.
- Add a policy activation badge sourced from backend compile/load status.
- Do not show a green policy state unless SecurityGate has loaded the compiled policy.
