"""Tests for backend/app/services/vault_migration.py (Phase 4a-3).

Verifies:
  - dry-run reports correct counts on synthetic legacy data
  - dual-read passes for byte-stable roundtrip
  - dual-read detects drift (corrupt ciphertext / DEK / decrypt failure)
  - --apply requires --force when drift occurs (else aborts batch)
  - Plaintext is NEVER printed (counts + structured fields only)
  - Already-migrated rows are skipped (idempotent)
  - tenant.dek_wrapped is provisioned in apply mode, not in dry-run
  - Empty / non-encrypted-string / dict-shape legacy values are handled
"""

from __future__ import annotations

import base64
import json
import logging
import uuid

import pytest
from sqlalchemy import select

from app.core.vault import encrypt_dict
from app.core.vault_v2 import (
    SecretClass,
    derive_tenant_kek,
    generate_dek,
    wrap_dek,
)
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User
from app.models.secret import Secret
from app.services.vault_migration import (
    MigrationOptions,
    _bound_to_for_instance,
    _canonical_json_bytes,
    _classify_legacy_credentials,
    run_migration,
)

KEK_SEED = b"k" * 32  # deterministic seed for tests


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_world(db_session, test_tenant_id):
    """Tenant + User + Connector to satisfy ConnectorInstance FKs."""
    tenant = Tenant(
        id=test_tenant_id, name="T", slug="t", settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        id=uuid.uuid4(), tenant_id=test_tenant_id,
        email="t@test.local", display_name="T", role="FOUNDER", settings={},
    )
    connector = Connector(
        id=uuid.uuid4(), name="test-connector",
        auth_type="API_KEY",
        config_schema={}, tools=[],
    )
    db_session.add(user)
    db_session.add(connector)
    await db_session.flush()
    return tenant, user, connector


_INSTANCE_COUNTER = 0


async def _add_legacy_instance(
    db, *, tenant_id, user_id, connector, plaintext: dict | str | None,
):
    """Create a ConnectorInstance with the given legacy credentials value.

    Each call gets its OWN fresh Connector so the unique constraint on
    (tenant_id, connector_id, user_id) doesn't collide when a test
    seeds multiple rows for the same user.
    """
    global _INSTANCE_COUNTER
    _INSTANCE_COUNTER += 1
    fresh_connector = Connector(
        id=uuid.uuid4(),
        name=f"test-connector-{_INSTANCE_COUNTER}-{uuid.uuid4().hex[:8]}",
        auth_type=connector.auth_type,
        config_schema={}, tools=[],
    )
    db.add(fresh_connector)
    await db.flush()

    if isinstance(plaintext, dict):
        creds = encrypt_dict(plaintext)
    else:
        creds = plaintext  # raw string or None
    inst = ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        connector_id=fresh_connector.id,
        user_id=user_id,
        credentials=creds,
        status="CONNECTED",
    )
    db.add(inst)
    await db.flush()
    return inst


# ──────────────────────────────────────────────────────────────────
# Pure helpers
# ──────────────────────────────────────────────────────────────────


class TestCanonicalJSON:
    def test_dict_keys_are_sorted(self):
        a = _canonical_json_bytes({"b": 1, "a": 2})
        b = _canonical_json_bytes({"a": 2, "b": 1})
        assert a == b
        assert a == b'{"a":2,"b":1}'

    def test_unicode_preserved(self):
        out = _canonical_json_bytes({"name": "café"})
        # ensure_ascii=False -> utf-8 bytes for the e-acute
        assert "café".encode("utf-8") in out

    def test_nested_structures(self):
        a = _canonical_json_bytes({"x": {"b": 1, "a": 2}, "y": [3, 1, 2]})
        b = _canonical_json_bytes({"y": [3, 1, 2], "x": {"a": 2, "b": 1}})
        assert a == b


class TestClassify:
    def test_null_returns_skip(self):
        d, reason = _classify_legacy_credentials(None)
        assert d is None
        assert reason == "null"

    def test_empty_dict_returns_skip(self):
        d, reason = _classify_legacy_credentials({})
        assert d is None
        assert reason == "empty_dict"

    def test_plain_dict_returns_dict(self):
        d, reason = _classify_legacy_credentials({"k": "v"})
        assert d == {"k": "v"}
        assert reason is None

    def test_unencrypted_string_skipped(self):
        d, reason = _classify_legacy_credentials("plain string not encrypted")
        assert d is None
        assert reason == "string_not_encrypted_format"

    def test_encrypted_string_decrypts(self):
        original = {"token": "fake-do-not-use", "scope": "read"}
        ciphertext = encrypt_dict(original)
        d, reason = _classify_legacy_credentials(ciphertext)
        assert d == original
        assert reason is None

    def test_unsupported_type_returns_reason(self):
        d, reason = _classify_legacy_credentials(12345)
        assert d is None
        assert reason.startswith("unsupported_type:")


# ──────────────────────────────────────────────────────────────────
# Dry-run end-to-end
# ──────────────────────────────────────────────────────────────────


class TestDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_counts_candidates_writes_nothing(
        self, db_session, seeded_world, test_tenant_id
    ):
        tenant, user, connector = seeded_world
        for plaintext in [
            {"api_key": "fake-1"},
            {"api_key": "fake-2"},
            {"api_key": "fake-3"},
        ]:
            await _add_legacy_instance(
                db_session,
                tenant_id=test_tenant_id,
                user_id=user.id,
                connector=connector,
                plaintext=plaintext,
            )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=True),
        )

        assert report.counters["candidate"] == 3
        assert report.counters["already_migrated"] == 0
        assert report.counters["skipped"] == 0
        assert report.counters["failed"] == 0
        assert report.counters["drift"] == 0
        assert report.counters["written"] == 0  # dry-run writes nothing
        assert report.counters["dek_provisioned"] == 0  # dry-run does not persist DEK
        assert report.aborted is False

        # Confirm: no Secret rows actually exist.
        rows = (await db_session.execute(select(Secret))).scalars().all()
        assert len(rows) == 0

        # Confirm: tenant.dek_wrapped still None.
        await db_session.refresh(tenant)
        assert tenant.dek_wrapped is None

    @pytest.mark.asyncio
    async def test_dry_run_with_no_candidates_returns_zero(
        self, db_session, seeded_world,
    ):
        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=True),
        )
        assert report.counters["candidate"] == 0
        assert report.counters["written"] == 0


# ──────────────────────────────────────────────────────────────────
# Apply mode end-to-end
# ──────────────────────────────────────────────────────────────────


class TestApplyMode:
    @pytest.mark.asyncio
    async def test_apply_writes_secret_and_provisions_dek(
        self, db_session, seeded_world, test_tenant_id,
    ):
        tenant, user, connector = seeded_world
        plaintext = {"api_key": "fake-do-not-use", "scope": "read"}
        inst = await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector, plaintext=plaintext,
        )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=False),
        )

        assert report.counters["candidate"] == 1
        assert report.counters["written"] == 1
        assert report.counters["dek_provisioned"] == 1
        assert report.counters["drift"] == 0
        assert report.aborted is False

        secrets = (await db_session.execute(select(Secret))).scalars().all()
        assert len(secrets) == 1
        sec = secrets[0]
        assert sec.tenant_id == test_tenant_id
        assert sec.secret_class == SecretClass.API_KEY.value
        assert sec.bound_to == _bound_to_for_instance(inst.id)
        assert len(sec.nonce) == 12
        assert len(sec.tag) == 16
        # Ciphertext exists and is non-empty (no plaintext leaked into row).
        assert isinstance(sec.ciphertext, bytes)
        assert len(sec.ciphertext) > 0

        # Tenant DEK was provisioned.
        await db_session.refresh(tenant)
        assert tenant.dek_wrapped is not None
        assert "wrapped_dek" in tenant.dek_wrapped

        # Legacy credentials NOT nulled (founder rule 6).
        await db_session.refresh(inst)
        assert inst.credentials is not None

    @pytest.mark.asyncio
    async def test_apply_is_idempotent_already_migrated_skipped(
        self, db_session, seeded_world, test_tenant_id,
    ):
        tenant, user, connector = seeded_world
        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": "fake"},
        )

        # First apply: writes 1.
        first = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=False),
        )
        assert first.counters["written"] == 1
        assert first.counters["already_migrated"] == 0

        # Second apply: same input, no new writes.
        second = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=False),
        )
        assert second.counters["candidate"] == 1
        assert second.counters["already_migrated"] == 1
        assert second.counters["written"] == 0


# ──────────────────────────────────────────────────────────────────
# Drift detection
# ──────────────────────────────────────────────────────────────────


class TestDriftDetection:
    @pytest.mark.asyncio
    async def test_legacy_decrypt_failure_counts_skipped(
        self, db_session, seeded_world, test_tenant_id,
    ):
        tenant, user, connector = seeded_world
        # Bogus enc:v1: prefix that fails GCM tag check.
        bad = "enc:v1:" + base64.urlsafe_b64encode(b"a" * 40).decode("ascii")
        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector, plaintext=bad,
        )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=True),
        )
        assert report.counters["candidate"] == 1
        assert report.counters["skipped"] == 1
        assert report.counters["drift"] == 0
        assert report.counters["written"] == 0

    @pytest.mark.asyncio
    async def test_apply_aborts_on_drift_without_force(
        self, db_session, seeded_world, test_tenant_id, monkeypatch,
    ):
        # Force drift by patching _canonical_json_bytes to prefix a
        # non-JSON marker -- the post-decrypt json.loads will raise,
        # which the migration counts as drift (json_decode_error).
        # This is a more reliable patch site than json.loads itself.
        tenant, user, connector = seeded_world
        from app.services import vault_migration as vm
        original_canonical = vm._canonical_json_bytes

        def corrupt_canonical(payload):
            return b"NOT_JSON_AT_ALL\x00" + original_canonical(payload)

        monkeypatch.setattr(vm, "_canonical_json_bytes", corrupt_canonical)

        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": "fake"},
        )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=False, force=False),
        )
        assert report.counters["drift"] == 1
        assert report.aborted is True
        assert report.aborted_reason == "drift_json_decode"
        assert report.counters["written"] == 0

        rows = (await db_session.execute(select(Secret))).scalars().all()
        assert len(rows) == 0

    @pytest.mark.asyncio
    async def test_apply_continues_through_drift_with_force(
        self, db_session, seeded_world, test_tenant_id, monkeypatch,
    ):
        tenant, user, connector = seeded_world
        from app.services import vault_migration as vm
        original_canonical = vm._canonical_json_bytes

        def corrupt_canonical(payload):
            return b"NOT_JSON_AT_ALL\x00" + original_canonical(payload)

        monkeypatch.setattr(vm, "_canonical_json_bytes", corrupt_canonical)

        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": "fake-1"},
        )
        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": "fake-2"},
        )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=False, force=True),
        )
        # With --force, drift is recorded but the batch continues
        # without writing the drifted rows (continue, not break).
        assert report.counters["drift"] == 2
        assert report.aborted is False
        assert report.counters["written"] == 0


# ──────────────────────────────────────────────────────────────────
# Plaintext leak prevention
# ──────────────────────────────────────────────────────────────────


class TestNoSecretLeakage:
    @pytest.mark.asyncio
    async def test_plaintext_never_appears_in_logs(
        self, db_session, seeded_world, test_tenant_id, caplog,
    ):
        tenant, user, connector = seeded_world
        secret_marker = "DO_NOT_LOG_THIS_VALUE_12345"
        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": secret_marker},
        )

        with caplog.at_level(logging.DEBUG, logger="app.services.vault_migration"):
            await run_migration(
                db_session, kek_seed=KEK_SEED,
                options=MigrationOptions(dry_run=False),
            )

        full_log = "\n".join(r.getMessage() for r in caplog.records)
        assert secret_marker not in full_log

    @pytest.mark.asyncio
    async def test_report_drift_records_never_include_plaintext(
        self, db_session, seeded_world, test_tenant_id, monkeypatch,
    ):
        tenant, user, connector = seeded_world
        secret_marker = "REPORT_LEAK_CHECK_67890"

        from app.services import vault_migration as vm
        original_canonical = vm._canonical_json_bytes

        def corrupt_canonical(payload):
            return b"NOT_JSON_AT_ALL\x00" + original_canonical(payload)

        monkeypatch.setattr(vm, "_canonical_json_bytes", corrupt_canonical)

        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": secret_marker},
        )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=True),  # dry-run still tracks drift
        )
        report_json = json.dumps({
            "options": report.options,
            "counters": report.counters,
            "drift_records": report.drift_records,
        }, default=str)
        assert secret_marker not in report_json


# ──────────────────────────────────────────────────────────────────
# Tenant scope + limit
# ──────────────────────────────────────────────────────────────────


class TestScoping:
    @pytest.mark.asyncio
    async def test_tenant_id_filter_only_picks_one_tenant(
        self, db_session, seeded_world, test_tenant_id,
    ):
        tenant_a, user, connector = seeded_world
        # Add a second tenant + their own instance.
        tid_b = uuid.uuid4()
        tenant_b = Tenant(id=tid_b, name="B", slug="b", settings={})
        db_session.add(tenant_b)
        await db_session.flush()
        await _add_legacy_instance(
            db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
            plaintext={"api_key": "tenant-a"},
        )
        await _add_legacy_instance(
            db_session, tenant_id=tid_b, user_id=user.id, connector=connector,
            plaintext={"api_key": "tenant-b"},
        )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=True, tenant_id=test_tenant_id),
        )
        assert report.counters["candidate"] == 1

    @pytest.mark.asyncio
    async def test_limit_caps_candidate_count(
        self, db_session, seeded_world, test_tenant_id,
    ):
        tenant, user, connector = seeded_world
        for i in range(5):
            await _add_legacy_instance(
                db_session, tenant_id=test_tenant_id, user_id=user.id, connector=connector,
                plaintext={"api_key": f"fake-{i}"},
            )

        report = await run_migration(
            db_session, kek_seed=KEK_SEED,
            options=MigrationOptions(dry_run=True, limit=2),
        )
        assert report.counters["candidate"] == 2
