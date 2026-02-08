"""
IDE API endpoints - Code Intelligence and Workspace Management.
Provides endpoints for file operations, code execution, and terminal commands.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import os
import subprocess
import shutil
import json
import logging

from backend.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/ide", tags=["IDE"])
logger = logging.getLogger(__name__)

# Workspace configuration
WORKSPACE_ROOT = Path(os.getenv('DAENA_WORKSPACE', './workspace'))

# Initialize workspace if it doesn't exist
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


# ==================== Models ====================

class CreateFileRequest(BaseModel):
    path: str
    content: str = ""

class SaveFileRequest(BaseModel):
    content: str

class ExecuteCodeRequest(BaseModel):
    code: str
    language: str = "python"
    timeout: int = 30

class TerminalCommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None


# ==================== File Operations ====================

@router.post("/files")
async def create_file(
    request: CreateFileRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new file in the workspace."""
    try:
        # Security check for role
        user_role = current_user.get("role", "user")
        if user_role not in ["founder", "daena_vp", "admin"]:
            raise HTTPException(403, "Only Founder/Admin can modify workspace")
        
        file_path = WORKSPACE_ROOT / request.path
        
        # Security: prevent directory traversal
        if not str(file_path.resolve()).startswith(str(WORKSPACE_ROOT.resolve())):
            raise HTTPException(403, "Access denied: path outside workspace")
        
        # Create parent directories
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        logger.info(f"File created: {request.path} by {current_user.get('username', 'unknown')}")
        
        return {
            'success': True,
            'path': request.path,
            'message': 'File created successfully',
            'size': len(request.content)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating file: {e}")
        raise HTTPException(500, f"Failed to create file: {str(e)}")


@router.get("/files/{path:path}")
async def read_file(
    path: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Read file contents from workspace."""
    try:
        file_path = WORKSPACE_ROOT / path
        
        # Security: prevent directory traversal
        if not str(file_path.resolve()).startswith(str(WORKSPACE_ROOT.resolve())):
            raise HTTPException(403, "Access denied: path outside workspace")
        
        if not file_path.exists():
            raise HTTPException(404, "File not found")
        
        if not file_path.is_file():
            raise HTTPException(400, "Path is not a file")
        
        # Check file size (limit to 1MB for text files)
        if file_path.stat().st_size > 1_000_000:
            raise HTTPException(400, "File too large (max 1MB)")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Detect language from extension
        ext = file_path.suffix.lower()
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.json': 'json',
            '.html': 'html',
            '.css': 'css',
            '.md': 'markdown',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.sql': 'sql',
            '.sh': 'bash',
            '.bat': 'batch'
        }
        
        return {
            'success': True,
            'path': path,
            'content': content,
            'language': language_map.get(ext, 'text'),
            'size': len(content),
            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
        }
    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(400, "Cannot read binary file")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(500, f"Failed to read file: {str(e)}")


@router.put("/files/{path:path}")
async def save_file(
    path: str,
    request: SaveFileRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Save/update file contents."""
    try:
        user_role = current_user.get("role", "user")
        if user_role not in ["founder", "daena_vp", "admin"]:
            raise HTTPException(403, "Only Founder/Admin can modify workspace")
        
        file_path = WORKSPACE_ROOT / path
        
        # Security: prevent directory traversal
        if not str(file_path.resolve()).startswith(str(WORKSPACE_ROOT.resolve())):
            raise HTTPException(403, "Access denied: path outside workspace")
        
        # Create backup if file exists
        if file_path.exists():
            backup_path = file_path.with_suffix(f'.bak.{int(datetime.now().timestamp())}')
            shutil.copy(file_path, backup_path)
        else:
            # Create parent directories if file doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        logger.info(f"File saved: {path} by {current_user.get('username', 'unknown')}")
        
        return {
            'success': True,
            'path': path,
            'message': 'File saved successfully',
            'size': len(request.content)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(500, f"Failed to save file: {str(e)}")


@router.delete("/files/{path:path}")
async def delete_file(
    path: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Delete a file from workspace."""
    try:
        user_role = current_user.get("role", "user")
        if user_role not in ["founder", "daena_vp", "admin"]:
            raise HTTPException(403, "Only Founder/Admin can modify workspace")
        
        file_path = WORKSPACE_ROOT / path
        
        # Security: prevent directory traversal
        if not str(file_path.resolve()).startswith(str(WORKSPACE_ROOT.resolve())):
            raise HTTPException(403, "Access denied: path outside workspace")
        
        if not file_path.exists():
            raise HTTPException(404, "File not found")
        
        if file_path.is_dir():
            shutil.rmtree(file_path)
        else:
            file_path.unlink()
        
        logger.info(f"File deleted: {path} by {current_user.get('username', 'unknown')}")
        
        return {
            'success': True,
            'path': path,
            'message': 'File deleted successfully'
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(500, f"Failed to delete file: {str(e)}")


# ==================== File Tree ====================

@router.get("/tree")
async def get_file_tree(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get workspace file tree structure."""
    try:
        def build_tree(directory: Path, prefix: str = "") -> List[Dict[str, Any]]:
            items = []
            try:
                entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
                for entry in entries:
                    # Skip hidden files and common build directories
                    if entry.name.startswith('.') or entry.name in ['node_modules', '__pycache__', 'venv', '.git']:
                        continue
                    
                    rel_path = str(entry.relative_to(WORKSPACE_ROOT))
                    item = {
                        'name': entry.name,
                        'path': rel_path,
                        'type': 'directory' if entry.is_dir() else 'file'
                    }
                    
                    if entry.is_file():
                        item['size'] = entry.stat().st_size
                        item['extension'] = entry.suffix
                    elif entry.is_dir():
                        item['children'] = build_tree(entry, prefix + "  ")
                    
                    items.append(item)
            except PermissionError:
                pass
            return items
        
        tree = build_tree(WORKSPACE_ROOT)
        
        return {
            'success': True,
            'root': str(WORKSPACE_ROOT),
            'tree': tree
        }
    except Exception as e:
        logger.error(f"Error building file tree: {e}")
        raise HTTPException(500, f"Failed to get file tree: {str(e)}")


# ==================== Code Execution ====================

@router.post("/execute")
async def execute_code(
    request: ExecuteCodeRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Execute code in a sandboxed environment."""
    try:
        user_role = current_user.get("role", "user")
        if user_role not in ["founder", "daena_vp"]:
            raise HTTPException(403, "Only Founder can execute code")
        
        # Whitelist of allowed languages
        allowed_languages = ['python', 'javascript', 'typescript', 'bash']
        if request.language not in allowed_languages:
            raise HTTPException(400, f"Language '{request.language}' not supported. Allowed: {allowed_languages}")
        
        # Create temp directory for execution
        temp_dir = WORKSPACE_ROOT / '.tmp'
        temp_dir.mkdir(exist_ok=True)
        
        timestamp = int(datetime.now().timestamp())
        user_id = current_user.get('id', 'unknown')
        
        result = {
            'success': False,
            'stdout': '',
            'stderr': '',
            'returncode': -1,
            'execution_time_ms': 0
        }
        
        import time
        start_time = time.time()
        
        if request.language == 'python':
            temp_file = temp_dir / f'exec_{user_id}_{timestamp}.py'
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(request.code)
                
                proc = subprocess.run(
                    ['python', str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=request.timeout,
                    cwd=str(WORKSPACE_ROOT)
                )
                
                result = {
                    'success': proc.returncode == 0,
                    'stdout': proc.stdout,
                    'stderr': proc.stderr,
                    'returncode': proc.returncode,
                    'execution_time_ms': int((time.time() - start_time) * 1000)
                }
            except subprocess.TimeoutExpired:
                result = {
                    'success': False,
                    'stdout': '',
                    'stderr': f'Execution timeout ({request.timeout}s)',
                    'returncode': -1,
                    'execution_time_ms': request.timeout * 1000
                }
            finally:
                if temp_file.exists():
                    temp_file.unlink()
        
        elif request.language in ['javascript', 'typescript']:
            # For JS/TS, use node
            ext = '.js' if request.language == 'javascript' else '.ts'
            temp_file = temp_dir / f'exec_{user_id}_{timestamp}{ext}'
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(request.code)
                
                cmd = ['node'] if request.language == 'javascript' else ['npx', 'tsx']
                proc = subprocess.run(
                    cmd + [str(temp_file)],
                    capture_output=True,
                    text=True,
                    timeout=request.timeout,
                    cwd=str(WORKSPACE_ROOT)
                )
                
                result = {
                    'success': proc.returncode == 0,
                    'stdout': proc.stdout,
                    'stderr': proc.stderr,
                    'returncode': proc.returncode,
                    'execution_time_ms': int((time.time() - start_time) * 1000)
                }
            except subprocess.TimeoutExpired:
                result = {
                    'success': False,
                    'stdout': '',
                    'stderr': f'Execution timeout ({request.timeout}s)',
                    'returncode': -1,
                    'execution_time_ms': request.timeout * 1000
                }
            finally:
                if temp_file.exists():
                    temp_file.unlink()
        
        logger.info(f"Code executed ({request.language}) by {current_user.get('username', 'unknown')}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        raise HTTPException(500, f"Execution failed: {str(e)}")


# ==================== Terminal Commands ====================

@router.post("/terminal")
async def run_terminal_command(
    request: TerminalCommandRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Run a whitelisted terminal command."""
    try:
        user_role = current_user.get("role", "user")
        if user_role not in ["founder", "daena_vp"]:
            raise HTTPException(403, "Only Founder can run terminal commands")
        
        # Whitelist of allowed commands
        allowed_commands = [
            'ls', 'dir', 'pwd', 'cat', 'echo', 'type',
            'git', 'npm', 'pip', 'python', 'node',
            'cd', 'mkdir', 'touch', 'cp', 'mv',
            'head', 'tail', 'grep', 'find', 'tree'
        ]
        
        cmd_parts = request.command.split()
        if not cmd_parts:
            raise HTTPException(400, "Empty command")
        
        base_cmd = cmd_parts[0].lower()
        
        # Check against whitelist
        if base_cmd not in allowed_commands:
            raise HTTPException(403, f"Command '{base_cmd}' not allowed. Allowed: {', '.join(allowed_commands)}")
        
        # Determine working directory
        cwd = WORKSPACE_ROOT
        if request.cwd:
            cwd = WORKSPACE_ROOT / request.cwd
            if not str(cwd.resolve()).startswith(str(WORKSPACE_ROOT.resolve())):
                raise HTTPException(403, "Cannot execute outside workspace")
        
        try:
            proc = subprocess.run(
                request.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(cwd)
            )
            
            return {
                'success': proc.returncode == 0,
                'command': request.command,
                'stdout': proc.stdout,
                'stderr': proc.stderr,
                'returncode': proc.returncode,
                'cwd': str(cwd)
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'command': request.command,
                'stdout': '',
                'stderr': 'Command timeout (30s)',
                'returncode': -1,
                'cwd': str(cwd)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running terminal command: {e}")
        raise HTTPException(500, f"Command failed: {str(e)}")


# ==================== Search ====================

@router.get("/search")
async def search_files(
    query: str,
    file_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Search for files in workspace by name or content."""
    try:
        results = []
        query_lower = query.lower()
        
        for root, dirs, files in os.walk(WORKSPACE_ROOT):
            # Skip hidden and build directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv']]
            
            for file in files:
                if query_lower in file.lower():
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(WORKSPACE_ROOT)
                    
                    # Filter by file type if specified
                    if file_type and not file.endswith(f'.{file_type}'):
                        continue
                    
                    results.append({
                        'name': file,
                        'path': str(rel_path),
                        'size': file_path.stat().st_size,
                        'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
                    
                    if len(results) >= 50:  # Limit results
                        break
            
            if len(results) >= 50:
                break
        
        return {
            'success': True,
            'query': query,
            'results': results,
            'count': len(results)
        }
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")
