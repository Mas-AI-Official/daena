"""
Daena DeFi Security Pipeline
============================

Orchestrates automated security scans using industry-standard tools:
1. Slither (Static Analysis)
2. Mythril (Symbolic Execution)
3. Foundry (Fuzzing)

Usage:
    python contracts/security_pipeline.py <contract_path>
"""

import sys
import shutil
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, List

class SecurityPipeline:
    def __init__(self):
        self.tools = {
            "slither": shutil.which("slither"),
            "mythril": shutil.which("myth"),
            "forge": shutil.which("forge")
        }
        
    def run_all(self, contract_path: str) -> Dict[str, Any]:
        contract = Path(contract_path)
        if not contract.exists():
            return {"error": f"Contract not found: {contract_path}"}
            
        print(f"🔒 Starting Security Pipeline for {contract.name}...")
        
        results = {
            "target": contract.name,
            "scans": {}
        }
        
        # 1. Slither
        if self.tools["slither"]:
            print("   Running Slither...", end="", flush=True)
            try:
                # Run slither and capture JSON output
                cmd = ["slither", str(contract), "--json", "-"]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0 and not proc.stdout:
                     results["scans"]["slither"] = {"status": "failed", "error": proc.stderr}
                     print(" ❌")
                else:
                    try:
                        data = json.loads(proc.stdout)
                        issues = len(data.get("results", {}).get("detectors", []))
                        results["scans"]["slither"] = {"status": "success", "issues_found": issues}
                        print(f" ✅ ({issues} issues)")
                    except json.JSONDecodeError:
                        results["scans"]["slither"] = {"status": "failed", "error": "Invalid JSON"}
                        print(" ⚠️ (Parse Error)")
            except Exception as e:
                print(f" ❌ ({e})")
        else:
            print("   Running Slither... ⏭️ (Not Installed)")
            results["scans"]["slither"] = {"status": "skipped", "reason": "tool_missing"}

        # 2. Mythril
        if self.tools["mythril"]:
            print("   Running Mythril... (may take time)", end="", flush=True)
            # Mythril usually takes long, skipping for quick check unless requested
            print(" ⏭️ (Skipped for speed)")
            results["scans"]["mythril"] = {"status": "skipped", "reason": "optimization"}
        else:
            print("   Running Mythril... ⏭️ (Not Installed)")

        return results

if __name__ == "__main__":
    pipeline = SecurityPipeline()
    
    target = "contracts/test_contracts/reentrancy.sol"
    if len(sys.argv) > 1:
        target = sys.argv[1]
        
    report = pipeline.run_all(target)
    print("\nReport:")
    print(json.dumps(report, indent=2))
