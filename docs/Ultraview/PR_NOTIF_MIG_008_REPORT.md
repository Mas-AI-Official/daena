# PR-NOTIF-MIG-008 — Notifications Table Migration

**Date:** 2026-05-01
**Branch:** `rebuild-connections-mcp-runtime`
**Scope:** Add Alembic migration 008 for the `notifications` table introduced by Phase 11 PR-S2 + retrofitted by PR-S2.1.
**Trigger:** `DAENA_BACKEND_BLINDSPOT_INVENTORY.md` §13 Item #1 — sole P0 production blocker.

---

## Why this PR exists

Phase 11 PR-S2 (commit `2e414cf`) introduced `app.models.notification.Notification` and `NotificationService.emit(...)`. PR-S2.1 (commit `f71892c`) retrofitted three core services to write notifications:

- `execution_service.py` — emits `task_complete` after a background task ends
- `cost_guard.py` — emits `budget_alert` from the warn-tier preflight branch (60-min per-user dedup)
- `approval.py` — emits `governance_rejection` to the requester (not the approver)

SQLite dev quietly hid the missing migration via `Base.metadata.create_all` in `main.py.lifespan`. PostgreSQL production has no such fallback — every emit would have raised `sqlalchemy.exc.ProgrammingError: relation "notifications" does not exist` and crashed the path it was wrapped in. Three of those three retrofits (`execution`, `approval`, `cost_guard`) wrap emit in `try/except ... logger.warning`, so the visible failure mode would have been "every prod task / rejection / budget warning silently logs a notify_failed warning forever." This PR closes that gap.

---

## Migration file

**Path:** `backend/migrations/versions/008_add_notifications.py`
**Revision ID:** `008_add_notifications`
**Down-revision:** `007_connection_v2_registry`
**Pattern:** Mirrors migrations 005–007 (idempotency helpers `_table_exists` + `_index_exists`, model-side decorator types via `app.models.base`, FK names `fk_<table>_<col>_<reftable>`, indexes `ix_<table>_<col>`, downgrade drops indexes before table).

---

## Columns created (11 total — all 8 brief-required fields plus the 3 from `TimestampMixin`)

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `GUID()` (UUID Postgres / String(36) SQLite) | NOT NULL | uuid4 (model-side) | Primary key `pk_notifications` |
| `tenant_id` | `GUID()` | NOT NULL | — | FK `fk_notifications_tenant_id_tenants` ON DELETE CASCADE |
| `user_id` | `GUID()` | NOT NULL | — | FK `fk_notifications_user_id_users` ON DELETE CASCADE |
| `type` | `String(40)` | NOT NULL | — | Event taxonomy from `_NOTIF_TYPES` |
| `title` | `String(200)` | NOT NULL | — | Bell row title |
| `message` | `Text` | NOT NULL | — | Bell row body |
| `severity` | `String(20)` | NOT NULL | `'info'` | info / success / warning / error |
| `source` | `String(100)` | NULL | — | Subsystem attribution (e.g. `cost_guard.preflight`) |
| `read_at` | `DateTime(timezone=True)` | NULL | — | NULL = unread |
| `created_at` | `DateTime(timezone=True)` | NOT NULL | `now()` (server) | From `TimestampMixin` |
| `updated_at` | `DateTime(timezone=True)` | NULL | `onupdate=now()` | From `TimestampMixin` |

Model parity verified by SQLite `PRAGMA table_info` against `notification.py` declaration — exact match on type, nullability, defaults.

---

## Indexes created (4)

| Index | Columns | Purpose |
|---|---|---|
| `ix_notifications_tenant_id` | `tenant_id` | Implicit from `index=True` on the model column. Tenant-scoped admin queries. |
| `ix_notifications_user_id` | `user_id` | Implicit from `index=True`. Per-user listing. |
| `ix_notifications_type` | `type` | Implicit from `index=True`. Future per-type filtering. |
| `ix_notifications_user_id_created_at` | `(user_id, created_at)` | Composite, declared in model `__table_args__`. **Bell hot query**: `WHERE user_id = ? ORDER BY created_at DESC LIMIT N`. Same composite covers the `unread_only` variant via post-fetch filter on `read_at IS NULL`. |

Plus the implicit `sqlite_autoindex_notifications_1` on the PK (auto-created by SQLite, not by the migration).

---

## Foreign keys (2)

| FK | From → To | ON DELETE | Reason |
|---|---|---|---|
| `fk_notifications_tenant_id_tenants` | `notifications.tenant_id` → `tenants.id` | CASCADE | Drop a tenant ⇒ drop their notifications. Defense-in-depth on top of API user-id filter. |
| `fk_notifications_user_id_users` | `notifications.user_id` → `users.id` | CASCADE | Drop a user ⇒ drop their notifications. |

---

## Verification commands run + results

All run from `backend/` against `daena_dev2.db` (SQLite) using `./.venv/Scripts/python.exe` and `./.venv/Scripts/alembic.exe`.

### 1. Pre-state — alembic head was 007

```
$ alembic -c migrations/alembic.ini current
007_connection_v2_registry
```

### 2. Upgrade head — single migration applied

```
$ alembic -c migrations/alembic.ini upgrade head
INFO  [alembic.runtime.migration] Running upgrade 007_connection_v2_registry -> 008_add_notifications,
      Add notifications table (Phase 11 PR-S2 + PR-S2.1).
```

### 3. Post-state — alembic head is now 008

```
$ alembic -c migrations/alembic.ini current
008_add_notifications (head)
```

### 4. Schema inspection — all columns + types + defaults + nullability match the model

```
$ python -c "import sqlite3; ... PRAGMA table_info('notifications')"
(0,  'id',         'VARCHAR(36)', 1, None,                 1)
(1,  'tenant_id',  'VARCHAR(36)', 1, None,                 0)
(2,  'user_id',    'VARCHAR(36)', 1, None,                 0)
(3,  'type',       'VARCHAR(40)', 1, None,                 0)
(4,  'title',      'VARCHAR(200)',1, None,                 0)
(5,  'message',    'TEXT',        1, None,                 0)
(6,  'severity',   'VARCHAR(20)', 1, "'info'",             0)
(7,  'source',     'VARCHAR(100)',0, None,                 0)
(8,  'read_at',    'DATETIME',    0, None,                 0)
(9,  'created_at', 'DATETIME',    1, 'CURRENT_TIMESTAMP',  0)
(10, 'updated_at', 'DATETIME',    0, None,                 0)
```

### 5. Index inspection — 4 named indexes plus the PK auto-index

```
ix_notifications_user_id_created_at
ix_notifications_type
ix_notifications_user_id
ix_notifications_tenant_id
sqlite_autoindex_notifications_1   (auto, PK)
```

### 6. FK inspection — both CASCADE deletes wired

```
notifications.user_id   -> users.id   ON DELETE CASCADE
notifications.tenant_id -> tenants.id ON DELETE CASCADE
```

### 7. Idempotency — re-run upgrade is no-op

```
$ alembic -c migrations/alembic.ini upgrade head
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
(no migration ran — already at head)
```

### 8. Roundtrip — downgrade -1 cleanly drops table + indexes, upgrade head restores

```
$ alembic -c migrations/alembic.ini downgrade -1
INFO  [alembic.runtime.migration] Running downgrade 008_add_notifications -> 007_connection_v2_registry

$ python -c "... SELECT name FROM sqlite_master WHERE name LIKE 'ix_notifications%'"
(empty result — all 4 indexes gone)

$ python -c "... SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'"
(empty result — table gone)

$ python -c "... SELECT * FROM alembic_version"
('007_connection_v2_registry',)

$ alembic -c migrations/alembic.ini upgrade head
INFO  [alembic.runtime.migration] Running upgrade 007_connection_v2_registry -> 008_add_notifications
```

Re-inspection after re-upgrade shows all 11 columns + 4 indexes + 2 FKs back. Roundtrip clean.

### 9. Phase 11 PR-S1 + PR-S2 + PR-S2.1 tests — all 19 pass against migrated schema

```
$ pytest tests/test_phase11_notification_emitter.py \
         tests/test_phase11_notification_retrofit.py \
         tests/test_phase11_privacy_enforcement.py -v --no-header

tests/test_phase11_notification_emitter.py::test_emit_default_writes_row                  PASSED
tests/test_phase11_notification_emitter.py::test_emit_disabled_flag_suppresses_row        PASSED
tests/test_phase11_notification_emitter.py::test_emit_ungated_type_always_writes          PASSED
tests/test_phase11_notification_emitter.py::test_post_test_endpoint_creates_row           PASSED
tests/test_phase11_notification_emitter.py::test_get_list_returns_recent_for_user         PASSED
tests/test_phase11_notification_emitter.py::test_get_list_unread_only_filter              PASSED
tests/test_phase11_notification_retrofit.py::test_task_complete_emits_notification_when_enabled        PASSED
tests/test_phase11_notification_retrofit.py::test_task_complete_suppressed_when_flag_off               PASSED
tests/test_phase11_notification_retrofit.py::test_governance_rejection_emits_notification_to_requester PASSED
tests/test_phase11_notification_retrofit.py::test_governance_rejection_suppressed_when_flag_off        PASSED
tests/test_phase11_notification_retrofit.py::test_budget_alert_emits_on_warn_action                    PASSED
tests/test_phase11_notification_retrofit.py::test_budget_alert_dedup_within_window                     PASSED
tests/test_phase11_notification_retrofit.py::test_budget_alert_suppressed_when_flag_off                PASSED
tests/test_phase11_privacy_enforcement.py::test_memory_generation_default_allows_write                 PASSED
tests/test_phase11_privacy_enforcement.py::test_memory_generation_explicit_true_allows_write           PASSED
tests/test_phase11_privacy_enforcement.py::test_memory_generation_false_blocks_write_and_audits        PASSED
tests/test_phase11_privacy_enforcement.py::test_memory_generation_block_audit_emits_only_once_per_user PASSED
tests/test_phase11_privacy_enforcement.py::test_search_past_conversations_default_returns_allow        PASSED
tests/test_phase11_privacy_enforcement.py::test_search_past_conversations_false_blocks_recall          PASSED

============================== 19 passed in 26.48s ==============================
```

`Base.metadata.create_all` was NOT used as a substitute for the migration — alembic provided the schema in steps 2–8 above. The tests use the same schema the migration produces, not a parallel `create_all` definition.

---

## Production deploy unblock verdict

**YES — the notifications-table side of production deploy is now unblocked.**

Specifically:

1. PostgreSQL prod can now upgrade to head and obtain the `notifications` table with the same column set, types, defaults, FKs, and indexes that the model declares.
2. After the upgrade, `NotificationService.emit(...)` calls from `execution_service`, `cost_guard`, `approval` (PR-S2.1 retrofits) will succeed instead of raising `ProgrammingError: relation "notifications" does not exist`.
3. The `GET /api/v1/notifications` and `POST /api/v1/notifications/test` routes (PR-S2) will return real rows instead of erroring at the first `session.execute` against the missing relation.
4. The frontend bell hydration (`hydrateNotificationsFromBackend(20)` in `Header.tsx` mount effect) will populate from the new table.

What this PR DOES NOT do:

- Does not deploy. Per the brief's hard rule #1 — local migration verification only.
- Does not flip `USE_CONNECTION_REGISTRY_V2`. Migration 007 already created the V2 tables behind the same flag; flipping is unrelated to PR-S2/S2.1.
- Does not touch vault, OAuth credentials store, or any other unrelated file.
- Does not run the broader test suite. Only the three Phase 11 test files were exercised — that is the surface PR-S2 / PR-S2.1 introduced and the surface this migration must back.
- Does not update production `alembic_version`. That happens during the eventual production deploy via `alembic upgrade head`; this PR only ships the migration file.

---

## Caveats

1. **Column-comment `index=True` parity**: The Notification model uses `index=True` on `tenant_id`, `user_id`, and `type`. The migration creates these as named single-column indexes (`ix_notifications_<col>`) via explicit `op.create_index` calls — same pattern as migrations 005–007 (which also do not pass `index=True` to `op.create_table`'s columns and instead emit explicit `op.create_index` after). This means the SQLite `Base.metadata.create_all` path and the alembic path produce identically named indexes.
2. **PostgreSQL `now()` server default**: SQLite renders `sa.func.now()` as `CURRENT_TIMESTAMP`; PostgreSQL renders as `now()`. Both compile to identical UTC behavior at the database layer. Verified by inspection in step 4 above (`'CURRENT_TIMESTAMP'` literal in SQLite output).
3. **Idempotency relies on inspector visibility**: `_table_exists` and `_index_exists` ask the bind's inspector. If a prior `Base.metadata.create_all` already produced an identically named table on PostgreSQL, the migration will skip and stamp 008 anyway. This matches the documented intent in migration 005's docstring and is the established Daena pattern for SQLite-dev-then-Postgres-prod alignment.
4. **No backfill needed**: No prior data migration is required because no rows existed pre-table. The 5-emitter retrofit is post-PR-S2; until PR-S2 landed, no service ever attempted to write a notification.
5. **Dev DB sprawl noted but untouched per Blind-Spot Inventory §11**: `daena.db` (0 bytes) and `daena_dev.db` (0 bytes) sit alongside `daena_dev2.db` (the real one). This migration was applied only to `daena_dev2.db` because that is the file `.env` declares as `DATABASE_URL`. The two zero-byte siblings remain untouched per "do not modify unrelated files."
6. **No frontend changes**: Frontend was not modified. The bell-hydration code path from PR-S2 already exists in `Header.tsx`; it now has a real backing table to hydrate from. `tsc --noEmit` was not run because frontend was untouched.
7. **Audit log not emitted for the migration itself**: This is a schema migration, not a runtime decision — no audit row is appropriate. The Phase 11 emitters that USE this table continue to write their own audit events for governance-relevant emits (e.g. `governance_rejection` notifications follow the existing `approval.reject` audit log entry).

---

## Files changed

```
A backend/migrations/versions/008_add_notifications.py     (155 lines)
A docs/Ultraview/PR_NOTIF_MIG_008_REPORT.md                (this file)
```

No other file modified.

---

## Next recommended PR

Per the Blind-Spot Inventory + Phase J recommendation, the next two PRs are:

1. **PR-AUDIT-VERIFY + PR-RAG-HONEST** (3 h, multi-agent split per CLAUDE.md delegation table) — original Backlog PR #1.
2. **PR-DOC-DRIFT-FIX** (15 min, doc-only) — downgrade BACKLOG P0 #4 (Dream Engine "UNSCHEDULED") to P2; fix CLAUDE.md `vault.py` reference to `vault_adapter.py`; add a Blindspot Reconciliation appendix to `DAENA_ARCHITECTURE_ATLAS.md`.

This PR (PR-NOTIF-MIG-008) does not block either of those — they can run in any order against this branch.

---

**End of report.**
