# PR-DAENA-SELF-DIAGNOSTIC-CHAT-INTEGRATION -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-2 of 7)

---

## 1. Goal

When Masoud asks Daena in chat:

* "are you ok?"
* "what's broken?"
* "why 0 callable?"
* "fix yourself?"

She answers from the deterministic `/system/self-diagnostic` snapshot
(Sprint-6 PR-7) instead of paying an LLM call to invent an answer.
Her response always carries the same safety boundary so the operator
knows she diagnoses but does not modify.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Diagnose only, no fixes | YES -- advisor never calls executors / settings writers / migrations / process killers; pinned by source-level static check that the orchestrator hook `return`s before reaching Stage 1 |
| No OS / cloud / secrets modifications | YES -- no `subprocess`, no `os.system`, no settings writes |
| No external network | YES -- advisor reuses the diagnostic stack which is loopback-only |
| No Phase 3 writes | YES -- short-circuit returns BEFORE the orchestrator's tool-call / executor stages |
| No secret substring in formatted answer | YES -- pinned by `test_formatter_does_not_leak_when_payload_contains_secret_shaped_strings` against 12 forbidden tokens |
| Graceful fallback if diagnostic stack throws | YES -- pinned by `test_gather_and_compose_returns_fallback_when_stack_imports_blow` |
| Hook must NEVER raise into chat | YES -- defensive try/except around the hook; failure logs and falls through to the normal pipeline |
| Persisted as a normal ASSISTANT turn | YES -- `self._chat.add_message(role="ASSISTANT", model_used="daena-self-diagnostic")` so chat history stays honest |

---

## 3. Surface area

### Backend

#### `backend/app/services/self_diagnostic_advisor.py` (NEW, ~210 LOC)

Pure-function service:

* `is_self_diagnostic_question(message: str) -> bool` -- regex
  classifier matching 35+ operator phrasings (parametrized in the
  test). Tightened so "what's wrong with this code?" / "diagnose
  this error trace" do NOT match.
* `compose_answer_text(payload) -> str` -- markdown formatter,
  deterministic, caps recommended actions at 3.
* `gather_and_compose(db, tenant_id) -> str` -- runs the existing
  diagnostic checks via lazy import + `asyncio.gather`, returns
  `_FALLBACK_RESPONSE` on any exception.
* `SAFETY_BOUNDARY` -- the verbatim "I can diagnose; I need approval
  to modify." string the response always ends with.

#### `backend/app/services/chat_orchestrator.py` (MODIFIED, +47 LOC)

Inserted Stage 0c short-circuit right after Stage 0b SecurityGate
and BEFORE Stage 1 (Load session + context):

* SecurityGate (shield + injection) still runs first -- a malicious
  "are you ok? <prompt-injection-payload>" still gets caught.
* When `is_self_diagnostic_question(user_content)` is True:
  - Run `gather_and_compose(db, tenant_id)` (no LLM).
  - Stream the response in 64-char chunks via `{"type": "chunk", ...}`.
  - Persist as ASSISTANT turn (provider="daena-internal",
    model_used="daena-self-diagnostic").
  - Yield `{"type": "done", "data": {"self_diagnostic": True}}`.
  - `return`.
* Defensively wrapped: any failure logs and falls through to the
  normal pipeline, so the chat NEVER crashes on a self-diagnostic ask.

### Tests

#### `backend/tests/test_self_diagnostic_advisor.py` (NEW, 53 tests)

1. **Intent classifier** -- 35 parametrized positive matches
   ("are you ok?", "are you alive", "why 0 callable?", "fix yourself",
   "system health", "diagnose yourself", etc.).
2. **Intent classifier negative** -- 9 parametrized rejections
   ("what's wrong with this code?", "scan https://...", "rm -rf",
   "list files in /tmp", empty/whitespace strings, etc.).
3. **Formatter shape** -- markdown headers, overall pill, top
   blockers, recommended actions, ends with SAFETY_BOUNDARY.
4. **Formatter caps actions at 3** -- pinned so a chatty diagnostic
   doesn't blow up the response.
5. **Formatter lists warning + blocked only** -- healthy checks
   are not enumerated under "Top blockers".
6. **Formatter all-healthy path** -- "All checks pass" copy.
7. **Formatter is deterministic** -- two calls = identical output.
8. **No secret substring leak** -- 12 forbidden tokens checked
   against output even when payload contains hostile fixture data.
9. **Gather fallback on diagnostic failure** -- chat must never
   crash on a self-diagnostic ask.
10. **Gather fallback when stack imports blow** -- worst-case path.
11. **Orchestrator hook static integration** -- pins the wire so
    a future refactor can't silently strip the short-circuit.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_self_diagnostic_advisor.py -q
.....................................................                    [100%]
53 passed in 2.89s

$ .venv/Scripts/python.exe -m pytest tests/test_chat.py tests/test_chat_scan_dispatch.py -q
................                                                         [100%]
16 passed in 28.04s
```

**Sprint progression:** end of Sprint-6 = 235 in scope.
PR-1 added 8 tests = 243; PR-2 adds 53 tests = **296 in scope**.

**Pre-existing baseline failures (NOT caused by PR-2):**
`test_orchestrator_pipeline.py::test_full_pipeline_10_stages` and
`::test_pipeline_with_governance_slider` fail on master baseline as
well -- the test expects a `governance` thinking event the orchestrator
no longer emits at that point. Confirmed via `git stash` -- both fail
without PR-2 changes. Out of scope for this PR.

---

## 5. Smoke (manual, tomorrow)

Open chat, ask:

* "are you ok?" -> short-circuited diagnostic, ends with safety boundary
* "why 0 callable?" -> same path, surfaces the connector_callability check
* "what's wrong with this code?" -> NOT short-circuited, normal LLM path
  (regression-pinned by classifier negative tests)

---

## 6. What did NOT change

* `system_self_diagnostic.py` endpoint -- untouched, same shape, same auth.
* Chat persistence schema -- ASSISTANT turn looks like any other.
* Connector behavior -- not relevant.
* Phase 3 writes -- still impossible (short-circuit returns before
  the executor stages run; static check pins the `return`).

---

## 7. Follow-up PRs

1. **`PR-DAENA-SELF-DIAGNOSTIC-CHAT-CARD`** -- when the orchestrator
   short-circuits, also emit a `{"type": "diagnostic_card", ...}`
   event so the frontend can render the structured payload alongside
   the markdown answer.
2. **`PR-DAENA-SELF-DIAGNOSTIC-AUTO-FIX-PROPOSALS`** -- when overall
   is `blocked`, surface a "propose fix" button that opens an approval
   queue ticket (operator approves explicitly; advisor never fixes
   on its own). Defer until at least one operator says the advisory
   text isn't enough.
3. **`PR-CHAT-SELF-DIAGNOSTIC-INTENT-LOGGED-AS-EVENT`** -- emit
   `{"type": "thinking", "stage": "self_diagnostic"}` BEFORE the
   chunks so the existing thinking-event UI shows the short-circuit
   reason.
