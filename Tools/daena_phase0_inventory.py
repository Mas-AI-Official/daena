#!/usr/bin/env python3
"""
Phase 0: Inventory & Health Check
Builds comprehensive code map and health report.
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any
import subprocess

# Fix encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'node_modules', 'Daena_Clean_Backup', 
                'Constraction AI', 'mas-ai', 'daena-website', 'xtts_temp', '.pytest_cache'}

def find_python_services(root: Path) -> Dict[str, List[str]]:
    """Find all Python service files."""
    services = {
        'memory': [],
        'cmp_bus': [],
        'council': [],
        'dashboards': [],
        'seed_scripts': [],
        'tests': []
    }
    
    # Memory services
    memory_path = root / 'memory_service'
    if memory_path.exists():
        for f in memory_path.rglob('*.py'):
            if not any(ex in str(f) for ex in EXCLUDE_DIRS):
                services['memory'].append(str(f.relative_to(root)))
    
    # CMP Bus
    for pattern in ['message_bus', 'quorum', 'backpressure', 'presence']:
        for f in root.rglob(f'*{pattern}*.py'):
            if not any(ex in str(f) for ex in EXCLUDE_DIRS):
                rel = str(f.relative_to(root))
                if rel not in services['cmp_bus']:
                    services['cmp_bus'].append(rel)
    
    # Council
    for pattern in ['council', 'scheduler']:
        for f in root.rglob(f'*{pattern}*.py'):
            if not any(ex in str(f) for ex in EXCLUDE_DIRS):
                rel = str(f.relative_to(root))
                if 'council' in rel.lower():
                    if rel not in services['council']:
                        services['council'].append(rel)
    
    # Dashboards
    dashboard_path = root / 'frontend' / 'templates'
    if dashboard_path.exists():
        for f in dashboard_path.rglob('*.html'):
            if 'dashboard' in f.name.lower():
                services['dashboards'].append(str(f.relative_to(root)))
    
    # Seed scripts
    for f in root.rglob('*seed*.py'):
        if not any(ex in str(f) for ex in EXCLUDE_DIRS):
            services['seed_scripts'].append(str(f.relative_to(root)))
    
    # Tests
    test_path = root / 'tests'
    if test_path.exists():
        for f in test_path.rglob('test_*.py'):
            if not any(ex in str(f) for ex in EXCLUDE_DIRS):
                services['tests'].append(str(f.relative_to(root)))
    
    return services

def find_agent_count_endpoints(root: Path) -> Dict[str, Any]:
    """Find all endpoints that return agent counts."""
    endpoints = []
    
    routes_path = root / 'backend' / 'routes'
    if routes_path.exists():
        for route_file in routes_path.rglob('*.py'):
            if not any(ex in str(route_file) for ex in EXCLUDE_DIRS):
                try:
                    content = route_file.read_text(encoding='utf-8', errors='ignore')
                    if 'agent' in content.lower() and 'count' in content.lower():
                        # Extract route definitions
                        import re
                        route_matches = re.findall(r'@router\.(get|post|put|delete)\(["\']([^"\']+)["\']', content)
                        for method, path in route_matches:
                            endpoints.append({
                                'file': str(route_file.relative_to(root)),
                                'method': method.upper(),
                                'path': path
                            })
                except:
                    pass
    
    return {'endpoints': endpoints}

def find_duplicate_files(root: Path) -> Dict[str, Any]:
    """Find duplicate files."""
    duplicates = {
        'exact_duplicates': {},
        'same_name_files': defaultdict(list),
        'dashboard_files': [],
        'voice_files': []
    }
    
    hash_map = defaultdict(list)
    name_map = defaultdict(list)
    
    for file_path in root.rglob('*'):
        if file_path.is_file():
            if any(ex in str(file_path) for ex in EXCLUDE_DIRS):
                continue
            
            rel_path = str(file_path.relative_to(root))
            
            # Check by name
            name_lower = file_path.name.lower()
            name_map[name_lower].append(rel_path)
            
            # Check by hash for Python/HTML files
            if file_path.suffix in ['.py', '.html', '.js']:
                try:
                    content = file_path.read_bytes()
                    file_hash = hash(content)
                    hash_map[file_hash].append(rel_path)
                except:
                    pass
    
    # Find exact duplicates
    for file_hash, paths in hash_map.items():
        if len(paths) > 1:
            duplicates['exact_duplicates'][file_hash] = paths
    
    # Find same-name files
    for name, paths in name_map.items():
        if len(paths) > 1 and name not in ['__init__.py', 'conftest.py']:
            duplicates['same_name_files'][name] = paths
    
    # Find dashboard files
    for name, paths in name_map.items():
        if 'dashboard' in name:
            duplicates['dashboard_files'].extend(paths)
    
    # Find voice files
    for name, paths in name_map.items():
        if 'voice' in name and file_path.suffix == '.py':
            duplicates['voice_files'].extend(paths)
    
    return duplicates

def run_test_suite() -> Dict[str, Any]:
    """Run test suite and capture results."""
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', '--collect-only', '-q'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=Path(__file__).parent.parent
        )
        
        output = result.stdout + result.stderr
        
        # Parse results
        collected = 0
        errors = 0
        
        for line in output.split('\n'):
            if 'collected' in line.lower():
                try:
                    collected = int(line.split()[0])
                except:
                    pass
            if 'error' in line.lower() and 'collecting' in line.lower():
                errors += 1
        
        return {
            'collected': collected,
            'errors': errors,
            'output': output[:1000]  # First 1000 chars
        }
    except Exception as e:
        return {
            'collected': 0,
            'errors': 1,
            'error': str(e)
        }

def main():
    root = Path(__file__).parent.parent
    
    print("Phase 0: Inventory & Health Check")
    print("=" * 60)
    
    # Build code map
    print("\n1. Building code map...")
    services = find_python_services(root)
    
    # Find agent count endpoints
    print("2. Finding agent count endpoints...")
    endpoints = find_agent_count_endpoints(root)
    
    # Find duplicates
    print("3. Finding duplicate files...")
    duplicates = find_duplicate_files(root)
    
    # Run tests
    print("4. Running test suite...")
    test_results = run_test_suite()
    
    # Build report
    report = {
        'services': services,
        'endpoints': endpoints,
        'duplicates': duplicates,
        'test_results': test_results,
        'summary': {
            'memory_services': len(services['memory']),
            'cmp_bus_services': len(services['cmp_bus']),
            'council_services': len(services['council']),
            'dashboards': len(services['dashboards']),
            'seed_scripts': len(services['seed_scripts']),
            'tests': len(services['tests']),
            'exact_duplicates': len(duplicates['exact_duplicates']),
            'same_name_files': len(duplicates['same_name_files']),
            'tests_collected': test_results.get('collected', 0),
            'test_errors': test_results.get('errors', 0)
        }
    }
    
    # Save report
    report_path = root / 'reports' / 'phase0_inventory.json'
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\nReport saved to: {report_path}")
    print(f"\nSummary:")
    print(f"  Memory services: {report['summary']['memory_services']}")
    print(f"  CMP Bus services: {report['summary']['cmp_bus_services']}")
    print(f"  Council services: {report['summary']['council_services']}")
    print(f"  Dashboards: {report['summary']['dashboards']}")
    print(f"  Tests: {report['summary']['tests']}")
    print(f"  Exact duplicates: {report['summary']['exact_duplicates']}")
    print(f"  Same-name files: {report['summary']['same_name_files']}")
    print(f"  Tests collected: {report['summary']['tests_collected']}")
    print(f"  Test errors: {report['summary']['test_errors']}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

