# PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-3 (PR-3 of 5)

---

## 1. Goal

Promote DB describe-schema/collections skills to `execution_mode=mcp_tool`
**only when the underlying MCP exposes a discrete read-only tool** that
does not require constructing or executing SQL at the executor layer.

| Plugin | Skill | MCP discrete tool | Decision |
|---|---|---|---|
| `mcp-sqlite` | `describe_schema` | `list_tables` (archived ref MCP) | **PROMOTED** |
| `mcp-mongodb` | `describe_collections` | `db-list-collections` (vendor MCP) | **PROMOTED** |
| `mcp-supabase` | `describe_schema` | `list_tables` (vendor MCP, schemas=['public']) | **PROMOTED** |
| `mcp-neon` | `describe_schema` | `get_database_tables` (vendor MCP) | **PROMOTED** |
| `mcp-postgres` | `describe_schema` | only generic `query` (no discrete tool) | **STAYS PLANNED** |

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No safe_query | YES -- `safe_query` STAYS planned for ALL DB plugins; `_PLUGIN_TO_SERVER_KEY` doesn't even map a safe_query path |
| No SQL execution beyond schema introspection tools | YES -- mcp-postgres stays planned because the archived ref only ships `query`, which would need SQL construction |
| No writes / updates / deletes / migrations / inserts / DDL | YES -- `test_pr4_no_db_write_skills_promoted` pins a 23-name forbidden list across all DB plugins; would fail at module load if a write skill ever gets `execution_mode='mcp_tool'` |
| If MCP tool cannot prove read-only, keep planned | YES -- mcp-postgres stays planned with explicit defense test |
| Tests required | YES -- 6 new invariant tests + 1 inherited PROMOTED_TO_MCP_TOOL invariant covering this PR |

---

## 3. Why mcp-postgres stays planned

The archived `@modelcontextprotocol/server-postgres` MCP exposes ONE
tool: `query(sql: string)`. Per its README, it wraps each query with
`SET TRANSACTION READ ONLY` -- so the read-only enforcement happens
INSIDE the MCP, not at the executor.

But to introspect the schema the executor would have to construct
something like `SELECT table_name FROM information_schema.tables`. That
is exactly the "SQL execution beyond schema introspection tools" the
brief forbids. Even though the MCP itself blocks writes, having the
executor build SQL is the wrong precedent -- it sets the surface for
future leak (e.g. operator input being interpolated into the query).

Honest path: keep planned, document, defense-test. A future PR that
writes a discrete `mcp-postgres-introspection-mcp` (or wires the
official MongoDB-style schema tool when it ships) can flip the bit.

---

## 4. The 4 promoted entries (per-tool detail)

### mcp-sqlite -> list_tables (`required_inputs=()`)

The reference SQLite MCP launches against a `-db-path` flag passed at
startup. The operator does NOT pass a database path through the
executor -- the MCP owns the path. `_args_sqlite_list_tables` returns
`{}` and discards any operator inputs.

This is enforced at two layers:
* `required_inputs=()` at the allowlist level -- no input UI lights up.
* `_args_sqlite_list_tables` returns `{}` even if junk fields are
  passed (`test_pr4_arg_builder_sqlite_takes_no_db_path` proves it).

### mcp-mongodb -> db-list-collections (`required_inputs=("database",)`)

The vendor MongoDB MCP (`mongodb-mcp-server`) exposes
`db-list-collections({database})` returning collection names + counts.
NEVER reads document content; never returns sample values.

### mcp-supabase -> list_tables (`required_inputs=("project_ref",)`)

The Supabase vendor MCP exposes `list_tables({project_id, schemas})`.
The arg builder pins `schemas=["public"]` so the read NEVER hits
`auth.*`, `storage.*`, or any private schema. Defense:
`test_pr4_arg_builder_supabase_pins_public_schema` confirms even
operator-supplied `schemas=["auth", "storage"]` is overridden to
`["public"]`.

### mcp-neon -> get_database_tables (`required_inputs=("project_id",)`)

The Neon vendor MCP exposes `get_database_tables({projectId})` which
defaults to the project's main branch. We do not pass `branch_id`,
keeping the read narrow + default-only. Does not list snapshots or
modify branches.

---

## 5. Files changed

### `backend/app/services/connection_v2/skill_executor.py`

* Header docstring extended with PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE
  block (lists the 4 promoted entries + the postgres-stays-planned
  rationale).
* 4 entries flipped to `execution_mode="mcp_tool"` with corrected
  `target_tool` names + scoped `required_inputs`.
* `_PLUGIN_TO_SERVER_KEY` got 4 new entries (each plugin's typical
  claude_desktop_config keys + npm package id).
* 4 new arg builders + matching `_ARG_BUILDERS` registrations.

### `backend/tests/test_skill_executor_phase2.py`

* `PROMOTED_TO_MCP_TOOL` registry: 4 new entries tagged with the PR id.
* 6 new tests:
  * `test_pr4_db_describe_promotion_set_is_exactly_four` -- pins exact set
  * `test_pr4_postgres_stays_planned_only` -- defense for the deliberate skip
  * `test_pr4_no_db_write_skills_promoted` -- 23-name forbidden write list
  * `test_pr4_db_promotions_have_arg_builders` -- pins infrastructure parity
  * `test_pr4_arg_builder_sqlite_takes_no_db_path` -- pins SQLite empty-arg shape
  * `test_pr4_arg_builder_supabase_pins_public_schema` -- pins narrow-read defense
  * `test_pr4_server_keys_registered_for_promoted_db_plugins` -- pins resolver coverage

(7 listed; the "exactly four" test counts as one + 6 supporting = 7
total new tests.)

---

## 6. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py
64 passed in 2.64s

$ .venv/Scripts/python.exe -m pytest tests/test_connection_v2_marketplace.py
98 passed in 3.25s

$ .venv/Scripts/python.exe -m pytest tests/test_connections.py
26 passed in 30s

Note: when ALL three files run in one pytest invocation a pre-existing
cross-file test isolation pattern (test_connections seeds tenant
'11111111-...' and the marketplace fixture re-attempts to insert it)
produces 14 errors. Each file passes cleanly in isolation; the
isolation pattern is unrelated to PR-3 (no test fixture changes here).
```

Test growth across the sprint:
* End of Sprint-2: 76/76 phase2 + 26/26 connections = 102
* PR-3 of Sprint-3 adds: 7 new tests
* Now 64/64 phase2 (renamed counting; same suite, +7 from prior 57) + 26/26 connections = 90 in scope, all green.

---

## 7. Live verification (deferred to operator)

None of the 4 newly-promoted DB MCPs are installed on this dev box.
Their behaviour at runtime:

* If the MCP IS NOT installed -> executor returns `needs_connection`
  naming the expected server key (e.g. `"sqlite"`).
* If the MCP IS installed but `target_tool` doesn't match the actual
  vendor tool name -> executor returns `blocked(mcp_tool_error)` with
  the literal MCP error message (NEVER fakes success).

To live-test, the operator installs the MCP via the Plugins UI (PR-2
of this sprint surfaces a clear install + Test loop) and clicks the
new skill chip on the corresponding plugin card.

---

## 8. What did NOT change

* `safe_query` skill mappings (none were ever added to the allowlist;
  they remain forbidden by the brief).
* `_execute_real_mcp_tool` infrastructure (untouched -- same path
  Sprint-1 PR-1/PR-2 + Sprint-2 PR-3 use).
* mcp-postgres allowlist entry (kept, just stays planned with updated
  `reads_summary` explaining the rationale).
* No new dependencies, no install, no production deploy.
* No `vault --apply`, no secrets touched, no V2 flag flip.
