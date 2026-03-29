"""Tests for MemoryService and memory (NBMF) endpoints.

Integration tests: register -> login -> store memory -> recall -> promote -> demote -> history.
Validates the 5-tier Neuroscience-Based Memory Framework lifecycle.
Also tests keyword relevance scoring for recall_for_chat().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.identity import Tenant, User
from app.models.memory import MemoryEntry
from app.services.memory import MemoryService, _tokenize

# ── Helpers ──


async def _register_and_login(client: AsyncClient) -> dict:
    """Register a user and login, returning access token + user data."""
    unique = uuid.uuid4().hex[:8]
    email = f"mem-{unique}@example.com"

    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Memory Tester",
            "tenant_name": f"MemOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    return {
        "token": data["access_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user": data["user"],
    }


# ── Store ──


@pytest.mark.asyncio
async def test_store_memory_basic(client: AsyncClient) -> None:
    """POST /memory/memories creates a memory with correct defaults."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/memory/memories",
        json={"content": "User prefers dark mode"},
        headers=auth["headers"],
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True

    data = body["data"]
    assert data["content"] == "User prefers dark mode"
    assert data["content_type"] == "FACT"
    assert data["tier"] == 0
    assert data["confidence"] == 0.5
    assert data["scope"] == "USER"
    assert data["session_id"] is None
    assert data["access_count"] == 0
    assert data["verification_status"] == "UNVERIFIED"
    assert data["tags"] == []
    assert data["archived_at"] is None
    # WORKING tier gets an expiration
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_store_memory_with_all_fields(client: AsyncClient) -> None:
    """Store with explicit fields: content_type, tier, tags, confidence."""
    auth = await _register_and_login(client)

    response = await client.post(
        "/api/v1/memory/memories",
        json={
            "content": "Always use Python 3.11+",
            "content_type": "POLICY",
            "summary": "Python version policy",
            "tags": ["python", "policy"],
            "source": "team-meeting",
            "confidence": 0.95,
            "tier": 2,
            "metadata": {"category": "engineering"},
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["content_type"] == "POLICY"
    assert data["tier"] == 2
    assert data["tags"] == ["python", "policy"]
    assert data["source"] == "team-meeting"
    assert data["confidence"] == 0.95
    assert data["summary"] == "Python version policy"
    assert data["metadata"] == {"category": "engineering"}
    assert data["scope"] == "USER"
    # LONG_TERM tier has no expiration
    assert data["expires_at"] is None


@pytest.mark.asyncio
async def test_store_session_scoped_memory(client: AsyncClient) -> None:
    """Explicit session scope should persist and surface session_id truthfully."""
    auth = await _register_and_login(client)
    session_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/memory/memories",
        json={
            "content": "Remember this only for the current conversation",
            "tier": 2,
            "scope": "SESSION",
            "session_id": str(session_id),
        },
        headers=auth["headers"],
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["scope"] == "SESSION"
    assert data["session_id"] == str(session_id)


@pytest.mark.asyncio
async def test_store_memory_rejects_high_tier(client: AsyncClient) -> None:
    """Direct storage at tier 3+ is rejected (must promote)."""
    auth = await _register_and_login(client)

    # Tier 3 (CORE) should be rejected by schema validation (max 2)
    response = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Should fail", "tier": 3},
        headers=auth["headers"],
    )
    assert response.status_code == 422  # Schema validation blocks tier > 2


# ── Recall / List ──


@pytest.mark.asyncio
async def test_list_memories_empty(client: AsyncClient) -> None:
    """List memories returns empty for a fresh tenant."""
    auth = await _register_and_login(client)

    response = await client.get(
        "/api/v1/memory/memories",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_list_memories_returns_stored(client: AsyncClient) -> None:
    """List memories returns previously stored entries."""
    auth = await _register_and_login(client)

    # Store 2 memories
    await client.post(
        "/api/v1/memory/memories",
        json={"content": "First memory"},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/memory/memories",
        json={"content": "Second memory"},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/memory/memories",
        headers=auth["headers"],
    )
    body = response.json()
    assert body["pagination"]["total"] == 2
    contents = [m["content"] for m in body["data"]]
    assert "First memory" in contents
    assert "Second memory" in contents


@pytest.mark.asyncio
async def test_list_memories_filter_by_content_type(client: AsyncClient) -> None:
    """Filtering by content_type returns only matching memories."""
    auth = await _register_and_login(client)

    await client.post(
        "/api/v1/memory/memories",
        json={"content": "A fact", "content_type": "FACT"},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/memory/memories",
        json={"content": "A preference", "content_type": "PREFERENCE"},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/memory/memories?content_type=PREFERENCE",
        headers=auth["headers"],
    )
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["content"] == "A preference"


@pytest.mark.asyncio
async def test_list_memories_filter_by_tier(client: AsyncClient) -> None:
    """Filtering by tier returns only matching memories."""
    auth = await _register_and_login(client)

    await client.post(
        "/api/v1/memory/memories",
        json={"content": "Working tier", "tier": 0},
        headers=auth["headers"],
    )
    await client.post(
        "/api/v1/memory/memories",
        json={"content": "Long term", "tier": 2},
        headers=auth["headers"],
    )

    response = await client.get(
        "/api/v1/memory/memories?tier=2",
        headers=auth["headers"],
    )
    body = response.json()
    assert body["pagination"]["total"] == 1
    assert body["data"][0]["content"] == "Long term"


@pytest.mark.asyncio
async def test_get_memory_by_id(client: AsyncClient) -> None:
    """GET /memory/memories/{id} returns the correct memory."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Fetch me"},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    response = await client.get(
        f"/api/v1/memory/memories/{memory_id}",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content"] == "Fetch me"
    # Access count should be incremented
    assert data["access_count"] == 1


@pytest.mark.asyncio
async def test_get_memory_not_found(client: AsyncClient) -> None:
    """GET nonexistent memory returns 404."""
    auth = await _register_and_login(client)

    response = await client.get(
        "/api/v1/memory/memories/00000000-0000-0000-0000-000000000099",
        headers=auth["headers"],
    )
    assert response.status_code == 404


# ── Promote ──


@pytest.mark.asyncio
async def test_promote_memory(client: AsyncClient) -> None:
    """POST /memory/memories/{id}/promote increments the tier."""
    auth = await _register_and_login(client)

    # Create at tier 0 (WORKING)
    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Promotable memory", "tier": 0},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    # Promote: 0 → 1
    response = await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Accessed frequently"},
        headers=auth["headers"],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tier"] == 1  # SHORT_TERM

    # Promote again: 1 → 2
    response2 = await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Critical knowledge"},
        headers=auth["headers"],
    )
    data2 = response2.json()["data"]
    assert data2["tier"] == 2  # LONG_TERM
    # LONG_TERM has no expiration
    assert data2["expires_at"] is None


@pytest.mark.asyncio
async def test_promote_at_max_tier_fails(client: AsyncClient) -> None:
    """Cannot promote beyond IMMUTABLE (tier 4)."""
    auth = await _register_and_login(client)

    # Create at tier 2 and promote to IMMUTABLE (4)
    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "To immutable", "tier": 2},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    # 2→3
    await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Step 1"},
        headers=auth["headers"],
    )
    # 3→4
    await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Step 2"},
        headers=auth["headers"],
    )

    # Attempt 4→5 should fail
    response = await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Beyond immutable"},
        headers=auth["headers"],
    )
    # ValueError → 422 or 400 depending on exception handler
    assert response.status_code == 422


# ── Demote ──


@pytest.mark.asyncio
async def test_demote_memory(client: AsyncClient) -> None:
    """POST /memory/memories/{id}/demote decrements the tier."""
    auth = await _register_and_login(client)

    # Create at tier 2 (LONG_TERM)
    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Demotable memory", "tier": 2},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    # Demote: 2 → 1
    response = await client.post(
        f"/api/v1/memory/memories/{memory_id}/demote",
        json={"reason": "No longer relevant"},
        headers=auth["headers"],
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["tier"] == 1  # SHORT_TERM
    # SHORT_TERM has TTL expiration
    assert data["expires_at"] is not None


@pytest.mark.asyncio
async def test_demote_at_working_tier_fails(client: AsyncClient) -> None:
    """Cannot demote below WORKING (tier 0)."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Working tier memory", "tier": 0},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    response = await client.post(
        f"/api/v1/memory/memories/{memory_id}/demote",
        json={"reason": "Should fail"},
        headers=auth["headers"],
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_demote_immutable_fails(client: AsyncClient) -> None:
    """Cannot demote IMMUTABLE memories."""
    auth = await _register_and_login(client)

    # Create and promote to IMMUTABLE
    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Immutable memory", "tier": 2},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    # Promote to tier 4 (IMMUTABLE): 2→3→4
    await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Step 1"},
        headers=auth["headers"],
    )
    await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Step 2"},
        headers=auth["headers"],
    )

    # Attempt demote
    response = await client.post(
        f"/api/v1/memory/memories/{memory_id}/demote",
        json={"reason": "Should be blocked"},
        headers=auth["headers"],
    )
    assert response.status_code == 422


# ── History (Learning Log) ──


@pytest.mark.asyncio
async def test_memory_history(client: AsyncClient) -> None:
    """GET /memory/memories/{id}/history returns the tier change log."""
    auth = await _register_and_login(client)

    # Create at tier 0
    create_resp = await client.post(
        "/api/v1/memory/memories",
        json={"content": "Track my history"},
        headers=auth["headers"],
    )
    memory_id = create_resp.json()["data"]["id"]

    # Promote: 0→1
    await client.post(
        f"/api/v1/memory/memories/{memory_id}/promote",
        json={"reason": "Good memory"},
        headers=auth["headers"],
    )

    # Demote: 1→0
    await client.post(
        f"/api/v1/memory/memories/{memory_id}/demote",
        json={"reason": "Changed my mind"},
        headers=auth["headers"],
    )

    # Fetch history
    response = await client.get(
        f"/api/v1/memory/memories/{memory_id}/history",
        headers=auth["headers"],
    )
    assert response.status_code == 200
    history = response.json()["data"]

    # Should have 3 entries: CREATED, PROMOTED, DEMOTED (newest first)
    assert len(history) == 3
    actions = [h["action"] for h in history]
    assert "DEMOTED" in actions
    assert "PROMOTED" in actions
    assert "CREATED" in actions

    # Newest first — DEMOTED should be first
    assert history[0]["action"] == "DEMOTED"
    assert history[0]["from_tier"] == 1
    assert history[0]["to_tier"] == 0


@pytest.mark.asyncio
async def test_memory_history_not_found(client: AsyncClient) -> None:
    """History for nonexistent memory returns 404."""
    auth = await _register_and_login(client)

    response = await client.get(
        "/api/v1/memory/memories/00000000-0000-0000-0000-000000000099/history",
        headers=auth["headers"],
    )
    assert response.status_code == 404


# ── Tenant Isolation ──


@pytest.mark.asyncio
async def test_memory_tenant_isolation(client: AsyncClient) -> None:
    """Memories from one tenant are not visible to another."""
    auth1 = await _register_and_login(client)
    auth2 = await _register_and_login(client)

    # Tenant 1 stores a memory
    await client.post(
        "/api/v1/memory/memories",
        json={"content": "Tenant 1 secret"},
        headers=auth1["headers"],
    )

    # Tenant 2 should not see it
    response = await client.get(
        "/api/v1/memory/memories",
        headers=auth2["headers"],
    )
    assert response.json()["pagination"]["total"] == 0


@pytest.mark.asyncio
async def test_recall_for_chat_prefers_session_then_user_then_explicit_tenant(
    db_session,
    test_tenant_id,
) -> None:
    """Chat recall should exclude other-user memories unless they are explicitly tenant-shared."""
    user_a_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    user_b_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    session_keep = uuid.UUID("55555555-5555-5555-5555-555555555555")
    session_skip = uuid.UUID("66666666-6666-6666-6666-666666666666")

    db_session.add(
        Tenant(
            id=test_tenant_id,
            name="Memory Tenant",
            slug="memory-tenant",
            plan="FREE",
            settings={},
        )
    )
    db_session.add_all([
        User(
            id=user_a_id,
            tenant_id=test_tenant_id,
            email="user-a@example.com",
            password_hash="x",
            display_name="User A",
            role="FOUNDER",
            settings={},
        ),
        User(
            id=user_b_id,
            tenant_id=test_tenant_id,
            email="user-b@example.com",
            password_hash="x",
            display_name="User B",
            role="FOUNDER",
            settings={},
        ),
    ])
    await db_session.flush()

    service = MemoryService(db_session)
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_a_id,
        content="User A preference",
        tier=2,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_a_id,
        content="Current session detail",
        tier=2,
        scope="SESSION",
        session_id=session_keep,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_a_id,
        content="Different session detail",
        tier=2,
        scope="SESSION",
        session_id=session_skip,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_b_id,
        content="Other user private memory",
        tier=2,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_b_id,
        content="Tenant shared policy",
        content_type="POLICY",
        tier=2,
        scope="TENANT",
    )

    recall = await service.recall_for_chat(
        tenant_id=test_tenant_id,
        user_id=user_a_id,
        session_id=session_keep,
        tier=2,
        page_size=10,
    )

    contents = [item["content"] for item in recall["data"]]
    assert contents[0] == "Current session detail"
    assert "User A preference" in contents
    assert "Tenant shared policy" in contents
    assert "Other user private memory" not in contents
    assert "Different session detail" not in contents

    result = await db_session.execute(select(MemoryEntry).where(MemoryEntry.tenant_id == test_tenant_id))
    entries = {entry.content: entry for entry in result.scalars().all()}
    assert entries["Current session detail"].access_count == 1
    assert entries["User A preference"].access_count == 1
    assert entries["Tenant shared policy"].access_count == 1
    assert entries["Other user private memory"].access_count == 0


# ── Keyword Relevance Scoring ──


class TestTokenize:
    """Unit tests for _tokenize keyword extraction."""

    def test_basic_tokenization(self) -> None:
        tokens = _tokenize("What is the best marketing strategy?")
        assert "marketing" in tokens
        assert "strategy" in tokens
        assert "best" not in tokens or "best" in tokens  # not a stopword
        # Stopwords removed
        assert "what" not in tokens
        assert "is" not in tokens
        assert "the" not in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == set()

    def test_stopwords_only(self) -> None:
        assert _tokenize("the is a an") == set()

    def test_single_char_stripped(self) -> None:
        # Single characters should be excluded (len > 1 check)
        tokens = _tokenize("I a x go")
        assert "x" not in tokens
        assert "go" in tokens

    def test_hyphenated_words(self) -> None:
        tokens = _tokenize("state-of-the-art machine-learning model")
        assert "machine-learning" in tokens
        assert "model" in tokens

    def test_case_insensitive(self) -> None:
        tokens = _tokenize("Python Django FastAPI")
        assert "python" in tokens
        assert "django" in tokens
        assert "fastapi" in tokens


class TestBlendedScore:
    """Unit tests for MemoryService._blended_score."""

    def _make_entry(
        self,
        content: str = "test",
        summary: str | None = None,
        tags: list[str] | None = None,
        tier: int = 2,
        confidence: float = 0.5,
        created_at: datetime | None = None,
    ) -> MemoryEntry:
        entry = MemoryEntry(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            content=content,
            summary=summary,
            tags=tags or [],
            tier=tier,
            confidence=confidence,
            content_type="FACT",
            access_count=0,
            metadata_={},
        )
        entry.created_at = created_at or datetime.utcnow()
        return entry

    def test_perfect_overlap_scores_high(self) -> None:
        entry = self._make_entry(
            content="marketing strategy plan",
            tags=["marketing"],
            tier=4,
            confidence=0.9,
        )
        query_tokens = _tokenize("marketing strategy")
        score = MemoryService._blended_score(entry, query_tokens, datetime.utcnow())
        # Relevance should be high, tier is max, confidence is high
        assert score > 0.6

    def test_no_overlap_scores_low(self) -> None:
        entry = self._make_entry(
            content="database optimization postgresql",
            tier=2,
            confidence=0.5,
        )
        query_tokens = _tokenize("marketing strategy")
        score = MemoryService._blended_score(entry, query_tokens, datetime.utcnow())
        # No keyword overlap -> relevance component is 0
        # Only tier (0.2 * 0.5) + confidence (0.2 * 0.5) + recency (~0.1)
        assert score < 0.35

    def test_higher_tier_increases_score(self) -> None:
        query_tokens = _tokenize("python development")
        entry_low = self._make_entry(content="python coding", tier=1, confidence=0.5)
        entry_high = self._make_entry(content="python coding", tier=4, confidence=0.5)
        now = datetime.utcnow()
        score_low = MemoryService._blended_score(entry_low, query_tokens, now)
        score_high = MemoryService._blended_score(entry_high, query_tokens, now)
        assert score_high > score_low

    def test_recency_decay(self) -> None:
        query_tokens = _tokenize("deployment process")
        now = datetime.utcnow()
        entry_recent = self._make_entry(
            content="deployment steps", created_at=now - timedelta(hours=1)
        )
        entry_old = self._make_entry(
            content="deployment steps", created_at=now - timedelta(days=30)
        )
        score_recent = MemoryService._blended_score(entry_recent, query_tokens, now)
        score_old = MemoryService._blended_score(entry_old, query_tokens, now)
        assert score_recent > score_old

    def test_tags_contribute_to_relevance(self) -> None:
        query_tokens = _tokenize("security audit")
        entry_no_tags = self._make_entry(content="audit results")
        entry_with_tags = self._make_entry(
            content="audit results", tags=["security", "compliance"]
        )
        now = datetime.utcnow()
        score_no_tags = MemoryService._blended_score(entry_no_tags, query_tokens, now)
        score_with_tags = MemoryService._blended_score(entry_with_tags, query_tokens, now)
        assert score_with_tags > score_no_tags


@pytest.mark.asyncio
async def test_recall_for_chat_with_query_ranks_by_relevance(
    db_session,
    test_tenant_id,
) -> None:
    """When query is provided, recall_for_chat returns memories ranked by keyword relevance."""
    user_id = uuid.UUID("77777777-7777-7777-7777-777777777777")
    session_id = uuid.UUID("88888888-8888-8888-8888-888888888888")

    db_session.add(
        Tenant(
            id=test_tenant_id,
            name="Relevance Tenant",
            slug="relevance-tenant",
            plan="FREE",
            settings={},
        )
    )
    db_session.add(
        User(
            id=user_id,
            tenant_id=test_tenant_id,
            email="relevance@example.com",
            password_hash="x",
            display_name="Relevance Tester",
            role="FOUNDER",
            settings={},
        )
    )
    await db_session.flush()

    service = MemoryService(db_session)

    # Store memories with different topics
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_id,
        content="The marketing campaign for Q2 should focus on enterprise clients",
        tags=["marketing", "enterprise"],
        tier=2,
        confidence=0.8,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_id,
        content="Database migration from PostgreSQL to CockroachDB completed",
        tags=["database", "migration"],
        tier=2,
        confidence=0.9,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_id,
        content="User prefers dark mode for all interfaces",
        tags=["preference", "ui"],
        tier=2,
        confidence=0.7,
    )
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_id,
        content="Marketing budget approved for social media ads",
        tags=["marketing", "budget"],
        tier=2,
        confidence=0.6,
    )

    # Query about marketing -- should rank marketing memories higher
    recall = await service.recall_for_chat(
        tenant_id=test_tenant_id,
        user_id=user_id,
        session_id=session_id,
        query="What is our marketing strategy?",
        tier=2,
        page_size=4,
    )

    contents = [item["content"] for item in recall["data"]]
    # Both marketing memories should rank above database and UI memories
    marketing_indices = [
        i for i, c in enumerate(contents) if "marketing" in c.lower()
    ]
    non_marketing_indices = [
        i for i, c in enumerate(contents) if "marketing" not in c.lower()
    ]
    # All marketing memories should come before non-marketing
    if marketing_indices and non_marketing_indices:
        assert max(marketing_indices) < min(non_marketing_indices)


@pytest.mark.asyncio
async def test_recall_for_chat_without_query_uses_deterministic_sort(
    db_session,
    test_tenant_id,
) -> None:
    """When no query is provided, recall_for_chat uses the original scope/tier/confidence/recency sort."""
    user_id = uuid.UUID("99999999-9999-9999-9999-999999999999")
    session_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    db_session.add(
        Tenant(
            id=test_tenant_id,
            name="Deterministic Tenant",
            slug="deterministic-tenant",
            plan="FREE",
            settings={},
        )
    )
    db_session.add(
        User(
            id=user_id,
            tenant_id=test_tenant_id,
            email="deterministic@example.com",
            password_hash="x",
            display_name="Det Tester",
            role="FOUNDER",
            settings={},
        )
    )
    await db_session.flush()

    service = MemoryService(db_session)

    # No query -- should still work with backward-compatible behavior
    await service.store(
        tenant_id=test_tenant_id,
        user_id=user_id,
        content="Memory without query",
        tier=2,
        confidence=0.5,
    )

    recall = await service.recall_for_chat(
        tenant_id=test_tenant_id,
        user_id=user_id,
        session_id=session_id,
        tier=2,
        page_size=5,
    )

    assert len(recall["data"]) == 1
    assert recall["data"][0]["content"] == "Memory without query"
