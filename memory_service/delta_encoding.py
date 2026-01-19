"""
Lightweight text diff helpers.
"""

from __future__ import annotations

import json
from difflib import ndiff, restore
from typing import List


def _split_lines(text: str) -> List[str]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return [""]
    return lines


def text_diff(original: str, updated: str) -> str:
    diff_lines = list(ndiff(_split_lines(original), _split_lines(updated)))
    return json.dumps(diff_lines)


def apply_text_diff(original: str, diff: str) -> str:
    if not diff:
        return original
    try:
        diff_lines = json.loads(diff)
        if not isinstance(diff_lines, list):  # pragma: no cover - defensive
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        # Fallback for legacy plain-text diffs
        diff_lines = diff.splitlines()
    restored = restore(diff_lines, 2)
    return "".join(restored)

