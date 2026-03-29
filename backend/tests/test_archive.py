"""Tests for ArchiveService: soft-delete and filesystem archival.

Validates:
- Database soft-delete pattern (is_archived flag)
- File archival to .archive/{category}/{timestamp}/
- Directory archival
- Developer mode hard-delete with safety downgrade
- Error handling for missing paths
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.archive import ArchiveService

# ── Filesystem Archival ──────────────────────────────────────────────


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create a temp workspace with test files."""
    # Create some test files
    (tmp_path / "test_file.txt").write_text("hello")
    (tmp_path / "test_dir").mkdir()
    (tmp_path / "test_dir" / "nested.txt").write_text("nested content")
    return tmp_path


class TestArchiveFile:
    """File archival to .archive/ directory."""

    def test_archive_moves_file_to_timestamped_dir(
        self, tmp_workspace: Path
    ) -> None:
        """File is moved to .archive/{category}/{timestamp}/{filename}."""
        source = tmp_workspace / "test_file.txt"
        archive_root = str(tmp_workspace / ".archive")

        result = ArchiveService.archive_file(
            str(source),
            category="configs",
            archive_root=archive_root,
        )

        # Source should no longer exist
        assert not source.exists()
        # Archived file should exist at new location
        assert Path(result).exists()
        assert "configs" in result
        assert "test_file.txt" in result

    def test_archive_file_not_found_raises(self) -> None:
        """Archiving a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            ArchiveService.archive_file("/nonexistent/path/file.txt")

    def test_archive_uses_default_category(self, tmp_workspace: Path) -> None:
        """Default category is 'general'."""
        source = tmp_workspace / "test_file.txt"
        archive_root = str(tmp_workspace / ".archive")

        result = ArchiveService.archive_file(
            str(source), archive_root=archive_root
        )
        assert "general" in result


class TestArchiveDirectory:
    """Directory archival."""

    def test_archive_moves_directory(self, tmp_workspace: Path) -> None:
        """Entire directory is moved to archive."""
        source = tmp_workspace / "test_dir"
        archive_root = str(tmp_workspace / ".archive")

        result = ArchiveService.archive_directory(
            str(source),
            category="exports",
            archive_root=archive_root,
        )

        assert not source.exists()
        assert Path(result).exists()
        assert (Path(result) / "nested.txt").exists()

    def test_archive_directory_not_found_raises(self) -> None:
        """Archiving a nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            ArchiveService.archive_directory("/nonexistent/dir")


# ── Developer Mode Hard Delete ───────────────────────────────────────


class TestDeleteFile:
    """Hard-delete with developer mode safety net."""

    def test_delete_file_in_developer_mode(self, tmp_workspace: Path) -> None:
        """developer_mode=True allows actual file deletion."""
        source = tmp_workspace / "test_file.txt"
        assert source.exists()

        with patch(
            "app.services.archive._is_developer_mode", return_value=True
        ):
            result = ArchiveService.delete_file(str(source))

        assert result["action"] == "deleted"
        assert not source.exists()

    def test_delete_file_without_developer_mode_archives_instead(
        self, tmp_workspace: Path
    ) -> None:
        """developer_mode=False downgrades delete to archive."""
        source = tmp_workspace / "test_file.txt"

        with patch(
            "app.services.archive._is_developer_mode", return_value=False
        ), patch.object(
            ArchiveService,
            "archive_file",
            return_value=str(tmp_workspace / ".archive" / "general" / "test_file.txt"),
        ):
            result = ArchiveService.delete_file(str(source))

        assert result["action"] == "archived"
        assert result["reason"] == "developer_mode=False"

    def test_delete_file_not_found_raises(self) -> None:
        """Deleting a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            ArchiveService.delete_file("/nonexistent/file.txt")


class TestDeleteDirectory:
    """Directory hard-delete with safety net."""

    def test_delete_directory_in_developer_mode(
        self, tmp_workspace: Path
    ) -> None:
        """developer_mode=True allows actual directory deletion."""
        source = tmp_workspace / "test_dir"
        assert source.exists()

        with patch(
            "app.services.archive._is_developer_mode", return_value=True
        ):
            result = ArchiveService.delete_directory(str(source))

        assert result["action"] == "deleted"
        assert not source.exists()

    def test_delete_directory_without_developer_mode_archives(
        self, tmp_workspace: Path
    ) -> None:
        """developer_mode=False downgrades directory delete to archive."""
        source = tmp_workspace / "test_dir"

        with patch(
            "app.services.archive._is_developer_mode", return_value=False
        ), patch.object(
            ArchiveService,
            "archive_directory",
            return_value=str(tmp_workspace / ".archive" / "general" / "test_dir"),
        ):
            result = ArchiveService.delete_directory(str(source))

        assert result["action"] == "archived"

    def test_delete_directory_not_found_raises(self) -> None:
        """Deleting a nonexistent directory raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="not found"):
            ArchiveService.delete_directory("/nonexistent/dir")


# ── Database Soft Delete ─────────────────────────────────────────────


class TestSoftDelete:
    """Database soft-delete (is_archived flag)."""

    @pytest.mark.asyncio
    async def test_soft_delete_marks_entity_archived(
        self, db_session: AsyncMock
    ) -> None:
        """soft_delete sets is_archived=True on the model.

        Uses a real SQLAlchemy model (ChatSession) so that
        select() and update() don't choke on MagicMock.
        We patch _get_or_404 to avoid needing real DB rows.
        """
        from app.models.chat import ChatSession

        mock_db = AsyncMock()
        mock_db.execute.return_value = MagicMock()

        svc = ArchiveService(mock_db)

        entity_id = uuid4()
        tenant_id = uuid4()

        with patch.object(svc, "_get_or_404", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = MagicMock(id=entity_id)
            result = await svc.soft_delete(ChatSession, entity_id, tenant_id)

        assert result["archived"] is True
        assert result["model"] == "ChatSession"
        assert result["id"] == str(entity_id)
        mock_db.execute.assert_awaited_once()
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_soft_delete_entity_not_found_raises(self) -> None:
        """soft_delete raises NotFoundError if entity doesn't exist."""
        from app.core.exceptions import NotFoundError

        mock_db = AsyncMock()
        svc = ArchiveService(mock_db)

        mock_model = MagicMock()
        mock_model.__name__ = "ChatSession"

        # Patch _get_or_404 to raise NotFoundError
        with patch.object(
            svc, "_get_or_404", new_callable=AsyncMock,
            side_effect=NotFoundError("ChatSession not found"),
        ), pytest.raises(NotFoundError):
            await svc.soft_delete(mock_model, uuid4(), uuid4())
