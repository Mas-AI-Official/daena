"""
PHASE A: SCAN & REPORT
Scans backend routes, frontend templates, and identifies mismatches
"""
import sys
from pathlib import Path
import re
import json

project_root = Path(__file__).parent.parent

def scan_backend_routes():
    """Scan all backend routes and list API endpoints"""
    print("\n" + "="*60)
    print("PHASE A1: SCANNING BACKEND ROUTES")
    print("="*60)
    
    routes_dir = project_root / "backend" / "routes"
    endpoints = {}
    
    for route_file in routes_dir.glob("*.py"):
        if route_file.name.startswith("__"):
            continue
        
        try:
            content = route_file.read_text(encoding='utf-8')
            
            # Find router prefix
            prefix_match = re.search(r'router\s*=\s*APIRouter\(prefix=["\']([^"\']+)["\']', content)
            prefix = prefix_match.group(1) if prefix_match else ""
            
            # Find all route decorators
            route_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
            routes = re.findall(route_pattern, content)
            
            if routes:
                endpoints[route_file.name] = {
                    "prefix": prefix,
                    "routes": [(method.upper(), path) for method, path in routes]
                }
        except Exception as e:
            print(f"  [WARNING] Error scanning {route_file.name}: {e}")
    
    # Print summary
    print(f"\nFound {len(endpoints)} route files:")
    for file, data in sorted(endpoints.items()):
        print(f"\n  {file}:")
        print(f"    Prefix: {data['prefix']}")
        for method, path in data['routes'][:10]:  # Show first 10
            full_path = f"{data['prefix']}{path}"
            print(f"      {method:6} {full_path}")
        if len(data['routes']) > 10:
            print(f"      ... and {len(data['routes']) - 10} more")
    
    return endpoints

def scan_frontend_templates():
    """Scan frontend templates for mock data"""
    print("\n" + "="*60)
    print("PHASE A2: SCANNING FRONTEND TEMPLATES")
    print("="*60)
    
    templates_dir = project_root / "frontend" / "templates"
    mock_patterns = [
        r'const\s+\w*mock\w*\s*=',
        r'let\s+\w*mock\w*\s*=',
        r'var\s+\w*mock\w*\s*=',
        r'MOCK_',
        r'mockData',
        r'placeholder.*data',
        r'hardcoded.*array',
    ]
    
    found_mock = []
    for template_file in templates_dir.glob("*.html"):
        try:
            content = template_file.read_text(encoding='utf-8')
            for pattern in mock_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    found_mock.append((template_file.name, pattern))
        except Exception as e:
            print(f"  [WARNING] Error scanning {template_file.name}: {e}")
    
    if found_mock:
        print(f"\n  [WARNING] Found {len(found_mock)} potential mock data references:")
        for file, pattern in found_mock[:10]:
            print(f"    - {file}: {pattern}")
    else:
        print("\n  [OK] No mock data found in templates")
    
    return found_mock

def identify_url_mismatches():
    """Identify mismatches between frontend fetch URLs and backend routes"""
    print("\n" + "="*60)
    print("PHASE A3: IDENTIFYING URL MISMATCHES")
    print("="*60)
    
    # This would require parsing JS files for fetch/axios calls
    # For now, we'll check common patterns
    js_dir = project_root / "frontend" / "static" / "js"
    
    api_calls = []
    for js_file in js_dir.glob("*.js"):
        try:
            content = js_file.read_text(encoding='utf-8')
            # Find fetch/axios calls
            fetch_pattern = r'(fetch|axios|request)\(["\']([^"\']+)["\']'
            matches = re.findall(fetch_pattern, content)
            for method, url in matches:
                if url.startswith('/api/') or url.startswith('http'):
                    api_calls.append((js_file.name, url))
        except Exception as e:
            pass
    
    print(f"\n  Found {len(api_calls)} API calls in frontend JS")
    if api_calls:
        print("  Sample API calls:")
        for file, url in api_calls[:10]:
            print(f"    {file}: {url}")
    
    return api_calls

def identify_offline_mock_usage():
    """Identify where agents fall back to OFFLINE mock"""
    print("\n" + "="*60)
    print("PHASE A4: IDENTIFYING OFFLINE MOCK USAGE")
    print("="*60)
    
    backend_dir = project_root / "backend"
    offline_patterns = [
        r'OFFLINE',
        r'offline.*mock',
        r'mock.*offline',
        r'fallback.*offline',
        r'brain.*offline',
        r'_generate_mock_response',
    ]
    
    found_offline = []
    for py_file in backend_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding='utf-8')
            for pattern in offline_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Get context
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            found_offline.append((
                                str(py_file.relative_to(project_root)),
                                i + 1,
                                line.strip()[:80]
                            ))
                            break
        except Exception as e:
            pass
    
    if found_offline:
        print(f"\n  [WARNING] Found {len(found_offline)} offline/mock references:")
        for file, line, context in found_offline[:15]:
            print(f"    {file}:{line} - {context}")
    else:
        print("\n  [OK] No offline mock usage found")
    
    return found_offline

def main():
    print("="*60)
    print("PHASE A: SCAN & REPORT")
    print("="*60)
    
    endpoints = scan_backend_routes()
    mock_data = scan_frontend_templates()
    mismatches = identify_url_mismatches()
    offline_usage = identify_offline_mock_usage()
    
    # Save report
    report = {
        "endpoints": {k: v for k, v in list(endpoints.items())[:20]},  # Limit size
        "mock_data_count": len(mock_data),
        "api_calls_count": len(mismatches),
        "offline_usage_count": len(offline_usage),
    }
    
    report_file = project_root / "PHASE_A_SCAN_REPORT.json"
    report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f"\n  [OK] Report saved to: {report_file}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())



