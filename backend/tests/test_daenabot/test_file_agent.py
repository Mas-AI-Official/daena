"""Unit tests for FileAgent — all filesystem I/O is mocked."""

from __future__ import annotations

import pytest
from pathlib import Path, PurePosixPath
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from app.services.daenabot.file_agent import FileAgent


# ── Helpers ────────────────────────────────────────────────────

def _agent(tmp_path: Path) -> FileAgent:
    """Create a FileAgent sandboxed to *tmp_path*."""
    return FileAgent(allowed_paths=[str(tmp_path)])


# ── read_file ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_read_file_success(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("Hello, Daena!", encoding="utf-8")
    agent = _agent(tmp_path)

    result = await agent.read_file(str(f))

    assert result["success"] is True
    assert result["operation"] == "read_file"
    assert result["output"]["content"] == "Hello, Daena!"
    assert result["output"]["size"] > 0


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    with pytest.raises(FileNotFoundError):
        await agent.read_file(str(tmp_path / "nope.txt"))


@pytest.mark.asyncio
async def test_read_file_outside_sandbox(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    with pytest.raises(ValueError, match="outside sandbox"):
        await agent.read_file("/etc/passwd")


# ── list_directory ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_directory_success(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "sub").mkdir()
    agent = _agent(tmp_path)

    result = await agent.list_directory(str(tmp_path))

    assert result["success"] is True
    assert result["output"]["count"] == 3
    names = {e["name"] for e in result["output"]["entries"]}
    assert names == {"a.txt", "b.txt", "sub"}


@pytest.mark.asyncio
async def test_list_directory_not_a_dir(tmp_path: Path) -> None:
    f = tmp_path / "file.txt"
    f.write_text("x")
    agent = _agent(tmp_path)

    result = await agent.list_directory(str(f))

    assert result["success"] is False
    assert "Not a directory" in result["error"]


# ── write_file ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_write_file_success(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    target = str(tmp_path / "out.txt")

    result = await agent.write_file(target, "written content")

    assert result["success"] is True
    assert result["output"]["bytes_written"] > 0
    assert Path(target).read_text() == "written content"


@pytest.mark.asyncio
async def test_write_file_creates_parents(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    target = str(tmp_path / "deep" / "nested" / "file.txt")

    result = await agent.write_file(target, "deep")

    assert result["success"] is True
    assert Path(target).exists()


@pytest.mark.asyncio
async def test_write_file_outside_sandbox(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    with pytest.raises(ValueError, match="outside sandbox"):
        await agent.write_file("/tmp/evil.txt", "bad")


# ── create_file ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_file_success(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    target = str(tmp_path / "new.txt")

    result = await agent.create_file(target, "initial")

    assert result["success"] is True
    assert result["output"]["created"] is True
    assert Path(target).read_text() == "initial"


@pytest.mark.asyncio
async def test_create_file_already_exists(tmp_path: Path) -> None:
    f = tmp_path / "exists.txt"
    f.write_text("x")
    agent = _agent(tmp_path)

    result = await agent.create_file(str(f), "overwrite?")

    assert result["success"] is False
    assert "already exists" in result["error"]


# ── move_file ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_move_file_success(tmp_path: Path) -> None:
    src = tmp_path / "src.txt"
    src.write_text("move me")
    dst = tmp_path / "dst.txt"
    agent = _agent(tmp_path)

    result = await agent.move_file(str(src), str(dst))

    assert result["success"] is True
    assert not src.exists()
    assert dst.read_text() == "move me"


# ── delete_file (archive) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_file_archives(tmp_path: Path) -> None:
    f = tmp_path / "doomed.txt"
    f.write_text("archive me")
    agent = _agent(tmp_path)

    with patch(
        "app.services.archive.ArchiveService.archive_file",
        return_value=str(tmp_path / ".archive" / "doomed.txt"),
    ) as mock_archive:
        result = await agent.delete_file(str(f))

    assert result["success"] is True
    assert "archived_to" in result["output"]
    mock_archive.assert_called_once()


# ── path validation ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_path_validation_null_bytes(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    with pytest.raises(ValueError, match="null byte"):
        await agent.read_file(str(tmp_path / "bad\x00file"))


@pytest.mark.asyncio
async def test_execute_unknown_operation(tmp_path: Path) -> None:
    agent = _agent(tmp_path)
    with pytest.raises(ValueError, match="unknown operation"):
        await agent.execute("hack_mainframe", {})


def test_operation_action_map_complete() -> None:
    """Every operation has a governance action_type mapping."""
    ops = {"read_file", "list_directory", "write_file",
           "create_file", "move_file", "delete_file"}
    assert set(FileAgent.OPERATION_ACTION_MAP.keys()) == ops
