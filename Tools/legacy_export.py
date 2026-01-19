from __future__ import annotations

import argparse
import json
import zlib
from pathlib import Path

from memory_service.router import MemoryRouter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive legacy store snapshot.")
    parser.add_argument("--out", default="legacy_archive.json.zst")
    args = parser.parse_args(argv)

    router = MemoryRouter()
    legacy = router.legacy_store
    snapshot = {item_id: legacy.get_record(item_id) for item_id in legacy.list_ids()}
    blob = json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    Path(args.out).write_bytes(zlib.compress(blob, level=9))
    print(f"wrote {args.out} ({len(blob)} bytes pre-compression)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
