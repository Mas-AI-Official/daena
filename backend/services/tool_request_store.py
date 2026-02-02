"""
Tool request queue and history for DaenaBot/OpenClaw governance.
Stores: id, created_at, requested_by, risk_level, action_json, status, result_json.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STORE_PATH = _PROJECT_ROOT / "config" / "tool_requests.json"


def _load() -> List[Dict[str, Any]]:
    if not _STORE_PATH.exists():
        return []
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("requests") or []
    except Exception as e:
        logger.warning("Tool request store load failed: %s", e)
        return []


def _save(requests: List[Dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump({"requests": requests}, f, indent=2)
    except Exception as e:
        logger.warning("Tool request store save failed: %s", e)


def create_request(
    requested_by: str,
    risk_level: str,
    action_json: Dict[str, Any],
) -> str:
    """Append a new tool request; returns id."""
    requests = _load()
    req_id = str(uuid.uuid4())
    requests.append({
        "id": req_id,
        "created_at": time.time(),
        "requested_by": requested_by,
        "risk_level": risk_level,
        "action_json": action_json,
        "status": "pending",
        "result_json": None,
    })
    _save(requests)
    return req_id


def get_request(req_id: str) -> Optional[Dict[str, Any]]:
    requests = _load()
    for r in requests:
        if r.get("id") == req_id:
            return r
    return None


def update_status(req_id: str, status: str, result_json: Optional[Dict[str, Any]] = None) -> bool:
    requests = _load()
    for r in requests:
        if r.get("id") == req_id:
            r["status"] = status
            if result_json is not None:
                r["result_json"] = result_json
            _save(requests)
            return True
    return False


def list_pending() -> List[Dict[str, Any]]:
    return [r for r in _load() if r.get("status") == "pending"]


def list_history(limit: int = 50) -> List[Dict[str, Any]]:
    requests = _load()
    requests.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return requests[:limit]
