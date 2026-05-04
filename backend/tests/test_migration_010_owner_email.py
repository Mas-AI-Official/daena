"""PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC (Sprint-5 PR-3) tests.

Pins:

  1. Revision wiring: 010 follows 009 in the chain.
  2. Migration runs cleanly on a PRE-Sprint-4-PR-3 schema (a
     ``connector_instances`` table without ``owner_email`` and with the
     original ``(tenant, connector, user)`` unique constraint). After
     upgrade, the column is present and the relaxed constraint allows
     two rows that differ only by owner_email.
  3. Migration is IDEMPOTENT: a second invocation against the
     already-upgraded schema does not raise.
  4. Downgrade is callable without raising.

These tests use a freshly-spun in-memory SQLite (NOT the
session-scoped ``test_engine`` fixture). That keeps the migration's
view of the schema isolated from SQLAlchemy's ``create_all`` view --
otherwise we'd be testing the model declaration, not the migration.
"""

from __future__ import annotations

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


# ──────────────────────────────────────────────────────────────────
# 1. Revision wiring
# ──────────────────────────────────────────────────────────────────


def test_revision_chain_points_at_009():
    mod = importlib.import_module(
        "migrations.versions."
        "010_add_connector_instance_owner_email",
    )
    assert mod.revision == "010_add_connector_instance_owner_email"
    assert mod.down_revision == "009_add_workstream_spine_fields"


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _build_pre_migration_schema(engine):
    """Build a connector_instances table that mirrors what existed
    BEFORE Sprint-4 PR-3 + Sprint-5 PR-1: no owner_email column, and
    a unique constraint on the (tenant, connector, user) triple."""
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE connector_instances ("
            "  id TEXT PRIMARY KEY,"
            "  tenant_id TEXT NOT NULL,"
            "  connector_id TEXT NOT NULL,"
            "  user_id TEXT NOT NULL,"
            "  status TEXT,"
            "  credentials TEXT,"
            "  last_used TEXT,"
            "  created_at TEXT,"
            "  updated_at TEXT,"
            "  CONSTRAINT uq_connector_instances_tenant_connector_user "
            "    UNIQUE (tenant_id, connector_id, user_id)"
            ")"
        ))


def _run_upgrade(engine):
    mod = importlib.import_module(
        "migrations.versions."
        "010_add_connector_instance_owner_email",
    )
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        original_op = mod.op
        mod.op = ops
        try:
            mod.upgrade()
        finally:
            mod.op = original_op


def _run_downgrade(engine):
    mod = importlib.import_module(
        "migrations.versions."
        "010_add_connector_instance_owner_email",
    )
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        ops = Operations(ctx)
        original_op = mod.op
        mod.op = ops
        try:
            mod.downgrade()
        finally:
            mod.op = original_op


def _column_names(engine):
    insp = sa.inspect(engine)
    return {c["name"] for c in insp.get_columns("connector_instances")}


def _index_names(engine):
    insp = sa.inspect(engine)
    return {ix["name"] for ix in insp.get_indexes("connector_instances")}


def _unique_constraint_columns(engine, name):
    insp = sa.inspect(engine)
    for uq in insp.get_unique_constraints("connector_instances"):
        if uq["name"] == name:
            return tuple(uq["column_names"])
    return None


# ──────────────────────────────────────────────────────────────────
# 2. Upgrade against pre-PR-3 schema
# ──────────────────────────────────────────────────────────────────


def test_upgrade_adds_column_index_and_relaxed_constraint():
    engine = sa.create_engine("sqlite://")
    _build_pre_migration_schema(engine)

    # Pre-state: column absent, old constraint exists.
    assert "owner_email" not in _column_names(engine)
    pre_uq = _unique_constraint_columns(
        engine, "uq_connector_instances_tenant_connector_user",
    )
    assert pre_uq == ("tenant_id", "connector_id", "user_id")

    _run_upgrade(engine)

    # Post-state: column present + indexed + relaxed constraint.
    assert "owner_email" in _column_names(engine)
    assert "ix_connector_instances_owner_email" in _index_names(engine)
    new_uq = _unique_constraint_columns(
        engine, "uq_connector_instances_tenant_connector_user_email",
    )
    assert new_uq == (
        "tenant_id", "connector_id", "user_id", "owner_email",
    )


def test_upgrade_allows_two_owner_emails_under_same_user():
    """The whole point of Sprint-5: the relaxed constraint MUST permit
    two rows with the same (tenant, connector, user) but different
    owner_email (masoud@... vs daena@...)."""
    engine = sa.create_engine("sqlite://")
    _build_pre_migration_schema(engine)
    _run_upgrade(engine)

    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO connector_instances "
            "(id, tenant_id, connector_id, user_id, status, owner_email) "
            "VALUES "
            "('id-1', 't', 'c', 'u', 'CONNECTED', 'masoud@mas-ai.co'),"
            "('id-2', 't', 'c', 'u', 'CONNECTED', 'daena@mas-ai.co')"
        ))
    with engine.begin() as conn:
        rows = list(conn.execute(sa.text(
            "SELECT owner_email FROM connector_instances ORDER BY owner_email"
        )))
    assert [r[0] for r in rows] == ["daena@mas-ai.co", "masoud@mas-ai.co"]


def test_upgrade_still_rejects_exact_duplicate_quad():
    """Relaxing one column does not REMOVE the uniqueness floor.
    Two rows with identical (tenant, connector, user, owner_email)
    must still violate."""
    engine = sa.create_engine("sqlite://")
    _build_pre_migration_schema(engine)
    _run_upgrade(engine)

    with engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO connector_instances "
            "(id, tenant_id, connector_id, user_id, status, owner_email) "
            "VALUES ('id-1', 't', 'c', 'u', 'CONNECTED', 'dupe@x.co')"
        ))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(sa.text(
                "INSERT INTO connector_instances "
                "(id, tenant_id, connector_id, user_id, status, "
                "owner_email) "
                "VALUES "
                "('id-2', 't', 'c', 'u', 'CONNECTED', 'dupe@x.co')"
            ))


# ──────────────────────────────────────────────────────────────────
# 3. Idempotency
# ──────────────────────────────────────────────────────────────────


def test_upgrade_is_idempotent():
    """Second invocation against the upgraded schema must be a no-op,
    not raise. Mirrors how Daena dev DBs handle migrations -- the
    schema is half-applied via create_all and then the migration
    backfills."""
    engine = sa.create_engine("sqlite://")
    _build_pre_migration_schema(engine)
    _run_upgrade(engine)
    # Second call -- must not raise.
    _run_upgrade(engine)


# ──────────────────────────────────────────────────────────────────
# 4. Downgrade callable
# ──────────────────────────────────────────────────────────────────


def test_downgrade_callable_after_upgrade():
    """Dev rollback path. Upgrade then downgrade should leave the
    schema without the new constraint / column without raising."""
    engine = sa.create_engine("sqlite://")
    _build_pre_migration_schema(engine)
    _run_upgrade(engine)

    _run_downgrade(engine)

    # owner_email column should be gone.
    assert "owner_email" not in _column_names(engine)
