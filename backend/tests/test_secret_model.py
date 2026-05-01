"""Tests for backend/app/models/secret.py + migration 006 (Phase 4a-2).

Verifies the Secret SQLAlchemy model:
- Insert + read roundtrip with envelope-encrypted blob columns
- Unique constraint on (tenant_id, secret_class, bound_to)
- Index presence (functional check via duplicate-key constraint)
- Tenant isolation at the row level (different tenants can hold the
  same (class, bound_to) pair without conflict)
- Round-trip with vault_v2 wire shape: encrypt -> persist -> read -> decrypt

Migration 006 (the schema source) is exercised indirectly via
``Base.metadata.create_all`` in the conftest test_engine fixture.
A separate ``test_migration_006_chain`` confirms the chain is valid.
"""

from __future__ import annotations

import base64
import importlib.util
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.vault_v2 import (
    SecretClass,
    derive_tenant_kek,
    encrypt_secret,
    generate_dek,
    unwrap_dek,
    wrap_dek,
)
from app.models.identity import Tenant
from app.models.secret import Secret


@pytest.fixture
async def seeded_tenant(db_session, test_tenant_id):
    """Insert a Tenant row so Secret.tenant_id FK has something to point at."""
    tenant = Tenant(
        id=test_tenant_id,
        name="Test Tenant",
        slug="test-tenant",
        settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    return tenant


# ──────────────────────────────────────────────────────────────────
# Insert / read roundtrip
# ──────────────────────────────────────────────────────────────────


class TestInsertReadRoundtrip:
    @pytest.mark.asyncio
    async def test_basic_insert_and_query_by_class_and_bound_to(
        self, db_session, seeded_tenant, test_tenant_id
    ):
        sec = Secret(
            tenant_id=test_tenant_id,
            secret_class=SecretClass.API_KEY.value,
            bound_to="connection_v2:01926e7f-test",
            ciphertext=b"\x00" * 64,
            nonce=b"\x01" * 12,
            tag=b"\x02" * 16,
            dek_version=1,
            kek_version=1,
            format_version=2,
        )
        db_session.add(sec)
        await db_session.flush()

        loaded = (
            await db_session.execute(
                select(Secret).where(
                    Secret.tenant_id == test_tenant_id,
                    Secret.secret_class == SecretClass.API_KEY.value,
                    Secret.bound_to == "connection_v2:01926e7f-test",
                )
            )
        ).scalar_one()
        assert loaded.id == sec.id
        assert loaded.ciphertext == b"\x00" * 64
        assert loaded.nonce == b"\x01" * 12
        assert loaded.tag == b"\x02" * 16
        assert loaded.dek_version == 1
        assert loaded.kek_version == 1
        assert loaded.format_version == 2
        assert loaded.created_at is not None
        assert loaded.rotated_at is None

    @pytest.mark.asyncio
    async def test_unique_constraint_on_class_bound_within_tenant(
        self, db_session, seeded_tenant, test_tenant_id
    ):
        sec_a = Secret(
            tenant_id=test_tenant_id,
            secret_class=SecretClass.OAUTH_TOKEN.value,
            bound_to="b:1",
            ciphertext=b"x" * 16,
            nonce=b"n" * 12,
            tag=b"t" * 16,
        )
        db_session.add(sec_a)
        await db_session.flush()

        sec_b = Secret(
            tenant_id=test_tenant_id,
            secret_class=SecretClass.OAUTH_TOKEN.value,
            bound_to="b:1",  # same triple
            ciphertext=b"y" * 16,
            nonce=b"m" * 12,
            tag=b"u" * 16,
        )
        db_session.add(sec_b)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_same_class_bound_allowed_across_tenants(
        self, db_session, seeded_tenant, test_tenant_id
    ):
        # Add a second tenant.
        other_tid = uuid.uuid4()
        other = Tenant(
            id=other_tid,
            name="Other Tenant",
            slug="other-tenant",
            settings={},
        )
        db_session.add(other)
        await db_session.flush()

        # Same (class, bound_to) for both tenants -> no conflict.
        for tid in (test_tenant_id, other_tid):
            db_session.add(Secret(
                tenant_id=tid,
                secret_class=SecretClass.MCP_ENV_VAR.value,
                bound_to="mcp:shared-name",
                ciphertext=b"x" * 8,
                nonce=b"n" * 12,
                tag=b"t" * 16,
            ))
        await db_session.flush()

        rows = (await db_session.execute(
            select(Secret).where(Secret.bound_to == "mcp:shared-name")
        )).scalars().all()
        assert len(rows) == 2
        assert {r.tenant_id for r in rows} == {test_tenant_id, other_tid}

    @pytest.mark.asyncio
    async def test_different_class_same_bound_within_tenant_allowed(
        self, db_session, seeded_tenant, test_tenant_id
    ):
        for cls in (SecretClass.API_KEY, SecretClass.OAUTH_CLIENT_SECRET):
            db_session.add(Secret(
                tenant_id=test_tenant_id,
                secret_class=cls.value,
                bound_to="connection_v2:abc",
                ciphertext=b"x" * 8,
                nonce=b"n" * 12,
                tag=b"t" * 16,
            ))
        await db_session.flush()

        rows = (await db_session.execute(
            select(Secret).where(
                Secret.tenant_id == test_tenant_id,
                Secret.bound_to == "connection_v2:abc",
            )
        )).scalars().all()
        assert len(rows) == 2
        assert {r.secret_class for r in rows} == {
            SecretClass.API_KEY.value,
            SecretClass.OAUTH_CLIENT_SECRET.value,
        }


# ──────────────────────────────────────────────────────────────────
# Vault_v2 round-trip via persistence
# ──────────────────────────────────────────────────────────────────


class TestVaultV2Persistence:
    @pytest.mark.asyncio
    async def test_encrypt_persist_read_decrypt_roundtrip(
        self, db_session, seeded_tenant, test_tenant_id
    ):
        # Phase 4a-2 itself does NOT plumb writes through this code path
        # in the application; the service-layer wiring is Phase 4b. But
        # the persistence shape MUST round-trip the wire format from
        # vault_v2.encrypt_secret. This test pins that contract.

        kek_seed = b"k" * 32
        tenant_kek = derive_tenant_kek(kek_seed, str(test_tenant_id))
        dek = generate_dek()
        # In production the wrapped DEK would land in tenants.dek_wrapped;
        # here we just exercise wrap/unwrap independently.
        wrapped = wrap_dek(dek, tenant_kek)
        unwrapped = unwrap_dek(wrapped, tenant_kek)
        assert unwrapped == dek

        plaintext = b"sk-fake-do-not-use"
        record = encrypt_secret(
            plaintext,
            dek=dek,
            secret_class=SecretClass.API_KEY,
            tenant_id=str(test_tenant_id),
            bound_to="connection_v2:end-to-end",
        )

        # Persist: base64 fields decode to BYTEA columns.
        sec = Secret(
            tenant_id=test_tenant_id,
            secret_class=record["class"],
            bound_to=record["bound_to"],
            ciphertext=base64.b64decode(record["ciphertext"]),
            nonce=base64.b64decode(record["nonce"]),
            tag=base64.b64decode(record["tag"]),
            dek_version=record["dek_version"],
            kek_version=record["kek_version"],
            format_version=record["format_version"],
        )
        db_session.add(sec)
        await db_session.flush()
        sec_id = sec.id

        # Read back, reconstruct the wire dict, decrypt.
        loaded = (await db_session.execute(
            select(Secret).where(Secret.id == sec_id)
        )).scalar_one()
        reconstructed = {
            "ciphertext": base64.b64encode(loaded.ciphertext).decode("ascii"),
            "nonce": base64.b64encode(loaded.nonce).decode("ascii"),
            "tag": base64.b64encode(loaded.tag).decode("ascii"),
            "dek_version": loaded.dek_version,
            "kek_version": loaded.kek_version,
            "tenant_id": str(loaded.tenant_id),
            "class": loaded.secret_class,
            "bound_to": loaded.bound_to,
            "format_version": loaded.format_version,
        }
        from app.core.vault_v2 import decrypt_secret
        assert decrypt_secret(
            reconstructed,
            dek=dek,
            secret_class=SecretClass.API_KEY,
            tenant_id=str(test_tenant_id),
            bound_to="connection_v2:end-to-end",
        ) == plaintext


# ──────────────────────────────────────────────────────────────────
# Migration chain sanity
# ──────────────────────────────────────────────────────────────────


class TestMigration006:
    """Confirm migration 006 plugs into the chain at the right point."""

    @staticmethod
    def _migration_path() -> str:
        # Resolve relative to this test file so cwd doesn't matter
        # (pytest runs from backend/, but absolute path is robust).
        from pathlib import Path
        return str(
            Path(__file__).resolve().parent.parent
            / "migrations" / "versions"
            / "006_secrets_envelope_vault.py"
        )

    def test_migration_006_revision_chain(self):
        spec = importlib.util.spec_from_file_location(
            "006_secrets_envelope_vault",
            self._migration_path(),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "006_secrets_envelope_vault"
        assert mod.down_revision == "005_add_cron_mcp_background_tables"

    def test_migration_006_imports_only_safe_dependencies(self):
        # Migration must not import service-layer code (would create
        # circular dependencies during migration runs). Only sqlalchemy,
        # alembic, and app.models.base.GUID/JSONBCompat are allowed.
        with open(self._migration_path()) as f:
            content = f.read()
        for forbidden in (
            "from app.services",
            "from app.api",
            "from app.core.vault_v2",  # don't import the cipher path into migration
        ):
            assert forbidden not in content, (
                f"migration 006 must not import {forbidden!r}"
            )
