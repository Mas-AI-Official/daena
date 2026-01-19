#!/usr/bin/env python3
"""
Daena Repository Inventory & Deduplication Tool
Scans entire repo to detect duplicates, conflicts, and dead code.
"""

import ast
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Exclude patterns
EXCLUDE_DIRS = {
    'venv', '__pycache__', '.git', 'node_modules', 
    'build', 'dist', '.pytest_cache', 'htmlcov',
    'wandb', 'models', 'trained_models', 'cache',
    'logs', 'backups', 'artifacts', 'xtts_temp'
}
EXCLUDE_FILES = {'.pyc', '.pyo', '.pyd', '.db', '.log', '.jsonl'}


class RepoInventory:
    def __init__(self, root_path: str = "."):
        self.root = Path(root_path).resolve()
        self.file_map: Dict[str, Dict] = {}
        self.class_map: Dict[str, List[Tuple[str, str]]] = defaultdict(list)  # class_name -> [(file_path, hash)]
        self.function_map: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        self.import_map: Dict[str, Set[str]] = defaultdict(set)  # module -> {importers}
        self.duplicates: List[Dict] = []
        self.conflicts: List[Dict] = []
        
    def scan_file(self, file_path: Path) -> Dict:
        """Scan a Python file and extract metadata."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Compute file hash
            file_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Parse AST
            try:
                tree = ast.parse(content)
            except SyntaxError:
                return {
                    'path': str(file_path.relative_to(self.root)),
                    'hash': file_hash,
                    'size': len(content),
                    'error': 'syntax_error'
                }
            
            # Extract classes and functions
            classes = []
            functions = []
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append({
                        'name': node.name,
                        'line': node.lineno,
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    })
                    # Register class
                    class_hash = hashlib.md5(f"{file_path}:{node.name}:{ast.dump(node)}".encode()).hexdigest()
                    self.class_map[node.name].append((str(file_path.relative_to(self.root)), class_hash))
                    
                elif isinstance(node, ast.FunctionDef):
                    if isinstance(node.parent if hasattr(node, 'parent') else None, ast.ClassDef):
                        continue  # Skip methods
                    functions.append({
                        'name': node.name,
                        'line': node.lineno,
                        'args': [arg.arg for arg in node.args.args]
                    })
                    func_hash = hashlib.md5(f"{file_path}:{node.name}:{ast.dump(node)}".encode()).hexdigest()
                    self.function_map[node.name].append((str(file_path.relative_to(self.root)), func_hash))
                    
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.append(node.module)
                            self.import_map[node.module].add(str(file_path.relative_to(self.root)))
                    else:
                        for alias in node.names:
                            imports.append(alias.name)
                            self.import_map[alias.name].add(str(file_path.relative_to(self.root)))
            
            return {
                'path': str(file_path.relative_to(self.root)),
                'hash': file_hash,
                'size': len(content),
                'classes': classes,
                'functions': functions,
                'imports': imports,
                'lines': len(content.splitlines())
            }
            
        except Exception as e:
            return {
                'path': str(file_path.relative_to(self.root)),
                'error': str(e)
            }
    
    def scan_repo(self):
        """Scan entire repository."""
        print(f"🔍 Scanning repository: {self.root}")
        
        python_files = []
        for path in self.root.rglob("*.py"):
            # Skip excluded directories
            if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
                continue
            
            if any(path.suffix == ext for ext in EXCLUDE_FILES):
                continue
                
            python_files.append(path)
        
        print(f"📁 Found {len(python_files)} Python files")
        
        for i, file_path in enumerate(python_files, 1):
            if i % 50 == 0:
                print(f"   Progress: {i}/{len(python_files)}")
            file_info = self.scan_file(file_path)
            self.file_map[file_info['path']] = file_info
    
    def detect_duplicates(self):
        """Detect duplicate files and classes."""
        print("\n🔎 Detecting duplicates...")
        
        # Duplicate files (same hash)
        hash_map: Dict[str, List[str]] = defaultdict(list)
        for path, info in self.file_map.items():
            if 'hash' in info:
                hash_map[info['hash']].append(path)
        
        for file_hash, paths in hash_map.items():
            if len(paths) > 1:
                self.duplicates.append({
                    'type': 'file',
                    'hash': file_hash,
                    'files': paths,
                    'size': self.file_map[paths[0]].get('size', 0)
                })
        
        # Duplicate classes (same name, different implementations)
        for class_name, occurrences in self.class_map.items():
            if len(occurrences) > 1:
                # Check if they're actually different
                hashes = set(hash for _, hash in occurrences)
                if len(hashes) > 1:
                    self.conflicts.append({
                        'type': 'class',
                        'name': class_name,
                        'locations': [path for path, _ in occurrences],
                        'unique_implementations': len(hashes)
                    })
        
        # Duplicate functions (same name, different implementations)
        for func_name, occurrences in self.function_map.items():
            if len(occurrences) > 1:
                hashes = set(hash for _, hash in occurrences)
                if len(hashes) > 1:
                    # Only report if in different files
                    files = set(path for path, _ in occurrences)
                    if len(files) > 1:
                        self.conflicts.append({
                            'type': 'function',
                            'name': func_name,
                            'locations': list(files),
                            'unique_implementations': len(hashes)
                        })
    
    def detect_dead_files(self) -> List[str]:
        """Detect files that aren't imported anywhere."""
        print("\n🗑️  Detecting potentially dead files...")
        
        dead_files = []
        for path, info in self.file_map.items():
            # Skip test files, scripts, main files
            if any(x in path for x in ['test_', 'tests/', 'Tools/', 'scripts/', 'main.py', '__init__.py']):
                continue
            
            # Convert file path to module name
            module_parts = path.replace('/', '.').replace('\\', '.').replace('.py', '').split('.')
            module_name = '.'.join(module_parts)
            
            # Check if this module is imported anywhere
            if module_name not in self.import_map:
                # Also check without last part (package imports)
                parent_module = '.'.join(module_parts[:-1]) if len(module_parts) > 1 else None
                if not parent_module or parent_module not in self.import_map:
                    dead_files.append(path)
        
        return dead_files
    
    def generate_report(self, output_path: str = "inventory_report.json"):
        """Generate comprehensive inventory report."""
        report = {
            'summary': {
                'total_files': len(self.file_map),
                'duplicate_files': len([d for d in self.duplicates if d['type'] == 'file']),
                'conflicting_classes': len([c for c in self.conflicts if c['type'] == 'class']),
                'conflicting_functions': len([c for c in self.conflicts if c['type'] == 'function']),
            },
            'duplicates': self.duplicates,
            'conflicts': self.conflicts,
            'dead_files': self.detect_dead_files(),
            'import_graph': {k: list(v) for k, v in self.import_map.items()}
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n✅ Report generated: {output_path}")
        return report
    
    def print_summary(self):
        """Print summary to console."""
        print("\n" + "="*60)
        print("📊 REPOSITORY INVENTORY SUMMARY")
        print("="*60)
        
        print(f"\n📁 Total Files Scanned: {len(self.file_map)}")
        print(f"🔄 Duplicate Files: {len([d for d in self.duplicates if d['type'] == 'file'])}")
        print(f"⚠️  Conflicting Classes: {len([c for c in self.conflicts if c['type'] == 'class'])}")
        print(f"⚠️  Conflicting Functions: {len([c for c in self.conflicts if c['type'] == 'function'])}")
        
        if self.duplicates:
            print("\n🔄 DUPLICATE FILES:")
            for dup in self.duplicates[:10]:  # Show first 10
                if dup['type'] == 'file':
                    print(f"   Hash: {dup['hash'][:8]}...")
                    for file in dup['files']:
                        print(f"      - {file}")
        
        if self.conflicts:
            print("\n⚠️  CONFLICTS:")
            for conflict in self.conflicts[:10]:  # Show first 10
                print(f"   {conflict['type'].upper()}: {conflict['name']}")
                print(f"      Locations: {', '.join(conflict['locations'])}")
                print(f"      Unique implementations: {conflict['unique_implementations']}")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    inventory = RepoInventory(root)
    
    inventory.scan_repo()
    inventory.detect_duplicates()
    inventory.print_summary()
    
    report = inventory.generate_report("inventory_report.json")
    
    # Generate conflict matrix
    print("\n📋 Generating conflict matrix...")
    conflict_matrix = []
    for conflict in inventory.conflicts:
        conflict_matrix.append({
            'name': conflict['name'],
            'type': conflict['type'],
            'files': conflict['locations'],
            'recommendation': 'keep_newest'  # TODO: Implement logic to choose which to keep
        })
    
    with open("conflict_matrix.json", 'w') as f:
        json.dump(conflict_matrix, f, indent=2)
    
    print("✅ Conflict matrix generated: conflict_matrix.json")


if __name__ == "__main__":
    main()

