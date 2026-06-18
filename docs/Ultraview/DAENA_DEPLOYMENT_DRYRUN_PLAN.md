# DAENA Deployment Dry-Run Plan

Status: Part A = non-gated (zero spend, no external effects). Part B = founder-gated.
Generated 2026-06-04. HEAD at authoring: `d07c3d8` (branch production-readiness-daena-vp).

Purpose: rehearse everything that can fail on a real deploy WITHOUT spending money,
touching a production DB, or making any external call. The single highest-value
unrun step was the Postgres migration rehearsal of 014/015/016 (A6); this run
executes the safe substance of it (see RESULTS).

---

## Part A -- non-gated dry-run (safe to run locally, repeatable)

### A1. Single migration head
Command:
    cd backend ; .\.venv\Scripts\python.exe -m alembic -c migrations/alembic.ini heads
Expect: SINGLE head `016_add_run_trace_events`.
RESULT 2026-06-04: PASS -- `016_add_run_trace_events (head)`.

### A2. Runtime smoke (read-only; no secrets/sends/scans/deploy)
Command:
    .\scripts\verify_runtime_local.ps1
Expect: 7 PASS (backend health, root 404-alive, frontend, vite->backend proxy,
F5 voice, two auth-gate 401s).
RESULT 2026-06-04: PASS=7 WARN=0 FAIL=0.

### A3. Config / env precedence sanity
- `Settings` uses `case_sensitive=False`, no `env_prefix`; env var == field name.
- Env precedence resolves via `DAENA_ENV_PRECEDENCE` (`env_file_first` |
  `process_env_first`); local `.env` with `APP_ENV=local` defaults to
  `env_file_first` (see `config.py:_default_env_precedence`).
- Verify no required prod secret is silently defaulting to empty: the OAuth and
  provider client fields default to `""` and fail loudly at use
  (`OAuthConfigError`) rather than sending an empty client_id.
Status: static-verified in source; no command needed.

### A4. Backend test gate (run if backend changed)
Command:
    cd backend ; .\.venv\Scripts\python.exe -m pytest -q --timeout=120
Last known: 6010 passed / 0 failed (re-run bejjyjpzw on d963d67). One intermittent
audit-ledger isolation flake (test-only, P2, validated unrelated to production
logic). Not re-run in this dry-run pass (no backend src change here -- docs only).

### A5. Frontend build / type gate (run if frontend changed)
Command:
    cd frontend ; npm run build   (and tsc --noEmit for types)
Not run in this pass (no frontend change). Reference only.

### A6. Postgres migration rehearsal of the chain (KEY STEP)
Goal: prove `alembic upgrade head` works on a FRESH database the way a first
production Postgres migration would -- the exact scenario migration `014_merge_heads`
was written to fix (revision 007 had branched into two never-reconverged heads;
`upgrade head` would die with "Multiple head revisions are present" on a clean DB).

What was executed 2026-06-04 (disposable, zero-spend, no network):

(a) FULL CHAIN on a throwaway SQLite DB, base -> head -> base:
    - Applied 001 ... 016 forward with no error; final revision = `016 (head)`.
    - Downgraded 016 ... base with no error; the 014 merge node correctly
      unwound BOTH reconciled sub-chains (014 -> {013, 010_add_error_events},
      then both the notifications chain and the quota/error chain fully reversed).
    - Confirms chain integrity from empty base + full reversibility.
    RESULT: PASS.

(b) POSTGRES-DIALECT DDL COMPILATION of the only schema-changing migrations in
    014-016 (015 heartbeat_config, 016 run_trace_events), compiled in-process
    against `sqlalchemy.dialects.postgresql`:
    - `JSONBCompat` -> `JSONB`
    - `GUID`        -> `UUID`
    - `DateTime(timezone=True)` -> `TIMESTAMP WITH TIME ZONE`
    - `server_default=func.now()` -> `DEFAULT now()`
    - all indexes render as native `CREATE INDEX`.
    No SQLite-ism leaks into the Postgres path; the new tables are PG-clean.
    RESULT: PASS (PG_COMPILE_OK).

REMAINING (optional, needs a live disposable Postgres -- see A6-live):
applying the chain against an actual postgres server. De-risked by (a)+(b): the
migrations use dialect-aware custom types and the chain is head-clean, but a live
apply is the only thing that exercises asyncpg + real PG DDL execution end to end.

### A6-live (optional; disposable Postgres, still zero recurring spend)
Spin a throwaway local Postgres and apply the chain (NOT a production DB):
    docker run --rm -d --name daena_pg_dryrun -e POSTGRES_PASSWORD=dryrun \
        -e POSTGRES_DB=daena_dryrun -p 55432:5432 postgres:16
    # then, with DATABASE_URL pointing at it:
    #   postgresql+asyncpg://postgres:dryrun@127.0.0.1:55432/daena_dryrun
    cd backend ; <set DATABASE_URL> ; \
        .\.venv\Scripts\python.exe -m alembic -c migrations/alembic.ini upgrade head
    # expect: ends at 016 with no "Multiple head revisions" and no DDL error
    docker rm -f daena_pg_dryrun
Note: requires Docker (not auto-run here -- needs operator approval to invoke the
docker daemon). It is disposable and free; it is NOT the gated prod migration.

---

## Part B -- founder-gated (do NOT auto-execute)

These are the steps that spend money, touch real data, or make external calls:

- DEP-001: rotate `backend/.env` keys (founder secret action; only remaining P0).
- Apply migrations 014/015/016 to the REAL production Postgres on real data.
- Live OAuth / Gmail verification (see DAENA_OAUTH_GMAIL_CHECKLIST.md).
- Paid Cloud Run / GCP deploy + image rebuild.
- DNS changes.
- Any external send / submit / post.

---

## Summary

| Step | What it proves | Result |
|------|----------------|--------|
| A1 | single alembic head | PASS (016) |
| A2 | local runtime up, auth-gated | PASS 7/7 |
| A3 | env/secret precedence loud-fail | static OK |
| A4 | backend suite green | 6010/0 (prior run) |
| A6 (a) | chain base->head->base integrity | PASS (SQLite) |
| A6 (b) | new tables PG-dialect clean | PASS (PG compile) |
| A6-live | real PG apply | OPTIONAL (needs docker approval) |

Part A migration risk is now substantially retired: the dual-head break is fixed
(014) and verified, and the new tables compile to native Postgres DDL. The only
unexercised path is asyncpg executing the DDL against a live server, which Part
A6-live covers on demand without spend.
