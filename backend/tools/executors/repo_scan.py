"""
Repo scan (read-only): dependency list + basic secrets scan. Local only, no exfiltration.
"""

from __future__ import annotations

import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _workspace_root() -> str:
    try:
        from backend.config.settings import settings
        root = getattr(settings, "execution_workspace_root", None)
        if root:
            return str(root)
    except Exception:
        pass
    return str(Path(__file__).resolve().parent.parent.parent.parent)


def _resolve_workspace(rel: str) -> Path:
    root = Path(_workspace_root()).resolve()
    path = (root / rel).resolve() if rel else root
    if not str(path).startswith(str(root)):
        raise ValueError("path outside workspace")
    return path


# Simple secret-like patterns (high false positive; for local audit only)
SECRET_PATTERNS = [
    (re.compile(r"(?i)api[_-]?key\s*=\s*['\"]?[a-zA-Z0-9_\-]{20,}"), "api_key"),
    (re.compile(r"(?i)secret\s*=\s*['\"]?[a-zA-Z0-9_\-]{16,}"), "secret"),
    (re.compile(r"(?i)password\s*=\s*['\"][^'\"]+['\"]"), "password"),
]


def run_repo_scan(
    *,
    cwd: Optional[str] = None,
    scan_deps: bool = True,
    scan_secrets: bool = True,
    max_file_size: int = 100_000,
) -> Dict[str, Any]:
    """
    Read-only scan: list dependencies (requirements.txt, package.json) and basic secret patterns.
    No exfiltration; results stay local.
    """
    root = _resolve_workspace(cwd or "")
    deps: Dict[str, List[str]] = {}
    secret_hits: List[Dict[str, Any]] = []

    if scan_deps:
        # requirements.txt
        req = root / "requirements.txt"
        if req.is_file():
            try:
                text = req.read_text(encoding="utf-8", errors="replace")[:max_file_size]
                deps["requirements.txt"] = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
            except Exception as e:
                deps["requirements.txt"] = [f"error: {e}"]
        # package.json
        pkg = root / "package.json"
        if pkg.is_file():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8")[:max_file_size])
                deps_list = data.get("dependencies", {}) or {}
                deps["package.json"] = [f"{k}@{v}" for k, v in list(deps_list.items())[:100]]
            except Exception as e:
                deps["package.json"] = [f"error: {e}"]

    if scan_secrets:
        for ext in (".py", ".env", ".yaml", ".yml", ".json", ".js", ".ts"):
            for f in root.rglob(f"*{ext}"):
                if not f.is_file() or f.stat().st_size > max_file_size:
                    continue
                try:
                    text = f.read_text(encoding="utf-8", errors="replace")
                    rel = str(f.relative_to(root))
                    for pat, label in SECRET_PATTERNS:
                        if pat.search(text):
                            secret_hits.append({"file": rel, "pattern": label})
                            break
                except Exception:
                    continue
                if len(secret_hits) >= 50:
                    break
            if len(secret_hits) >= 50:
                break

    return {
        "status": "ok",
        "workspace": str(root),
        "dependencies": deps,
        "secret_hits_count": len(secret_hits),
        "secret_hits": secret_hits[:20],
    }
