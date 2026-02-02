"""
Internal tool audit logging (JSONL).

No secrets in logs (redacted). No credentials harvested. Keeps system debuggable.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from backend.tools.policies import redact


def write_audit_event(
    *,
    tool_name: str,
    args: Dict[str, Any],
    department: Optional[str],
    agent_id: Optional[str],
    reason: Optional[str],
    status: str,
    trace_id: str,
    error: Optional[str] = None,
    duration_ms: Optional[float] = None,
) -> str:
    audit_id = uuid.uuid4().hex

    entry = {
        "audit_id": audit_id,
        "ts": time.time(),
        "tool_name": tool_name,
        "department": department,
        "agent_id": agent_id,
        "reason": reason,
        "status": status,
        "trace_id": trace_id,
        "duration_ms": duration_ms,
        "error": error,
        "args": redact(args or {}),
    }

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    path = logs_dir / "tools_audit.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return audit_id


def _audit_path() -> Path:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir / "tools_audit.jsonl"


def read_audit_recent(limit: int = 50) -> list:
    """Read most recent audit entries (last N lines). Returns list of dicts."""
    path = _audit_path()
    if not path.exists():
        return []
    out: list = []
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in reversed(lines[-limit:] if len(lines) > limit else lines):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        out.reverse()
    except Exception:
        pass
    return out


def get_audit_by_id(audit_id: str):
    """Return one audit entry by audit_id or None."""
    path = _audit_path()
    if not path.exists() or not audit_id:
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("audit_id") == audit_id:
                        return entry
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    return None











