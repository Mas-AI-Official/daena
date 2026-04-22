"""Regression tests for the DATABASE_URL resolver in config.py.

The resolver anchors relative sqlite paths to the backend package root
so the DB file opens the same way regardless of the cwd uvicorn /
pytest / docker launched from. We have burned half a session twice on
this (Windows preview_start using ``D:\\Ideas`` cwd, Linux server
exiting on "unable to open database file"), so these tests lock the
contract:

    * Relative sqlite -> rewritten to an absolute path under backend/
    * POSIX absolute sqlite -> untouched (operator choice)
    * Windows drive-letter sqlite -> untouched (operator choice)
    * :memory: sqlite -> untouched
    * postgres / mysql / anything non-sqlite -> untouched
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core import config as config_module
from app.core.config import Settings


BACKEND_ROOT: Path = config_module._BACKEND_ROOT


def _resolve(url: str) -> str:
    """Invoke the classmethod validator directly -- no env loading."""
    return Settings.resolve_sqlite_relative_path(url)


def test_relative_sqlite_gets_anchored_to_backend_root():
    out = _resolve("sqlite+aiosqlite:///./daena_dev2.db")
    expected = f"sqlite+aiosqlite:///{(BACKEND_ROOT / 'daena_dev2.db').resolve().as_posix()}"
    assert out == expected


def test_relative_nested_path_anchored():
    out = _resolve("sqlite+aiosqlite:///data/dev.db")
    expected = f"sqlite+aiosqlite:///{(BACKEND_ROOT / 'data' / 'dev.db').resolve().as_posix()}"
    assert out == expected
    # Parent dir was created by the resolver.
    assert (BACKEND_ROOT / "data").is_dir()


def test_posix_absolute_sqlite_untouched():
    url = "sqlite+aiosqlite:////root/daena_venv/daena.db"
    assert _resolve(url) == url


def test_windows_drive_letter_sqlite_untouched():
    url = "sqlite+aiosqlite:///C:/daena/prod.db"
    assert _resolve(url) == url


def test_memory_sqlite_untouched():
    url = "sqlite+aiosqlite:///:memory:"
    assert _resolve(url) == url


def test_postgres_untouched():
    url = "postgresql+asyncpg://user:pass@db.internal:5432/daena"
    assert _resolve(url) == url


def test_mysql_untouched():
    url = "mysql+aiomysql://user:pass@db:3306/daena"
    assert _resolve(url) == url


def test_plain_sqlite_no_driver_suffix():
    # Pure sqlite:// scheme (no async driver) still parses and gets
    # anchored to the backend root.
    out = _resolve("sqlite:///./dev.db")
    assert out.startswith("sqlite:///")
    assert out.endswith("dev.db")
    # Anchored: the resolved path should contain the backend root.
    assert BACKEND_ROOT.as_posix() in out


@pytest.mark.parametrize("bad", ["", "not-a-url", "://broken"])
def test_malformed_urls_do_not_crash(bad: str):
    # Must return SOMETHING (untouched) rather than raising during
    # pydantic validation at startup.
    result = _resolve(bad)
    assert isinstance(result, str)
