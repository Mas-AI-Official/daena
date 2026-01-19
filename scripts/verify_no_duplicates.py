"""
Guardrail: detect duplicate route modules and duplicate same-purpose files.

This prevents accidental duplication of:
- Two auth middlewares
- Two brain routers
- Two tool registries
- Competing implementations of the same service
"""

from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict
import re


# Patterns that indicate "same purpose" files
SAME_PURPOSE_PATTERNS = [
    # Auth-related
    (r"auth.*middleware", ["auth_middleware", "auth_middleware_v2", "auth_middleware_new"]),
    (r"auth.*service", ["auth_service", "auth_service_v2", "authentication_service"]),
    # Brain/LLM routing
    (r"(brain|llm).*router", ["brain_router", "llm_router", "model_router", "enhanced_brain"]),
    (r"(brain|llm).*service", ["llm_service", "brain_service", "enhanced_brain_service"]),
    # Tool registries
    (r"tool.*registry", ["tool_registry", "cmp_tool_registry", "tool_runner"]),
    (r"tool.*service", ["tool_service", "automation_service", "cmp_service"]),
    # Route duplicates (routes/ vs routers/)
    (r"routes?/(agents|departments|health|llm|voice)", ["routes/agents", "routers/agents"]),
]


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
    "archive",  # Archive is allowed to have duplicates
    "tests",  # Tests can have duplicates
}


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if any(p in parts for p in EXCLUDE_DIR_PARTS):
        return True
    # Exclude this script itself
    if path.name == "verify_no_duplicates.py":
        return True
    return False


def normalize_name(name: str) -> str:
    """Normalize filename for comparison (remove _v2, _new, etc.)"""
    # Remove common version suffixes
    name = re.sub(r"_v\d+$", "", name)
    name = re.sub(r"_new$", "", name)
    name = re.sub(r"_old$", "", name)
    name = re.sub(r"_backup$", "", name)
    return name.lower()


def find_duplicates(root: Path) -> list[tuple[str, list[str]]]:
    """Find duplicate files by name and same-purpose patterns."""
    failures = []
    
    # Group files by normalized name
    by_normalized = defaultdict(list)
    all_files = []
    
    for p in root.rglob("*.py"):
        if should_skip(p):
            continue
        rel_path = str(p.relative_to(root))
        all_files.append((rel_path, p))
        norm = normalize_name(p.stem)
        by_normalized[norm].append(rel_path)
    
    # Check for exact name duplicates (different paths)
    for norm_name, paths in by_normalized.items():
        if len(paths) > 1:
            # Filter out legitimate cases (e.g., __init__.py in different packages)
            if norm_name == "__init__":
                continue
            # Check if they're in different logical locations
            dirs = [Path(p).parent for p in paths]
            if len(set(dirs)) == len(paths):
                # Different directories - might be legitimate
                # But flag if they're both in backend/ and serve same purpose
                backend_paths = [p for p in paths if "backend/" in p]
                if len(backend_paths) > 1:
                    failures.append((
                        f"Duplicate normalized name: {norm_name}",
                        backend_paths
                    ))
    
    # Check for same-purpose patterns
    for pattern, variants in SAME_PURPOSE_PATTERNS:
        matches = []
        for rel_path, p in all_files:
            if should_skip(p):
                continue
            name_lower = p.stem.lower()
            if re.search(pattern, name_lower):
                matches.append(rel_path)
        
        if len(matches) > 1:
            # Check if they're in competing locations (both in backend/)
            backend_matches = [m for m in matches if "backend/" in m]
            if len(backend_matches) > 1:
                failures.append((
                    f"Same-purpose files (pattern: {pattern}):",
                    backend_matches
                ))
    
    # Check for routes/ vs routers/ duplicates
    routes_files = {Path(p).name: p for p, _ in all_files if "backend/routes/" in p}
    routers_files = {Path(p).name: p for p, _ in all_files if "backend/routers/" in p}
    
    for name in routes_files:
        if name in routers_files:
            failures.append((
                f"Duplicate route module: {name}",
                [routes_files[name], routers_files[name]]
            ))
    
    return failures


def main() -> int:
    root = Path(".").resolve()
    failures = find_duplicates(root)
    
    if failures:
        print("FAIL: duplicate/same-purpose files detected:")
        for reason, paths in failures:
            print(f"\n{reason}:")
            for p in paths:
                print(f"  - {p}")
        return 1
    
    print("OK: no duplicate/same-purpose files detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())









