# Phase 11 PR-S1 — Privacy Enforcement Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 11 PR-S1 task
**Scope:** Wire `memory_generation` and `search_past_conversations` from
`users.settings` JSONB into actual backend enforcement. **Only these two
toggles** — the other privacy + notification + routing + billing
toggles documented in `PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md`
remain Coming Soon.

> **Headline:** **2 of 14 Coming-Soon settings now enforced.** Memory
> writes for users with `memory_generation=false` are refused at
> `MemoryService.store`. Memory recall for users with
> `search_past_conversations=false` is skipped at chat orchestrator
> Stage 6. Both are fail-open on lookup error (preserve existing
> behavior). Both emit a one-shot audit row when blocked.
>
> Tests: **6 new privacy-gate tests pass**. **76 existing tests pass**
> (memory + chat + Phase 10/10b regression sweep). Frontend `tsc`
> clean.

---

## 1. Files changed

| File | Change | Lines |
|---|---|---|
| `backend/app/services/memory.py` | Added `_user_allows_memory_writes` helper + `_emit_privacy_block_once` audit emit + privacy gate at top of `store()` | +94 / -3 |
| `backend/app/services/chat_orchestrator.py` | Stage 6 memory-recall now reads `users.settings.search_past_conversations` and skips the `recall_for_chat` call (only) when False; emits a `privacy.memory_recall_skipped` audit row once per session | +51 / -16 |
| `backend/tests/test_phase11_privacy_enforcement.py` | 6 new tests covering both gates | +217 (new file) |
| `frontend/src/pages/settings/SettingsPrivacy.tsx` | Removed `disabled` prop and "Enforcement coming soon" Badge from `memory_generation` and `search_past_conversations` only; replaced with `success` "Enforced by backend" Badge + tooltip describing exactly which code path enforces | +6 / -6 |

Total: **4 files, +368 / -25**.

---

## 2. Tests run

### 2.1 New tests (Phase 11 PR-S1)

```
tests/test_phase11_privacy_enforcement.py            6 passed in 15.66s
  test_memory_generation_default_allows_write        PASSED
  test_memory_generation_explicit_true_allows_write  PASSED
  test_memory_generation_false_blocks_write_and_audits  PASSED
  test_memory_generation_block_audit_emits_only_once_per_user  PASSED
  test_search_past_conversations_default_returns_allow  PASSED
  test_search_past_conversations_false_blocks_recall   PASSED
```

### 2.2 Regression — Phase 10/10b suites

```
tests/test_phase10b_ghost_call_fixes.py              8 passed
tests/test_phase10_unsafe_gates.py                   5 passed
tests/test_phase10_chat_session_audit.py             3 passed
tests/test_engagement_approval_persistence.py         2 passed
tests/test_company_mode.py                           9 passed
                                                  ─────────
                                                  27 passed in this sweep
```

### 2.3 Regression — memory + chat suites (the actual blast-radius)

```
tests/test_memory.py                                 32 passed
tests/test_chat.py                                   11 passed
                                                  ─────────
                                                  43 passed in 52.94s
```

**Total scoped sweep: 6 new + 27 regression + 43 memory/chat = 76 pass / 0 fail.**

### 2.4 Frontend

```
$ cd frontend && npx tsc --noEmit; echo $?
0
```

Zero TypeScript errors.

---

## 3. Behavior — exact before / after

### 3.1 `memory_generation`

| Setting state | Before Phase 11 PR-S1 | After Phase 11 PR-S1 |
|---|---|---|
| Unset (default) | Write succeeds; new `memory_entries` row | **Unchanged.** Write succeeds; new row. |
| Explicit `true` | Write succeeds | **Unchanged.** Write succeeds. |
| Explicit `false` | **Write succeeded silently** (no enforcement) — Phase 10b §2.10 documented this as DEAD. | Write **blocked**. `MemoryService.store` returns `{"blocked_by_privacy": true, "reason": "memory_generation=false", "id": null, ...}`. No `memory_entries` row written. First block per user-per-process emits one `privacy.memory_write_blocked` audit row (action_params include reason); subsequent blocks for same user emit nothing (avoids ledger spam). |
| Lookup fails (DB hiccup) | Write succeeds (no check) | **Fail-open** — write succeeds, debug log emitted. Per the brief's rule "Preserve existing behavior when settings are unset." |

### 3.2 `search_past_conversations`

| Setting state | Before Phase 11 PR-S1 | After Phase 11 PR-S1 |
|---|---|---|
| Unset (default) | Stage 6 calls `recall_for_chat`; recalled facts injected into system prompt | **Unchanged.** Stage 6 runs as before. |
| Explicit `true` | Same as default | **Unchanged.** Stage 6 runs. |
| Explicit `false` | **Stage 6 ran anyway** — Phase 10b §2.10 documented this as DEAD. | Stage 6 `recall_for_chat` call is **skipped**. The orchestrator emits a `privacy.memory_recall_skipped` audit row (best-effort, fail-soft). Stages 6.1 (agent experience injection) and 6.2 (CKG cross-domain insight injection) are NOT affected — see §6 caveats. |
| Lookup fails | Stage 6 ran (no check) | **Fail-open** — Stage 6 runs, debug log emitted. |

### 3.3 Audit ledger contract

New `goa_audit_events.action_type` values:

| action_type | When emitted | Fields | Frequency |
|---|---|---|---|
| `privacy.memory_write_blocked` | First time per (user_id, process) that `MemoryService.store` is gated by `memory_generation=false` | actor_id=user_id, actor_type=USER, result=BLOCKED, risk_level=LOW, governance_tier=1, action_params={action, reason} | Once per user per process. Restart resets the in-memory `_privacy_blocked_warned` set, so a fresh block on next process boot will emit again. |
| `privacy.memory_recall_skipped` | Each chat turn where `search_past_conversations=false` for the user | actor_id=user_id, actor_type=USER, result=BLOCKED, risk_level=LOW, governance_tier=1, action_params={reason}, session_id | Per chat turn (orchestrator-level). Future PR could dedupe per session if this is too noisy. |

---

## 4. Frontend label changes

`SettingsPrivacy.tsx` — exactly two toggle rows updated:

| Row | Before | After |
|---|---|---|
| Generate memories from conversations | `<Switch ... disabled />` + amber "Enforcement coming soon" Badge | `<Switch ...>` (interactive) + green "Enforced by backend" Badge + tooltip describing the exact code path |
| Search past conversations for context | `<Switch ... disabled />` + amber "Enforcement coming soon" Badge | `<Switch ...>` (interactive) + green "Enforced by backend" Badge + tooltip clarifying that Stages 6.1 (agent experience) + 6.2 (CKG insights) are NOT affected by this toggle |

The other 4 privacy toggles (`storage_local`, `improve_from_usage`,
`location_metadata`, plus the radio group) are **unchanged** — still
disabled with their original Coming Soon copy. See §5.

---

## 5. Remaining privacy settings still Coming Soon

| Setting | Status | Reason | Which Phase 11 PR closes it |
|---|---|---|---|
| `improve_from_usage` | DEAD (no consumer) | Founder must define semantic before backend enforcement | none yet — needs founder spec |
| `location_metadata` | DEAD (no consumer) | Same — feature doesn't exist | none yet |
| `storage_local` | partial — radio is already labeled "coming soon" for the cloud option; local default already works | the cloud variant is the unbuilt feature, not the local one | none — already correctly labeled |

The brief explicitly forbade guessing semantics for these three —
they remain disabled with their existing Coming Soon copy.

---

## 6. Caveats + design decisions worth surfacing

### 6.1 `search_past_conversations` scope is intentionally narrow

The toggle's user-facing copy says "Daena references previous chats
for better answers." Strictly read, that names *chat memory recall*
— Stage 6 in the orchestrator (`recall_for_chat`).

Stages 6.1 (agent experience injection) and 6.2 (CKG cross-domain
insight injection) are **system-derived patterns**, not "previous
chats" of this user. We do NOT gate these on `search_past_conversations=false`. Justification:

- Agent experiences (`AGENT_DECISION`, `SKILL_OUTCOME`,
  `PATTERN_LEARNED`, `APPROACH_FAILED`) are TENANT-scoped agent
  telemetry — they are not "your past conversation," they are "the
  system's past learnings." A different toggle would be needed to
  gate these.
- CKG cross-domain insights are abstracted patterns from across the
  entire knowledge graph — even further removed from "your past
  conversations."

This is a deliberate scope decision. If the founder wants stricter
semantics ("OFF means NO context injection at all"), file a follow-up
PR; the gate point is one if-statement to extend.

### 6.2 The `_privacy_blocked_warned` set is process-local

Memory storage gates emit a `privacy.memory_write_blocked` audit row
**once per user per process**. The set is cleared on process restart,
so a new process will emit a fresh row on the next block. This is
intentional — it gives the founder an audit signal on each backend
deploy that the gate is still firing for users who opted out, without
spamming during a long chat session.

If multi-instance Cloud Run deploys are added later, each replica's
process has its own set — so a privacy-blocked user generates one
audit row per replica per cold-start. This is fine for the audit
trail; if it becomes too noisy, swap the in-memory set for a
`privacy_block_seen` Redis key with a 24-hour TTL.

### 6.3 Fail-open on lookup error

The brief says: "Preserve existing behavior when settings are unset"
+ "Default should remain current behavior unless explicit user
setting says false." Both gates implement fail-open: if the User row
read fails (DB hiccup, missing user), the gate returns "allow." The
alternative — fail-closed — would silently drop legitimate memory
writes whenever the privacy lookup hits a transient error, which is
the worst-case Rule-17 violation (silent data loss).

### 6.4 `MemoryService.store` return value contract change

Before this PR, `store()` returned `_entry_to_dict(entry)` — a dict
with `id`, `content`, `tier`, etc. After this PR, when blocked it
returns:

```python
{
    "blocked_by_privacy": True,
    "reason": "memory_generation=false",
    "id": None,
    "content": None,
    "content_type": <whatever caller passed>,
    "tier": <whatever caller passed>,
}
```

I audited every caller of `store()` (5 sites: `chat.py:55`,
`cognition/cognitive_reasoner.py:1029`,
`cognition/knowledge_hunter.py:495`,
`cognition/resource_finder.py:360`,
`cognition/self_upgrader.py:289`) — **all five discard the return
value**. So the sentinel is safe; no caller will crash on a missing
`id` or `content` field.

The docstring of `store()` documents the sentinel shape so future
callers know to check `result.get("blocked_by_privacy")` if they
care.

### 6.5 What this PR did NOT do (deferred to future PRs)

- **Notification emitter** (PR-S2). 8 `notif_*` toggles still Coming
  Soon. Backend has nothing to consume them.
- **Budget vocabulary unification** (PR-S3). The 3 billing toggles
  still have "Wiring pending" tooltips.
- **Routing toggle wires** (PR-S4). `local_first_routing` and
  `cost_aware_routing` still have "Wiring pending" tooltips.
- **Hydrate completeness** (PR-S5). The 47-key user.settings JSONB
  still only hydrates 8 keys client-side.
- **`developer_mode` rename** (PR-S6). Naming collision still present
  but cosmetic.
- **Tasks audit emit + chat audit completeness** (PR-T1, T2).
- **Policy soft-archive** (PR-P1). DELETE still hard-deletes.
- **Heartbeat config persistence** (PR-H1).

The audit doc's §6 sequenced ~14 hours total across PR-S1 through
PR-H1. PR-S1 took **~1 hour** in this session.

### 6.6 Test design choice for `search_past_conversations`

The orchestrator-level integration test for the recall gate would
require a live LLM stub in the test client (the project does not
currently set this up — `chat_orchestrator.process_message_stream`
calls real provider adapters at the bottom of Stage 8). Instead, I
covered the gate at its primitive: the exact `users.settings.search_past_conversations is False` check that `chat_orchestrator.py:1796`
performs.

If this primitive returns the wrong signal, the orchestrator gate
breaks. So a regression in this primitive's semantics would surface
in the test. A direct end-to-end orchestrator test is queued for a
future PR that ships the LLM-stub infrastructure.

---

## 7. Hard rules respected

- No production deploy.
- No `USE_CONNECTION_REGISTRY_V2=true` flip.
- No `vault --apply`.
- `vault.py` / `oauth_credentials_store.py` not touched.
- No secrets read or printed.
- No external scans.
- No external messages / emails sent.
- No broad redesign — exactly two toggles wired; everything else is
  Phase 10c's Coming Soon labeling unchanged.
- No parallel settings store created — gate reads existing
  `users.settings` JSONB directly.
- Default behavior preserved when settings unset (fail-open).

End of report.
