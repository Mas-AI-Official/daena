"""
Execution Layer config: tool enabled toggles, approval mode, budget guards.
Stored in config/execution_layer_config.json. Safe by default (risky tools disabled).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Project root: backend/services -> backend -> project
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config" / "execution_layer_config.json"

# risk_level: low=0, medium=1, high=2. Tools with medium+ require approval when approval_mode == "require_approval"
TOOL_RISK_LEVELS: Dict[str, int] = {
    "git_status": 0,
    "filesystem_read": 0,
    "git_diff": 0,
    "web_scrape_bs4": 1,
    "shell_exec": 1,
    "filesystem_write": 2,
    "apply_patch": 2,
    "browser_automation_selenium": 2,
    "desktop_automation_pyautogui": 2,
    "consult_ui": 2,
    "windows_node_safe_shell_exec": 1,
    "windows_node_file_read_workspace": 1,
    "windows_node_file_write_workspace": 2,
    "sandbox_worker_run": 1,
    "browser_e2e_runner": 1,
    "screenshot_capture": 1,
    "repo_scan": 0,
}

# Approval store: approval_id -> { tool_name, expires_at }
_approvals: Dict[str, Dict[str, Any]] = {}
APPROVAL_TTL_SEC = 300


def create_approval(tool_name: str) -> str:
    """Create a short-lived approval for a tool. Returns approval_id."""
    aid = uuid.uuid4().hex
    _approvals[aid] = {"tool_name": tool_name, "expires_at": time.time() + APPROVAL_TTL_SEC}
    return aid


def consume_approval(approval_id: Optional[str], tool_name: str) -> bool:
    """Validate and consume approval for tool. Returns True if allowed."""
    if not approval_id:
        return False
    rec = _approvals.get(approval_id)
    if not rec:
        return False
    if rec.get("tool_name") != tool_name:
        return False
    if time.time() > rec.get("expires_at", 0):
        del _approvals[approval_id]
        return False
    del _approvals[approval_id]
    return True


def get_tool_risk_level(tool_name: str) -> int:
    """Return risk level 0=low, 1=medium, 2=high."""
    return TOOL_RISK_LEVELS.get(tool_name, 1)


_DEFAULT = {
    "tool_enabled": {
        "git_status": True,
        "repo_git_status": True,
        "repo_git_diff": True,
        "git_diff": True,
        "filesystem_read": True,
        "system_info": True,
        "process_list": True,
        "service_list": True,
        "net_connections": True,
        "windows_eventlog_read": True,
        "defender_status_read": True,
        "web_scrape_bs4": True,
        "browser_automation_selenium": False,
        "desktop_automation_pyautogui": False,
        "consult_ui": False,
        "filesystem_write": False,
        "apply_patch": False,
        "shell_exec": True,
        "windows_node_safe_shell_exec": False,
        "windows_node_file_read_workspace": False,
        "windows_node_file_write_workspace": False,
        "sandbox_worker_run": False,
        "run_tests": True,
        "browser_e2e_runner": True,
        "screenshot_capture": True,
        "repo_scan": True,
    },
    "approval_mode": "auto",
    "require_approval_for_risky": True,
    "max_steps_per_run": 50,
    "max_retries_per_tool": 3,
    "dry_run_default": False,
}


def _load() -> Dict[str, Any]:
    out = _DEFAULT.copy()
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if k == "tool_enabled" and isinstance(v, dict):
                    out["tool_enabled"] = {**out.get("tool_enabled", {}), **v}
                else:
                    out[k] = v
        except Exception as e:
            logger.warning(f"Execution layer config load failed: {e}, using defaults")
    return out


def _save(data: Dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


_cached: Dict[str, Any] | None = None


def get_execution_config() -> Dict[str, Any]:
    global _cached
    if _cached is None:
        _cached = _load()
    return _cached


def reload_execution_config() -> Dict[str, Any]:
    global _cached
    _cached = _load()
    return _cached


def is_tool_enabled(tool_name: str) -> bool:
    cfg = get_execution_config()
    enabled = cfg.get("tool_enabled") or {}
    return enabled.get(tool_name, False)


def set_tool_enabled(tool_name: str, enabled: bool) -> None:
    cfg = get_execution_config()
    if "tool_enabled" not in cfg:
        cfg["tool_enabled"] = {}
    cfg["tool_enabled"][tool_name] = enabled
    _save(cfg)
    reload_execution_config()


def update_execution_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    cfg = get_execution_config().copy()
    for k, v in updates.items():
        if k in ("tool_enabled", "approval_mode", "require_approval_for_risky",
                 "max_steps_per_run", "max_retries_per_tool", "dry_run_default"):
            cfg[k] = v
    _save(cfg)
    reload_execution_config()
    return get_execution_config()
