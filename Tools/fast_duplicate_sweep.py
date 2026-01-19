#!/usr/bin/env python3
"""
Fast Duplicate Sweep - Focused on critical areas
Quick scan for duplicates in memory_service, backend, and docs
"""

import json
import os
from pathlib import Path
from collections import defaultdict
import hashlib

EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'node_modules', 'Daena_Clean_Backup', 
                'Constraction AI', 'mas-ai', 'daena-website', 'xtts_temp'}

def file_hash(path):
    try:
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return ""

def find_duplicates():
    root = Path(__file__).parent.parent
    hash_map = defaultdict(list)
    name_map = defaultdict(list)
    
    # Focus on key areas
    target_dirs = ['memory_service', 'backend', 'docs', 'Tools']
    
    for target in target_dirs:
        target_path = root / target
        if not target_path.exists():
            continue
            
        for file_path in target_path.rglob('*'):
            if file_path.is_file():
                # Skip excluded
                if any(ex in str(file_path) for ex in EXCLUDE_DIRS):
                    continue
                    
                if file_path.suffix in ['.py', '.md']:
                    rel_path = str(file_path.relative_to(root))
                    file_hash_val = file_hash(file_path)
                    file_name = file_path.name.lower()
                    
                    if file_hash_val:
                        hash_map[file_hash_val].append(rel_path)
                    name_map[file_name].append(rel_path)
    
    # Find exact duplicates (same hash)
    exact_dupes = {h: paths for h, paths in hash_map.items() if len(paths) > 1}
    
    # Find same-name files
    name_dupes = {n: paths for n, paths in name_map.items() if len(paths) > 1}
    
    return exact_dupes, name_dupes

def find_complete_files():
    """Find all *COMPLETE*.md files"""
    root = Path(__file__).parent.parent
    complete_files = []
    
    for md_file in root.rglob('*COMPLETE*.md'):
        if any(ex in str(md_file) for ex in EXCLUDE_DIRS):
            continue
        complete_files.append(str(md_file.relative_to(root)))
    
    return sorted(complete_files)

def find_summary_files():
    """Find all *SUMMARY*.md files"""
    root = Path(__file__).parent.parent
    summary_files = []
    
    for md_file in root.rglob('*SUMMARY*.md'):
        if any(ex in str(md_file) for ex in EXCLUDE_DIRS):
            continue
        summary_files.append(str(md_file.relative_to(root)))
    
    return sorted(summary_files)

def find_status_files():
    """Find all *STATUS*.md files"""
    root = Path(__file__).parent.parent
    status_files = []
    
    for md_file in root.rglob('*STATUS*.md'):
        if any(ex in str(md_file) for ex in EXCLUDE_DIRS):
            continue
        status_files.append(str(md_file.relative_to(root)))
    
    return sorted(status_files)

if __name__ == "__main__":
    import sys
    
    # Check if running as pre-commit hook
    is_pre_commit = "--pre-commit" in sys.argv
    
    if not is_pre_commit:
        print("🔍 Fast Duplicate Sweep...")
    
    exact_dupes, name_dupes = find_duplicates()
    complete_files = find_complete_files()
    summary_files = find_summary_files()
    status_files = find_status_files()
    
    # Pre-commit mode: exit with error if duplicates found
    if is_pre_commit:
        if exact_dupes:
            print(f"\n❌ ERROR: Found {len(exact_dupes)} exact duplicate files. Please resolve before committing.")
            for hash_val, paths in list(exact_dupes.items())[:5]:  # Show first 5
                print(f"  Duplicate: {paths[0]} == {paths[1]}")
            sys.exit(1)
        else:
            print("✅ No duplicate files detected.")
            sys.exit(0)
    
    # Normal mode: save report and print results
    report = {
        'exact_duplicates': exact_dupes,
        'same_name_files': name_dupes,
        'complete_files': complete_files,
        'summary_files': summary_files,
        'status_files': status_files
    }
    
    output = Path(__file__).parent.parent / 'reports' / 'fast_duplicate_report.json'
    output.parent.mkdir(exist_ok=True)
    
    with open(output, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✅ Report: {output}")
    print(f"📄 Exact duplicates: {len(exact_dupes)}")
    print(f"📄 Same-name files: {len(name_dupes)}")
    print(f"📄 *COMPLETE*.md files: {len(complete_files)}")
    print(f"📄 *SUMMARY*.md files: {len(summary_files)}")
    print(f"📄 *STATUS*.md files: {len(status_files)}")

