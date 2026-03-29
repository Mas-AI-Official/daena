"""Archive service: soft-delete with filesystem mirror.

Implements Daena Rule #2: "NEVER delete — archive to .archive/".
Provides both database-level soft-delete (is_archived flag) and
filesystem archival for file-based resources.

Developer Mode:
    When ``developer_mode=False`` (default), all delete operations move
    files/directories to ``.archive/`` — nothing is permanently removed.
    When ``developer_mode=True``, callers may pass ``force_delete=True``
    to perform actual filesystem deletion.  Every hard-delete is logged
    to preserve the audit trail (Hard Law #1).
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import update

from app.core.logging import get_logger
from app.services._base import BaseService

logger = get_logger(__name__)

# Default archive root — relative to project root
DEFAULT_ARCHIVE_DIR = ".archive"


def _is_developer_mode() -> bool:
    """Read developer_mode from settings (import-safe helper)."""
    from app.core.config import get_settings
    return get_settings().developer_mode


class ArchiveService(BaseService):
    """Soft-delete and filesystem archival operations.

    Database records are marked with ``is_archived=True``.
    Files are moved to ``.archive/{category}/{timestamp}/``.

    When developer_mode is **off** (default), ``force_delete`` is
    silently downgraded to an archive operation — safety first.

    Usage::

        svc = ArchiveService(db)
        await svc.soft_delete(ChatSession, session_id, tenant_id)
        svc.archive_file("/path/to/file.txt", category="configs")

        # Only works when developer_mode=True in settings:
        svc.delete_file("/tmp/scratch.txt")
    """

    # ── Database soft-delete ───────────────────────────────────────

    async def soft_delete(
        self,
        model: type,
        entity_id: UUID,
        tenant_id: UUID,
    ) -> dict:
        """Mark a database record as archived.

        Sets ``is_archived=True`` and ``updated_at=now()`` on the model.
        The record remains in the database but is excluded from normal queries.

        Args:
            model: SQLAlchemy model class (must have is_archived column).
            entity_id: UUID of the record.
            tenant_id: Tenant UUID for scoping.

        Returns:
            Summary dict with entity info.

        Raises:
            NotFoundError: If entity doesn't exist for tenant.
        """
        await self._get_or_404(
            model, entity_id, model.__name__, tenant_id=tenant_id
        )

        stmt = (
            update(model)
            .where(model.id == entity_id)
            .values(is_archived=True, updated_at=datetime.utcnow())
        )
        await self.db.execute(stmt)
        await self.db.flush()

        logger.info(
            "entity_archived",
            model=model.__name__,
            entity_id=str(entity_id),
            tenant_id=str(tenant_id),
        )

        return {
            "id": str(entity_id),
            "model": model.__name__,
            "archived": True,
        }

    # ── File archival ──────────────────────────────────────────────

    @staticmethod
    def archive_file(
        source_path: str,
        *,
        category: str = "general",
        archive_root: str = DEFAULT_ARCHIVE_DIR,
    ) -> str:
        """Move a file to the archive directory.

        Creates a timestamped subdirectory to prevent collisions:
        ``.archive/{category}/{YYYYMMDD_HHMMSS}/{filename}``

        Args:
            source_path: Absolute or relative path to the file.
            category: Subdirectory category (e.g. "configs", "exports").
            archive_root: Root archive directory.

        Returns:
            Path to the archived file (as string).

        Raises:
            FileNotFoundError: If source file doesn't exist.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Cannot archive: {source_path} not found")

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_dir = Path(archive_root) / category / timestamp
        archive_dir.mkdir(parents=True, exist_ok=True)

        dest = archive_dir / source.name
        shutil.move(str(source), str(dest))

        logger.info(
            "file_archived",
            source=str(source),
            destination=str(dest),
            category=category,
        )

        return str(dest)

    @staticmethod
    def archive_directory(
        source_path: str,
        *,
        category: str = "general",
        archive_root: str = DEFAULT_ARCHIVE_DIR,
    ) -> str:
        """Move an entire directory to the archive.

        Args:
            source_path: Path to the directory.
            category: Subdirectory category.
            archive_root: Root archive directory.

        Returns:
            Path to the archived directory.

        Raises:
            FileNotFoundError: If source directory doesn't exist.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(
                f"Cannot archive: {source_path} not found"
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_dir = Path(archive_root) / category / timestamp
        archive_dir.mkdir(parents=True, exist_ok=True)

        dest = archive_dir / source.name
        shutil.move(str(source), str(dest))

        logger.info(
            "directory_archived",
            source=str(source),
            destination=str(dest),
            category=category,
        )

        return str(dest)

    # ── Developer-mode hard delete ─────────────────────────────────

    @staticmethod
    def delete_file(source_path: str) -> dict:
        """Permanently delete a file (developer mode only).

        When developer_mode is False, this falls back to archive_file
        instead of deleting — safety net for accidental calls.

        Returns:
            Dict with action taken and path.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Cannot delete: {source_path} not found")

        if not _is_developer_mode():
            archived = ArchiveService.archive_file(source_path)
            logger.warning(
                "delete_downgraded_to_archive",
                source=source_path,
                reason="developer_mode is off",
                archived_to=archived,
            )
            return {"action": "archived", "path": archived, "reason": "developer_mode=False"}

        os.remove(source_path)
        logger.warning(
            "file_permanently_deleted",
            path=source_path,
        )
        return {"action": "deleted", "path": source_path}

    @staticmethod
    def delete_directory(source_path: str) -> dict:
        """Permanently delete a directory (developer mode only).

        When developer_mode is False, this falls back to archive_directory.

        Returns:
            Dict with action taken and path.
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Cannot delete: {source_path} not found")

        if not _is_developer_mode():
            archived = ArchiveService.archive_directory(source_path)
            logger.warning(
                "delete_downgraded_to_archive",
                source=source_path,
                reason="developer_mode is off",
                archived_to=archived,
            )
            return {"action": "archived", "path": archived, "reason": "developer_mode=False"}

        shutil.rmtree(source_path)
        logger.warning(
            "directory_permanently_deleted",
            path=source_path,
        )
        return {"action": "deleted", "path": source_path}
