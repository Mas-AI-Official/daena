# PR-1 — Real chat VP-command integration

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 1 of 7
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Wire `/api/v1/vp-commands` into the real Daena chat. The operator can
type natural English ("review my drafts", "create a work plan from
draft <id>", "what should I do next?") in the normal chat box and
Daena renders a structured VP-command card. Unrecognized chat falls
through to the LLM stream as before.

## Architecture

Sprint-12 PR-5 already shipped the deterministic regex parser at
`POST /api/v1/vp-commands`. PR-1 closes the loop by adding a chat
preflight on the frontend.

```
[ChatInput] → sendMessageStream(content)
                │
                ▼
       ┌────────────────────────────┐
       │ tryVPCommandPreflight       │   POST /vp-commands
       │ (silent, 60s timeout)       │ ──────────────────► [vp_commands.py]
       └────────────────────────────┘                       (regex parser
                │                                            + service runners)
   ┌────────────┴───────────────┐
   │ intent != "unrecognized"   │
   ▼                            ▼
 render VPCommandCard      fall through to existing
 + skip LLM                 SSE LLM stream
```

The preflight is **silent on failure**: any 401 / 5xx / network error
silently falls through to the LLM so the chat remains useful even if
`/vp-commands` is unavailable.

## Files

```
new:        frontend/src/components/chat/VPCommandCard.tsx     (267 lines)
new:        backend/tests/test_chat_vp_preflight_contract.py   (114 lines, 5 tests)
modified:   frontend/src/types/api.ts                          (+18 lines: VPCommandResult + MessageResponse field)
modified:   frontend/src/stores/chatStore.ts                   (+74 lines: tryVPCommandPreflight + integration)
modified:   frontend/src/components/chat/MessageBubble.tsx     (+6 lines: render VPCommandCard when present)
modified:   backend/app/services/vp_work_commands.py           (+1 phrase: "what is next" → next_steps)
new:        docs/Ultraview/PR_CHAT_VP_COMMAND_INTEGRATION_REPORT.md
```

## What Daena now understands in chat

| Operator types | Intent | Card rendered |
|---|---|---|
| "Daena, review my drafts" / "show my drafts" | `review_drafts` | research + form draft lists with deep-links |
| "What should I do next?" / "what is next" / "what's next" / "next step" | `next_steps` | open workstreams with next-step text |
| "Enrich draft <id>" | `enrich_draft` | refusal-code or "Enriched ✓" |
| "Run council on draft <id>" / "QE review <id>" | `qe_review_draft` | mode (full/degraded/unavailable) + reviewer count |
| "Create a work plan from draft <id>" / "Promote this draft to a workstream" | `create_workstream_from_draft` | new workstream id + next-step + Open link |
| "Which department should handle draft <id>?" | `which_department` | routed department + reason pill |
| anything else | `unrecognized` | fall through to LLM (no card) |

## Card states (visible to the operator)

- **Done (green pill)** -- `success=true`, summary + intent-specific body, optional next-action footer.
- **Need a draft id (amber pill)** -- `needs_disambiguation=true`, summary explains what's missing.
- **Refused (red pill)** -- backend refused (no main brain ready, metered API not allowed, etc.); the verbatim `next_action` text is rendered so the operator sees the exact missing piece.
- **Unrecognized** -- never rendered; falls through to LLM.

## Hard-rule audit

| Rule | Status |
|---|---|
| Deterministic backend state (regex parser, no LLM for parsing) | ✅ — backend `parse_command` unchanged |
| Tenant + user scoped | ✅ — backend run_command unchanged |
| Runtime not ready -> exact missing string surfaces in chat | ✅ — `result.next_action` rendered verbatim by VPCommandCard |
| No external action | ✅ — card is read-only; deep-links go to local pages only |
| No /submit /send /apply /post /publish endpoint | ✅ — endpoint stays `/vp-commands` |
| LLM remains the safety net | ✅ — silent fallback on any preflight error |
| Card never shows for unrecognized chat | ✅ — `intent === "unrecognized"` returns null from preflight |
| No secrets read/printed/committed | ✅ |
| Phase 3 writes blocked | ✅ |

## Tests

**Backend:** 103 / 103 pass on the Sprint-12 + new contract subset.

```
tests/test_chat_vp_preflight_contract.py  5 (NEW)
tests/test_vp_work_commands.py           25
tests/test_draft_enrichment.py           24
tests/test_draft_qe_review.py            10
tests/test_workstream_from_draft.py      11
tests/test_sprint12_full_smoke.py        28
                                       ────
                                        103
```

The new contract test pins the chat-preflight contract:

1. `hello daena` -> `intent="unrecognized"` (so chat falls through to LLM)
2. `review my drafts` -> `intent="review_drafts"`
3. `what is next` / `what's next` / `what should I do next?` -> `intent="next_steps"`
4. `CommandResult` exposes all six fields the frontend reads
5. `/vp-commands` is mounted under the v1 router

**Frontend:** `npx tsc --noEmit` exit 0.

## What this PR does NOT do

* Does not deeply integrate into `chat_orchestrator.py`. The orchestrator stays untouched -- the preflight is a clean front-of-pipeline gate. If the regex parser ever needs LLM-assisted disambiguation, that would be a separate PR.
* Does not persist VP-command messages to the chat session DB. Cards are ephemeral in the chat history (the underlying state changes are persisted by the actual service layer, e.g. workstream creation, audit ledger). Persisting cards is a future polish PR.
* Does not stream council/QE-review progress. The card waits for the full backend response before rendering. Council reviews can take several seconds; that's acceptable for a card render but a streaming variant could come later.

## Live UX

Operator types in the chat: **"create a work plan from draft a6787a57"**

Daena renders (without firing the LLM):

```
┌─ Create workstream                           [Done ✓] ─┐
│                                                        │
│ Workstream d8e4e264 created -- next: tailor resume to  │
│ their stack                                            │
│                                                        │
│ ┌──────────────────────────┐                           │
│ │ Workstream                │                           │
│ │ d8e4e26                   │  [ Open ↗ ]              │
│ │ Next: tailor resume to    │                           │
│ │ their stack               │                           │
│ └──────────────────────────┘                           │
└────────────────────────────────────────────────────────┘
```

## Next: PR-2 — Frontend/backend sync hardening
