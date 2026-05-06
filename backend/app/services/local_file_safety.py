"""Shared local-file safety helpers -- Sprint-17 PR-1 (2026-05-06).

Both ``local.file_change_proposal`` (Sprint-14 PR-4) and the new
``local.file_change_proposal.apply`` (Sprint-17 PR-1) need the
exact same path / secret-file / pytest-test guards. Per CLAUDE.md
Rule 2 (one canonical file per concern), they live here so a
future PR can't drift two parallel copies.

Public API:
  REPO_ROOT                       absolute Path to D:\\Ideas\\Daena
  SECRET_FILE_PATTERNS            tuple of compiled regex
  is_secret_file(path_str)        bool
  resolve_under_repo(target_path) -> Path  (raises on escape)
  validate_pytest_path(s)         -> str    (raises on shell-shaped or
                                             arbitrary command)

The pytest validator is NEW for Sprint-17. It locks the strings the
apply handler is allowed to execute via ``python -m pytest <path>``
to repo-relative test files (or test files plus a ``::test_name``
selector). Anything that looks like a shell command is refused.
This is the wall against test_to_run_after_apply being weaponized
into RCE.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.controlled_execution_dispatch import ControlledExecutionRefused


# ── Repo root anchor ─────────────────────────────────────────────────


# This file lives at backend/app/services/local_file_safety.py
# parents[0]=services, [1]=app, [2]=backend, [3]=Daena (repo root).
REPO_ROOT: Path = Path(__file__).resolve().parents[3]


# ── Secret-file patterns (mirrors Sprint-14 PR-4) ────────────────────


SECRET_FILE_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"\.pem$", re.IGNORECASE),
    re.compile(r"\.key$", re.IGNORECASE),
    re.compile(r"\.p12$", re.IGNORECASE),
    re.compile(r"(?:^|[\\/])(?:\.)?secrets[\\/]", re.IGNORECASE),
    re.compile(r"credentials.*\.json$", re.IGNORECASE),
    re.compile(r"\.daena_oauth_overrides\.json$", re.IGNORECASE),
    re.compile(r"\.autonomy_mode\.json$", re.IGNORECASE),
    re.compile(r"\.credentials$", re.IGNORECASE),
    re.compile(r"_token(s)?\.json$", re.IGNORECASE),
)


def is_secret_file(path_str: str) -> bool:
    """True iff the path matches any known secret-file pattern."""
    return any(p.search(path_str) for p in SECRET_FILE_PATTERNS)


def resolve_under_repo(target_path: str) -> Path:
    """Resolve ``target_path`` against the repo root and refuse if
    it escapes. Symlink-resolving + parent-traversal-safe via
    ``Path.resolve()``.

    Raises ``ControlledExecutionRefused('target_path_outside_repo')``
    on escape.
    """
    p = Path(target_path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    resolved = p.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ControlledExecutionRefused(
            "target_path_outside_repo",
            f"{target_path!r} resolves to {resolved}, which is outside "
            f"{REPO_ROOT}.",
        ) from exc
    return resolved


# ── pytest-path validator (Sprint-17) ────────────────────────────────


# Locked regex: a repo-relative path that ends in .py, optionally
# followed by ``::TestClass`` / ``::test_name`` selector segments
# (each consisting of word chars only). Forward and backward slashes
# both allowed because Windows + POSIX are both supported.
#
# Explicitly forbidden (would have matched a broader pattern):
#   shell metachars: ; & | > < ` $ ( ) { } [ ] '
#   space-separated args:  -- mode flags / --quiet / etc
#   absolute paths starting with /  or  drive letters
#
# A future PR can extend this with -k / -m markers, but each
# extension requires a paired test that proves the new char class
# doesn't open a shell-injection vector.
_PYTEST_PATH_REGEX = re.compile(
    r"^(?!/)(?![A-Za-z]:[\\/])"          # no leading / or drive
    r"[A-Za-z0-9_./\\\-]+\.py"            # repo-relative .py file
    r"(?:::[A-Za-z0-9_]+){0,2}"            # optional ::Class::test
    r"$",
)


def validate_pytest_path(test_spec: str) -> str:
    """Refuse anything that is not a repo-relative pytest path.

    Returns the (stripped) input string when valid; raises
    ``ControlledExecutionRefused('invalid_test_path')`` otherwise.

    The apply handler runs ``python -m pytest <each-validated-spec>``
    via ``subprocess.run(args_as_list, shell=False)``. Locking the
    spec format here is the single wall against
    ``tests_to_run_after_apply`` being weaponized into RCE.
    """
    if not isinstance(test_spec, str):
        raise ControlledExecutionRefused(
            "invalid_test_path",
            f"test spec must be a string; got {type(test_spec).__name__}",
        )
    s = test_spec.strip()
    if not s:
        raise ControlledExecutionRefused(
            "invalid_test_path", "empty test spec",
        )
    if not _PYTEST_PATH_REGEX.match(s):
        raise ControlledExecutionRefused(
            "invalid_test_path",
            f"{test_spec!r} is not a repo-relative pytest path "
            f"(expected pattern '<path>.py[::Class[::test]]', no shell "
            f"metachars, no flags, no absolute paths).",
        )
    # Path-traversal guard: even if the regex matches, a path full
    # of '..' could still escape the repo. Resolve and check.
    resolve_under_repo(s.split("::", 1)[0])
    return s
