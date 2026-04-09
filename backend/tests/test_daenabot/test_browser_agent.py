"""Unit tests for BrowserAgent — Playwright is fully mocked."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.daenabot.browser_agent import BrowserAgent


# ── Helpers ────────────────────────────────────────────────────

def _mock_page() -> AsyncMock:
    """Build a mock Playwright page."""
    page = AsyncMock()
    page.url = "https://example.com"
    page.title = AsyncMock(return_value="Example Domain")
    page.inner_text = AsyncMock(return_value="Hello World")
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    page.fill = AsyncMock()
    page.click = AsyncMock()
    page.keyboard = AsyncMock()
    page.keyboard.press = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.close = AsyncMock()

    response = MagicMock()
    response.status = 200
    page.goto = AsyncMock(return_value=response)

    return page


def _agent_with_mock_page() -> tuple[BrowserAgent, AsyncMock]:
    """Create a BrowserAgent with pre-injected mock page."""
    agent = BrowserAgent(headless=True)
    page = _mock_page()
    agent._page = page
    agent._browser = AsyncMock()
    agent._playwright = AsyncMock()
    return agent, page


# ── navigate ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_navigate_success() -> None:
    agent, page = _agent_with_mock_page()

    result = await agent.navigate("https://example.com")

    assert result["success"] is True
    assert result["output"]["status"] == 200
    assert result["output"]["title"] == "Example Domain"
    page.goto.assert_called_once()


@pytest.mark.asyncio
async def test_navigate_invalid_scheme() -> None:
    agent, _ = _agent_with_mock_page()

    with pytest.raises(ValueError, match="scheme not allowed"):
        await agent.navigate("file:///etc/passwd")

    with pytest.raises(ValueError, match="scheme not allowed"):
        await agent.navigate("javascript:alert(1)")


# ── extract_text ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_extract_text_full_page() -> None:
    agent, page = _agent_with_mock_page()

    result = await agent.extract_text()

    assert result["success"] is True
    assert result["output"]["text"] == "Hello World"
    assert result["output"]["selector"] == "body"
    page.inner_text.assert_called_with("body")


@pytest.mark.asyncio
async def test_extract_text_selector() -> None:
    agent, page = _agent_with_mock_page()
    page.inner_text = AsyncMock(return_value="Specific text")

    result = await agent.extract_text(selector="#main")

    assert result["output"]["text"] == "Specific text"
    page.inner_text.assert_called_with("#main")


# ── screenshot ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_screenshot_base64() -> None:
    agent, page = _agent_with_mock_page()

    result = await agent.screenshot()

    assert result["success"] is True
    assert "base64" in result["output"]
    assert result["output"]["size_bytes"] > 0


@pytest.mark.asyncio
async def test_screenshot_to_file(tmp_path) -> None:
    agent, page = _agent_with_mock_page()
    out = str(tmp_path / "shot.png")

    # Mock screenshot to write a file
    async def _write_screenshot(**kwargs):
        with open(kwargs["path"], "wb") as f:
            f.write(b"\x89PNG" + b"\x00" * 100)

    page.screenshot = _write_screenshot

    result = await agent.screenshot(path=out)

    assert result["success"] is True
    assert result["output"]["path"] == out


# ── fill_form ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fill_form_success() -> None:
    agent, page = _agent_with_mock_page()

    result = await agent.fill_form(selector="#email", value="test@test.com")

    assert result["success"] is True
    assert result["output"]["filled"] is True
    page.fill.assert_called_with("#email", "test@test.com")


# ── click_element ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_click_element_success() -> None:
    agent, page = _agent_with_mock_page()

    result = await agent.click_element(selector="button.submit")

    assert result["success"] is True
    assert result["output"]["clicked"] is True
    page.click.assert_called_with("button.submit")


# ── submit_form ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_form_success() -> None:
    agent, page = _agent_with_mock_page()
    page.url = "https://example.com/done"

    result = await agent.submit_form(selector="#submit-btn")

    assert result["success"] is True
    assert result["output"]["submitted"] is True
    assert result["output"]["url_after"] == "https://example.com/done"


# ── close ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close_cleanup() -> None:
    agent, page = _agent_with_mock_page()
    browser = agent._browser
    pw = agent._playwright

    await agent.close()

    page.close.assert_called_once()
    browser.close.assert_called_once()
    pw.stop.assert_called_once()
    assert agent._page is None
    assert agent._browser is None
    assert agent._playwright is None


# ── dispatch ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_execute_unknown_operation() -> None:
    agent, _ = _agent_with_mock_page()
    with pytest.raises(ValueError, match="unknown operation"):
        await agent.execute("hack_browser", {})


def test_operation_action_map_complete() -> None:
    ops = {"navigate", "extract_text", "screenshot",
           "fill_form", "click_element", "submit_form",
           "extract_links", "get_form_fields", "wait_for"}
    assert set(BrowserAgent.OPERATION_ACTION_MAP.keys()) == ops
