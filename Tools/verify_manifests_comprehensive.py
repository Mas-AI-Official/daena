"""
Comprehensive Manifest Verification Tool.

Verifies signed rotation manifests with:
- Chain integrity (prev_manifest_hash links)
- Signature verification (HMAC)
- Hash verification
- Cloud KMS integration check
- Compliance reporting
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from memory_service.kms import KeyManagementService


def verify_manifest_chain(
    manifest_dir: Path,
    signing_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Verify complete manifest chain.
    
    Returns:
        Dict with verification results
    """
    if not manifest_dir.exists():
        return {
            "status": "error",
            "error": "Manifest directory does not exist",
            "path": str(manifest_dir)
        }
    
    manifest_paths = sorted(manifest_dir.glob("*.json"))
    
    if not manifest_paths:
        return {
            "status": "warning",
            "message": "No manifests found",
            "path": str(manifest_dir)
        }
    
    results = {
        "status": "success",
        "total_manifests": len(manifest_paths),
        "verified": 0,
        "failed": 0,
        "chain_breaks": 0,
        "details": []
    }
    
    previous_hash: Optional[str] = None
    
    for path in manifest_paths:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            
            # Check chain link
            if previous_hash and manifest.get("prev_manifest_hash") != previous_hash:
                results["chain_breaks"] += 1
                results["details"].append({
                    "manifest": path.name,
                    "status": "chain_break",
                    "expected_hash": previous_hash,
                    "found_hash": manifest.get("prev_manifest_hash")
                })
                results["failed"] += 1
            else:
                # Verify signature
                if KeyManagementService.verify_manifest(manifest, signing_key):
                    results["verified"] += 1
                    results["details"].append({
                        "manifest": path.name,
                        "status": "verified",
                        "timestamp": manifest.get("timestamp"),
                        "key_id": manifest.get("key_id"),
                        "operator": manifest.get("operator")
                    })
                else:
                    results["failed"] += 1
                    results["details"].append({
                        "manifest": path.name,
                        "status": "signature_failed"
                    })
            
            previous_hash = manifest.get("manifest_hash")
            
        except Exception as e:
            results["failed"] += 1
            results["details"].append({
                "manifest": path.name,
                "status": "error",
                "error": str(e)
            })
    
    if results["failed"] > 0 or results["chain_breaks"] > 0:
        results["status"] = "failed"
    
    return results


def check_cloud_kms_integration() -> Dict[str, Any]:
    """Check if cloud KMS integration is configured."""
    kms_endpoint = os.getenv("DAENA_KMS_ENDPOINT")
    signing_key = os.getenv("DAENA_KMS_SIGNING_KEY")
    
    return {
        "kms_endpoint_configured": kms_endpoint is not None,
        "signing_key_configured": signing_key is not None,
        "kms_endpoint": kms_endpoint if kms_endpoint else None,
        "integration_status": "configured" if (kms_endpoint or signing_key) else "not_configured"
    }


def generate_compliance_report(
    manifest_dir: Path,
    signing_key: Optional[str] = None
) -> Dict[str, Any]:
    """Generate compliance report for manifests."""
    chain_results = verify_manifest_chain(manifest_dir, signing_key)
    kms_check = check_cloud_kms_integration()
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "manifest_verification": chain_results,
        "kms_integration": kms_check,
        "compliance_status": "compliant" if chain_results.get("status") == "success" else "non_compliant",
        "recommendations": _generate_recommendations(chain_results, kms_check)
    }


def _generate_recommendations(
    chain_results: Dict[str, Any],
    kms_check: Dict[str, Any]
) -> List[str]:
    """Generate recommendations based on verification results."""
    recommendations = []
    
    if chain_results.get("chain_breaks", 0) > 0:
        recommendations.append("Fix manifest chain breaks - ensure prev_manifest_hash links are correct")
    
    if chain_results.get("failed", 0) > 0:
        recommendations.append("Investigate failed manifest signatures")
    
    if kms_check.get("integration_status") == "not_configured":
        recommendations.append("Configure cloud KMS integration for production use")
    
    if chain_results.get("total_manifests", 0) == 0:
        recommendations.append("Create initial manifest to establish chain")
    
    return recommendations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Comprehensive manifest verification and compliance reporting."
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=Path(".kms/manifests"),
        help="Directory containing rotation manifests"
    )
    parser.add_argument(
        "--signing-key",
        help="Signing key for verification (base64/hex/plaintext, or use DAENA_KMS_SIGNING_KEY env)"
    )
    parser.add_argument(
        "--compliance-report",
        action="store_true",
        help="Generate full compliance report"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for report (JSON)"
    )
    args = parser.parse_args(argv)
    
    signing_key = args.signing_key or os.getenv("DAENA_KMS_SIGNING_KEY")
    
    if args.compliance_report:
        report = generate_compliance_report(args.manifest_dir, signing_key)
        
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Compliance report saved to {args.output}")
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        
        return 0 if report["compliance_status"] == "compliant" else 1
    else:
        results = verify_manifest_chain(args.manifest_dir, signing_key)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
        return 0 if results["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())

