"""Sprint-17 PR-1 -- shared local-file safety helpers.

Pins:
  1. REPO_ROOT resolves to D:\\Ideas\\Daena (or wherever the
     repo lives) -- not a parent or sibling.
  2. is_secret_file matches the same set as Sprint-14 PR-4
     (regression: refactoring must not silently drop a pattern).
  3. resolve_under_repo refuses path traversal escapes.
  4. validate_pytest_path:
      - accepts repo-relative .py files
      - accepts ::TestClass::test_method selectors
      - REFUSES shell metachars
      - REFUSES absolute paths
      - REFUSES drive letters
      - REFUSES non-.py paths
      - REFUSES empty / whitespace
"""

from __future__ import annotations

import pytest


class TestRepoRoot:
    def test_repo_root_resolves_correctly(self):
        from app.services.local_file_safety import REPO_ROOT

        # Anchor file lives at backend/app/services/local_file_safety.py
        # so REPO_ROOT must contain backend/, frontend/, docs/.
        assert (REPO_ROOT / "backend").exists()
        assert (REPO_ROOT / "frontend").exists()


class TestIsSecretFile:
    @pytest.mark.parametrize("path,expected", [
        (".env", True),
        (".env.production", True),
        ("backend/.env", True),
        ("private.pem", True),
        ("ssh_key.key", True),
        ("backend/secrets/google.json", True),
        ("secrets/api_key.txt", True),
        ("credentials.json", True),
        (".credentials", True),
        ("oauth_tokens.json", True),
        (".daena_oauth_overrides.json", True),
        (".autonomy_mode.json", True),
        # Should NOT match
        ("backend/app/main.py", False),
        ("frontend/src/App.tsx", False),
        ("README.md", False),
        ("docs/file.md", False),
    ])
    def test_secret_file_classification(self, path, expected):
        from app.services.local_file_safety import is_secret_file
        assert is_secret_file(path) is expected


class TestResolveUnderRepo:
    def test_repo_relative_path_accepted(self):
        from app.services.local_file_safety import resolve_under_repo

        resolved = resolve_under_repo("backend/app/main.py")
        assert resolved.name == "main.py"

    def test_path_traversal_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.local_file_safety import resolve_under_repo

        with pytest.raises(ControlledExecutionRefused) as ei:
            resolve_under_repo("../../../etc/passwd")
        assert ei.value.code == "target_path_outside_repo"

    def test_absolute_outside_repo_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.local_file_safety import resolve_under_repo

        with pytest.raises(ControlledExecutionRefused) as ei:
            resolve_under_repo("C:/Windows/System32/config")
        assert ei.value.code == "target_path_outside_repo"


class TestValidatePytestPath:
    @pytest.mark.parametrize("spec", [
        "backend/tests/test_a.py",
        "backend/tests/test_a.py::TestClass",
        "backend/tests/test_a.py::TestClass::test_method",
        "backend/tests/test_a.py::test_function",
        "tests/services/test_x.py",
        # backslash form (Windows)
        "backend\\tests\\test_a.py",
    ])
    def test_valid_pytest_paths(self, spec):
        from app.services.local_file_safety import validate_pytest_path
        assert validate_pytest_path(spec) == spec

    @pytest.mark.parametrize("spec,reason", [
        ("", "empty"),
        ("   ", "whitespace"),
        ("/etc/passwd", "absolute"),
        ("C:/Windows/test.py", "drive letter"),
        ("backend/test.py; rm -rf /", "shell metachar ;"),
        ("backend/test.py && evil", "shell metachar &"),
        ("backend/test.py | evil", "shell metachar |"),
        ("backend/test.py > out", "shell metachar >"),
        ("backend/test.py `evil`", "backtick"),
        ("backend/test.py $(evil)", "shell substitution"),
        ("--mode=quiet", "flag instead of path"),
        ("backend/test.txt", "non-.py"),
        ("backend/test", "no extension"),
        ("../../../etc/passwd.py", "path traversal even with .py"),
    ])
    def test_invalid_pytest_paths_refused(self, spec, reason):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.local_file_safety import validate_pytest_path

        with pytest.raises(ControlledExecutionRefused) as ei:
            validate_pytest_path(spec)
        assert ei.value.code in (
            "invalid_test_path",
            "target_path_outside_repo",  # path-traversal check
        ), f"unexpected refusal code for {reason}: {ei.value.code}"
