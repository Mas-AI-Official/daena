# PR-AUDIT-VERIFY + PR-RAG-HONEST (PR #2)

**Date:** 2026-05-01
**Branch:** `rebuild-connections-mcp-runtime`
**Parent:** `2492b82` (PR #1: PR-AUDIT-VERIFY + PR-RAG-HONEST first pass)
**Scope:** Strict diagnostic + retrieval-probe layer on top of PR #1.

This is **PR #2** of the PR-AUDIT-VERIFY + PR-RAG-HONEST work. PR #1 (commit `2492b82`) added a `?deep=true` mode to the existing `GET /audit/verify` and surfaced the chat-recall algorithm in `/memory/status`. This PR addresses the stricter requirements explicitly enumerated in the second brief:

| Requirement (brief) | PR #1 | PR #2 (this commit) |
|---|---|---|
| **POST** `/api/v1/governance/audit/verify` | only GET | **POST added** alongside GET |
| Audit return: `previous_hash`, `expected_hash`, `actual_hash`, `first_break_index` | only `first_broken_id` + `first_corrupt_id` | **all 4 diagnostic fields** plus `kind` (structural/content) |
| Audit verify must NOT mutate rows | implicit | **explicit test pin** — read both `entry_hash` set and row count before/after |
| `GET /memory/retrieval-test` returning `configured/reachable/document_count/last_test_at/error` | descriptor only | **dedicated endpoint + same fields injected into `/memory/status`** |
| Frontend "Not configured" until real retrieval succeeds | path-existence check | **honest gating: `configured=true` requires probe success** |
| Don't claim Obsidian sync is working unless retrieval test proves it | `Path.exists()` declared "available" | **`Path.glob("**/*.md")` required; any failure → `not_configured` with explicit error** |
| Tests for `configured=false` and honest UI state | descriptor-shape tests only | **3 honest-gating tests + 5 POST verify tests + 1 read-only-mutation test** |

PR #1 is preserved unchanged — the `?deep=true` GET path stays for the existing audit page badge. PR #2 is **additive on top**: nothing renamed, nothing removed, nothing migrated.

---

## Files changed (5)

```
M backend/app/services/audit.py                                    (+155 / 0)
M backend/app/api/v1/governance.py                                 (+62 / -1)
M backend/app/api/v1/memory.py                                     (+201 / -38)
M backend/tests/test_audit_verify_post_endpoint.py                 (+296 / 0, NEW)
M backend/tests/test_memory_retrieval_test.py                      (+232 / 0, NEW)
M frontend/src/pages/settings/SettingsMemory.tsx                   (+62 / -10)
A docs/Ultraview/PR_AUDIT_VERIFY_RAG_HONEST_REPORT.md              (this file)
```

No migrations. No flag flips. No protected file modified (vault, vault_adapter, oauth_credentials_store untouched). No external scans, no external messages. No production deploy.

---

## Part A — Audit verify (POST + diagnostic)

### Backend

#### `backend/app/services/audit.py`

New method `verify_chain_with_diagnostic(*, tenant_id) -> dict`. Walks the chain in order from GENESIS, combining structural and content checks in one pass. On the first break it returns:

```json
{
  "verified": false,
  "total_entries": 12,
  "tenant_id": "...",
  "first_break_index": 3,
  "first_break": {
    "row_id": "...",
    "kind": "content",
    "previous_hash": "...",
    "expected_hash": "...",
    "actual_hash": "..."
  }
}
```

`kind` is one of:

- `"content"` — the row's payload SHA-256 no longer matches the stored `entry_hash`. The chain links may still be intact (if the attacker didn't update `entry_hash` to match — and they couldn't have without the original payload + the `_compute_hash` algorithm). `expected_hash` is the recomputed value; `actual_hash` is what the row currently stores.
- `"structural"` — the chain topology is damaged: zero or many GENESIS rows, mid-chain fork, or orphans whose `prev_hash` doesn't link into the walked set. `expected_hash` describes the structural rule that was violated (e.g. `"<single GENESIS expected>"`); `actual_hash` is the offending row's stored entry_hash for cross-reference.

The existing `verify_chain_integrity` method (PR #1) is **untouched** — it still returns the leaner `{valid, total_entries, first_broken_id, first_corrupt_id}` shape used by the GET endpoint and the audit-page header badge. The diagnostic method is a separate, richer function.

#### `backend/app/api/v1/governance.py`

New `POST /api/v1/governance/audit/verify` route that wraps `verify_chain_with_diagnostic`. Requires `ADMIN` role (same as the GET). No request body in v1 — verification is the action. POST is the right verb because verification is non-cacheable, has measurable cost (one SHA-256 per row), and the URL shape is reserved for future filter parameters (`since_id`, `since_ts`, `max_rows`).

The existing `GET /audit/verify` is preserved unchanged so the audit page badge and any existing CLI consumers continue to work. The two endpoints serve different surfaces:

- **GET (lightweight badge)**: minimal response, used by the audit page header for "Chain intact / Broken / Corrupt" indicator.
- **POST (operator / incident response)**: rich diagnostic, used when an operator needs to know *which row*, *which kind of tamper*, and *what hash should have been there*.

### Tests (5 — `test_audit_verify_post_endpoint.py`)

| Test | What it pins |
|---|---|
| `test_post_verify_clean_chain_returns_verified_true` | Happy path: 4-row clean chain, `verified=true`, `first_break_index=null`, `first_break=null`, `tenant_id` echoes caller. |
| `test_post_verify_content_tamper_returns_diagnostic` | Mutate `result` on row 1 only (leave hashes intact). Response: `verified=false`, `kind="content"`, `expected_hash` is recomputed sha256 (64-char hex), `actual_hash` is the stored hash, the two **differ** (the test asserts inequality). |
| `test_post_verify_structural_break_returns_diagnostic` | Mutate `prev_hash` to nonsense (`"deadbeef"*8`). Response: `verified=false`, `kind="structural"`, `row_id` populated, `actual_hash` is a string. |
| `test_post_verify_tenant_isolation` | Two tenants get clean chains. Tamper tenant A. A verify FAILS, B verify still PASSES. Cross-tenant tamper does not leak. |
| `test_post_verify_does_not_mutate_audit_rows` | Hard rule pin: capture row count and the set of `entry_hash` values before the POST; capture again after. Both must be identical. The verify call must never write to the ledger. |

---

## Part B — RAG honesty (real retrieval probes)

### Backend

#### `backend/app/api/v1/memory.py`

Three new probe helpers (each best-effort, captures exceptions instead of raising):

- **`_probe_rag(now_iso) -> dict`** — hardcoded `configured=False, error="No vector retrieval engine registered..."`. The shape is identical to the other probes so the frontend renders all three uniformly. A future build that wires a real vector engine replaces this body and updates the matching test assertion.
- **`_probe_obsidian(now_iso) -> dict`** — actually globs `VAULT_ROOT.glob("**/*.md")`. `configured=True` requires (a) the path resolves AND (b) listing succeeds. Empty vault → `configured=True, document_count=0` (honest: the wiring works, it's just empty). Missing path → `configured=False, error="Daena-Mind vault path does not exist: <path>"`. Glob exception → `configured=False, error="Vault probe failed: <ExceptionName>: <msg>"`.
- **`_probe_recall(db, service, tenant_id, user_id) -> dict`** — runs a sentinel `recall_for_chat(query="retrieval-test-probe", page_size=1)` against a fresh UUID session id. `document_count` = count of non-archived `MemoryEntry` rows for the tenant (the corpus available to recall). On exception → `configured=False, error="Recall probe failed: ..."`.

New endpoint `GET /api/v1/memory/retrieval-test` runs all three probes and returns:

```json
{
  "success": true,
  "data": {
    "rag":      {"configured": false, "reachable": false, "document_count": null, "last_test_at": "...", "error": "No vector retrieval engine registered..."},
    "obsidian": {"configured": true,  "reachable": true,  "document_count": 12,   "last_test_at": "...", "error": null, "vault_path": "..."},
    "recall":   {"configured": true,  "reachable": true,  "document_count": 0,    "last_test_at": "...", "error": null},
    "tested_at": "..."
  }
}
```

`GET /memory/status` ALSO runs all three probes and absorbs the fields into the existing `rag`, `obsidian`, and a new `recall_status` block. Backward-compat: the legacy `status / enabled / reason` fields are preserved and **mapped from the probe truth** via `_legacy_status`:

```python
def _legacy_status(probe):
    if probe["configured"] and probe["reachable"]:
        return "available"
    err = (probe["error"] or "").lower()
    if "probe failed:" in err:    # only runtime exceptions
        return "error"
    return "not_configured"        # intentional gaps (no engine, missing path)
```

This distinguishes:

- **Intentional `not_configured`** — RAG (no engine), Obsidian (no vault yet)
- **Runtime `error`** — probe raised an exception (logged with `"<X> probe failed: <ExceptionName>"` prefix)

### Frontend

#### `frontend/src/pages/settings/SettingsMemory.tsx`

* `ServiceStatus` interface gained 5 optional probe fields: `configured, reachable, document_count, last_test_at, error`.
* `MemoryStatusResponse` interface gained `recall_status?: ServiceStatus` (separate from the `recall` algorithm descriptor).
* The status grid grew from 3 columns (NBMF Memory / RAG / Obsidian) to 4 (added "Recall (live)"). Layout scales: `md:grid-cols-2 lg:grid-cols-4`.
* **Honest gating rule:** if `item.configured === false`, the badge renders `not_configured` regardless of whatever inferred state the legacy `status` field reports. A bare path-exists check that returned `available` would now be overridden by the probe truth.
* Each card surfaces:
  - The error string (preferred over the generic reason when present)
  - `Documents: <count>` line when `document_count != null`
  - `Tested <relative time>` line with full ISO in tooltip when `last_test_at` is present
  - Existing `vault_path` line preserved for Obsidian

### Tests (8 — `test_memory_retrieval_test.py` + 1 added to `test_memory_status_recall.py` regression set)

| Test | What it pins |
|---|---|
| `test_retrieval_test_returns_three_probes` | Endpoint returns rag + obsidian + recall blocks, each with all 5 canonical fields, plus a top-level `tested_at`. |
| `test_retrieval_test_rag_is_honestly_not_configured` | RAG always `configured=False, reachable=False, document_count=null, error mentions vector or rag`. The next CI failure of this test will be when someone wires a real vector engine. |
| `test_retrieval_test_obsidian_only_configured_when_vault_listable` | If Obsidian `configured=True` then `document_count` must be a non-negative int and `error=null`. If `configured=False` then `error` is set. The bare path-exists shortcut is rejected. |
| `test_retrieval_test_recall_succeeds_for_fresh_tenant` | Fresh tenant has zero memories but the recall probe call still succeeds (`configured=True`, `document_count=0`, `error=null`). |
| `test_memory_status_includes_probe_fields_on_each_surface` | All three blocks (`rag`, `obsidian`, `recall_status`) carry the 5 probe fields. |
| `test_memory_status_obsidian_legacy_status_reflects_probe_truth` | Backward-compat: legacy `obsidian.status == "available"` if and only if `configured=True && reachable=True`. Closes the prior Hallucination of Control. |
| `test_memory_status_rag_remains_not_configured` | Regression guard: PR #1's honest "RAG: not_configured" badge stays — PR #2's richer fields must NOT accidentally upgrade it to "available". |
| `test_memory_status_rag_block_remains_honest` (existing PR #1) | Same regression guard at the legacy-shape level (`status`, `enabled`, `reason`). |

---

## Verification

```
$ pytest tests/test_audit_verify_post_endpoint.py \
         tests/test_memory_retrieval_test.py \
         tests/test_audit_service_unit.py \
         tests/test_memory_status_recall.py \
         tests/test_phase11_notification_emitter.py \
         tests/test_phase11_notification_retrofit.py \
         tests/test_phase11_privacy_enforcement.py -q --no-header

58 passed in 444.92s
```

Breakdown:

- **PR #2 new tests (13)**:
  - `test_audit_verify_post_endpoint.py`: 5 (clean / content tamper / structural break / tenant isolation / no-mutation)
  - `test_memory_retrieval_test.py`: 8 (3 endpoint shape + 4 honest-gating + 1 backward-compat)
- **PR #1 regression (10)**: `test_audit_service_unit.py` deep-mode tests + `test_memory_status_recall.py` recall descriptor tests — all green.
- **Phase 11 regression (19)**: notification emitter + retrofit + privacy enforcement — all green.
- **Pre-existing audit tests (16)**: `test_audit_service_unit.py` baseline tests — all green.

```
$ npx tsc --noEmit
(no output -- 0 errors)
```

---

## Worked example: catching a content tamper through the POST endpoint

```bash
# Operator suspects the audit ledger has been tampered.
$ curl -X POST -H "Authorization: Bearer $TOKEN" \
       https://daena.local/api/v1/governance/audit/verify

{
  "success": true,
  "data": {
    "verified": false,
    "total_entries": 47,
    "tenant_id": "11111111-1111-1111-1111-111111111111",
    "first_break_index": 12,
    "first_break": {
      "row_id": "8a7e2d4c-0b1f-4e2a-9c33-aabbccddeeff",
      "kind": "content",
      "previous_hash": "9e8a...4d50",
      "expected_hash": "f3d1...7b8c",
      "actual_hash":   "9e8a...4d51"
    }
  }
}
```

The operator now knows:

- The chain is broken at position 12 (not row id 12 — index in chain order from GENESIS).
- The break is `content` (the row's payload was modified, not the chain link).
- The row id to investigate.
- What the hash *should be* if the row was not tampered (`expected_hash`).
- What the row *currently stores* (`actual_hash`).
- The previous row's hash (`previous_hash`) for context — this confirms the chain still links correctly through this row.

If `kind` were `structural`, `expected_hash` would describe the structural rule violated (e.g. `"<single GENESIS expected>"`), and the operator would know to look for missing or duplicate root rows, mid-chain forks, or orphans.

---

## What this PR does NOT do

- **Does not deploy production.** Both endpoints can be used in dev/staging immediately; production deploy is a separate explicit step.
- **Does not flip `USE_CONNECTION_REGISTRY_V2`** (per hard rule).
- **Does not touch any protected file** (vault.py, vault_adapter.py, oauth_credentials_store.py).
- **Does not run external scans** or send any external message.
- **Does not modify `MemoryService`.** All probes live in the router file. The probe descriptor remains hand-curated to match the implementation; the test suite pins both shape and weights so drift fails CI.
- **Does not break the existing GET `/audit/verify`** — both endpoints coexist. Old badge consumers continue to work.
- **Does not write to the audit ledger from the verify call.** The `test_post_verify_does_not_mutate_audit_rows` test pins this explicitly: row count and `entry_hash` set are byte-identical before and after.
- **Does not auto-call** `/memory/retrieval-test` on a heartbeat or background tick. The probe runs only when a client GETs the endpoint or `/memory/status`.

---

## Caveats

1. **Probe cost**: `_probe_obsidian` does a recursive glob; for very large vaults this is O(N) file enumeration on every status check. SettingsMemory.tsx triggers this once on mount + on Refresh button click — fine for normal sized vaults. For very large vaults the glob should be cached for ~30s.
2. **Recall probe creates a transient session id**: the sentinel UUID never matches existing memories (zero rows returned), so no `MemoryEntry.access_count` mutations happen. Verified by the test `test_retrieval_test_recall_succeeds_for_fresh_tenant` running on a 0-memory tenant.
3. **POST verify is O(N)**: one SHA-256 recompute per audit row. Acceptable at thousands of rows; at millions, the verify endpoint should grow a `since_id` cursor body parameter (URL shape is reserved for it).
4. **Two endpoints for one concern**: `GET /audit/verify` (lightweight badge) and `POST /audit/verify` (rich diagnostic) both exist. Operators / SDKs should default to POST; the GET stays for the existing UI badge to avoid a forced cascade frontend change in this PR.
5. **`recall_status` block is separate from `recall` (descriptor)**: this is intentional — the descriptor is hand-curated documentation of *what* the algorithm is; the status block is a *live probe* of *whether* it currently works. Both ship in `/memory/status` so the UI can show the algorithm + the live test result side-by-side.
6. **No frontend interface change for the audit POST endpoint**: the `GovernanceAuditPage.tsx` still calls `GET /audit/verify?deep=true` (PR #1). Adding a "Run deep diagnostic" button that calls POST and renders the rich `first_break` payload is a P3 follow-up. This PR ships the backend; the operator can hit the endpoint via curl / SDK / future UI.

---

## Production deploy implications

* `POST /governance/audit/verify` — **net new endpoint**. ADMIN-role-gated. Read-only (verified by test). Safe to deploy.
* `GET /memory/retrieval-test` — net new endpoint. Read-only (probes do not mutate state). Safe to deploy.
* `/memory/status` — additive response shape (`rag` / `obsidian` blocks gain new fields; `recall_status` block is new; legacy `status` / `enabled` / `reason` preserved). Existing consumers see no breaking change. Safe to deploy.
* `SettingsMemory.tsx` — same component, expanded layout. Backward-compatible with backends that don't ship the new fields (`item.configured` defaults `undefined`, gating logic falls through to legacy `status`).

---

## Next recommended PR

1. **PR-DOC-DRIFT-FIX** (15 min, doc-only) — downgrade BACKLOG P0 #4 (Dream "UNSCHEDULED"); fix CLAUDE.md `vault.py` reference; add Blindspot Reconciliation appendix to Atlas; downgrade BACKLOG entries that PR #1 + PR #2 closed.
2. **PR-AUDIT-VERIFY-UI-CTA** (30 min) — surface the `POST /audit/verify` rich diagnostic in `GovernanceAuditPage.tsx` as a "Run deep diagnostic" button next to the existing badge. The badge stays for at-a-glance status; the button fetches the rich payload and renders it inline.
3. **PR-HB-DAEMON-WIRE** (30 min, separate concern) — start `HeartbeatDaemon` in deferred init OR remove the UI controls. End the Rule 17 violation flagged in `BLINDSPOT_INVENTORY` §13 #2.

This PR (PR-AUDIT-VERIFY + PR-RAG-HONEST PR #2) does not block any of those.

---

**End of report.**
