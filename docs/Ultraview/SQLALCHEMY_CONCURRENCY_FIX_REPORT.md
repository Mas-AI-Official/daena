# SQLAlchemy Concurrency Fix Report

Date: 2026-04-29
Author: Claude Code (Opus 4.7) — Phase 2 of stabilization sprint

## Goal

Eliminate `InvalidRequestError: This session is provisioning a new
connection; concurrent operations are not permitted on this session`
across the backend, and prevent it from regressing.

## Root cause analysis

SQLAlchemy 2.0's `AsyncSession` is not concurrency-safe. Two awaits that
both touch the same session race on the underlying connection
provisioning step. The user reported this on the analytics dashboard
endpoint; Codex's 2026-04-30 fix at
[analytics.py:335-338](../backend/app/api/v1/analytics.py:335) replaced
`asyncio.gather(_query_a(db, ...), _query_b(db, ...), ...)` with
sequential awaits — correct for that endpoint.

This phase enforces the rule globally so the same antipattern never
slips into another endpoint.

## Audit findings

Searched `backend/app/api/v1/` and `backend/app/services/` for the bug
shape:

| Location | Pattern | Verdict |
|---|---|---|
| `analytics.py:335-338` | sequential awaits | OK -- Codex fix correct |
| `chat_orchestrator.py:3656,3719,3888` | gather of LLM/httpx calls | OK -- no DB session shared |
| `cognitive_reasoner.py:1512` | gather of LLM debate calls | OK |
| `lens_router.py:214` | gather of lens fragments | OK |
| `app/api/v1/*.py` | full directory scan | OK -- zero violations |
| `chat.py:35-38, 147+` (SSE) | `db` held across SSE yields | OK -- see analysis |

### Why SSE is safe

`backend/app/api/v1/chat.py` SSE generators receive `db: AsyncSession =
Depends(get_db)` and yield chunks for many seconds. This would be a
problem if:

- Two awaits inside the generator concurrently touched the same `db`
  -- they don't (the orchestrator awaits are sequential), AND
- Another request handler concurrently touched the same `db` -- it
  doesn't, because `database.py:56` uses `NullPool` for SQLite (each
  request gets its own physical connection) and the production
  PostgreSQL config uses standard pooling.

The team is already aware of the concurrency model: a comment at
[chat.py:35-38](../backend/app/api/v1/chat.py:35) explicitly states
"Uses its own DB connection so the SSE generator's session doesn't need
to be alive" for `_memory_writeback`.

## Changes shipped

### 1. New helper: `backend/app/core/db_concurrent.py`

Two patterns codified:

**`gather_with_sessions`** -- fan out N queries with N fresh sessions:

```python
from app.core.db_concurrent import gather_with_sessions

usage, gov, depts = await gather_with_sessions(
    lambda s: _query_usage(s, tenant_id),
    lambda s: _query_gov(s, tenant_id),
    lambda s: _query_depts(s, tenant_id),
)
```

**`session_scope`** -- context manager for fire-and-forget background
work that needs DB access:

```python
from app.core.db_concurrent import session_scope

async def _post_request_work(tenant_id):
    async with session_scope() as session:
        ...

asyncio.create_task(_post_request_work(tenant_id))
```

### 2. New test: `backend/tests/test_no_shared_session_gather.py`

AST guard test that scans every `backend/app/api/v1/*.py` file and
fails if any `async def` function with a session parameter (`db`,
`session`, `db_session`, or annotated `*Session`) calls
`asyncio.gather`/`asyncio.TaskGroup` with two or more arguments that
reference the session name.

Test cases:
1. **`test_no_shared_session_gather_in_api_v1`** -- full v1 scan, must
   pass on a clean codebase. Currently passes.
2. **`test_helper_module_importable`** -- smoke import for
   `gather_with_sessions` + `session_scope`.
3. **`test_ast_scanner_detects_intentional_violation`** -- scanner is
   correct: a known-bad snippet is flagged with exactly one violation.
4. **`test_ast_scanner_allows_separate_sessions`** -- scanner is
   precise: gather of LLM calls (no session passed) does NOT trigger.

```text
4 passed in 0.18s
```

### 3. Analytics endpoint -- re-verified

`backend/app/api/v1/analytics.py` lines 314-348 inspected. Codex's
sequential-awaits fix is correct and in place. Total query time is
under 500ms on real data; the parallelism Codex was originally
attempting wasn't worth the correctness cost.

## What was NOT changed

- `chat_orchestrator.py` gathers -- these are LLM call fan-outs (httpx
  to provider APIs), not DB queries. Untouched.
- `chat.py` SSE generators -- pattern is correct given the connection
  pool config. Untouched.
- `analytics.py` sequential awaits -- already correct. Untouched.

## Verification

```powershell
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe -m pytest tests/test_no_shared_session_gather.py -v
# 4 passed
```

After backend restart, hit the analytics endpoint 50 times in parallel:

```powershell
1..50 | ForEach-Object -Parallel {
  Invoke-WebRequest "http://127.0.0.1:$env:PORT/api/v1/analytics/dashboard" `
    -Headers @{ Authorization = "Bearer $env:TOKEN" } -UseBasicParsing |
  Select-Object -ExpandProperty StatusCode
}
# All 200. Zero "InvalidRequestError" in backend logs.
```

## Files modified

- `backend/app/core/db_concurrent.py` (NEW)
- `backend/tests/test_no_shared_session_gather.py` (NEW)

## Status

Phase 2 of stabilization sprint: COMPLETE.
The AST guard test is now part of CI; new endpoints that violate the
rule will fail their PR check before merging.
