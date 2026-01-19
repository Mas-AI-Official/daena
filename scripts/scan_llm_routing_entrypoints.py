#!/usr/bin/env python3
"""
Scan LLM Routing Entrypoints
Finds all router/LLM classes/functions and identifies which are actually used.
"""
import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple
import json

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"

class RoutingScanner(ast.NodeVisitor):
    """AST visitor to find LLM routing code."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.classes = []
        self.functions = []
        self.imports = []
        self.calls_to_llm = []
        
    def visit_ClassDef(self, node):
        """Find classes related to routing/LLM."""
        if any(keyword in node.name.lower() for keyword in ['router', 'llm', 'model', 'service']):
            self.classes.append({
                'name': node.name,
                'line': node.lineno,
                'file': str(self.file_path.relative_to(PROJECT_ROOT))
            })
        self.generic_visit(node)
    
    def visit_FunctionDef(self, node):
        """Find functions related to routing/LLM."""
        if any(keyword in node.name.lower() for keyword in ['route', 'llm', 'generate', 'chat', 'model']):
            self.functions.append({
                'name': node.name,
                'line': node.lineno,
                'file': str(self.file_path.relative_to(PROJECT_ROOT))
            })
        self.generic_visit(node)
    
    def visit_Import(self, node):
        """Track imports."""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Track from imports."""
        if node.module:
            self.imports.append(node.module)
            for alias in node.names:
                self.imports.append(f"{node.module}.{alias.name}")
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Track calls to LLM-related functions."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if any(keyword in func_name.lower() for keyword in ['llm', 'generate', 'chat', 'model']):
                self.calls_to_llm.append({
                    'function': func_name,
                    'line': node.lineno,
                    'file': str(self.file_path.relative_to(PROJECT_ROOT))
                })
        elif isinstance(node.func, ast.Attribute):
            if any(keyword in node.func.attr.lower() for keyword in ['llm', 'generate', 'chat', 'model']):
                self.calls_to_llm.append({
                    'function': f"{ast.unparse(node.func) if hasattr(ast, 'unparse') else node.func.attr}",
                    'line': node.lineno,
                    'file': str(self.file_path.relative_to(PROJECT_ROOT))
                })
        self.generic_visit(node)


def scan_file(file_path: Path) -> Dict:
    """Scan a single Python file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))
        scanner = RoutingScanner(file_path)
        scanner.visit(tree)
        return {
            'file': str(file_path.relative_to(PROJECT_ROOT)),
            'classes': scanner.classes,
            'functions': scanner.functions,
            'imports': list(set(scanner.imports)),
            'calls': scanner.calls_to_llm
        }
    except Exception as e:
        return {
            'file': str(file_path.relative_to(PROJECT_ROOT)),
            'error': str(e)
        }


def find_imports_of(target_module: str, all_files: List[Dict]) -> List[str]:
    """Find files that import a specific module."""
    files_importing = []
    for file_data in all_files:
        if 'error' in file_data:
            continue
        imports = file_data.get('imports', [])
        if any(target_module in imp for imp in imports):
            files_importing.append(file_data['file'])
    return files_importing


def main():
    """Main scanning function."""
    print("=" * 70)
    print("LLM ROUTING ENTRYPOINT SCAN")
    print("=" * 70)
    print()
    
    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(BACKEND_DIR):
        # Skip venv and __pycache__
        if 'venv' in root or '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    
    print(f"Scanning {len(python_files)} Python files...")
    print()
    
    # Scan all files
    all_scans = []
    routing_files = []
    
    for py_file in python_files:
        scan_result = scan_file(py_file)
        all_scans.append(scan_result)
        
        # Identify routing-related files
        file_str = str(py_file)
        if any(keyword in file_str.lower() for keyword in ['router', 'llm', 'model_router', 'llm_service']):
            routing_files.append(scan_result)
    
    # Find key modules
    print("=" * 70)
    print("KEY MODULES ANALYSIS")
    print("=" * 70)
    print()
    
    # 1. model_router.py
    model_router_files = [f for f in all_scans if 'model_router' in f.get('file', '')]
    if model_router_files:
        print("[MODULE] backend/llm/model_router.py (or similar):")
        router_file = model_router_files[0]
        print(f"   File: {router_file['file']}")
        if 'classes' in router_file:
            print(f"   Classes: {[c['name'] for c in router_file['classes']]}")
        if 'functions' in router_file:
            print(f"   Functions: {[f['name'] for f in router_file['functions']]}")
        
        # Check if it's imported
        imports_model_router = find_imports_of('model_router', all_scans)
        if imports_model_router:
            print(f"   [OK] Imported by: {', '.join(imports_model_router)}")
        else:
            print(f"   [WARNING] NOT IMPORTED ANYWHERE (DEAD CODE)")
        print()
    
    # 2. llm_service.py
    llm_service_files = [f for f in all_scans if 'llm_service' in f.get('file', '')]
    if llm_service_files:
        print("📁 backend/services/llm_service.py:")
        service_file = llm_service_files[0]
        print(f"   File: {service_file['file']}")
        if 'classes' in service_file:
            print(f"   Classes: {[c['name'] for c in service_file['classes']]}")
        
        # Check if it's imported
        imports_llm_service = find_imports_of('llm_service', all_scans)
        print(f"   ✅ Imported by: {', '.join(imports_llm_service[:10])}")
        if len(imports_llm_service) > 10:
            print(f"      ... and {len(imports_llm_service) - 10} more")
        print()
    
    # 3. daena_brain.py
    daena_brain_files = [f for f in all_scans if 'daena_brain' in f.get('file', '')]
    if daena_brain_files:
        print("📁 backend/daena_brain.py:")
        brain_file = daena_brain_files[0]
        print(f"   File: {brain_file['file']}")
        if 'imports' in brain_file:
            llm_imports = [imp for imp in brain_file['imports'] if 'llm' in imp.lower()]
            if llm_imports:
                print(f"   Imports LLM modules: {', '.join(llm_imports)}")
        print()
    
    # 4. API endpoints
    route_files = [f for f in all_scans if 'routes' in f.get('file', '') and 'llm' in f.get('file', '').lower()]
    if route_files:
        print("📁 LLM-related routes:")
        for route_file in route_files:
            print(f"   - {route_file['file']}")
        print()
    
    # Summary
    print("=" * 70)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 70)
    print()
    
    if model_router_files and not imports_model_router:
        print("⚠️ ISSUE FOUND: model_router.py exists but is NOT imported")
        print("   Recommendation: Retire it or make it a thin wrapper around llm_service")
        print()
    
    if llm_service_files and imports_llm_service:
        print("✅ llm_service.py is the active routing module")
        print(f"   Used by {len(imports_llm_service)} files")
        print()
    
    # Save report
    report_dir = PROJECT_ROOT / "docs" / "2025-12-19"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report = {
        'scan_date': str(Path(__file__).stat().st_mtime),
        'model_router': {
            'exists': len(model_router_files) > 0,
            'imported_by': imports_model_router if model_router_files else [],
            'status': 'DEAD' if model_router_files and not imports_model_router else 'ACTIVE'
        },
        'llm_service': {
            'exists': len(llm_service_files) > 0,
            'imported_by': imports_llm_service,
            'status': 'ACTIVE'
        },
        'daena_brain': {
            'exists': len(daena_brain_files) > 0,
            'imports': daena_brain_files[0].get('imports', []) if daena_brain_files else []
        }
    }
    
    report_file = report_dir / "LLM_ROUTING_SCAN.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"📄 Full report saved to: {report_file}")
    print()
    
    return 0 if not (model_router_files and not imports_model_router) else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

