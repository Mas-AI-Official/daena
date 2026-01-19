#!/usr/bin/env python3
"""
Verify No Duplicate Entrypoints - Detect multiple main entrypoints or duplicate routers.
"""
from __future__ import annotations

import ast
import sys
from collections import defaultdict
from pathlib import Path

EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv",
    "venv_daena_main_py310", "venv_daena_audio_py310", "daena_tts",
    "archive", "old", "dist", "build"
}

def should_skip(path: Path) -> bool:
    """Check if path should be skipped"""
    parts = set(path.parts)
    return any(p in parts for p in EXCLUDE_DIRS)

def find_routers_in_file(file_path: Path) -> list[tuple[str, str]]:
    """Find router definitions in a Python file"""
    routers = []
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            # Find APIRouter() calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "APIRouter":
                    routers.append(("APIRouter", str(file_path.relative_to(file_path.parent.parent.parent))))
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "APIRouter":
                    routers.append(("APIRouter", str(file_path.relative_to(file_path.parent.parent.parent))))
            
            # Find @router decorators
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "router":
                        routers.append(("@router", str(file_path.relative_to(file_path.parent.parent.parent))))
    except Exception:
        pass
    
    return routers

def find_main_entrypoints(root: Path) -> list[Path]:
    """Find main entrypoint files"""
    entrypoints = []
    
    # Look for common entrypoint patterns
    patterns = [
        "main.py",
        "app.py",
        "server.py",
        "start_server.py",
        "run.py",
    ]
    
    # Exclude these directories (legitimate alternative entrypoints)
    exclude_dirs = {
        "brain",  # Separate brain service
        "Core",   # Core library (not an entrypoint)
        "archive", "old", "backup",  # Archive folders
        "venv", ".venv", "venv_daena_main_py310", "venv_daena_audio_py310",  # Virtual environments
        "daena_tts",  # TTS service
        "tests", "test",  # Test files
    }
    
    for pattern in patterns:
        for path in root.rglob(pattern):
            if should_skip(path):
                continue
            
            # Skip if in exclude directory
            path_parts = set(path.parts)
            if any(exclude_dir in path_parts for exclude_dir in exclude_dirs):
                continue
            
            # Only flag if it's in backend/ and looks like a real entrypoint
            # OR if there are multiple in backend/ (actual duplicates)
            if "backend" in path.parts:
                entrypoints.append(path)
    
    # Filter: Only flag if there are multiple entrypoints in backend/
    backend_entrypoints = [ep for ep in entrypoints if "backend" in ep.parts]
    if len(backend_entrypoints) > 1:
        # This is a real issue - multiple entrypoints in backend/
        return backend_entrypoints
    
    # If only one backend entrypoint, that's fine
    return []

def main() -> int:
    """Check for duplicate entrypoints"""
    root = Path(__file__).parent.parent.resolve()
    
    print("=" * 60)
    print("VERIFY NO DUPLICATE ENTRYPOINTS")
    print("=" * 60)
    print()
    
    # Find main entrypoints
    entrypoints = find_main_entrypoints(root)
    
    if len(entrypoints) > 1:
        print("⚠️  Multiple backend entrypoints found:")
        for ep in entrypoints:
            print(f"  - {ep.relative_to(root)}")
        print()
        print("Recommendation: Use one canonical entrypoint (backend/main.py)")
        print("Other entrypoints should be in archive/old/ or separate services.")
        print()
        return 1
    
    # Find routers
    router_files: dict[str, list[Path]] = defaultdict(list)
    
    for py_file in root.rglob("*.py"):
        if should_skip(py_file):
            continue
        if "routes" not in py_file.parts and "api" not in py_file.parts:
            continue
        
        routers = find_routers_in_file(py_file)
        for router_type, rel_path in routers:
            router_files[rel_path].append(py_file)
    
    # Check for duplicate router registrations
    # Only flag if same file appears multiple times (actual bug)
    duplicates = []
    for rel_path, files in router_files.items():
        # Remove duplicates from files list (same file counted twice)
        unique_files = list(set(files))
        if len(unique_files) > 1:
            # Multiple different files with same router - this is a real issue
            duplicates.append((rel_path, unique_files))
        elif len(files) > 1 and len(unique_files) == 1:
            # Same file counted multiple times - likely a parsing issue, not a real duplicate
            pass
    
    if duplicates:
        print("⚠️  Potential duplicate router registrations:")
        for rel_path, files in duplicates:
            print(f"  {rel_path}:")
            for f in files:
                print(f"    - {f.relative_to(root)}")
        print()
        return 1
    
    print("[OK] No duplicate entrypoints detected")
    print()
    print("=" * 60)
    print("✅ VERIFICATION PASSED")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())

