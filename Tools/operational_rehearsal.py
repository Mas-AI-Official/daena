#!/usr/bin/env python
"""
Operational Rehearsal Script

Runs comprehensive operational checks:
1. Cutover verification
2. Disaster recovery drill
3. Monitoring endpoint checks

Usage:
    python Tools/operational_rehearsal.py [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Import operational tools
from Tools.daena_cutover import main as cutover_main
from Tools.daena_drill import main as drill_main


class OperationalRehearsal:
    """Comprehensive operational rehearsal runner."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: Dict[str, Any] = {
            "timestamp": time.time(),
            "checks": {},
            "summary": {}
        }
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def check_cutover(self) -> Dict[str, Any]:
        """Run cutover verification."""
        print("\n" + "="*60)
        print("CHECK 1: Cutover Verification")
        print("="*60)
        
        try:
            # Run cutover verification
            result = cutover_main(["--verify-only"])
            
            if result == 0:
                print("[PASS] Cutover verification PASSED")
                return {"status": "PASS", "exit_code": result}
            else:
                self.errors.append("Cutover verification failed")
                return {"status": "FAIL", "exit_code": result}
        except Exception as e:
            self.errors.append(f"Cutover verification error: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    def check_dr_drill(self) -> Dict[str, Any]:
        """Run disaster recovery drill."""
        print("\n" + "="*60)
        print("CHECK 2: Disaster Recovery Drill")
        print("="*60)
        
        try:
            # Run DR drill
            result = drill_main([])
            
            if result == 0:
                print("[PASS] DR drill PASSED")
                return {"status": "PASS", "exit_code": result}
            else:
                self.errors.append("DR drill failed")
                return {"status": "FAIL", "exit_code": result}
        except Exception as e:
            self.errors.append(f"DR drill error: {e}")
            return {"status": "ERROR", "error": str(e)}
    
    def check_monitoring_endpoints(self) -> Dict[str, Any]:
        """Check monitoring endpoints availability."""
        print("\n" + "="*60)
        print("CHECK 3: Monitoring Endpoints")
        print("="*60)
        
        results = {}
        endpoints = [
            ("/monitoring/memory", "Memory metrics"),
            ("/monitoring/memory/cas", "CAS efficiency"),
            ("/monitoring/memory/snapshot", "Memory snapshot"),
            ("/monitoring/memory/policy", "Policy summary"),
        ]
        
        # Check if backend is running (simplified check)
        try:
            from memory_service.metrics import snapshot as memory_snapshot
            from memory_service.stats import collect_memory_stats
            from memory_service.policy_summary import load_policy_summary
            
            # Test memory snapshot
            try:
                snap = memory_snapshot()
                results["memory_snapshot"] = {
                    "status": "PASS",
                    "has_data": bool(snap),
                    "keys": list(snap.keys())[:10] if snap else []
                }
                print("[PASS] Memory snapshot accessible")
            except Exception as e:
                results["memory_snapshot"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                self.errors.append(f"Memory snapshot error: {e}")
                print(f"[FAIL] Memory snapshot FAILED: {e}")
            
            # Test memory stats
            try:
                stats = collect_memory_stats()
                results["memory_stats"] = {
                    "status": "PASS",
                    "has_data": bool(stats),
                    "tiers": list(stats.keys()) if stats else []
                }
                print("[PASS] Memory stats accessible")
            except Exception as e:
                results["memory_stats"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                self.errors.append(f"Memory stats error: {e}")
                print(f"[FAIL] Memory stats FAILED: {e}")
            
            # Test policy summary
            try:
                policy = load_policy_summary()
                results["policy_summary"] = {
                    "status": "PASS",
                    "has_data": bool(policy)
                }
                print("[PASS] Policy summary accessible")
            except Exception as e:
                results["policy_summary"] = {
                    "status": "FAIL",
                    "error": str(e)
                }
                self.warnings.append(f"Policy summary error: {e}")
                print(f"[WARN] Policy summary warning: {e}")
            
            # Note: Full HTTP endpoint checks require running server
            results["http_endpoints"] = {
                "status": "SKIP",
                "note": "HTTP endpoint checks require running backend server",
                "endpoints": [ep[0] for ep in endpoints]
            }
            print("[SKIP] HTTP endpoint checks skipped (server not running)")
            
        except ImportError as e:
            results["import_error"] = {
                "status": "ERROR",
                "error": str(e)
            }
            self.errors.append(f"Import error: {e}")
            print(f"❌ Import error: {e}")
        
        return results
    
    def check_governance_artifacts(self) -> Dict[str, Any]:
        """Check governance artifacts generation."""
        print("\n" + "="*60)
        print("CHECK 4: Governance Artifacts")
        print("="*60)
        
        results = {}
        artifacts = [
            ("ledger", "ledger/manifest.json"),
            ("policy", "governance_artifacts/policy_summary.json"),
            ("drill", "governance_artifacts/drill_report.json"),
        ]
        
        for name, path in artifacts:
            artifact_path = Path(path)
            if artifact_path.exists():
                try:
                    with open(artifact_path) as f:
                        data = json.load(f)
                    results[name] = {
                        "status": "PASS",
                        "path": str(artifact_path),
                        "has_data": bool(data)
                    }
                    print(f"[PASS] {name} artifact exists: {artifact_path}")
                except Exception as e:
                    results[name] = {
                        "status": "WARN",
                        "path": str(artifact_path),
                        "error": str(e)
                    }
                    self.warnings.append(f"{name} artifact error: {e}")
                    print(f"[WARN] {name} artifact warning: {e}")
            else:
                results[name] = {
                    "status": "WARN",
                    "path": str(artifact_path),
                    "note": "Artifact not found (may be generated on demand)"
                }
                self.warnings.append(f"{name} artifact not found")
                print(f"[WARN] {name} artifact not found: {artifact_path}")
        
        return results
    
    def run(self) -> Dict[str, Any]:
        """Run all operational checks."""
        print("\n" + "="*60)
        print("OPERATIONAL REHEARSAL")
        print("="*60)
        print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        start_time = time.time()
        
        # Run checks
        self.results["checks"]["cutover"] = self.check_cutover()
        self.results["checks"]["dr_drill"] = self.check_dr_drill()
        self.results["checks"]["monitoring"] = self.check_monitoring_endpoints()
        self.results["checks"]["governance"] = self.check_governance_artifacts()
        
        # Generate summary
        duration = time.time() - start_time
        self.results["duration_sec"] = duration
        
        # Count passes/fails
        passes = sum(1 for check in self.results["checks"].values() 
                    if isinstance(check, dict) and check.get("status") == "PASS")
        fails = len(self.errors)
        warns = len(self.warnings)
        
        self.results["summary"] = {
            "total_checks": len(self.results["checks"]),
            "passed": passes,
            "failed": fails,
            "warnings": warns,
            "errors": self.errors,
            "warnings_list": self.warnings,
            "overall_status": "PASS" if fails == 0 else "FAIL"
        }
        
        # Print summary
        print("\n" + "="*60)
        print("REHEARSAL SUMMARY")
        print("="*60)
        print(f"Duration: {duration:.2f}s")
        print(f"Checks: {passes} passed, {fails} failed, {warns} warnings")
        print(f"Overall: {self.results['summary']['overall_status']}")
        
        if self.errors:
            print("\nErrors:")
            for error in self.errors:
                print(f"  [ERROR] {error}")
        
        if self.warnings:
            print("\nWarnings:")
            for warning in self.warnings:
                print(f"  [WARN] {warning}")
        
        return self.results
    
    def save_results(self, output_path: Path):
        """Save results to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.results, f, indent=2)
        print(f"\nResults saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Operational Rehearsal Script")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", type=str, default="operational_rehearsal_results.json",
                       help="Output JSON file path")
    
    args = parser.parse_args()
    
    rehearsal = OperationalRehearsal(verbose=args.verbose)
    results = rehearsal.run()
    
    # Save results
    output_path = Path(args.output)
    rehearsal.save_results(output_path)
    
    # Exit with appropriate code
    sys.exit(0 if results["summary"]["overall_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()

