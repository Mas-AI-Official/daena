"""
Thin wrapper to run the root-level truncation guard from within backend/.

This keeps a single source of truth for the actual checks in
`scripts/verify_no_truncation.py` while satisfying tools that expect the
script under `backend/scripts/`.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).parent.parent.resolve()

    # Import the real implementation from scripts/verify_no_truncation.py
    scripts_dir = project_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        import verify_no_truncation  # type: ignore
    except Exception as e:
        print(f"FATAL: Could not import root truncation guard: {e}")
        return 1

    # Delegate to the real main()
    if hasattr(verify_no_truncation, "main"):
        return int(verify_no_truncation.main())

    print("FATAL: verify_no_truncation.main() not found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())









