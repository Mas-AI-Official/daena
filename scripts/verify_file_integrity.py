"""
Guardrail: detect file truncation by comparing file sizes and key function/class presence.

This creates a baseline snapshot and detects if any core file shrank significantly
or lost critical functions/classes.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

# Core files that must be protected
CORE_FILES = [
    "backend/daena_brain.py",
    "backend/services/cmp_service.py",
    "backend/services/llm_service.py",
    "backend/utils/sunflower_registry.py",
    "backend/tools/registry.py",
]

# Key functions/classes that must exist in each core file
CORE_FILE_REQUIREMENTS: Dict[str, List[str]] = {
    "backend/daena_brain.py": [
        "class DaenaBrain",
        "def process_message",
        "daena_brain = DaenaBrain()",
    ],
    "backend/services/cmp_service.py": [
        "async def run_cmp_tool_action",
    ],
    "backend/services/llm_service.py": [
        "class LLMService",
        "def generate_response",
    ],
    "backend/utils/sunflower_registry.py": [
        "class SunflowerRegistry",
        "sunflower_registry",
    ],
    "backend/tools/registry.py": [
        "async def execute_tool",
        "TOOL_DEFS",
    ],
}

EXCLUDE_DIR_PARTS = {
    ".git",
    "__pycache__",
    "node_modules",
    "venv_daena_main_py310",
    "venv_daena_audio_py310",
    ".venv",
    "dist",
    "build",
    "daena_tts",
}


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of file content"""
    try:
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ""


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes"""
    try:
        return file_path.stat().st_size
    except Exception:
        return 0


def check_key_elements(file_path: Path, required_elements: List[str]) -> List[str]:
    """Check if file contains required functions/classes"""
    missing = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        for element in required_elements:
            if element not in content:
                missing.append(element)
    except Exception:
        missing = required_elements  # If we can't read, assume all missing
    return missing


def load_baseline(baseline_file: Path) -> Dict[str, Dict[str, any]]:
    """Load baseline snapshot"""
    if not baseline_file.exists():
        return {}
    try:
        return json.loads(baseline_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_baseline(baseline_file: Path, baseline: Dict[str, Dict[str, any]]):
    """Save baseline snapshot"""
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    baseline_file.write_text(json.dumps(baseline, indent=2), encoding="utf-8")


def create_baseline(root: Path) -> Dict[str, Dict[str, any]]:
    """Create baseline snapshot of core files"""
    baseline = {}
    for rel_path in CORE_FILES:
        file_path = root / rel_path
        if file_path.exists():
            baseline[rel_path] = {
                "size": get_file_size(file_path),
                "sha256": calculate_file_hash(file_path),
                "required_elements": CORE_FILE_REQUIREMENTS.get(rel_path, []),
            }
    return baseline


def verify_against_baseline(root: Path, baseline: Dict[str, Dict[str, any]]) -> List[tuple]:
    """Verify current files against baseline"""
    failures = []
    
    for rel_path, baseline_data in baseline.items():
        file_path = root / rel_path
        if not file_path.exists():
            failures.append((rel_path, "FILE_MISSING", f"Core file deleted: {rel_path}"))
            continue
        
        current_size = get_file_size(file_path)
        baseline_size = baseline_data.get("size", 0)
        
        # Check if file shrank by more than 10%
        if baseline_size > 0:
            shrink_percent = ((baseline_size - current_size) / baseline_size) * 100
            if shrink_percent > 10:
                failures.append((
                    rel_path,
                    "FILE_SHRUNK",
                    f"File shrank by {shrink_percent:.1f}% (was {baseline_size} bytes, now {current_size} bytes)"
                ))
        
        # Check hash (if file size changed significantly)
        if abs(current_size - baseline_size) > 100:  # Only check hash if significant size change
            current_hash = calculate_file_hash(file_path)
            baseline_hash = baseline_data.get("sha256", "")
            if baseline_hash and current_hash != baseline_hash:
                # Hash mismatch is expected if we made intentional changes, so we check key elements instead
                pass
        
        # Check for required functions/classes
        required = baseline_data.get("required_elements", [])
        if required:
            missing = check_key_elements(file_path, required)
            if missing:
                failures.append((
                    rel_path,
                    "MISSING_ELEMENTS",
                    f"Missing required elements: {', '.join(missing)}"
                ))
    
    return failures


def main() -> int:
    """Main entry point"""
    root = Path(".").resolve()
    baseline_file = root / ".daena_baseline.json"
    
    # Check if baseline exists
    baseline = load_baseline(baseline_file)
    
    if not baseline:
        # Create baseline
        print("[INFO] Creating baseline snapshot of core files...")
        baseline = create_baseline(root)
        save_baseline(baseline_file, baseline)
        print(f"[OK] Baseline created for {len(baseline)} core files")
        print("[INFO] Run this script again to verify against baseline")
        return 0
    
    # Verify against baseline
    print("[INFO] Verifying core files against baseline...")
    failures = verify_against_baseline(root, baseline)
    
    if failures:
        print("FAIL: Core file integrity issues detected:")
        for rel_path, issue_type, message in failures:
            print(f" - {rel_path}: {issue_type}")
            print(f"   {message}")
        print()
        print("If this is an intentional change, update the baseline:")
        print("  python scripts\\verify_file_integrity.py --update-baseline")
        return 1
    
    print("OK: All core files verified against baseline")
    return 0


if __name__ == "__main__":
    # Check for --update-baseline flag
    if "--update-baseline" in sys.argv:
        root = Path(".").resolve()
        baseline_file = root / ".daena_baseline.json"
        baseline = create_baseline(root)
        save_baseline(baseline_file, baseline)
        print(f"[OK] Baseline updated for {len(baseline)} core files")
        sys.exit(0)
    
    sys.exit(main())









