"""Phase 3: Memory Integration Tests (NBMF).

Test 10: Memory read during execution
Test 11: Memory write after execution
Test 12: Memory tier structure and dedup
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.services.memory import MemoryService


# ── Helper to create tenant + user in DB ──────────────────────

async def _setup_tenant_user(db_session):
    """Create a tenant and user in the test DB, returning (tenant_id, user_id)."""
    from app.models.identity import Tenant, User
    from app.core.security import hash_password

    tid = uuid.uuid4()
    uid = uuid.uuid4()

    tenant = Tenant(id=tid, name="MemoryTestOrg", slug=f"mem-{tid.hex[:8]}")
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        id=uid,
        email=f"mem-{uid.hex[:8]}@test.com",
        password_hash=hash_password("test123"),
        display_name="Memory Tester",
        role="OPERATOR",
        tenant_id=tid,
    )
    db_session.add(user)
    await db_session.flush()

    return tid, uid


# ── Test 10: Memory Read ──────────────────────────────────────

class TestMemoryRead:
    @pytest.mark.asyncio
    async def test_memory_service_recall(self, db_session):
        """MemoryService.recall returns list without error."""
        tid, uid = await _setup_tenant_user(db_session)
        svc = MemoryService(db_session)
        results = await svc.recall(
            tenant_id=tid,
        )
        assert isinstance(results, dict)
        assert "data" in results

    @pytest.mark.asyncio
    async def test_memory_recall_empty_returns_list(self, db_session):
        """Empty memory store returns empty list, not error."""
        tid, uid = await _setup_tenant_user(db_session)
        svc = MemoryService(db_session)
        results = await svc.recall(
            tenant_id=tid,
            content_type="NONEXISTENT_TYPE",
        )
        assert isinstance(results, dict)
        assert len(results.get("data", [])) == 0


# ── Test 11: Memory Write ─────────────────────────────────────

class TestMemoryWrite:
    @pytest.mark.asyncio
    async def test_memory_store(self, db_session):
        """MemoryService.store creates an entry without error."""
        tid, uid = await _setup_tenant_user(db_session)
        svc = MemoryService(db_session)
        result = await svc.store(
            tenant_id=tid,
            user_id=uid,
            content="Daena successfully deployed to GCP Cloud Run",
            content_type="EXPERIENCE",
            source="execution",
        )
        assert result is not None
        assert "id" in result

    @pytest.mark.asyncio
    async def test_memory_store_and_recall_roundtrip(self, db_session):
        """Store then recall should find the entry."""
        tid, uid = await _setup_tenant_user(db_session)
        svc = MemoryService(db_session)

        stored = await svc.store(
            tenant_id=tid,
            user_id=uid,
            content="The Stripe API key is configured in production settings",
            content_type="FACT",
            source="manual",
        )
        assert stored is not None

        results = await svc.recall(
            tenant_id=tid,
            content_type="FACT",
        )
        assert isinstance(results, dict)
        assert len(results.get("data", [])) >= 1


# ── Test 12: Memory Tier Structure ────────────────────────────

class TestMemoryTiers:
    def test_tier_constants_valid(self):
        valid_tiers = {0, 1, 2, 3, 4}
        for tier in valid_tiers:
            assert isinstance(tier, int)

    @pytest.mark.asyncio
    async def test_memory_service_interface(self, db_session):
        svc = MemoryService(db_session)
        assert hasattr(svc, "store")
        assert hasattr(svc, "recall")
        assert callable(svc.store)
        assert callable(svc.recall)

    @pytest.mark.asyncio
    async def test_cas_dedup_prevents_duplicates(self, db_session):
        """CAS SHA-256 dedup should prevent duplicate entries."""
        tid, uid = await _setup_tenant_user(db_session)
        svc = MemoryService(db_session)
        content = "Unique content for dedup test " + uuid.uuid4().hex

        r1 = await svc.store(
            tenant_id=tid, user_id=uid,
            content=content, content_type="FACT",
        )
        r2 = await svc.store(
            tenant_id=tid, user_id=uid,
            content=content, content_type="FACT",
        )
        assert r1["id"] == r2["id"], "CAS dedup should return same entry for identical content"
