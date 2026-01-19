#!/usr/bin/env python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / "Governance" / "artifacts"


def _run(command: list[str]) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    ledger_path = ARTIFACT_DIR / "ledger_manifest.json"
    policy_path = ARTIFACT_DIR / "policy_summary.json"
    drill_path = ARTIFACT_DIR / "drill_report.json"

    ledger_out = _run([sys.executable, "Tools/ledger_chain_export.py", "--out", str(ledger_path)])
    policy_out = _run([sys.executable, "Tools/daena_policy_inspector.py"])
    policy_path.write_text(policy_out, encoding="utf-8")
    drill_out = _run([sys.executable, "Tools/daena_drill.py", "--limit", "0"])
    drill_path.write_text(drill_out, encoding="utf-8")

    summary: Dict[str, str] = {
        "ledger_manifest": str(ledger_path.relative_to(REPO_ROOT)),
        "policy_summary": str(policy_path.relative_to(REPO_ROOT)),
        "drill_report": str(drill_path.relative_to(REPO_ROOT)),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
