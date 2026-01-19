from __future__ import annotations

from pathlib import Path
import sys


DEFAULT_FILES = [
    Path("LAUNCH_DAENA_COMPLETE.bat"),
    Path("START_DAENA.bat"),
    Path("setup_environments.bat"),
]


def _to_crlf(text: str) -> str:
    # Normalize to LF first, then convert to CRLF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "\r\n")


def convert_file(path: Path) -> None:
    raw = path.read_bytes()

    # Strip UTF-8 BOM if present (cmd.exe can choke on it in some cases)
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]

    # Best-effort decode; batch files may include unicode glyphs but should be UTF-8 here
    text = raw.decode("utf-8", errors="replace")
    fixed = _to_crlf(text)
    path.write_bytes(fixed.encode("utf-8"))


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv[1:]] if len(argv) > 1 else DEFAULT_FILES
    changed = 0

    for p in files:
        if not p.exists():
            print(f"[skip] {p} (missing)")
            continue
        before = p.read_bytes()
        convert_file(p)
        after = p.read_bytes()
        if after != before:
            changed += 1
            print(f"[ok] CRLF written: {p}")
        else:
            print(f"[ok] already stable: {p}")

    print(f"Done. Files touched: {changed}/{len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))











