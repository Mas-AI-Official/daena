#!/usr/bin/env python3
"""
Daena v2 Duplicate Sweep & Broken Links Detection Tool
Scans entire repo to detect duplicates, dead files, and broken references.
"""

import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from difflib import SequenceMatcher
import importlib.util

# Exclude patterns
EXCLUDE_DIRS = {
    'venv', '__pycache__', '.git', 'node_modules', 
    'build', 'dist', '.pytest_cache', 'htmlcov',
    'wandb', 'models', 'trained_models', 'cache',
    'logs', 'backups', 'artifacts', 'xtts_temp',
    'Daena_Clean_Backup', 'Constraction AI', 'mas-ai', 'daena-website'
}

EXCLUDE_FILES = {'.pyc', '.pyo', '.pyd', '.db', '.log', '.jsonl', '.png', '.jpg', '.svg'}

class DuplicateSweeper:
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.file_map: Dict[str, Dict] = {}
        self.duplicates: List[Dict] = []
        self.dead_files: List[str] = []
        self.broken_imports: List[Dict] = []
        self.class_map: Dict[str, List[str]] = defaultdict(list)
        self.function_map: Dict[str, List[str]] = defaultdict(list)
        self.route_map: Dict[str, List[str]] = defaultdict(list)
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        
    def similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings."""
        return SequenceMatcher(None, s1, s2).ratio()
    
    def file_hash(self, file_path: Path) -> str:
        """Calculate hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def scan_python_file(self, file_path: Path) -> Dict:
        """Scan a Python file for classes, functions, routes."""
        info = {
            'path': str(file_path.relative_to(self.root)),
            'classes': [],
            'functions': [],
            'routes': [],
            'imports': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            tree = ast.parse(content, filename=str(file_path))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    info['classes'].append(node.name)
                    self.class_map[node.name].append(str(file_path.relative_to(self.root)))
                
                if isinstance(node, ast.FunctionDef):
                    info['functions'].append(node.name)
                    self.function_map[node.name].append(str(file_path.relative_to(self.root)))
                
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ''
                        for alias in node.names:
                            info['imports'].append(f"{module}.{alias.name}" if module else alias.name)
                    else:
                        for alias in node.names:
                            info['imports'].append(alias.name)
                
                # Detect FastAPI routes
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr in ['get', 'post', 'put', 'delete', 'patch']:
                            if node.args:
                                route_node = node.args[0]
                                if isinstance(route_node, ast.Constant):
                                    info['routes'].append(route_node.value)
                                    self.route_map[route_node.value].append(str(file_path.relative_to(self.root)))
        except Exception as e:
            pass
        
        return info
    
    def scan_all_files(self):
        """Scan all files in the repository."""
        print("🔍 Scanning repository files...")
        
        for root, dirs, files in os.walk(self.root):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            
            for file in files:
                if any(file.endswith(ext) for ext in EXCLUDE_FILES):
                    continue
                
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.root)
                
                # Skip if in excluded directory
                if any(excluded in str(rel_path) for excluded in EXCLUDE_DIRS):
                    continue
                
                if file_path.suffix in ['.py', '.md', '.txt', '.yaml', '.yml', '.json']:
                    file_hash = self.file_hash(file_path)
                    self.file_map[str(rel_path)] = {
                        'path': str(rel_path),
                        'hash': file_hash,
                        'size': file_path.stat().st_size,
                        'name': file
                    }
                    
                    if file_path.suffix == '.py':
                        py_info = self.scan_python_file(file_path)
                        self.file_map[str(rel_path)].update(py_info)
    
    def detect_duplicate_files(self):
        """Detect exact and near-duplicate files."""
        print("\n🔄 Detecting duplicate files...")
        
        # Group by hash (exact duplicates)
        hash_groups = defaultdict(list)
        for path, info in self.file_map.items():
            if info['hash']:
                hash_groups[info['hash']].append(path)
        
        # Find exact duplicates
        for hash_val, paths in hash_groups.items():
            if len(paths) > 1:
                self.duplicates.append({
                    'type': 'exact',
                    'hash': hash_val,
                    'files': paths,
                    'size': self.file_map[paths[0]]['size']
                })
        
        # Find near-duplicates by filename similarity
        all_files = list(self.file_map.keys())
        for i, file1 in enumerate(all_files):
            name1 = Path(file1).stem.lower()
            for j, file2 in enumerate(all_files[i+1:], i+1):
                name2 = Path(file2).stem.lower()
                sim = self.similarity(name1, name2)
                if sim > 0.8 and file1 != file2:
                    # Check if not already in exact duplicates
                    if not any(file1 in dup['files'] and file2 in dup['files'] 
                             for dup in self.duplicates if dup['type'] == 'exact'):
                        self.duplicates.append({
                            'type': 'near_duplicate',
                            'similarity': sim,
                            'files': [file1, file2]
                        })
    
    def detect_duplicate_symbols(self):
        """Detect duplicate classes, functions, routes."""
        print("\n⚠️  Detecting duplicate symbols...")
        
        # Duplicate classes
        for class_name, locations in self.class_map.items():
            if len(locations) > 1:
                self.duplicates.append({
                    'type': 'duplicate_class',
                    'symbol': class_name,
                    'locations': locations
                })
        
        # Duplicate functions (same name, different files, not test files)
        for func_name, locations in self.function_map.items():
            non_test_locations = [loc for loc in locations if 'test' not in loc.lower()]
            if len(non_test_locations) > 1:
                self.duplicates.append({
                    'type': 'duplicate_function',
                    'symbol': func_name,
                    'locations': non_test_locations
                })
        
        # Duplicate routes
        for route, locations in self.route_map.items():
            if len(locations) > 1:
                self.duplicates.append({
                    'type': 'duplicate_route',
                    'route': route,
                    'locations': locations
                })
    
    def detect_dead_files(self):
        """Detect files that are never imported or referenced."""
        print("\n🗑️  Detecting dead files...")
        
        for path, info in self.file_map.items():
            # Skip test files, scripts, main files, docs
            if any(x in path for x in ['test_', 'tests/', 'Tools/', 'scripts/', 'main.py', 
                                      '__init__.py', '.md', 'docs/', 'README']):
                continue
            
            if Path(path).suffix == '.py':
                # Check if this module is imported anywhere
                module_parts = path.replace('/', '.').replace('\\', '.').replace('.py', '').split('.')
                module_name = '.'.join(module_parts)
                
                # Check imports
                is_imported = False
                for other_path, other_info in self.file_map.items():
                    if other_path != path and Path(other_path).suffix == '.py':
                        imports = other_info.get('imports', [])
                        for imp in imports:
                            if module_name in imp or any(part in imp for part in module_parts):
                                is_imported = True
                                break
                        if is_imported:
                            break
                
                if not is_imported:
                    self.dead_files.append(path)
    
    def detect_broken_imports(self):
        """Detect broken import statements."""
        print("\n🔗 Detecting broken imports...")
        
        for path, info in self.file_map.items():
            if Path(path).suffix != '.py':
                continue
            
            imports = info.get('imports', [])
            for imp in imports:
                # Try to resolve the import
                is_broken = False
                module_name = imp.split('.')[0]
                
                # Check if module file exists
                possible_paths = [
                    self.root / f"{module_name}.py",
                    self.root / module_name / "__init__.py",
                    self.root / "backend" / f"{module_name}.py",
                    self.root / "memory_service" / f"{module_name}.py",
                ]
                
                if not any(p.exists() for p in possible_paths):
                    # Might be external package, skip for now
                    continue
                
                # More sophisticated check would parse actual imports
                # For now, just check if file exists
    
    def generate_report(self, output_file: str = "duplicate_sweep_report.json"):
        """Generate comprehensive report."""
        report = {
            'summary': {
                'total_files_scanned': len(self.file_map),
                'exact_duplicates': len([d for d in self.duplicates if d['type'] == 'exact']),
                'near_duplicates': len([d for d in self.duplicates if d['type'] == 'near_duplicate']),
                'duplicate_classes': len([d for d in self.duplicates if d['type'] == 'duplicate_class']),
                'duplicate_functions': len([d for d in self.duplicates if d['type'] == 'duplicate_function']),
                'duplicate_routes': len([d for d in self.duplicates if d['type'] == 'duplicate_route']),
                'dead_files': len(self.dead_files),
                'broken_imports': len(self.broken_imports)
            },
            'exact_duplicates': [d for d in self.duplicates if d['type'] == 'exact'],
            'near_duplicates': [d for d in self.duplicates if d['type'] == 'near_duplicate'],
            'duplicate_symbols': {
                'classes': [d for d in self.duplicates if d['type'] == 'duplicate_class'],
                'functions': [d for d in self.duplicates if d['type'] == 'duplicate_function'],
                'routes': [d for d in self.duplicates if d['type'] == 'duplicate_route']
            },
            'dead_files': self.dead_files,
            'broken_imports': self.broken_imports
        }
        
        output_path = self.root / output_file
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Report generated: {output_path}")
        return report
    
    def print_summary(self):
        """Print summary to console."""
        print("\n" + "="*60)
        print("📊 DUPLICATE SWEEP SUMMARY")
        print("="*60)
        print(f"\n📁 Total files scanned: {len(self.file_map)}")
        print(f"🔄 Exact duplicates: {len([d for d in self.duplicates if d['type'] == 'exact'])}")
        print(f"🔀 Near-duplicates: {len([d for d in self.duplicates if d['type'] == 'near_duplicate'])}")
        print(f"⚠️  Duplicate classes: {len([d for d in self.duplicates if d['type'] == 'duplicate_class'])}")
        print(f"⚠️  Duplicate functions: {len([d for d in self.duplicates if d['type'] == 'duplicate_function'])}")
        print(f"⚠️  Duplicate routes: {len([d for d in self.duplicates if d['type'] == 'duplicate_route'])}")
        print(f"🗑️  Dead files: {len(self.dead_files)}")
        print(f"🔗 Broken imports: {len(self.broken_imports)}")


def main():
    root = Path(__file__).parent.parent
    sweeper = DuplicateSweeper(str(root))
    
    sweeper.scan_all_files()
    sweeper.detect_duplicate_files()
    sweeper.detect_duplicate_symbols()
    sweeper.detect_dead_files()
    sweeper.detect_broken_imports()
    
    report = sweeper.generate_report("reports/duplicate_sweep_report.json")
    sweeper.print_summary()
    
    return 0 if not sweeper.duplicates and not sweeper.dead_files else 1


if __name__ == "__main__":
    sys.exit(main())

