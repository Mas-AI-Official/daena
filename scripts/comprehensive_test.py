#!/usr/bin/env python3
"""
Comprehensive Test Suite (Phase H).

Runs all validation tests and checks for system drift.
"""

import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RESULTS_DIR = PROJECT_ROOT / "docs" / "2025-12-19"


def run_test(script_name: str, description: str) -> tuple[bool, str]:
    """Run a test script and return (success, output)"""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        return False, f"Script not found: {script_name}"
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        return success, output
    except subprocess.TimeoutExpired:
        return False, f"Test timed out after 300 seconds"
    except Exception as e:
        return False, f"Error running test: {e}"


def check_guardrails() -> tuple[bool, str]:
    """Run guardrail scripts"""
    results = []
    
    # Truncation check
    success, output = run_test("verify_no_truncation.py", "Truncation check")
    results.append(("Truncation Check", success, output))
    
    # Duplicate check
    success, output = run_test("verify_no_duplicates.py", "Duplicate check")
    results.append(("Duplicate Check", success, output))
    
    all_passed = all(success for _, success, _ in results)
    output_summary = "\n".join([
        f"{name}: {'PASS' if success else 'FAIL'}"
        for name, success, _ in results
    ])
    
    return all_passed, output_summary


def check_contracts() -> tuple[bool, str]:
    """Run contract tests"""
    success, output = run_test("contract_test.py", "Contract test")
    return success, output


def check_phases() -> tuple[bool, str]:
    """Run phase validation"""
    success, output = run_test("validate_phase.py", "Phase validation")
    return success, output


def check_smoke() -> tuple[bool, str]:
    """Run smoke tests (if backend is running)"""
    success, output = run_test("smoke_test.py", "Smoke test")
    return success, output


def main():
    """Run comprehensive test suite"""
    print("=" * 60)
    print("Comprehensive Test Suite - Phase H")
    print("=" * 60)
    print()
    
    results = []
    
    # Guardrails
    print("Running guardrail checks...")
    success, output = check_guardrails()
    results.append(("Guardrails", success, output))
    print("[OK] Guardrails" if success else "[FAIL] Guardrails")
    print()
    
    # Contract tests
    print("Running contract tests...")
    success, output = check_contracts()
    results.append(("Contract Tests", success, output))
    print("[OK] Contract Tests" if success else "[FAIL] Contract Tests")
    print()
    
    # Phase validation
    print("Running phase validation...")
    success, output = check_phases()
    results.append(("Phase Validation", success, output))
    print("[OK] Phase Validation" if success else "[FAIL] Phase Validation")
    print()
    
    # Smoke tests (optional - backend must be running)
    print("Running smoke tests (optional - requires running backend)...")
    success, output = check_smoke()
    if "Connection refused" in output or "ConnectionError" in output:
        print("[WARN] Smoke tests skipped (backend not running)")
        results.append(("Smoke Tests", None, "Skipped - backend not running"))
    else:
        results.append(("Smoke Tests", success, output))
        print("[OK] Smoke Tests" if success else "[FAIL] Smoke Tests")
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success, _ in results if success is True)
    failed = sum(1 for _, success, _ in results if success is False)
    skipped = sum(1 for _, success, _ in results if success is None)
    total = len(results)
    
    for name, success, output in results:
        if success is True:
            status = "[OK] PASS"
        elif success is False:
            status = "[FAIL] FAIL"
        else:
            status = "[SKIP] SKIP"
        print(f"{status} - {name}")
    
    print()
    print(f"Total: {total} | Passed: {passed} | Failed: {failed} | Skipped: {skipped}")
    
    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = RESULTS_DIR / "COMPREHENSIVE_TEST_RESULTS.txt"
    with open(results_file, 'w', encoding='utf-8') as f:
        f.write("Comprehensive Test Suite Results\n")
        f.write("=" * 60 + "\n\n")
        for name, success, output in results:
            f.write(f"{name}: {'PASS' if success else 'FAIL' if success is False else 'SKIP'}\n")
            f.write("-" * 60 + "\n")
            f.write(output[:1000])  # First 1000 chars
            f.write("\n\n")
    
    print(f"\nResults saved to: {results_file}")
    
    # Return exit code
    if failed > 0:
        print("\n[FAIL] Test suite FAILED")
        return 1
    else:
        print("\n[OK] Test suite PASSED")
        return 0


if __name__ == "__main__":
    exit(main())

