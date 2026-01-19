"""
Safe requirements.txt refresh:
- dedupe package lines
- preserve comments/blank lines
- DO NOT guess new dependencies
"""

from __future__ import annotations

from pathlib import Path


def _is_pkg_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and not s.startswith("#")


def main() -> int:
    path = Path("requirements.txt")
    if not path.exists():
        print("[refresh_requirements_txt] requirements.txt not found - skipping")
        return 0

    lines = path.read_text(encoding="utf-8").splitlines(True)
    seen = set()
    out = []
    for raw in lines:
        if not _is_pkg_line(raw):
            out.append(raw)
            continue
        key = raw.strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(raw if raw.endswith(("\n", "\r\n")) else raw + "\n")

    new_text = "".join(out)
    old_text = path.read_text(encoding="utf-8")
    if new_text != old_text:
        path.write_text(new_text, encoding="utf-8")
        print("[refresh_requirements_txt] requirements.txt normalized (deduped)")
    else:
        print("[refresh_requirements_txt] requirements.txt unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())











