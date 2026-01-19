"""
Guardrail: detect accidental "truncation placeholders" in source files.

This does not prove correctness, but prevents known failure modes like:
- truncation phrases inserted by tools/editors
- placeholder ellipses used as file content

We scan:
- Python source: *.py
- HTML templates: *.html
- Frontend JS files: *.js
"""

from __future__ import annotations

import sys
from pathlib import Path


BAD_PATTERNS = [
    # editor/assistant truncation phrases (case-insensitive)
    "contents have been truncated",
    "file is too long and truncated",
    "file content was truncated",
    # real git merge markers (do NOT include "=======" alone; too many false positives)
    "<<<<<<<",
    ">>>>>>>",
]


EXCLUDE_DIR_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv_daena_main_py310",
    "venv_daena_audio_py310",
    ".venv",
    "dist",
    "build",
    "daena_tts",
}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if any(p in parts for p in EXCLUDE_DIR_PARTS):
        return True
    # Exclude this script itself (it contains the patterns as strings)
    if path.name == "verify_no_truncation.py":
        return True
    return False


def main() -> int:
    root = Path(".").resolve()
    failures = []
    exts = (".py", ".html", ".js")

    for p in root.rglob("*"):
        if not p.suffix.lower() in exts:
            continue
        if should_skip(p):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace").lower()
        except Exception as e:
            failures.append((str(p), f"read_error: {e}"))
            continue
        for pat in BAD_PATTERNS:
            if pat.lower() in text:
                failures.append((str(p), f"found: {pat}"))
                break

    if failures:
        print("FAIL: truncation/merge-marker patterns detected:")
        for f, why in failures[:200]:
            print(f" - {f}: {why}")
        if len(failures) > 200:
            print(f"... and {len(failures) - 200} more")
        return 1

    print("OK: no truncation placeholder patterns detected in .py/.html/.js files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


