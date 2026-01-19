"""
Generate governance artifacts for NBMF system.

This script orchestrates the generation of all governance artifacts:
- Ledger manifest with Merkle root
- Policy summary (ABAC + compression)
- Disaster recovery drill report

Run this before releases or as part of CI/CD.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,  # 5 minute timeout for safety
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out after 5 minutes"
    except Exception as e:
        return 1, "", str(e)


def generate_ledger_manifest(output_dir: Path) -> dict[str, any]:
    """Generate ledger manifest with Merkle root."""
    print("Generating ledger manifest...")
    manifest_path = output_dir / "ledger_manifest.json"
    code, stdout, stderr = run_command(
        ["python", "Tools/ledger_chain_export.py", "--out", str(manifest_path), "--print"],
        cwd=Path.cwd(),
    )
    if code != 0:
        print(f"ERROR: Ledger export failed: {stderr}")
        return {"error": stderr, "status": "failed"}
    
    # Try to read from file first, then stdout
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            print(f"Ledger manifest saved to {manifest_path}")
            return manifest
        except json.JSONDecodeError:
            pass
    
    # Try parsing stdout
    try:
        manifest = json.loads(stdout)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"Ledger manifest saved to {manifest_path}")
        return manifest
    except json.JSONDecodeError:
        return {"error": "Failed to parse JSON", "raw_output": stdout}


def generate_policy_summary(output_dir: Path) -> dict[str, any]:
    """Generate policy summary."""
    print("Generating policy summary...")
    # Use build_summary directly instead of CLI
    try:
        from memory_service.policy_summary import load_policy_summary
        policy = load_policy_summary()
        policy_path = output_dir / "policy_summary.json"
        policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")
        print(f"Policy summary saved to {policy_path}")
        return policy
    except Exception as e:
        print(f"Warning: Policy summary generation failed: {e}")
        return {"error": str(e), "status": "failed"}


def generate_drill_report(output_dir: Path) -> dict[str, any]:
    """Generate disaster recovery drill report."""
    print("Running disaster recovery drill...")
    code, stdout, stderr = run_command(
        ["python", "Tools/daena_drill.py"],
        cwd=Path.cwd(),
    )
    if code != 0:
        print(f"ERROR: DR drill failed: {stderr}")
        return {"error": stderr, "status": "failed", "output": stdout}
    try:
        drill = json.loads(stdout)
        drill_path = output_dir / "drill_report.json"
        drill_path.write_text(json.dumps(drill, indent=2))
        print(f"Drill report saved to {drill_path}")
        return drill
    except json.JSONDecodeError:
        drill_path = output_dir / "drill_report.txt"
        drill_path.write_text(stdout)
        return {"raw_output": stdout}


def generate_summary_report(
    output_dir: Path,
    ledger: dict[str, any],
    policy: dict[str, any],
    drill: dict[str, any],
) -> None:
    """Generate a summary report combining all artifacts."""
    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "ledger": {
            "status": "ok" if "error" not in ledger else "failed",
            "merkle_root": ledger.get("merkle_root"),
            "total_transactions": ledger.get("total_transactions"),
        },
        "policy": {
            "status": "ok" if "error" not in policy else "failed",
            "abac_rules": len(policy.get("abac_rules", [])),
            "compression_profiles": len(policy.get("compression_profiles", [])),
        },
        "drill": {
            "status": "ok" if "error" not in drill else "failed",
            "backfill_status": drill.get("backfill_status"),
            "ledger_verification": drill.get("ledger_verification"),
        },
    }
    summary_path = output_dir / "governance_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary report saved to {summary_path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate all NBMF governance artifacts for release/audit."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="governance_artifacts",
        help="Output directory for artifacts (default: governance_artifacts)",
    )
    parser.add_argument(
        "--skip-drill",
        action="store_true",
        help="Skip disaster recovery drill (faster, less comprehensive)",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating governance artifacts in {output_dir}...")
    print("=" * 60)

    ledger = generate_ledger_manifest(output_dir)
    policy = generate_policy_summary(output_dir)

    drill = {}
    if not args.skip_drill:
        drill = generate_drill_report(output_dir)
    else:
        print("Skipping disaster recovery drill (--skip-drill)")

    generate_summary_report(output_dir, ledger, policy, drill)

    print("=" * 60)
    print("Governance artifacts generation complete!")
    print(f"Artifacts saved to: {output_dir}")

    # Return non-zero if any critical step failed
    if "error" in ledger or "error" in policy or ("error" in drill and not args.skip_drill):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

