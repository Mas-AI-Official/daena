# PR-5 — Runtime autofix proposals

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 5 of 7
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Daena should *propose* fixes for runtime readiness, not run anything
that touches the operator's machine without consent. Every proposal
is either a copyable command or a deep link to a settings page —
never an "auto-execute" button.

## What's new

The `/system/morning-readiness` response now carries an
`autofix_proposals: AutofixProposal[]` array. Each proposal:

```ts
interface AutofixProposal {
  id: string                  // stable id for dedupe + UI key
  title: string               // short headline
  rationale: string           // one-line "why"
  copy_command: string | null // operator pastes into terminal
  deep_link: string | null    // frontend route
  severity: 'info' | 'warn' | 'blocker'
}
```

The shape is **locked**: there is no `auto_execute` / `run_now` /
`apply` / `execute` field. The frontend renders a Copy button or a
Router link, never a "run on my machine" action.

## Mapping (deterministic)

| Detected gap | Proposal |
|---|---|
| Ollama not running | `copy_command: "ollama serve"` |
| llama-server / vLLM offline | `copy_command: "powershell ... start-llama-server.ps1 -Model qwen3-8b"` |
| Claude Code CLI missing/unauthenticated | `copy_command: "npm install -g @anthropic-ai/claude-code && claude login"` |
| Codex CLI missing/unauthenticated | `copy_command: "npm install -g @openai/codex && codex login"` |
| Gemini CLI missing/unauthenticated | `copy_command: "npm install -g @google/gemini-cli && gemini login"` |
| API key not configured (OpenAI / Anthropic / etc.) | `deep_link: "/settings/connections"` (no command — secret entry happens through the vault) |
| Provider configured-but-untested | `deep_link: "/settings/models-runtimes"` |

## Frontend

`MorningReadinessPanel.tsx` gained an "Autofix proposals" section
under the blockers list. Each row renders:
- Title + rationale
- A monospaced `<code>` pill for the command (read-only) + Copy button
- An "Open" deep-link button (when relevant)

The Copy button uses `navigator.clipboard.writeText` and surfaces a
toast. There is no "execute on my machine" code path — Daena cannot
and will not auto-run shell commands.

## Hard rules — encoded + tested

| Rule | Status |
|---|---|
| Daena proposes; never auto-executes | ✅ — shape locked; `test_autofix_keys_locked` asserts no `auto_execute / run_now / apply / execute` field |
| No automatic OS install | ✅ — buttons are Copy + Open Settings only |
| No secret entry in commands | ✅ — API key flow goes through `/settings/connections` vault deep-link, never a copyable command containing a secret |
| Stable proposal id | ✅ — `id` is deterministic from runtime id |
| Multiple blockers map to multiple proposals | ✅ — independent rules per row |

## Files

```
modified:   backend/app/api/v1/system_self_diagnostic.py             (+115 lines: autofix proposal builder)
modified:   backend/tests/test_morning_readiness_endpoint.py         (+78 lines: TestAutofixProposals)
modified:   frontend/src/components/common/MorningReadinessPanel.tsx (+90 lines: AutofixProposals component + Copy button)
new:        docs/Ultraview/PR_RUNTIME_AUTOFIX_PROPOSALS_REPORT.md
```

## Tests

**Backend:** 121/121 pass on the Sprint-12 + PR-1..PR-5 fast subset.

```
tests/test_morning_readiness_endpoint.py     5  (1 new = TestAutofixProposals)
tests/test_morning_route_contract.py        13
tests/test_chat_vp_preflight_contract.py     5
tests/test_vp_work_commands.py              25
tests/test_draft_enrichment.py              24
tests/test_draft_qe_review.py               10
tests/test_workstream_from_draft.py         11
tests/test_sprint12_full_smoke.py           28
                                          ────
                                           121
```

The new test pins the proposal shape:

1. Each proposal carries exactly the six allowed keys.
2. No `auto_execute`, `run_now`, `apply`, or `execute` field appears.
3. Ollama proposal surfaces `copy_command="ollama serve"`.
4. OpenAI key proposal carries `deep_link="/settings/connections"` and
   `copy_command=null` (no secret in a copyable command).

**Frontend:** `npx tsc --noEmit` exit 0.

## What this PR does NOT do

* Does NOT call `child_process` or any shell. No backend code path
  exists that runs an OS command from a proposal.
* Does NOT install npm packages. The proposal copy commands are
  strings; the operator decides whether to run them.
* Does NOT auto-fill or auto-test API keys. The deep-link surface
  routes the operator to the vault flow.

## Next: PR-6 — End-to-end NUser browser smoke
