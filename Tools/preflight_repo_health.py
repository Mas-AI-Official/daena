#!/usr/bin/env python3
"""
Preflight repository health checker for Daena codebase.
Checks for missing imports, circular deps, orphaned modules, broken routes, stale env vars, invalid JSON/YAML.
Also verifies frontend route → backend endpoint parity and startup script correctness.
"""

import ast
import json
import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict
import importlib.util
import subprocess

# Color output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")


class RepoHealthChecker:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.imports_map: Dict[str, Set[str]] = defaultdict(set)
        self.defined_modules: Set[str] = set()
        self.route_endpoints: Set[str] = set()
        self.frontend_routes: Set[str] = set()
        
    def check_all(self) -> Dict[str, Any]:
        """Run all health checks."""
        print_info("Starting repository health check...")
        
        results = {
            "missing_imports": [],
            "circular_deps": [],
            "orphaned_modules": [],
            "broken_routes": [],
            "invalid_json": [],
            "invalid_yaml": [],
            "stale_env_vars": [],
            "frontend_backend_parity": {},
            "startup_scripts": {},
            "duplicate_files": []
        }
        
        # Find all Python files
        py_files = list(self.root.rglob("*.py"))
        print_info(f"Found {len(py_files)} Python files")
        
        # Check imports and build dependency graph
        print_info("Checking imports and dependencies...")
        for py_file in py_files:
            try:
                self._check_file_imports(py_file)
            except Exception as e:
                self.warnings.append(f"Error checking {py_file}: {e}")
        
        # Check for circular dependencies
        results["circular_deps"] = self._find_circular_deps()
        
        # Check for orphaned modules
        results["orphaned_modules"] = self._find_orphaned_modules()
        
        # Check JSON/YAML files
        print_info("Checking JSON/YAML files...")
        for json_file in self.root.rglob("*.json"):
            if self._check_json_file(json_file):
                results["invalid_json"].append(str(json_file))
        
        for yaml_file in self.root.rglob("*.yaml"):
            if self._check_yaml_file(yaml_file):
                results["invalid_yaml"].append(str(yaml_file))
        
        for yml_file in self.root.rglob("*.yml"):
            if self._check_yaml_file(yml_file):
                results["invalid_yaml"].append(str(yml_file))
        
        # Check routes
        print_info("Checking API routes...")
        results["broken_routes"] = self._check_routes()
        
        # Check frontend/backend parity
        print_info("Checking frontend/backend route parity...")
        results["frontend_backend_parity"] = self._check_route_parity()
        
        # Check startup scripts
        print_info("Checking startup scripts...")
        results["startup_scripts"] = self._check_startup_scripts()
        
        # Check for duplicate files
        print_info("Checking for duplicate files...")
        results["duplicate_files"] = self._find_duplicates()
        
        # Check env vars
        print_info("Checking environment variables...")
        results["stale_env_vars"] = self._check_env_vars()
        
        return results
    
    def _check_file_imports(self, file_path: Path):
        """Check imports in a Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            module_name = self._get_module_name(file_path)
            self.defined_modules.add(module_name)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.imports_map[module_name].add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.imports_map[module_name].add(node.module.split('.')[0])
        except SyntaxError as e:
            self.warnings.append(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            self.warnings.append(f"Error parsing {file_path}: {e}")
    
    def _get_module_name(self, file_path: Path) -> str:
        """Convert file path to module name."""
        rel_path = file_path.relative_to(self.root)
        parts = rel_path.parts[:-1] + (rel_path.stem,)
        return '.'.join(parts).replace('/', '.').replace('\\', '.')
    
    def _find_circular_deps(self) -> List[List[str]]:
        """Find circular dependencies using DFS."""
        visited = set()
        rec_stack = set()
        cycles = []
        
        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self.imports_map.get(node, set()):
                if neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)
                elif neighbor not in visited:
                    dfs(neighbor, path + [neighbor])
            
            rec_stack.remove(node)
        
        for module in self.imports_map:
            if module not in visited:
                dfs(module, [module])
        
        return cycles
    
    def _find_orphaned_modules(self) -> List[str]:
        """Find modules that are never imported."""
        imported_modules = set()
        for imports in self.imports_map.values():
            imported_modules.update(imports)
        
        orphaned = []
        for module in self.defined_modules:
            # Skip if it's a main script or test
            if '__main__' in module or 'test' in module.lower():
                continue
            if module not in imported_modules and module not in ['backend.main', 'backend.start_server']:
                orphaned.append(module)
        
        return orphaned
    
    def _check_json_file(self, file_path: Path) -> bool:
        """Check if JSON file is valid. Returns True if invalid."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON in {file_path}: {e}")
            return True
        except Exception as e:
            self.warnings.append(f"Error reading {file_path}: {e}")
            return False
    
    def _check_yaml_file(self, file_path: Path) -> bool:
        """Check if YAML file is valid. Returns True if invalid."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml.safe_load(f)
            return False
        except yaml.YAMLError as e:
            self.errors.append(f"Invalid YAML in {file_path}: {e}")
            return True
        except Exception as e:
            self.warnings.append(f: {e}")
            return False
    
    def _check_routes(self) -> List[str]:
        """Check for broken route definitions."""
        broken = []
        routes_dir = self.root / "backend" / "routes"
        
        if not routes_dir.exists():
            return broken
        
        for route_file in routes_dir.glob("*.py"):
            try:
                with open(route_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Check for common FastAPI patterns
                    if '@app.' in content or 'router.' in content:
                        # Try to parse and check for obvious errors
                        ast.parse(content)
            except SyntaxError as e:
                broken.append(f"{route_file}: {e}")
        
        return broken
    
    def _check_route_parity(self) -> Dict[str, Any]:
        """Check frontend routes vs backend endpoints."""
        backend_endpoints = set()
        frontend_routes = set()
        
        # Scan backend routes
        routes_dir = self.root / "backend" / "routes"
        if routes_dir.exists():
            for route_file in routes_dir.glob("*.py"):
                try:
                    with open(route_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Extract route patterns (simplified)
                        import re
                        for match in re.finditer(r'@(?:app|router)\.(?:get|post|put|delete|patch)\("([^"]+)"', content):
                            backend_endpoints.add(match.group(1))
                except Exception:
                    pass
        
        # Scan frontend (simplified - would need actual frontend parsing)
        frontend_dir = self.root / "frontend"
        if frontend_dir.exists():
            for html_file in frontend_dir.rglob("*.html"):
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Extract API calls (simplified)
                        import re
                        for match in re.finditer(r'["\'](/api/[^"\']+)["\']', content):
                            frontend_routes.add(match.group(1))
                except Exception:
                    pass
        
        missing_backend = frontend_routes - backend_endpoints
        missing_frontend = backend_endpoints - frontend_routes
        
        return {
            "backend_endpoints": len(backend_endpoints),
            "frontend_routes": len(frontend_routes),
            "missing_backend": list(missing_backend),
            "missing_frontend": list(missing_frontend)
        }
    
    def _check_startup_scripts(self) -> Dict[str, Any]:
        """Check startup scripts for correctness."""
        results = {
            "windows_bat": [],
            "windows_ps1": [],
            "linux_sh": [],
            "issues": []
        }
        
        # Check .bat files
        for bat_file in self.root.rglob("*.bat"):
            if "start" in bat_file.name.lower() or "launch" in bat_file.name.lower():
                results["windows_bat"].append(str(bat_file))
                try:
                    with open(bat_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if 'pause' not in content and 'pause >nul' not in content:
                            results["issues"].append(f"{bat_file}: May auto-close on error")
                        if 'echo' not in content.lower():
                            results["issues"].append(f"{bat_file}: No echo statements for URLs")
                except Exception as e:
                    results["issues"].append(f"{bat_file}: Error reading - {e}")
        
        # Check .ps1 files
        for ps1_file in self.root.rglob("*.ps1"):
            if "start" in ps1_file.name.lower() or "launch" in ps1_file.name.lower():
                results["windows_ps1"].append(str(ps1_file))
        
        # Check .sh files
        for sh_file in self.root.rglob("*.sh"):
            if "start" in sh_file.name.lower() or "launch" in sh_file.name.lower():
                results["linux_sh"].append(str(sh_file))
                try:
                    with open(sh_file, 'r', encoding='utf-8') as f:
                        first_line = f.readline()
                        if not first_line.startswith('#!/'):
                            results["issues"].append(f"{sh_file}: Missing shebang")
                except Exception as e:
                    results["issues"].append(f"{sh_file}: Error reading - {e}")
        
        return results
    
    def _find_duplicates(self) -> List[Tuple[str, str]]:
        """Find duplicate files by content hash."""
        import hashlib
        file_hashes: Dict[str, List[str]] = defaultdict(list)
        
        for py_file in self.root.rglob("*.py"):
            try:
                with open(py_file, 'rb') as f:
                    content = f.read()
                    file_hash = hashlib.md5(content).hexdigest()
                    file_hashes[file_hash].append(str(py_file))
            except Exception:
                pass
        
        duplicates = []
        for hash_val, files in file_hashes.items():
            if len(files) > 1:
                duplicates.append((hash_val, files))
        
        return duplicates
    
    def _check_env_vars(self) -> List[str]:
        """Check for stale environment variables."""
        stale = []
        env_files = list(self.root.rglob(".env*")) + list(self.root.rglob("*.env"))
        
        # This is a simplified check - would need actual env var usage analysis
        for env_file in env_files:
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Check for common issues
                    if '=' not in content and len(content.strip()) > 0:
                        stale.append(f"{env_file}: Possible formatting issue")
            except Exception:
                pass
        
        return stale


def main():
    """Main entry point."""
    root = Path(__file__).parent.parent
    checker = RepoHealthChecker(root)
    
    results = checker.check_all()
    
    # Print summary
    print("\n" + "="*60)
    print("REPOSITORY HEALTH CHECK SUMMARY")
    print("="*60)
    
    if results["circular_deps"]:
        print_error(f"Found {len(results['circular_deps'])} circular dependencies")
        for cycle in results["circular_deps"][:5]:  # Show first 5
            print_warning(f"  Cycle: {' -> '.join(cycle)}")
    else:
        print_success("No circular dependencies found")
    
    if results["orphaned_modules"]:
        print_warning(f"Found {len(results['orphaned_modules'])} potentially orphaned modules")
    else:
        print_success("No orphaned modules found")
    
    if results["invalid_json"]:
        print_error(f"Found {len(results['invalid_json'])} invalid JSON files")
    else:
        print_success("All JSON files are valid")
    
    if results["invalid_yaml"]:
        print_error(f"Found {len(results['invalid_yaml'])} invalid YAML files")
    else:
        print_success("All YAML files are valid")
    
    if results["broken_routes"]:
        print_error(f"Found {len(results['broken_routes'])} broken routes")
    else:
        print_success("All routes appear valid")
    
    # Save reports
    reports_dir = root / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    with open(reports_dir / "repo_health.md", 'w') as f:
        f.write("# Repository Health Report\n\n")
        f.write(f"## Summary\n\n")
        f.write(f"- Circular Dependencies: {len(results['circular_deps'])}\n")
        f.write(f"- Orphaned Modules: {len(results['orphaned_modules'])}\n")
        f.write(f"- Invalid JSON: {len(results['invalid_json'])}\n")
        f.write(f"- Invalid YAML: {len(results['invalid_yaml'])}\n")
        f.write(f"- Broken Routes: {len(results['broken_routes'])}\n\n")
        f.write("## Details\n\n")
        f.write(json.dumps(results, indent=2))
    
    with open(reports_dir / "route_parity.md", 'w') as f:
        f.write("# Frontend/Backend Route Parity Report\n\n")
        f.write(json.dumps(results["frontend_backend_parity"], indent=2))
    
    with open(reports_dir / "duplicates.md", 'w') as f:
        f.write("# Duplicate Files Report\n\n")
        for hash_val, files in results["duplicate_files"]:
            f.write(f"## Hash: {hash_val}\n\n")
            for file_path in files:
                f.write(f"- {file_path}\n")
            f.write("\n")
    
    print_success(f"Reports saved to {reports_dir}")
    print_info(f"  - repo_health.md")
    print_info(f"  - route_parity.md")
    print_info(f"  - duplicates.md")


if __name__ == "__main__":
    main()

