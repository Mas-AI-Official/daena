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











