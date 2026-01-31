"""
Smoke test: Moltbot-style provider control.
- Mocks provider inbound message -> verifies ToolRequest creation
- Verifies denial when tool disabled / not in allowlist
- Verifies approval needed for medium+ risk when approval_mode == require_approval
"""

from __future__ import annotations

import os
import sys
import pytest

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.providers.base import InboundMessage
from backend.providers.config import (
    get_provider_config,
    update_provider_settings,
    reload_provider_config,
    is_provider_enabled,
    get_allowed_tools,
)
from backend.services.provider_tool_request import (
    create_tool_request_from_message,
    submit_tool_request,
    ProviderToolRequest,
)
from backend.services.execution_layer_config import (
    get_execution_config,
    get_tool_risk_level,
    create_approval,
    consume_approval,
)


def _inbound(provider_id: str, text: str, channel_id: str = "test_ch", user_id: str = "test_user") -> InboundMessage:
    return InboundMessage(
        provider_id=provider_id,
        channel_id=channel_id,
        user_id=user_id,
        user_name="TestUser",
        text=text,
        raw={},
    )


@pytest.mark.asyncio
async def test_create_tool_request_health_check():
    """Inbound 'health check' creates ToolRequest when provider enabled and tool in allowlist."""
    update_provider_settings("discord", enabled=True, allowed_tools=["health_check", "list_tools"])
    reload_provider_config()
    msg = _inbound("discord", "health check")
    req = create_tool_request_from_message(msg)
    assert req is not None
    assert req.provider_id == "discord"
    assert req.tool_name == "health_check"


@pytest.mark.asyncio
async def test_denial_when_provider_disabled():
    """When provider is disabled, no ToolRequest is created."""
    update_provider_settings("discord", enabled=False, allowed_tools=["health_check"])
    reload_provider_config()
    msg = _inbound("discord", "health check")
    req = create_tool_request_from_message(msg)
    assert req is None


@pytest.mark.asyncio
async def test_denial_when_tool_not_in_allowlist():
    """When tool is not in provider allowlist, no ToolRequest is created."""
    update_provider_settings("discord", enabled=True, allowed_tools=[])  # empty = deny all
    reload_provider_config()
    msg = _inbound("discord", "health check")
    req = create_tool_request_from_message(msg)
    assert req is None

    update_provider_settings("discord", enabled=True, allowed_tools=["list_tools"])  # health_check not allowed
    reload_provider_config()
    msg = _inbound("discord", "health check")
    req = create_tool_request_from_message(msg)
    assert req is None


@pytest.mark.asyncio
async def test_submit_health_check_succeeds():
    """Submit health_check ToolRequest runs and returns result."""
    update_provider_settings("discord", enabled=True, allowed_tools=["health_check"])
    reload_provider_config()
    msg = _inbound("discord", "health check")
    req = create_tool_request_from_message(msg)
    assert req is not None
    result = await submit_tool_request(req)
    assert result.get("success") is True
    assert "result" in result


@pytest.mark.asyncio
async def test_approval_needed_for_risky_tool():
    """When approval_mode is require_approval and tool is medium+ risk, submission without approval_id fails."""
    from unittest.mock import patch

    risk = get_tool_risk_level("web_scrape_bs4")
    assert risk >= 1, "web_scrape_bs4 should be medium+ risk"

    # Mock execution config to require approval (no disk write)
    mock_cfg = {
        "approval_mode": "require_approval",
        "require_approval_for_risky": True,
        "tool_enabled": {"web_scrape_bs4": True, "git_status": True},
        "max_steps_per_run": 50,
        "max_retries_per_tool": 3,
    }
    with patch("backend.services.provider_tool_request.get_execution_config", return_value=mock_cfg):
        # Build a risky-tool request by hand (no intent map for web_scrape in message)
        req = ProviderToolRequest(
            provider_id="discord",
            tool_name="web_scrape_bs4",
            args={"url": "https://example.com"},
            channel_id="test_ch",
            user_id="test_user",
            reason="provider:discord",
        )
        result = await submit_tool_request(req)
    assert result.get("success") is False
    assert result.get("requires_approval") is True or "approval" in (result.get("error") or "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
