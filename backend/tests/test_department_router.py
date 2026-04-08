"""Tests for DepartmentRouter: task-to-agent routing.

Covers:
- Task type to department mapping
- Agent loading from mock DB
- Subtask routing with department metadata injection
- Unknown task types return None
- Available departments listing
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.department_router import (
    DepartmentRouter,
    TASK_DEPARTMENT_MAP,
    AgentAssignment,
)


class TestTaskDepartmentMap:
    """Tests for the static task type to department mapping."""

    def test_code_generation_maps_to_engineering(self):
        dept, sub = TASK_DEPARTMENT_MAP["code_generation"]
        assert dept == "Engineering"
        assert sub == "HANDS"

    def test_web_research_maps_to_research(self):
        dept, sub = TASK_DEPARTMENT_MAP["web_research"]
        assert dept == "Research"
        assert sub == "EYES"

    def test_complex_reasoning_maps_to_operations(self):
        dept, sub = TASK_DEPARTMENT_MAP["complex_reasoning"]
        assert dept == "Operations"
        assert sub == "MIND"

    def test_security_scan_maps_to_security(self):
        dept, sub = TASK_DEPARTMENT_MAP["security_scan"]
        assert dept == "Security Operations"
        assert sub == "SHIELD"

    def test_all_mappings_have_two_parts(self):
        for task_type, (dept, sub) in TASK_DEPARTMENT_MAP.items():
            assert isinstance(dept, str) and dept, f"Bad department for {task_type}"
            assert isinstance(sub, str) and sub, f"Bad sub_capability for {task_type}"

    def test_sub_capabilities_are_valid(self):
        valid = {"MIND", "EYES", "HANDS", "VOICE", "SHIELD", "MEMORY"}
        for task_type, (_, sub) in TASK_DEPARTMENT_MAP.items():
            assert sub in valid, f"Invalid sub_capability '{sub}' for {task_type}"


class TestDepartmentRouter:
    """Tests for DepartmentRouter service."""

    @pytest.mark.asyncio
    async def test_route_known_task_type(self):
        """Route a known task type to a department agent."""
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        # Pre-load agents manually
        router._agents = {
            ("Engineering", "HANDS"): AgentAssignment(
                department_name="Engineering",
                sub_capability="HANDS",
                agent_id="agent-1",
                department_id="dept-1",
                model_preference="claude-code-cli",
            ),
        }
        router._loaded = True

        result = await router.route("code_generation")
        assert result is not None
        assert result.department_name == "Engineering"
        assert result.sub_capability == "HANDS"
        assert result.agent_id == "agent-1"
        assert result.model_preference == "claude-code-cli"

    @pytest.mark.asyncio
    async def test_route_unknown_task_type(self):
        """Unknown task types should return None."""
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        router._loaded = True

        result = await router.route("unknown_task_type")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_missing_agent(self):
        """Known task type but no matching agent should return None."""
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        router._agents = {}  # No agents loaded
        router._loaded = True

        result = await router.route("code_generation")
        assert result is None

    @pytest.mark.asyncio
    async def test_route_subtasks(self):
        """Route a list of subtasks, injecting metadata."""
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        router._agents = {
            ("Engineering", "HANDS"): AgentAssignment(
                department_name="Engineering",
                sub_capability="HANDS",
                agent_id="agent-eng",
            ),
            ("Research", "EYES"): AgentAssignment(
                department_name="Research",
                sub_capability="EYES",
                agent_id="agent-res",
            ),
        }
        router._loaded = True

        # Mock subtasks (duck-type -- just need task_type and metadata)
        class FakeSubTask:
            def __init__(self, task_type):
                self.task_type = task_type
                self.metadata = {}

        subtasks = [
            FakeSubTask("code_generation"),
            FakeSubTask("web_research"),
            FakeSubTask("unknown_type"),
        ]

        result = await router.route_subtasks(subtasks)
        assert len(result) == 3

        # First subtask should be routed to Engineering
        assert subtasks[0].metadata.get("department") == "Engineering"
        assert subtasks[0].metadata.get("agent_id") == "agent-eng"

        # Second subtask should be routed to Research
        assert subtasks[1].metadata.get("department") == "Research"
        assert subtasks[1].metadata.get("agent_id") == "agent-res"

        # Third subtask should have no routing
        assert "department" not in subtasks[2].metadata
        assert "agent_id" not in subtasks[2].metadata

    @pytest.mark.asyncio
    async def test_get_department_for_task(self):
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        assert router.get_department_for_task("code_generation") == "Engineering"
        assert router.get_department_for_task("web_research") == "Research"
        assert router.get_department_for_task("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_available_departments(self):
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        router._agents = {
            ("Engineering", "HANDS"): AgentAssignment(department_name="Engineering", sub_capability="HANDS"),
            ("Research", "EYES"): AgentAssignment(department_name="Research", sub_capability="EYES"),
            ("Engineering", "MIND"): AgentAssignment(department_name="Engineering", sub_capability="MIND"),
        }
        router._loaded = True

        depts = router.get_available_departments()
        assert depts == ["Engineering", "Research"]

    @pytest.mark.asyncio
    async def test_preferred_department_override(self):
        """User can override the default department routing."""
        router = DepartmentRouter(db=AsyncMock(), tenant_id=uuid.uuid4())
        router._agents = {
            ("Marketing", "HANDS"): AgentAssignment(
                department_name="Marketing",
                sub_capability="HANDS",
                agent_id="mkt-hands",
            ),
        }
        router._loaded = True

        # code_generation normally goes to Engineering, but user prefers Marketing
        result = await router.route("code_generation", preferred_department="Marketing")
        assert result is not None
        assert result.department_name == "Marketing"

    @pytest.mark.asyncio
    async def test_load_agents_handles_db_failure(self):
        """DB failure during load should not crash."""
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=Exception("DB down"))
        router = DepartmentRouter(db=db, tenant_id=uuid.uuid4())

        count = await router.load_agents()
        assert count == 0
        assert router._loaded is True  # Should not retry


class TestOAuthService:
    """Tests for ConnectorOAuthService (multi-provider)."""

    def test_generate_auth_url(self):
        from app.services.integrations.oauth_service import ConnectorOAuthService
        service = ConnectorOAuthService(db=AsyncMock())
        # Mock settings to have a client ID
        service._settings = MagicMock(google_client_id="test-client-id", google_client_secret="test-secret")
        url, state = service.generate_auth_url(
            provider="gmail",
            redirect_uri="http://localhost:8000/callback",
        )
        assert "accounts.google.com" in url
        assert "gmail.modify" in url
        assert "test-client-id" in url
        assert state is not None
        assert len(state) > 20

    def test_generate_auth_url_calendar(self):
        from app.services.integrations.oauth_service import ConnectorOAuthService
        service = ConnectorOAuthService(db=AsyncMock())
        service._settings = MagicMock(google_client_id="test-client-id")
        url, state = service.generate_auth_url(
            provider="google-calendar",
            redirect_uri="http://localhost:8000/callback",
        )
        assert "calendar" in url

    def test_generate_auth_url_github(self):
        from app.services.integrations.oauth_service import ConnectorOAuthService
        service = ConnectorOAuthService(db=AsyncMock())
        service._settings = MagicMock(github_client_id="gh-test-id")
        url, state = service.generate_auth_url(
            provider="github",
            redirect_uri="http://localhost:8000/callback",
        )
        assert "github.com/login/oauth" in url
        assert "gh-test-id" in url

    def test_generate_auth_url_missing_credentials(self):
        from app.services.integrations.oauth_service import ConnectorOAuthService, OAuthConfigError
        service = ConnectorOAuthService(db=AsyncMock())
        service._settings = MagicMock(google_client_id="")
        with pytest.raises(OAuthConfigError, match="OAuth not configured"):
            service.generate_auth_url(
                provider="gmail",
                redirect_uri="http://localhost:8000/callback",
            )

    def test_generate_auth_url_unknown_provider(self):
        from app.services.integrations.oauth_service import ConnectorOAuthService
        service = ConnectorOAuthService(db=AsyncMock())
        with pytest.raises(ValueError, match="No OAuth provider configured"):
            service.generate_auth_url(
                provider="unknown-provider",
                redirect_uri="http://localhost:8000/callback",
            )

    def test_supported_providers(self):
        from app.services.integrations.oauth_service import ConnectorOAuthService, OAUTH_PROVIDERS
        service = ConnectorOAuthService(db=AsyncMock())
        providers = service.get_supported_providers()
        assert len(providers) == len(OAUTH_PROVIDERS)
        assert any(p["provider_id"] == "github" for p in providers)

    @pytest.mark.asyncio
    async def test_check_and_refresh_valid_token(self):
        """Valid (not expired) token should pass through unchanged."""
        from datetime import datetime, timezone, timedelta
        from app.services.integrations.oauth_service import ConnectorOAuthService

        service = ConnectorOAuthService(db=AsyncMock())
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        creds = {
            "access_token": "valid-token",
            "refresh_token": "refresh-token",
            "expires_at": future,
        }
        result = await service.check_and_refresh(creds)
        assert result["access_token"] == "valid-token"

    @pytest.mark.asyncio
    async def test_check_and_refresh_no_refresh_token(self):
        """Missing refresh token should pass through unchanged."""
        from app.services.integrations.oauth_service import ConnectorOAuthService

        service = ConnectorOAuthService(db=AsyncMock())
        creds = {"access_token": "some-token"}
        result = await service.check_and_refresh(creds)
        assert result["access_token"] == "some-token"
