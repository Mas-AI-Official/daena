"""
Weekly Automated Drill Bundle.

Runs comprehensive compliance and operational checks:
- Chaos/soak tests
- Ledger verification
- Key-manifest checks
- Governance artifact generation
- Generates one-page compliance summary
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from memory_service.ledger import Ledger
from memory_service.metrics import snapshot as metrics_snapshot


def run_chaos_test() -> Dict[str, Any]:
    """Run chaos engineering scenario."""
    try:
        result = subprocess.run(
            [sys.executable, "Tools/daena_chaos.py", "--scenario", "read_surge"],
            capture_output=True,
            text=True,
            timeout=60
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "Chaos test timed out"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def verify_ledger() -> Dict[str, Any]:
    """Verify ledger integrity."""
    try:
        ledger = Ledger(Path(".ledger/ledger.jsonl"))
        manifest = ledger.generate_manifest()
        
        # Verify ledger
        result = subprocess.run(
            [sys.executable, "Tools/daena_ledger_verify.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "merkle_root": manifest.get("merkle_root"),
            "entry_count": manifest.get("entry_count", 0),
            "verification": result.stdout if result.returncode == 0 else result.stderr
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def verify_key_manifests() -> Dict[str, Any]:
    """Verify key rotation manifests."""
    try:
        result = subprocess.run(
            [sys.executable, "Tools/verify_manifests_comprehensive.py", "--compliance-report"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            try:
                report = json.loads(result.stdout)
                return {
                    "status": "success",
                    "compliance_status": report.get("compliance_status"),
                    "manifest_verification": report.get("manifest_verification", {}),
                    "kms_integration": report.get("kms_integration", {})
                }
            except json.JSONDecodeError:
                return {
                    "status": "success",
                    "raw_output": result.stdout
                }
        else:
            return {
                "status": "failed",
                "error": result.stderr
            }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_governance_artifacts() -> Dict[str, Any]:
    """Generate governance artifacts."""
    try:
        result = subprocess.run(
            [sys.executable, "Tools/generate_governance_artifacts.py", "--skip-drill"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": result.returncode,
            "output": result.stdout,
            "error": result.stderr if result.returncode != 0 else None
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def generate_compliance_summary(
    chaos_result: Dict[str, Any],
    ledger_result: Dict[str, Any],
    manifest_result: Dict[str, Any],
    governance_result: Dict[str, Any],
    metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate one-page compliance summary."""
    
    # Determine overall status
    all_passed = (
        chaos_result.get("status") == "success" and
        ledger_result.get("status") == "success" and
        manifest_result.get("status") == "success" and
        governance_result.get("status") == "success"
    )
    
    # Key metrics
    ledger_entries = ledger_result.get("entry_count", 0)
    manifest_compliance = manifest_result.get("compliance_status", "unknown")
    
    # CAS efficiency
    cas_hit_rate = metrics.get("llm_cas_hit_rate", 0.0)
    near_dup_rate = metrics.get("llm_near_dup_rate", 0.0)
    
    # Divergence rate
    divergence_rate = metrics.get("divergence_rate", 0.0)
    
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "PASS" if all_passed else "FAIL",
        "checks": {
            "chaos_test": {
                "status": chaos_result.get("status"),
                "passed": chaos_result.get("status") == "success"
            },
            "ledger_verification": {
                "status": ledger_result.get("status"),
                "passed": ledger_result.get("status") == "success",
                "entry_count": ledger_entries,
                "merkle_root": ledger_result.get("merkle_root")
            },
            "key_manifests": {
                "status": manifest_result.get("status"),
                "passed": manifest_result.get("status") == "success",
                "compliance": manifest_compliance
            },
            "governance_artifacts": {
                "status": governance_result.get("status"),
                "passed": governance_result.get("status") == "success"
            }
        },
        "key_metrics": {
            "ledger_entries": ledger_entries,
            "cas_hit_rate": round(cas_hit_rate, 4),
            "near_dup_rate": round(near_dup_rate, 4),
            "divergence_rate": round(divergence_rate, 6),
            "nbmf_reads": metrics.get("nbmf_reads", 0),
            "nbmf_writes": metrics.get("nbmf_writes", 0)
        },
        "recommendations": []
    }
    
    # Add recommendations
    if divergence_rate > 0.005:
        summary["recommendations"].append(f"Divergence rate ({divergence_rate:.4f}) exceeds threshold (0.005)")
    
    if cas_hit_rate < 0.6:
        summary["recommendations"].append(f"CAS hit rate ({cas_hit_rate:.2%}) below target (60%)")
    
    if manifest_compliance != "compliant":
        summary["recommendations"].append("Key manifest chain needs attention")
    
    if not all_passed:
        summary["recommendations"].append("Some compliance checks failed - review details")
    
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Weekly automated drill bundle for compliance and operational checks."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/weekly_drill"),
        help="Directory for drill outputs"
    )
    parser.add_argument(
        "--skip-chaos",
        action="store_true",
        help="Skip chaos tests (faster execution)"
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Generate summary only (skip detailed checks)"
    )
    args = parser.parse_args(argv)
    
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Weekly Automated Drill Bundle")
    print("=" * 60)
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    start_time = time.time()
    
    # Run checks
    print("1. Running chaos test...")
    chaos_result = run_chaos_test() if not args.skip_chaos else {"status": "skipped"}
    print(f"   Status: {chaos_result.get('status')}")
    
    print("2. Verifying ledger...")
    ledger_result = verify_ledger()
    print(f"   Status: {ledger_result.get('status')}")
    if ledger_result.get("entry_count"):
        print(f"   Entries: {ledger_result.get('entry_count')}")
    
    print("3. Verifying key manifests...")
    manifest_result = verify_key_manifests()
    print(f"   Status: {manifest_result.get('status')}")
    if manifest_result.get("compliance_status"):
        print(f"   Compliance: {manifest_result.get('compliance_status')}")
    
    print("4. Generating governance artifacts...")
    governance_result = generate_governance_artifacts()
    print(f"   Status: {governance_result.get('status')}")
    
    print("5. Collecting metrics...")
    metrics = metrics_snapshot()
    print(f"   CAS hit rate: {metrics.get('llm_cas_hit_rate', 0.0):.2%}")
    print(f"   Divergence rate: {metrics.get('divergence_rate', 0.0):.6f}")
    
    # Generate summary
    print("\n6. Generating compliance summary...")
    summary = generate_compliance_summary(
        chaos_result,
        ledger_result,
        manifest_result,
        governance_result,
        metrics
    )
    
    # Save summary
    summary_path = args.output_dir / "compliance_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Save detailed results
    detailed_path = args.output_dir / "detailed_results.json"
    detailed_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_sec": time.time() - start_time,
        "chaos_test": chaos_result,
        "ledger_verification": ledger_result,
        "key_manifests": manifest_result,
        "governance_artifacts": governance_result,
        "metrics": metrics
    }
    detailed_path.write_text(json.dumps(detailed_results, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Print summary
    print("\n" + "=" * 60)
    print("COMPLIANCE SUMMARY")
    print("=" * 60)
    print(f"Overall Status: {summary['overall_status']}")
    print(f"\nChecks:")
    for check_name, check_result in summary["checks"].items():
        status_icon = "PASS" if check_result["passed"] else "FAIL"
        print(f"  [{status_icon}] {check_name}: {check_result['status']}")
    
    print(f"\nKey Metrics:")
    for metric_name, metric_value in summary["key_metrics"].items():
        print(f"  {metric_name}: {metric_value}")
    
    if summary["recommendations"]:
        print(f"\nRecommendations:")
        for rec in summary["recommendations"]:
            print(f"  - {rec}")
    
    print(f"\nDuration: {time.time() - start_time:.2f}s")
    print(f"Summary saved to: {summary_path}")
    print(f"Detailed results saved to: {detailed_path}")
    print("=" * 60)
    
    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

