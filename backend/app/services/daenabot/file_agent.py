"""FileAgent — governed file-system operations.

Supports read, write, create, list, move, and archive (soft-delete).
All paths are validated against a sandbox allowlist before any I/O.
Blocking I/O is wrapped in ``asyncio.to_thread`` so the event loop
is never blocked.

Hard Law #6 compliance: ``delete_file`` delegates to
``ArchiveService.archive_file()`` — no permanent deletion.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)


class FileAgent(BaseAgent):
    """Governed file-system agent for Daena's EXE mode."""

    agent_name = "file"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "read_file": "READ",
        "list_directory": "LIST",
        "write_file": "WRITE_FILE",
        "create_file": "WRITE_FILE",
        "move_file": "WRITE_FILE",
        "delete_file": "ARCHIVE",
    }

    def __init__(self, allowed_paths: list[str] | None = None) -> None:
        self.allowed_paths: list[Path] = [
            Path(p).resolve() for p in (allowed_paths or [])
        ]

    # ── dispatch ───────────────────────────────────────────────

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        ops = {
            "read_file": self.read_file,
            "list_directory": self.list_directory,
            "write_file": self.write_file,
            "create_file": self.create_file,
            "move_file": self.move_file,
            "delete_file": self.delete_file,
        }
        fn = ops.get(operation)
        if fn is None:
            raise ValueError(
                f"FileAgent: unknown operation '{operation}'. "
                f"Supported: {list(ops)}"
            )
        return await fn(**params)

    # ── operations ─────────────────────────────────────────────

    async def read_file(self, path: str) -> dict[str, Any]:
        """Read file contents."""
        resolved = self._validate_path(path)
        content = await asyncio.to_thread(resolved.read_text, encoding="utf-8")
        size = await asyncio.to_thread(lambda: resolved.stat().st_size)
        logger.info("file_agent.read", path=str(resolved), size=size)
        return self._result("read_file", {
            "path": str(resolved),
            "content": content,
            "size": size,
        })

    async def list_directory(
        self, path: str, pattern: str = "*",
    ) -> dict[str, Any]:
        """List directory contents with optional glob pattern."""
        resolved = self._validate_path(path)
        if not resolved.is_dir():
            return self._error("list_directory", f"Not a directory: {path}")

        def _list() -> list[dict[str, Any]]:
            entries: list[dict[str, Any]] = []
            for entry in sorted(resolved.glob(pattern)):
                try:
                    stat = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "type": "dir" if entry.is_dir() else "file",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(
                            stat.st_mtime, tz=UTC,
                        ).isoformat(),
                    })
                except OSError:
                    continue
            return entries

        entries = await asyncio.to_thread(_list)
        logger.info("file_agent.list", path=str(resolved), count=len(entries))
        return self._result("list_directory", {
            "path": str(resolved),
            "entries": entries,
            "count": len(entries),
        })

    async def write_file(self, path: str, content: str) -> dict[str, Any]:
        """Write content to a file, creating parent dirs if needed."""
        resolved = self._validate_path(path, must_exist=False)

        def _write() -> int:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return resolved.stat().st_size

        size = await asyncio.to_thread(_write)
        logger.info("file_agent.write", path=str(resolved), bytes=size)
        return self._result("write_file", {
            "path": str(resolved),
            "bytes_written": size,
        })

    async def create_file(
        self, path: str, content: str = "",
    ) -> dict[str, Any]:
        """Create a new file. Fails if the file already exists."""
        resolved = self._validate_path(path, must_exist=False)
        if await asyncio.to_thread(resolved.exists):
            return self._error("create_file", f"File already exists: {path}")

        def _create() -> int:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            return resolved.stat().st_size

        size = await asyncio.to_thread(_create)
        logger.info("file_agent.create", path=str(resolved), bytes=size)
        return self._result("create_file", {
            "path": str(resolved),
            "created": True,
            "bytes_written": size,
        })

    async def move_file(
        self, source: str, destination: str,
    ) -> dict[str, Any]:
        """Move or rename a file."""
        src = self._validate_path(source)
        dst = self._validate_path(destination, must_exist=False)
        await asyncio.to_thread(shutil.move, str(src), str(dst))
        logger.info("file_agent.move", source=str(src), destination=str(dst))
        return self._result("move_file", {
            "source": str(src),
            "destination": str(dst),
        })

    async def delete_file(self, path: str) -> dict[str, Any]:
        """Archive a file (Hard Law #6 — no permanent deletion)."""
        resolved = self._validate_path(path)

        from app.services.archive import ArchiveService

        archived_to = await asyncio.to_thread(
            ArchiveService.archive_file,
            str(resolved),
            category="daenabot",
        )
        logger.info(
            "file_agent.archive", path=str(resolved), archived_to=archived_to,
        )
        return self._result("delete_file", {
            "path": str(resolved),
            "archived_to": archived_to,
        })

    # ── path validation ────────────────────────────────────────

    def _validate_path(
        self, path: str, *, must_exist: bool = True,
    ) -> Path:
        """Resolve and validate a path against sandbox rules.

        Checks:
            1. No null bytes
            2. Resolve to absolute (canonicalise ..)
            3. Must be under one of ``allowed_paths``
            4. If ``must_exist``, file/dir must exist

        Raises:
            ValueError: If the path fails validation.
        """
        if "\x00" in path:
            raise ValueError("Path contains null byte")

        resolved = Path(path).resolve()

        # Sandbox check
        if self.allowed_paths and not any(
            self._is_subpath(resolved, base)
            for base in self.allowed_paths
        ):
            raise ValueError(
                f"Path '{resolved}' is outside sandbox. "
                f"Allowed: {[str(p) for p in self.allowed_paths]}"
            )

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Path not found: {resolved}")

        return resolved

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        """Check if *child* is equal to or under *parent*."""
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False
