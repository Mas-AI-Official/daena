#!/usr/bin/env python3
"""
Contract Test Script (Phase G).

Verifies that frontend API calls match backend endpoints.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
RESULTS_DIR = PROJECT_ROOT / "docs" / "2025-12-19"


def extract_backend_routes() -> Dict[str, Set[str]]:
    """Extract all backend API routes"""
    routes = {}
    
    # Scan routes directory
    routes_dir = BACKEND_DIR / "routes"
    if not routes_dir.exists():
        return routes
    
    for route_file in routes_dir.glob("*.py"):
        try:
            content = route_file.read_text(encoding="utf-8")
            
            # Extract router prefix
            prefix_match = re.search(r'router\s*=\s*APIRouter\([^)]*prefix=["\']([^"\']+)["\']', content)
            prefix = prefix_match.group(1) if prefix_match else ""
            
            # Extract route decorators
            route_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
            matches = re.findall(route_pattern, content)
            
            for method, path in matches:
                full_path = f"{prefix}{path}"
                if full_path not in routes:
                    routes[full_path] = set()
                routes[full_path].add(method.upper())
        except Exception as e:
            print(f"Warning: Could not parse {route_file}: {e}")
    
    return routes


def extract_frontend_api_calls() -> Dict[str, Set[str]]:
    """Extract all frontend API calls"""
    api_calls = {}
    
    # Scan frontend directory
    if not FRONTEND_DIR.exists():
        return api_calls
    
    for file_path in FRONTEND_DIR.rglob("*.{html,js,ts,tsx,jsx}"):
        try:
            content = file_path.read_text(encoding="utf-8")
            
            # Pattern 1: fetch('/api/...')
            fetch_pattern = r"fetch\(['\"]([^'\"]+)['\"]"
            matches = re.findall(fetch_pattern, content)
            for url in matches:
                if url.startswith("/api/"):
                    method = "GET"  # Default for fetch without method
                    if "method:" in content or "method:" in content.lower():
                        # Try to find method
                        method_match = re.search(r"method:\s*['\"]([^'\"]+)['\"]", content, re.IGNORECASE)
                        if method_match:
                            method = method_match.group(1).upper()
                    
                    if url not in api_calls:
                        api_calls[url] = set()
                    api_calls[url].add(method)
            
            # Pattern 2: hx-get="/api/..." or hx-post="/api/..."
            htmx_pattern = r"hx-(get|post|put|delete|patch)=['\"]([^'\"]+)['\"]"
            matches = re.findall(htmx_pattern, content, re.IGNORECASE)
            for method, url in matches:
                if url.startswith("/api/"):
                    if url not in api_calls:
                        api_calls[url] = set()
                    api_calls[url].add(method.upper())
            
            # Pattern 3: axios.get('/api/...')
            axios_pattern = r"axios\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]"
            matches = re.findall(axios_pattern, content, re.IGNORECASE)
            for method, url in matches:
                if url.startswith("/api/"):
                    if url not in api_calls:
                        api_calls[url] = set()
                    api_calls[url].add(method.upper())
                    
        except Exception as e:
            print(f"Warning: Could not parse {file_path}: {e}")
    
    return api_calls


def normalize_path(path: str) -> str:
    """Normalize API path (remove trailing slashes, normalize variables)"""
    # Remove trailing slash
    path = path.rstrip("/")
    
    # Normalize path variables (e.g., {id} -> :id)
    path = re.sub(r"\{(\w+)\}", r":\1", path)
    
    return path


def compare_routes(backend_routes: Dict[str, Set[str]], frontend_calls: Dict[str, Set[str]]) -> Dict[str, Any]:
    """Compare backend routes and frontend calls"""
    backend_paths = {normalize_path(p): methods for p, methods in backend_routes.items()}
    frontend_paths = {normalize_path(p): methods for p, methods in frontend_calls.items()}
    
    missing_in_backend = []
    missing_in_frontend = []
    method_mismatches = []
    
    # Check frontend calls against backend
    for path, frontend_methods in frontend_paths.items():
        if path not in backend_paths:
            missing_in_backend.append({
                "path": path,
                "methods": list(frontend_methods)
            })
        else:
            backend_methods = backend_paths[path]
            missing_methods = frontend_methods - backend_methods
            if missing_methods:
                method_mismatches.append({
                    "path": path,
                    "frontend_methods": list(frontend_methods),
                    "backend_methods": list(backend_methods),
                    "missing": list(missing_methods)
                })
    
    # Check backend routes not used by frontend
    for path, backend_methods in backend_paths.items():
        if path not in frontend_paths:
            missing_in_frontend.append({
                "path": path,
                "methods": list(backend_methods)
            })
    
    return {
        "missing_in_backend": missing_in_backend,
        "missing_in_frontend": missing_in_frontend,
        "method_mismatches": method_mismatches,
        "total_backend_routes": len(backend_paths),
        "total_frontend_calls": len(frontend_paths),
        "matched_routes": len(set(backend_paths.keys()) & set(frontend_paths.keys()))
    }


def main():
    """Run contract test"""
    print("=" * 60)
    print("Contract Test: Backend <-> Frontend Sync")
    print("=" * 60)
    print()
    
    print("Extracting backend routes...")
    backend_routes = extract_backend_routes()
    print(f"Found {len(backend_routes)} backend routes")
    
    print("Extracting frontend API calls...")
    frontend_calls = extract_frontend_api_calls()
    print(f"Found {len(frontend_calls)} frontend API calls")
    
    print("Comparing routes...")
    comparison = compare_routes(backend_routes, frontend_calls)
    
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total backend routes: {comparison['total_backend_routes']}")
    print(f"Total frontend calls: {comparison['total_frontend_calls']}")
    print(f"Matched routes: {comparison['matched_routes']}")
    print()
    
    if comparison["missing_in_backend"]:
        print(f"⚠️  {len(comparison['missing_in_backend'])} frontend calls missing in backend:")
        for item in comparison["missing_in_backend"][:10]:
            print(f"   {item['path']} ({', '.join(item['methods'])})")
        if len(comparison["missing_in_backend"]) > 10:
            print(f"   ... and {len(comparison['missing_in_backend']) - 10} more")
        print()
    
    if comparison["missing_in_frontend"]:
        print(f"ℹ️  {len(comparison['missing_in_frontend'])} backend routes not used by frontend:")
        for item in comparison["missing_in_frontend"][:10]:
            print(f"   {item['path']} ({', '.join(item['methods'])})")
        if len(comparison["missing_in_frontend"]) > 10:
            print(f"   ... and {len(comparison['missing_in_frontend']) - 10} more")
        print()
    
    if comparison["method_mismatches"]:
        print(f"⚠️  {len(comparison['method_mismatches'])} method mismatches:")
        for item in comparison["method_mismatches"][:5]:
            print(f"   {item['path']}: frontend uses {item['missing']}, backend has {item['backend_methods']}")
        if len(comparison["method_mismatches"]) > 5:
            print(f"   ... and {len(comparison['method_mismatches']) - 5} more")
        print()
    
    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = RESULTS_DIR / "CONTRACT_TEST_RESULTS.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2)
    
    print(f"Results saved to: {results_file}")
    
    # Return exit code
    if comparison["missing_in_backend"] or comparison["method_mismatches"]:
        print()
        print("❌ Contract test FAILED")
        return 1
    else:
        print()
        print("✅ Contract test PASSED")
        return 0


if __name__ == "__main__":
    exit(main())

