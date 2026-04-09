"""Integration tests for DaenaBot dispatch routing in ExecutionService."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.execution_service import ExecutionService


# ── _resolve_action_type ───────────────────────────────────────

def test_resolve_action_type_file_read() -> None:
    assert ExecutionService._resolve_action_type("file.read_file", {}) == "READ"


def test_resolve_action_type_file_write() -> None:
    assert ExecutionService._resolve_action_type("file.write_file", {}) == "WRITE_FILE"


def test_resolve_action_type_file_delete() -> None:
    assert ExecutionService._resolve_action_type("file.delete_file", {}) == "ARCHIVE"


def test_resolve_action_type_terminal_dangerous() -> None:
    result = ExecutionService._resolve_action_type(
        "terminal.execute_command", {"command": "rm -rf /"},
    )
    assert result == "DELETE"


def test_resolve_action_type_terminal_readonly() -> None:
    result = ExecutionService._resolve_action_type(
        "terminal.execute_command", {"command": "ls -la"},
    )
    assert result == "READ"


def test_resolve_action_type_terminal_regular() -> None:
    result = ExecutionService._resolve_action_type(
        "terminal.execute_command", {"command": "npm run build"},
    )
    assert result == "EXECUTE"


def test_resolve_action_type_browser_navigate() -> None:
    assert ExecutionService._resolve_action_type("browser.navigate", {}) == "READ"


def test_resolve_action_type_browser_submit() -> None:
    assert ExecutionService._resolve_action_type("browser.submit_form", {}) == "POST_PUBLIC"


def test_resolve_action_type_legacy_fallback() -> None:
    """Tool names without dots fall back to tool_name.upper()."""
    assert ExecutionService._resolve_action_type("CUSTOM_TOOL", {}) == "CUSTOM_TOOL"


def test_resolve_action_type_unknown_agent() -> None:
    """Unknown agent prefix falls back to tool_name.upper()."""
    assert ExecutionService._resolve_action_type("desktop.click", {}) == "DESKTOP.CLICK"


# ── _dispatch_tool ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dispatch_disabled_by_feature_flag() -> None:
    """When enable_daenabot=False, dispatch returns error."""
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=False)
        result = await svc._dispatch_tool("file.read_file", {"path": "/tmp"})

    assert result["success"] is False
    assert "not enabled" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_file_agent() -> None:
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            enable_daenabot=True,
            daenabot_allowed_paths=["/tmp"],
        )
        with patch(
            "app.services.daenabot.file_agent.FileAgent.execute",
            new_callable=AsyncMock,
            return_value={"agent": "file", "success": True, "operation": "list_directory", "output": {}, "error": None},
        ):
            result = await svc._dispatch_tool(
                "file.list_directory", {"path": "/tmp"},
            )

    assert result["success"] is True
    assert result["agent"] == "file"


@pytest.mark.asyncio
async def test_dispatch_terminal_agent() -> None:
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            enable_daenabot=True,
            daenabot_terminal_timeout=30,
            daenabot_terminal_max_timeout=300,
        )
        with patch(
            "app.services.daenabot.terminal_agent.TerminalAgent.execute",
            new_callable=AsyncMock,
            return_value={"agent": "terminal", "success": True, "operation": "execute_command", "output": {}, "error": None},
        ):
            result = await svc._dispatch_tool(
                "terminal.execute_command", {"command": "echo hi"},
            )

    assert result["success"] is True
    assert result["agent"] == "terminal"


@pytest.mark.asyncio
async def test_dispatch_browser_agent() -> None:
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=True)
        with patch(
            "app.services.daenabot.browser_agent.BrowserAgent.execute",
            new_callable=AsyncMock,
            return_value={"agent": "browser", "success": True, "operation": "navigate", "output": {}, "error": None},
        ):
            with patch(
                "app.services.daenabot.browser_agent.BrowserAgent.close",
                new_callable=AsyncMock,
            ):
                result = await svc._dispatch_tool(
                    "browser.navigate", {"url": "https://example.com"},
                )

    assert result["success"] is True
    assert result["agent"] == "browser"


@pytest.mark.asyncio
async def test_dispatch_security_cognitive_scan() -> None:
    """Security scan dispatch creates CognitiveScanEngine and runs scan."""
    svc = ExecutionService.__new__(ExecutionService)

    mock_result = MagicMock()
    mock_result.target = "target.com"
    mock_result.total_findings = 3
    mock_result.cycles_used = 2
    mock_result.strategies_tried = ["passive_osint"]
    mock_result.report_path = "/tmp/report.pdf"
    mock_result.evidence_summary = {}
    mock_result.offensive_mode = False
    mock_result.thinking_log = ["test"]

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=True)
        with patch(
            "app.services.security.cognitive_scan_engine.CognitiveScanEngine.scan",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await svc._dispatch_tool(
                "security.cognitive_scan",
                {"target": "target.com", "program": "test"},
            )

    assert result["success"] is True
    assert result["agent"] == "SecurityAgent"
    assert result["output"]["target"] == "target.com"
    assert result["output"]["findings"] == 3


@pytest.mark.asyncio
async def test_dispatch_security_offensive_scan() -> None:
    """Offensive scan dispatch passes offensive_mode=True."""
    svc = ExecutionService.__new__(ExecutionService)

    mock_result = MagicMock()
    mock_result.target = "target.com"
    mock_result.total_findings = 1
    mock_result.cycles_used = 1
    mock_result.strategies_tried = []
    mock_result.report_path = ""
    mock_result.evidence_summary = {"total_evidence": 5}
    mock_result.offensive_mode = True
    mock_result.thinking_log = []

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=True)
        with patch(
            "app.services.security.cognitive_scan_engine.CognitiveScanEngine.__init__",
            return_value=None,
        ) as mock_init:
            with patch(
                "app.services.security.cognitive_scan_engine.CognitiveScanEngine.scan",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                result = await svc._dispatch_tool(
                    "security.cognitive_scan_offensive",
                    {"target": "target.com", "offensive_mode": True, "agi_mode": True},
                )

    assert result["success"] is True
    assert result["output"]["offensive_mode"] is True
    # Verify CognitiveScanEngine was constructed with offensive params
    mock_init.assert_called_once_with(agi_mode=True, offensive_mode=True)


@pytest.mark.asyncio
async def test_dispatch_security_view_evidence() -> None:
    """Evidence view returns vault listing."""
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=True)
        with patch(
            "app.services.security.evidence_capture.EvidenceCapture.list_vault_contents",
            return_value=[{"name": "20260408_target_com_abc", "file_count": 5, "path": "/vault"}],
        ):
            result = await svc._dispatch_tool(
                "security.view_evidence",
                {"target": "target.com"},
            )

    assert result["success"] is True
    assert len(result["output"]["vaults"]) == 1


@pytest.mark.asyncio
async def test_dispatch_security_unknown_operation() -> None:
    """Unknown security operation returns error."""
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=True)
        result = await svc._dispatch_tool(
            "security.nonexistent",
            {},
        )

    assert result["success"] is False
    assert "Unknown security operation" in result["error"]


@pytest.mark.asyncio
async def test_dispatch_unknown_agent() -> None:
    svc = ExecutionService.__new__(ExecutionService)

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(enable_daenabot=True)
        result = await svc._dispatch_tool("desktop.click", {"x": 100, "y": 200})

    assert result["success"] is False
    assert "Unknown agent" in result["error"]
