import pytest
import asyncio
import os
from backend.services.daenabot_hands_server import handle_action

# Set allowed commands for test
os.environ["ALLOWED_SHELL_COMMANDS"] = "dir,ls,echo,ipconfig"

@pytest.mark.asyncio
async def test_handle_action_echo():
    """Test safe shell command execution."""
    action = {
        "action_type": "shell.run",
        "parameters": {"command": "echo Hello world"}
    }
    result = await handle_action(action)
    assert result["success"] is True
    assert "Hello world" in result["stdout"]

@pytest.mark.asyncio
async def test_handle_action_blocked_command():
    """Test blocked shell command."""
    action = {
        "action_type": "shell.run",
        "parameters": {"command": "format c:"}
    }
    result = await handle_action(action)
    assert result["success"] is False
    assert "whitelist" in result.get("error", "").lower()

@pytest.mark.asyncio
async def test_desktop_click_params():
    """Test desktop click parameter validation."""
    # We expect it might fail because pyautogui is not valid in headless, 
    # but we check if it validates params or handles import error nicely.
    action = {
        "action_type": "desktop.click",
        "parameters": {} # Missing x, y
    }
    result = await handle_action(action)
    
    # It should fail either due to missing params or pyautogui missing
    assert result["success"] is False
    if "pyautogui" not in result.get("error", ""):
        assert "Missing" in result.get("error", "")
