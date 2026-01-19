#!/usr/bin/env python3
"""
Phase A: Deep Audit - Dependency Mapping Script

This script:
1. Enumerates all backend modules and their imports
2. Enumerates all frontend pages/templates/components and their API calls
3. Identifies dead code, duplicate modules, mismatched imports
4. Outputs dependency graph report
"""

import ast
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def extract_imports(file_path: Path) -> Tuple[Set[str], Set[str]]:
    """Extract imports from a Python file"""
    imports = set()
    from_imports = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    from_imports.add(node.module.split('.')[0])
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return imports, from_imports


def extract_api_calls(file_path: Path) -> List[str]:
    """Extract API endpoint calls from frontend files"""
    api_calls = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Match fetch('/api/...'), hx-get="/api/...", etc.
        patterns = [
            r"fetch\(['\"]([^'\"]+)['\"]",
            r"hx-get=['\"]([^'\"]+)['\"]",
            r"hx-post=['\"]([^'\"]+)['\"]",
            r"hx-put=['\"]([^'\"]+)['\"]",
            r"hx-delete=['\"]([^'\"]+)['\"]",
            r"axios\.(get|post|put|delete)\(['\"]([^'\"]+)['\"]",
            r"/api/v[0-9]+/[^'\"]+",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    api_calls.extend([m for m in match if m.startswith('/api/')])
                elif isinstance(match, str) and match.startswith('/api/'):
                    api_calls.append(match)
    except Exception as e:
        print(f"Warning: Could not parse {file_path}: {e}")
    
    return list(set(api_calls))


def scan_backend_modules() -> Dict[str, Dict]:
    """Scan all backend Python modules"""
    modules = {}
    
    for py_file in BACKEND_DIR.rglob("*.py"):
        if py_file.name.startswith('__'):
            continue
        
        rel_path = py_file.relative_to(PROJECT_ROOT)
        module_name = str(rel_path).replace('\\', '/').replace('.py', '').replace('/', '.')
        
        imports, from_imports = extract_imports(py_file)
        
        modules[module_name] = {
            "path": str(rel_path),
            "imports": sorted(imports),
            "from_imports": sorted(from_imports),
            "all_imports": sorted(imports | from_imports),
        }
    
    return modules


def scan_frontend_files() -> Dict[str, Dict]:
    """Scan all frontend files for API calls"""
    frontend_files = {}
    
    # Scan HTML templates
    for html_file in (FRONTEND_DIR / "templates").rglob("*.html"):
        rel_path = html_file.relative_to(PROJECT_ROOT)
        api_calls = extract_api_calls(html_file)
        
        frontend_files[str(rel_path)] = {
            "type": "template",
            "api_calls": sorted(api_calls),
        }
    
    # Scan JavaScript files
    for js_file in (FRONTEND_DIR / "static").rglob("*.js"):
        rel_path = js_file.relative_to(PROJECT_ROOT)
        api_calls = extract_api_calls(js_file)
        
        frontend_files[str(rel_path)] = {
            "type": "javascript",
            "api_calls": sorted(api_calls),
        }
    
    return frontend_files


def find_duplicate_modules(modules: Dict[str, Dict]) -> Dict[str, List[str]]:
    """Find modules with duplicate names"""
    name_to_paths = defaultdict(list)
    
    for module_name, info in modules.items():
        # Extract base name (last component)
        base_name = module_name.split('.')[-1]
        name_to_paths[base_name].append(module_name)
    
    duplicates = {name: paths for name, paths in name_to_paths.items() if len(paths) > 1}
    return duplicates


def find_unused_modules(modules: Dict[str, Dict], all_imports: Set[str]) -> List[str]:
    """Find modules that are never imported"""
    module_names = set(modules.keys())
    used_modules = set()
    
    for module_name, info in modules.items():
        # Check if any import references this module
        for imp in info["all_imports"]:
            if imp in module_names:
                used_modules.add(imp)
    
    unused = module_names - used_modules
    # Filter out entry points (main.py, __init__.py, etc.)
    unused = {m for m in unused if not any(m.endswith(x) for x in ['main', '__init__', 'setup', 'config'])}
    
    return sorted(unused)


def extract_backend_routes() -> Set[str]:
    """Extract all API routes from backend"""
    routes = set()
    
    for route_file in (BACKEND_DIR / "routes").glob("*.py"):
        try:
            with open(route_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Match @router.get("/api/..."), @app.get("/api/..."), etc.
            patterns = [
                r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
                r'@app\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    route = match[1] if isinstance(match, tuple) else match
                    routes.add(route)
        except Exception as e:
            print(f"Warning: Could not scan routes in {route_file}: {e}")
    
    return routes


def main():
    """Run the audit"""
    print("Phase A: Deep Audit - Dependency Mapping")
    print("=" * 60)
    
    print("\n1. Scanning backend modules...")
    backend_modules = scan_backend_modules()
    print(f"   Found {len(backend_modules)} backend modules")
    
    print("\n2. Scanning frontend files...")
    frontend_files = scan_frontend_files()
    print(f"   Found {len(frontend_files)} frontend files")
    
    print("\n3. Finding duplicate modules...")
    duplicates = find_duplicate_modules(backend_modules)
    print(f"   Found {len(duplicates)} duplicate module names")
    
    print("\n4. Extracting backend routes...")
    backend_routes = extract_backend_routes()
    print(f"   Found {len(backend_routes)} backend routes")
    
    print("\n5. Extracting frontend API calls...")
    all_frontend_apis = set()
    for file_info in frontend_files.values():
        all_frontend_apis.update(file_info["api_calls"])
    print(f"   Found {len(all_frontend_apis)} unique frontend API calls")
    
    print("\n6. Finding mismatched APIs...")
    # Normalize routes (remove query params, etc.)
    normalized_backend = {r.split('?')[0].split('{')[0] for r in backend_routes}
    normalized_frontend = {r.split('?')[0].split('{')[0] for r in all_frontend_apis}
    
    missing_backend = normalized_frontend - normalized_backend
    unused_backend = normalized_backend - normalized_frontend
    
    print(f"   Frontend APIs missing in backend: {len(missing_backend)}")
    print(f"   Backend APIs not used by frontend: {len(unused_backend)}")
    
    # Generate report
    report = {
        "summary": {
            "backend_modules": len(backend_modules),
            "frontend_files": len(frontend_files),
            "duplicate_modules": len(duplicates),
            "backend_routes": len(backend_routes),
            "frontend_api_calls": len(all_frontend_apis),
            "missing_backend_routes": len(missing_backend),
            "unused_backend_routes": len(unused_backend),
        },
        "duplicate_modules": duplicates,
        "missing_backend_routes": sorted(missing_backend),
        "unused_backend_routes": sorted(unused_backend),
        "backend_modules": {k: {"path": v["path"], "imports_count": len(v["all_imports"])} 
                           for k, v in backend_modules.items()},
        "frontend_files": frontend_files,
    }
    
    # Write report
    report_dir = PROJECT_ROOT / "docs" / "2025-12-13"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report_file = report_dir / "REPO_DEPENDENCY_MAP.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# Repository Dependency Map\n\n")
        f.write("Generated by `scripts/audit_dependencies.py`\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Backend Modules: {report['summary']['backend_modules']}\n")
        f.write(f"- Frontend Files: {report['summary']['frontend_files']}\n")
        f.write(f"- Duplicate Module Names: {report['summary']['duplicate_modules']}\n")
        f.write(f"- Backend Routes: {report['summary']['backend_routes']}\n")
        f.write(f"- Frontend API Calls: {report['summary']['frontend_api_calls']}\n")
        f.write(f"- Missing Backend Routes: {report['summary']['missing_backend_routes']}\n")
        f.write(f"- Unused Backend Routes: {report['summary']['unused_backend_routes']}\n\n")
        
        if duplicates:
            f.write("## Duplicate Module Names\n\n")
            for name, paths in sorted(duplicates.items()):
                f.write(f"### {name}\n")
                for path in paths:
                    f.write(f"- `{path}`\n")
                f.write("\n")
        
        if missing_backend:
            f.write("## Frontend APIs Missing in Backend\n\n")
            for api in sorted(missing_backend):
                f.write(f"- `{api}`\n")
            f.write("\n")
        
        if unused_backend:
            f.write("## Backend APIs Not Used by Frontend\n\n")
            for api in sorted(unused_backend):
                f.write(f"- `{api}`\n")
            f.write("\n")
    
    print(f"\n[OK] Report written to: {report_file}")
    
    # Also write JSON for programmatic access
    json_file = report_dir / "REPO_DEPENDENCY_MAP.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"[OK] JSON report written to: {json_file}")


if __name__ == "__main__":
    main()
