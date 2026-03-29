"""SmartResolver -- multi-source answer chain.

When Daena doesn't know something, she searches everywhere.
Resolution chain (tries each until answer found):
1. Daena-Mind vault (local markdown files)
2. Project files (Doc/, pitch deck, config)
3. Web search (via Claude Code CLI)
4. Alternative runtime (ask different model)
5. Filesystem scan (grep for relevant files)
6. NEEDS_HUMAN (all sources exhausted)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

CONFIDENCE_THRESHOLD = 0.7


def _run_sync(cmd: list[str], *, cwd: str | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def _search_files(root: str, query: str, extensions: tuple[str, ...] = (".md", ".txt", ".py", ".ts")) -> list[dict[str, Any]]:
    """Search files under a directory for keyword matches. Sync, for thread pool."""
    results = []
    query_lower = query.lower()
    keywords = [w for w in query_lower.split() if len(w) > 3]

    root_path = Path(root)
    if not root_path.exists():
        return results

    for fpath in root_path.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.suffix not in extensions:
            continue
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
            content_lower = content.lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            if matches >= max(1, len(keywords) // 2):
                # Extract relevant snippet
                for kw in keywords:
                    idx = content_lower.find(kw)
                    if idx >= 0:
                        start = max(0, idx - 100)
                        end = min(len(content), idx + 200)
                        snippet = content[start:end].strip()
                        results.append({
                            "file": str(fpath),
                            "snippet": snippet,
                            "match_score": matches / len(keywords),
                        })
                        break
        except Exception:
            continue

    results.sort(key=lambda r: r["match_score"], reverse=True)
    return results[:5]


class SmartResolver:
    """Multi-source answer resolution chain."""

    def __init__(self) -> None:
        _project_root = Path(__file__).resolve().parents[3]
        self._vault_path = str(
            Path(os.environ.get("DAENA_MIND_PATH", str(_project_root / "data" / "mind")))
        )
        self._project_paths = [
            str(_project_root / "Doc"),
        ]
        self._pitch_path = str(_project_root / "Doc")

    async def resolve(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Try all sources to resolve a question."""
        context = context or {}
        attempts: list[dict[str, Any]] = []

        sources = [
            ("vault", self._search_vault),
            ("project_files", self._search_project_files),
            ("web_search", self._search_web),
            ("filesystem", self._scan_filesystem),
        ]

        for source_name, search_fn in sources:
            try:
                result = await search_fn(question, context)
                confidence = result.get("confidence", 0) if result else 0
                attempts.append({
                    "source": source_name,
                    "found": bool(result and confidence > 0),
                    "confidence": confidence,
                })

                if result and confidence >= CONFIDENCE_THRESHOLD:
                    logger.info(
                        "resolver.found",
                        source=source_name,
                        confidence=confidence,
                        question=question[:100],
                    )
                    return {
                        "answer": result.get("answer"),
                        "confidence": confidence,
                        "source": source_name,
                        "attempts": attempts,
                    }
            except Exception as exc:
                attempts.append({
                    "source": source_name,
                    "found": False,
                    "error": str(exc)[:100],
                })
                continue

        logger.warning("resolver.exhausted", question=question[:100], attempts=len(attempts))
        return {
            "answer": None,
            "confidence": 0,
            "source": "none",
            "attempts": attempts,
            "needs_human": True,
        }

    async def _search_vault(self, question: str, context: dict) -> dict[str, Any] | None:
        """Search Daena-Mind vault markdown files."""
        results = await asyncio.to_thread(_search_files, self._vault_path, question)
        if results:
            best = results[0]
            return {
                "answer": best["snippet"],
                "confidence": min(0.9, best["match_score"]),
                "file": best["file"],
            }
        return None

    async def _search_project_files(self, question: str, context: dict) -> dict[str, Any] | None:
        """Search project files and pitch deck."""
        all_results = []
        for path in self._project_paths + [self._pitch_path]:
            results = await asyncio.to_thread(_search_files, path, question)
            all_results.extend(results)

        all_results.sort(key=lambda r: r["match_score"], reverse=True)
        if all_results:
            best = all_results[0]
            return {
                "answer": best["snippet"],
                "confidence": min(0.85, best["match_score"]),
                "file": best["file"],
            }
        return None

    async def _search_web(self, question: str, context: dict) -> dict[str, Any] | None:
        """Web search via Claude Code CLI."""
        import shutil

        claude_bin = shutil.which("claude")
        if not claude_bin:
            return None

        try:
            result = await asyncio.to_thread(
                _run_sync,
                [claude_bin, "-p", f"Search the web and answer concisely: {question}", "--output-format", "json", "--dangerously-skip-permissions"],
                timeout=60.0,
            )
            if result.returncode == 0:
                import json

                lines = result.stdout.strip().splitlines()
                for line in reversed(lines):
                    try:
                        data = json.loads(line)
                        if data.get("type") == "result" and data.get("result"):
                            return {
                                "answer": data["result"],
                                "confidence": 0.8,
                            }
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return None

    async def _scan_filesystem(self, question: str, context: dict) -> dict[str, Any] | None:
        """Last resort: grep relevant paths."""
        search_roots = ["D:/Ideas/Daena/backend/app", "D:/Ideas/Daena/frontend/src"]
        all_results = []
        for root in search_roots:
            results = await asyncio.to_thread(
                _search_files, root, question, (".py", ".ts", ".tsx", ".md"),
            )
            all_results.extend(results)

        all_results.sort(key=lambda r: r["match_score"], reverse=True)
        if all_results:
            best = all_results[0]
            return {
                "answer": best["snippet"],
                "confidence": min(0.6, best["match_score"]),
                "file": best["file"],
            }
        return None
