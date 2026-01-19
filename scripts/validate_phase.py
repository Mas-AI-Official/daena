#!/usr/bin/env python3
"""
Phase Validation Script

Validates each phase after completion to ensure all requirements are met.
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
RESULTS_DIR = PROJECT_ROOT / "docs" / "2025-12-19"


def validate_phase_b() -> Tuple[bool, List[str]]:
    """Validate Phase B: Stabilize Live Boot"""
    errors = []
    
    # Check launcher exists
    launcher = PROJECT_ROOT / "START_DAENA.bat"
    if not launcher.exists():
        errors.append("START_DAENA.bat not found")
    
    # Check PowerShell launcher exists
    ps_launcher = PROJECT_ROOT / "launch_backend.ps1"
    if not ps_launcher.exists():
        errors.append("launch_backend.ps1 not found")
    
    # Check smoke test exists
    smoke_test = PROJECT_ROOT / "scripts" / "smoke_test.py"
    if not smoke_test.exists():
        errors.append("scripts/smoke_test.py not found")
    
    # Check guard scripts exist
    guard_scripts = [
        "scripts/verify_no_truncation.py",
        "scripts/verify_no_duplicates.py",
    ]
    for script in guard_scripts:
        if not (PROJECT_ROOT / script).exists():
            errors.append(f"{script} not found")
    
    return len(errors) == 0, errors


def validate_phase_c() -> Tuple[bool, List[str]]:
    """Validate Phase C: Brain Architecture"""
    errors = []
    
    # Check canonical brain exists
    brain_file = PROJECT_ROOT / "backend" / "daena_brain.py"
    if not brain_file.exists():
        errors.append("backend/daena_brain.py not found")
    
    # Check brain store exists
    brain_store = PROJECT_ROOT / "backend" / "core" / "brain" / "store.py"
    if not brain_store.exists():
        errors.append("backend/core/brain/store.py not found")
    
    # Check governance routes exist
    brain_routes = PROJECT_ROOT / "backend" / "routes" / "brain.py"
    if not brain_routes.exists():
        errors.append("backend/routes/brain.py not found")
    
    return len(errors) == 0, errors


def validate_phase_d() -> Tuple[bool, List[str]]:
    """Validate Phase D: Model Layer Upgrade"""
    errors = []
    
    # Check model registry exists
    model_registry = PROJECT_ROOT / "backend" / "services" / "model_registry.py"
    if not model_registry.exists():
        errors.append("backend/services/model_registry.py not found")
    
    return len(errors) == 0, errors


def validate_phase_e() -> Tuple[bool, List[str]]:
    """Validate Phase E: Prompt Engineering"""
    errors = []
    
    # Will check for prompt library when implemented
    prompt_lib = PROJECT_ROOT / "backend" / "services" / "prompt_library.py"
    if not prompt_lib.exists():
        errors.append("backend/services/prompt_library.py not found (expected in Phase E)")
    
    return len(errors) == 0, errors


def validate_phase_f() -> Tuple[bool, List[str]]:
    """Validate Phase F: Skills Growth"""
    errors = []
    
    # Will check for tool playbooks when implemented
    playbooks = PROJECT_ROOT / "backend" / "services" / "tool_playbooks.py"
    if not playbooks.exists():
        errors.append("backend/services/tool_playbooks.py not found (expected in Phase F)")
    
    return len(errors) == 0, errors


def validate_phase_g() -> Tuple[bool, List[str]]:
    """Validate Phase G: Backend/Frontend Sync"""
    errors = []
    
    # Check contract test exists
    contract_test = PROJECT_ROOT / "scripts" / "contract_test.py"
    if not contract_test.exists():
        errors.append("scripts/contract_test.py not found")
    
    return len(errors) == 0, errors


def validate_phase_h() -> Tuple[bool, List[str]]:
    """Validate Phase H: Verification"""
    errors = []
    
    # Check verification scripts exist
    verify_scripts = [
        "scripts/verify_no_truncation.py",
        "scripts/verify_no_duplicates.py",
        "scripts/smoke_test.py",
    ]
    for script in verify_scripts:
        if not (PROJECT_ROOT / script).exists():
            errors.append(f"{script} not found")
    
    return len(errors) == 0, errors


def main():
    """Run validation for all phases"""
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    validators = {
        "B": validate_phase_b,
        "C": validate_phase_c,
        "D": validate_phase_d,
        "E": validate_phase_e,
        "F": validate_phase_f,
        "G": validate_phase_g,
        "H": validate_phase_h,
    }
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    if phase == "all":
        results = {}
        for phase_name, validator in validators.items():
            passed, errors = validator()
            results[phase_name] = {
                "passed": passed,
                "errors": errors
            }
            print(f"Phase {phase_name}: {'PASS' if passed else 'FAIL'}")
            if errors:
                for error in errors:
                    print(f"  - {error}")
        
        # Write results
        results_file = RESULTS_DIR / f"validation_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults written to: {results_file}")
    else:
        if phase.upper() in validators:
            passed, errors = validators[phase.upper()]()
            print(f"Phase {phase.upper()}: {'PASS' if passed else 'FAIL'}")
            if errors:
                for error in errors:
                    print(f"  - {error}")
            sys.exit(0 if passed else 1)
        else:
            print(f"Unknown phase: {phase}")
            sys.exit(1)


if __name__ == "__main__":
    main()





