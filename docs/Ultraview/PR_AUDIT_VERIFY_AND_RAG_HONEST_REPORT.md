# PR-AUDIT-VERIFY + PR-RAG-HONEST

**Date:** 2026-05-01
**Branch:** `rebuild-connections-mcp-runtime`
**Parent:** `fe57ff7` (PR-NOTIF-MIG-008)
**Scope:** Two minimal-blast-radius truth-telling PRs bundled per Phase J recommendation.

This bundle:

1. **PR-AUDIT-VERIFY** -- closes the audit chain payload-recompute gap. The existing `verify_chain_integrity` was structural-only (walks `prev_hash → entry_hash` links) and could not detect a tamper that left the chain links intact, e.g. an attacker who flips `result` from `BLOCKED` to `ALLOWED` without touching the hash columns. Adds `deep=True` mode that recomputes SHA-256 from each row's payload and compares to the stored `entry_hash`. Frontend now calls with `?deep=true` so the badge reflects the real check.
2. **PR-RAG-HONEST** -- surfaces the actual chat-recall algorithm in `/memory/status`. The Atlas + Backlog framed Daena's recall as "RAG NOT IMPLEMENTED" -- technically correct (no embeddings) but understated. `recall_for_chat` runs a deterministic keyword Jaccard blend across NBMF tier, entry confidence, and recency. Operators can now see the algorithm + scoring weights in Settings → Memory without reading code.

Neither PR adds new endpoints, neither requires a migration, neither flips a feature flag, neither touches any of the protected files (vault, vault_adapter, oauth_credentials_store).

---

## What was already there (and what was NOT)

A blind-spot audit before writing any code surfaced two structural surprises:

| Claim from prior Atlas | Reality on disk |
|---|---|
| "Audit hash chain not validated" | `AuditService.verify_chain_integrity` already exists at `audit.py:170` and `GET /api/v1/governance/audit/verify` already mounted at `governance.py:306`. The walker is sophisticated (AUD-001 algorithm, walks via `prev_hash` links). What's missing is **payload recompute** — a content tamper that leaves the chain links intact passes structural verification. |
| "RAG NOT IMPLEMENTED" | `MemoryService.recall_for_chat` runs a 4-component blended score (50% keyword Jaccard + 20% tier + 20% confidence + 10% recency decay). `/memory/status` already says `"rag": {"status": "not_configured"}`. The honest piece missing is a **descriptor** of what the actual fallback algorithm IS, not just what it isn't. |

So both PRs are **additive** rather than from-zero implementation. Existing tests stay green; new tests pin the new behavior.

---

## PR-AUDIT-VERIFY

### Backend

#### `backend/app/services/audit.py`

* `verify_chain_integrity(*, tenant_id, deep: bool = False)` — added `deep` keyword arg, defaults to `False` for backwards compatibility with all existing callers.
* Extracted the existing AUD-001 structural walk into `_structural_walk(events) → {valid, first_broken_id}` static method so the deep mode can compose with it.
* New `_recompute_event_hash(event) → str` static method recomputes `SHA-256(actor_id|action_type|result|prev_hash|timestamp)` from a stored row and returns the hex hash. Strips `tzinfo` from `created_at` to handle the SQLite-vs-Postgres dialect difference (SQLite returns naive datetime, Postgres returns aware; `log_decision` writes naive `datetime.utcnow()`).
* Response shape gained `first_corrupt_id` field — always `None` when `deep=False`, so the structural-only contract is preserved.

#### `backend/app/api/v1/governance.py`

* `verify_audit_integrity` route gained a `deep: bool = Query(False)` parameter, passed through to the service. ADMIN role still required. Backwards-compatible default preserves existing callers.
* Docstring documents the response shape including the new `first_corrupt_id` key and what triggers it.

### Frontend

#### `frontend/src/pages/GovernanceAuditPage.tsx`

* `AuditVerifyResponse` interface gained `first_corrupt_id?: string | null` (optional so older backends without the field don't break the type).
* `chainStatus` type union extended from `'verifying' | 'ok' | 'broken' | 'unknown'` to also include `'corrupt'`.
* Added `chainCorruptAt` state alongside `chainBrokenAt`.
* `verifyChain` now calls `?deep=true` so the badge actually checks payload integrity, not just chain topology.
* Badge button: distinct copy + tooltip for content tamper (`"Corrupt at <hash8>"`) vs structural break (`"Broken at <hash8>"`). Both render red but the operator can tell which class of tamper occurred.

### Why it matters

The structural walker passes if `prev_hash → entry_hash` links form a valid chain. An attacker who already has DB write access can:

1. Read row N: `actor=alice action=DELETE result=BLOCKED prev_hash=<X> entry_hash=<Y>`
2. Update row N: `result=ALLOWED` (leave prev_hash + entry_hash untouched)
3. Walk passes — the chain still walks `X → Y → next_row.prev_hash → ...` cleanly.

The deep recompute catches this because `SHA-256(alice|DELETE|ALLOWED|X|<ts>)` no longer equals the stored `Y`. The new test `test_chain_integrity_deep_mode_catches_content_tamper` explicitly demonstrates the gap by performing exactly this attack and verifying that structural mode misses it while deep mode catches it.

---

## PR-RAG-HONEST

### Backend

#### `backend/app/api/v1/memory.py`

* `memory_status` endpoint response gained a `recall` block alongside the existing `memory` / `rag` / `obsidian` blocks. The `rag` block is **unchanged** -- it still says `"status": "not_configured"` because that is also true. The new `recall` block describes what runs:

```jsonc
"recall": {
  "mode": "keyword_jaccard_blend",
  "embeddings_enabled": false,
  "function_path": "app.services.memory.MemoryService.recall_for_chat",
  "scoring": {
    "keyword_relevance": 0.50,
    "tier_normalized":   0.20,
    "confidence":        0.20,
    "recency_decay":     0.10
  },
  "scope_priority": ["SESSION", "USER", "TENANT"],
  "filters": ["non_quarantined", "non_expired", "tier_>=_LONG_TERM"],
  "tokenizer": "ASCII alphanumeric with dash/underscore separators, min length 2, English stopwords stripped",
  "default_top_k": 5,
  "reason": "Chat recall is a deterministic blend of keyword Jaccard overlap, NBMF tier, entry confidence, and recency decay. No vector/embedding retrieval is configured in this build."
}
```

This was a router-only change. **No changes to `MemoryService`** — the algorithm description must NEVER drift from the actual implementation, and the test `test_memory_status_recall_describes_keyword_blend` pins both the structure and the weights so any future implementation change forces a documentation update at the same commit.

### Frontend

#### `frontend/src/pages/settings/SettingsMemory.tsx`

* `MemoryStatusResponse` interface gained a `recall?: RecallDescriptor` typing.
* New "Recall Algorithm" Card placed between the existing "Memory / RAG / Obsidian Status" card and the "NBMF Tiers" card. Renders only when the descriptor is present (forwards-compatible with backends that haven't shipped the field).
* The card shows:
  * Mode + `no embeddings` badge (with `embeddings` color if a future build flips it to true)
  * The reason sentence (operator gets context for why no embeddings)
  * Scoring weights as horizontal bars with percentages
  * Scope priority arrow chain (`SESSION › USER › TENANT`)
  * Filters + tokenizer + source function path

The visual encoding reuses Daena's existing card palette (no new design tokens). Total added LOC: ~100 in one component file.

### Why it matters

Surfacing the algorithm closes one face of the "Hallucination of Control" risk class identified in `DAENA_BACKEND_BLINDSPOT_INVENTORY.md`. A user who sees `RAG: not_configured` might assume Daena has no recall at all and bring its own RAG layer outside the governance pipeline. The Recall Algorithm card tells them: yes there IS recall, here's exactly what it does, here are the weights, here's where the code lives — make an informed decision.

---

## Files changed (6)

```
M backend/app/services/audit.py                              (+98 / -27)
M backend/app/api/v1/governance.py                           (+30 / -3)
M backend/app/api/v1/memory.py                               (+34 / -0)
M backend/tests/test_audit_service_unit.py                   (+158 / -0)
A backend/tests/test_memory_status_recall.py                 (+139 / 0)
M frontend/src/pages/GovernanceAuditPage.tsx                 (+50 / -10)
M frontend/src/pages/settings/SettingsMemory.tsx             (+103 / -2)
A docs/Ultraview/PR_AUDIT_VERIFY_AND_RAG_HONEST_REPORT.md    (this file)
```

No migrations. No flag flips. No protected file modified.

---

## Verification

### Tests

All run against `daena_dev2.db` SQLite + in-memory fixtures.

```
$ pytest tests/test_audit_service_unit.py \
         tests/test_memory_status_recall.py \
         tests/test_phase11_notification_emitter.py \
         tests/test_phase11_notification_retrofit.py \
         tests/test_phase11_privacy_enforcement.py -v --no-header

============================= 46 passed in 30.83s =============================
```

#### New tests (10)

* `test_audit_service_unit.py::test_chain_integrity_deep_mode_passes_clean_chain` -- happy path: 4-entry chain, deep mode reports valid, both `first_broken_id` and `first_corrupt_id` are `null`.
* `test_audit_service_unit.py::test_chain_integrity_deep_mode_catches_content_tamper` -- the load-bearing test: write 3 entries, mutate row 1's `result` field only (leave `prev_hash` + `entry_hash` untouched), verify (a) structural mode passes, (b) deep mode reports `valid=False` with `first_corrupt_id` = the mutated row's id and `first_broken_id` = None.
* `test_audit_service_unit.py::test_chain_integrity_default_mode_misses_content_tamper` -- regression guard: documents that the structural walker by-design cannot catch content tampering. If this test ever fails, the structural walker has gained payload validation and deep mode is no longer needed.
* `test_audit_service_unit.py::test_chain_integrity_response_shape_includes_corrupt_field` -- contract: `first_corrupt_id` key is always present in the response, regardless of `deep` flag, so frontend interfaces can rely on it.
* `test_audit_service_unit.py::test_recompute_event_hash_matches_log_decision_hash` -- pure function: recomputed hash for a freshly built event matches what `log_decision` would have written. Validates payload ordering + tz-strip normalization.
* `test_audit_service_unit.py::test_recompute_event_hash_strips_timezone` -- naive vs aware datetime produce the same hash (cross-dialect parity).
* `test_memory_status_recall.py::test_memory_status_returns_recall_descriptor` -- the `recall` key appears on the response.
* `test_memory_status_recall.py::test_memory_status_recall_has_required_keys` -- 9 required keys present (mode, embeddings_enabled, function_path, scoring, scope_priority, filters, tokenizer, default_top_k, reason).
* `test_memory_status_recall.py::test_memory_status_recall_describes_keyword_blend` -- 4 scoring weights sum to exactly 1.0; mode == `"keyword_jaccard_blend"`; `embeddings_enabled` is False; function path ends in `recall_for_chat`; scope priority is `[SESSION, USER, TENANT]`.
* `test_memory_status_recall.py::test_memory_status_rag_block_remains_honest` -- regression guard: PR-RAG-HONEST must NOT remove the existing honest `rag.status = not_configured` badge. Both signals coexist.

#### Regression (36)

* All 19 Phase 11 tests (`test_phase11_notification_emitter` + `_retrofit` + `_privacy_enforcement`) — green.
* All 17 pre-existing `test_audit_service_unit` tests — green. Includes `test_chain_integrity_detects_tampering` (mutates `prev_hash`, structural mode catches the structural break) and `test_chains_isolated_per_tenant` (mutates `result` on tenant 1, verifies tenant 2's chain stays valid).

### Frontend type check

```
$ npx tsc --noEmit
(no output -- clean)
```

No new TS errors introduced. Existing baseline of 0 errors maintained.

### Manual API contract check

GovernanceAuditPage.tsx interface declares `first_corrupt_id?: string | null` (optional). Backend returns the field unconditionally now, but the optional declaration keeps the frontend forwards-compatible if a future contract change removes it.

---

## What this PR does NOT do

- **Does not add a new endpoint.** Both `/governance/audit/verify` and `/memory/status` already existed; this PR extends them. Reusing the surface keeps the API count flat.
- **Does not modify `MemoryService`.** The recall descriptor lives in the router endpoint and is hand-curated to match the implementation. The accompanying test pins the weights so drift is caught at next CI run.
- **Does not run a deep verification on every page load.** Frontend calls `?deep=true` once per `verifyChain` invocation (page mount + manual click). For a tenant with 100k audit events the recompute is O(N) sha256 ops -- locally measurable in tens of ms, not seconds. If that ever becomes a hot-path concern, frontend can fall back to `deep=false` for the auto-verify and offer "deep verify" as an explicit operator action.
- **Does not flip `USE_CONNECTION_REGISTRY_V2`** (per hard rule).
- **Does not run any external scan, send any external message, or modify any protected file.**
- **Does not bundle the housekeeping commits** identified in the Blind-Spot Inventory (e.g., dropping `cve_intel.py` duplicate, moving root-level `run_*.py` benchmarks). Those are P2 and stay in the backlog.

---

## Caveats

1. **Postgres timestamp round-trip:** the `_recompute_event_hash` helper strips `tzinfo` so SQLite (naive) and Postgres (aware) produce identical hash inputs. This works because `log_decision` writes `datetime.utcnow()` (naive). If `log_decision` ever switches to `datetime.now(timezone.utc)` (aware), the recompute will still match because the strip is symmetric, but the unit test `test_recompute_event_hash_strips_timezone` should be re-read to make sure the new code path is still exercised.
2. **Microsecond precision required:** the hash payload includes `created_at.isoformat()` which on Windows has ~15.6ms granularity. As long as the row keeps the same `created_at` value used at insert (it does — `log_decision` sets it explicitly), the recompute is byte-identical. SQLite/Postgres both round-trip microseconds correctly via DateTime columns.
3. **Deep mode is O(N) sha256** per row. For tenants with audit ledgers in the millions, the verifier should grow a `since_ts=...` cursor; current shape walks all events for the tenant. Out of scope for this PR but documented here as the next bottleneck.
4. **Recall descriptor is hand-curated.** If `_blended_score` weights ever change in `MemoryService`, the descriptor in `memory.py` and the assertion in `test_memory_status_recall_describes_keyword_blend` must change in lockstep. The test failure is the load-bearing safety net.
5. **No migration delivered.** Both PRs are pure-code; no schema changes.
6. **Frontend tsc passes but no runtime browser test was performed.** The added Card uses only existing components (`Card`, `Badge`, lucide icons). The only state read is the new optional response field, gated by `memoryStatus?.recall && (...)` so absence renders nothing instead of crashing.

---

## Production deploy implications

* PR-AUDIT-VERIFY: API surface change is **additive** (`?deep=true` query param + new optional response field). Existing callers that don't pass `deep` see the original behavior plus a `first_corrupt_id: null` field they can ignore. **Safe to deploy.**
* PR-RAG-HONEST: Response shape is **additive** (new `recall` block). Existing consumers (SettingsMemory.tsx in this branch is the only one) gracefully ignore unknown fields. **Safe to deploy.**

Production deploy of either PR does **not** require running migration 008 (which PR-NOTIF-MIG-008 already shipped). Both PRs only consume the existing `goa_audit_events` and `users.settings` tables.

---

## Next recommended PR

Per the Blind-Spot Inventory + Phase J recommendation, this clears the way for:

1. **PR-DOC-DRIFT-FIX** (15 min, doc-only) — downgrade BACKLOG P0 #4 (Dream Engine "UNSCHEDULED") to P2; fix CLAUDE.md `vault.py` reference to `vault_adapter.py`; add a Blindspot Reconciliation appendix to `DAENA_ARCHITECTURE_ATLAS.md`.
2. **PR-LEARN-01 + PR-DREAM-01** (~7 h, multi-agent split per CLAUDE.md delegation table) — original Backlog PR #2.
3. **PR-HB-DAEMON-WIRE** (30 min) — start `HeartbeatDaemon` in deferred init OR remove the UI controls. End the Rule 17 violation flagged in BLINDSPOT_INVENTORY §13 #2.

This PR (PR-AUDIT-VERIFY + PR-RAG-HONEST) does not block any of those.

---

**End of report.**
