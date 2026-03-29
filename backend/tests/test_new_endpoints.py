"""Tests for newly added endpoints: memory/stats, settings/user."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMemoryStats:
    """GET /api/v1/memory/stats returns per-tier counts."""

    @pytest.mark.asyncio
    async def test_stats_endpoint_structure(self):
        """Memory stats should return total and per-tier counts."""
        from app.api.v1.memory import memory_stats

        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.recall.return_value = {
            "data": [],
            "pagination": {"total": 3, "page": 1, "page_size": 1},
        }
        mock_service.get_experience_stats.return_value = {
            "experience_count": 2,
            "quarantined_count": 1,
            "avg_trust_score": 0.65,
        }

        result = await memory_stats(user=mock_user, service=mock_service)
        assert result["success"] is True
        data = result["data"]
        assert "total_memories" in data
        assert "per_tier_counts" in data
        assert data["total_memories"] == 15  # 3 per tier x 5 tiers
        assert "T0" in data["per_tier_counts"]
        assert "T4" in data["per_tier_counts"]
        assert data["experience_count"] == 2
        assert data["quarantined_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_empty_memory(self):
        """Stats should handle zero memories gracefully."""
        from app.api.v1.memory import memory_stats

        mock_user = MagicMock()
        mock_user.tenant_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.recall.return_value = {
            "data": [],
            "pagination": {"total": 0, "page": 1, "page_size": 1},
        }
        mock_service.get_experience_stats.return_value = {
            "experience_count": 0,
            "quarantined_count": 0,
            "avg_trust_score": 0.0,
        }

        result = await memory_stats(user=mock_user, service=mock_service)
        assert result["data"]["total_memories"] == 0
        assert result["data"]["experience_count"] == 0


class TestMemoryClear:
    """POST /api/v1/memory/memories/clear-ephemeral."""

    @pytest.mark.asyncio
    async def test_clear_ephemeral_endpoint_structure(self):
        """Endpoint should return archived_count + tiers."""
        from app.api.v1.memory import clear_ephemeral_memories

        mock_user = MagicMock()
        mock_user.id = uuid.uuid4()
        mock_user.tenant_id = uuid.uuid4()

        mock_service = AsyncMock()
        mock_service.clear_ephemeral.return_value = {
            "archived_count": 3,
            "tiers": [0, 1],
        }

        result = await clear_ephemeral_memories(user=mock_user, service=mock_service)
        assert result["success"] is True
        assert result["data"]["archived_count"] == 3
        assert result["data"]["tiers"] == [0, 1]


class TestUserPreferences:
    """GET/PUT /api/v1/settings/user."""

    @pytest.mark.asyncio
    async def test_get_user_preferences(self):
        """Should return display_name, email, role, preferred_model."""
        from app.api.v1.settings import get_user_preferences

        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.display_name = "Test User"
        mock_user.email = "test@example.com"
        mock_user.role = "FOUNDER"

        # Mock db.execute to return user settings with preferred_model
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {"preferred_model": "gpt-4o"}
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_user_preferences(user=mock_user, db=mock_db)
        assert result["success"] is True
        data = result["data"]
        assert data["display_name"] == "Test User"
        assert data["email"] == "test@example.com"
        assert data["role"] == "FOUNDER"
        assert data["preferred_model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_update_user_display_name(self):
        """PUT should update display name."""
        from app.api.v1.settings import UserPreferencesUpdate, update_user_preferences

        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.display_name = "Old Name"
        mock_user.email = "test@example.com"
        mock_user.role = "FOUNDER"

        # Mock the db_user returned by select(User)
        mock_db_user = MagicMock()
        mock_db_user.display_name = "Old Name"
        mock_db_user.settings = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_user

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        body = UserPreferencesUpdate(display_name="New Name")
        result = await update_user_preferences(body=body, user=mock_user, db=mock_db)

        assert result["success"] is True
        assert result["data"]["display_name"] == "New Name"
        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_user_data(self):
        """Export endpoint should include timestamp + user payload."""
        from app.api.v1.settings import export_user_data

        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.display_name = "Test User"
        mock_user.email = "test@example.com"
        mock_user.role = "FOUNDER"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = {"preferred_model": "gpt-4o"}
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await export_user_data(user=mock_user, db=mock_db)
        assert result["success"] is True
        assert "exported_at" in result["data"]
        assert result["data"]["user"]["display_name"] == "Test User"

    @pytest.mark.asyncio
    async def test_request_user_data_deletion(self):
        """Delete request endpoint should stamp settings and return success."""
        from app.api.v1.settings import request_user_data_deletion

        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"

        mock_db_user = MagicMock()
        mock_db_user.settings = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_db_user
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await request_user_data_deletion(user=mock_user, db=mock_db)
        assert result["success"] is True
        assert result["data"]["requested"] is True
        assert "requested_at" in result["data"]
        assert "pending_delete_requested_at" in mock_db_user.settings
        mock_db.flush.assert_called_once()
