"""
Code Scanner Tool for Daena AI VP

Gives Daena the ability to read and analyze the codebase.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


def scan_file(path: str, max_lines: int = 500) -> Dict[str, Any]:
    """
    Read a file and return its contents.
    
    Args:
        path: Relative or absolute path to file
        max_lines: Maximum lines to return (default 500)
    
    Returns:
        {success, content, line_count, truncated, error}
    """
    try:
        # Handle relative paths
        if not os.path.isabs(path):
            full_path = PROJECT_ROOT / path
        else:
            full_path = Path(path)
        
        # Security: ensure path is within project
        if not str(full_path.resolve()).startswith(str(PROJECT_ROOT.resolve())):
            return {"success": False, "error": "Access denied: path outside project"}
        
        if not full_path.exists():
            return {"success": False, "error": f"File not found: {path}"}
        
        if not full_path.is_file():
            return {"success": False, "error": f"Not a file: {path}"}
        
        content = full_path.read_text(encoding='utf-8', errors='replace')
        lines = content.split('\n')
        truncated = len(lines) > max_lines
        
        if truncated:
            lines = lines[:max_lines]
            content = '\n'.join(lines) + '\n... (truncated)'
        
        return {
            "success": True,
            "content": content,
            "line_count": len(lines),
            "truncated": truncated,
            "path": str(full_path.relative_to(PROJECT_ROOT))
        }
    except Exception as e:
        logger.error(f"scan_file error: {e}")
        return {"success": False, "error": str(e)}


def search_code(query: str, file_pattern: str = "*.py", max_results: int = 50) -> Dict[str, Any]:
    """
    Search codebase for a pattern.
    
    Args:
        query: Text or regex pattern to search
        file_pattern: Glob pattern for files (default *.py)
        max_results: Maximum matches to return
    
    Returns:
        {success, matches, total_found, error}
    """
    try:
        matches = []
        total_found = 0
        
        for file_path in PROJECT_ROOT.rglob(file_pattern):
            # Skip venv, node_modules, etc.
            skip_dirs = ['venv', 'node_modules', '__pycache__', '.git', 'local_brain']
            if any(d in str(file_path) for d in skip_dirs):
                continue
            
            try:
                content = file_path.read_text(encoding='utf-8', errors='replace')
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    if query.lower() in line.lower():
                        total_found += 1
                        if len(matches) < max_results:
                            matches.append({
                                "file": str(file_path.relative_to(PROJECT_ROOT)),
                                "line": line_num,
                                "content": line.strip()[:200]
                            })
            except:
                continue
        
        return {
            "success": True,
            "matches": matches,
            "total_found": total_found,
            "truncated": total_found > max_results
        }
    except Exception as e:
        logger.error(f"search_code error: {e}")
        return {"success": False, "error": str(e)}


def analyze_structure(path: str = ".") -> Dict[str, Any]:
    """
    Analyze the structure of a directory.
    
    Returns file counts, types, and key files.
    """
    try:
        if not os.path.isabs(path):
            full_path = PROJECT_ROOT / path
        else:
            full_path = Path(path)
        
        if not full_path.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        
        stats = {
            "total_files": 0,
            "total_dirs": 0,
            "by_extension": {},
            "key_files": [],
            "directories": []
        }
        
        key_file_names = ['main.py', 'app.py', 'index.html', 'package.json', 'requirements.txt', 'README.md']
        
        for item in full_path.iterdir():
            if item.name.startswith('.'):
                continue
            
            if item.is_dir():
                stats["total_dirs"] += 1
                if item.name not in ['venv', 'node_modules', '__pycache__', 'local_brain']:
                    stats["directories"].append(item.name)
            elif item.is_file():
                stats["total_files"] += 1
                ext = item.suffix or 'no_ext'
                stats["by_extension"][ext] = stats["by_extension"].get(ext, 0) + 1
                
                if item.name in key_file_names:
                    stats["key_files"].append(item.name)
        
        return {"success": True, **stats}
    except Exception as e:
        logger.error(f"analyze_structure error: {e}")
        return {"success": False, "error": str(e)}


def list_directory(path: str = ".", include_hidden: bool = False) -> Dict[str, Any]:
    """
    List contents of a directory.
    
    Returns:
        {success, files, directories, error}
    """
    try:
        if not os.path.isabs(path):
            full_path = PROJECT_ROOT / path
        else:
            full_path = Path(path)
        
        if not full_path.exists():
            return {"success": False, "error": f"Path not found: {path}"}
        
        if not full_path.is_dir():
            return {"success": False, "error": f"Not a directory: {path}"}
        
        files = []
        directories = []
        
        for item in sorted(full_path.iterdir()):
            if not include_hidden and item.name.startswith('.'):
                continue
            
            if item.is_dir():
                directories.append({
                    "name": item.name,
                    "type": "directory"
                })
            else:
                files.append({
                    "name": item.name,
                    "type": "file",
                    "size": item.stat().st_size
                })
        
        return {
            "success": True,
            "path": str(full_path.relative_to(PROJECT_ROOT)),
            "directories": directories,
            "files": files
        }
    except Exception as e:
        logger.error(f"list_directory error: {e}")
        return {"success": False, "error": str(e)}


# Convenience function for Daena
async def daena_scan(command: str) -> Dict[str, Any]:
    """
    Parse a natural language scan command and execute appropriate tool.
    
    Examples:
        "scan backend/routes/daena.py"
        "search for getChatHistory"
        "list backend/routes"
        "analyze backend structure"
    """
    command = command.lower().strip()
    
    if command.startswith("scan "):
        path = command[5:].strip()
        return scan_file(path)
    
    elif command.startswith("search ") or command.startswith("find "):
        query = command.split(" ", 1)[1].strip()
        # Remove quotes if present
        query = query.strip('"\'')
        return search_code(query)
    
    elif command.startswith("list ") or command.startswith("ls "):
        path = command.split(" ", 1)[1].strip() if " " in command else "."
        return list_directory(path)
    
    elif "analyze" in command or "structure" in command:
        path = "."
        parts = command.split()
        for p in parts:
            if "/" in p or p.startswith("backend") or p.startswith("frontend"):
                path = p
                break
        return analyze_structure(path)
    
    else:
        return {
            "success": False,
            "error": "Unknown command. Try: scan <file>, search <query>, list <dir>, or analyze <dir>"
        }
