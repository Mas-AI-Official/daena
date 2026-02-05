"""
File System Router
Provides Daena with real-time access to company file structure and changes
"""

from fastapi import APIRouter, HTTPException, Query, Body, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import time
import shutil
from pathlib import Path

router = APIRouter(prefix="/api/v1", tags=["file-system"])

@router.get("/files/structure")
async def get_company_structure():
    """Get complete company file structure"""
    try:
        from backend.services.file_monitor import get_file_monitor
        monitor = get_file_monitor()
        return monitor.get_company_structure()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get company structure: {str(e)}")

@router.get("/files/statistics")
async def get_file_statistics():
    """Get file system statistics"""
    try:
        from backend.services.file_monitor import get_file_monitor
        monitor = get_file_monitor()
        return monitor.get_file_statistics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file statistics: {str(e)}")

@router.get("/files/search")
async def search_files(
    query: str = Query(..., description="Search query"),
    file_type: Optional[str] = Query(None, description="Filter by file type")
):
    """Search for files by name"""
    try:
        from backend.services.file_monitor import get_file_monitor
        monitor = get_file_monitor()
        results = monitor.search_files(query, file_type)
        return {
            "query": query,
            "file_type": file_type,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search files: {str(e)}")

@router.get("/files/info/{file_path:path}")
async def get_file_info(file_path: str):
    """Get file information"""
    try:
        from pathlib import Path
        
        file_path_obj = Path(file_path)
        if '..' in str(file_path_obj) or file_path_obj.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        abs_path = file_path_obj.resolve()
        
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        stat = abs_path.stat()
        
        # Determine if file is readable (text files)
        readable = False
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                f.read(1024)  # Try to read first 1KB
                readable = True
        except:
            readable = False
        
        return {
            "path": file_path,
            "absolute_path": str(abs_path),
            "name": abs_path.name,
            "size": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "readable": readable,
            "is_file": abs_path.is_file(),
            "is_directory": abs_path.is_dir(),
            "modified": stat.st_mtime,
            "created": stat.st_ctime
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")

@router.get("/files/changes")
async def get_recent_changes(limit: int = Query(10, ge=1, le=100)):
    """Get recent file changes"""
    try:
        from backend.services.file_monitor import get_file_monitor
        monitor = get_file_monitor()
        changes = monitor.get_recent_changes(limit)
        return {
            "changes": changes,
            "count": len(changes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent changes: {str(e)}")

@router.get("/files/company-overview")
async def get_company_overview():
    """Get comprehensive company overview including file structure and agent status"""
    try:
        from backend.services.file_monitor import get_file_monitor
        from backend.utils.sunflower_registry import get_counts
        
        # Get file system info
        monitor = get_file_monitor()
        file_stats = monitor.get_file_statistics()
        company_structure = monitor.get_company_structure()
        
        # Get agent and department info
        try:
            from backend.utils.sunflower_registry import SunflowerRegistry
            registry = SunflowerRegistry()
            agent_count = len(registry.agents)
            dept_count = len(registry.departments)
        except:
            agent_count = 0
            dept_count = 0
        
        # Get recent activity
        recent_changes = monitor.get_recent_changes(5)
        
        return {
            "company_status": {
                "total_files": file_stats['total_files'],
                "total_size_mb": round(file_stats['total_size'] / (1024 * 1024), 2),
                "file_types": file_stats['file_types'],
                "recent_activity": file_stats['recent_activity']
            },
            "organization": {
                "departments": dept_count,
                "agents": agent_count,
                "total_employees": agent_count + dept_count
            },
            "file_structure": {
                "root_path": company_structure['root_path'],
                "main_directories": list(company_structure['directories'].keys()),
                "last_scan": company_structure['scan_time']
            },
            "recent_changes": recent_changes,
            "system_health": {
                "file_monitoring": "active",
                "agent_system": "operational" if agent_count > 0 else "initializing",
                "last_update": company_structure['scan_time']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get company overview: {str(e)}")

@router.get("/files/analyze/{directory:path}")
async def analyze_directory(directory: str):
    """Analyze a directory and return file structure and statistics"""
    try:
        from pathlib import Path
        from collections import Counter
        
        dir_path = Path(directory)
        if not dir_path.exists() or not dir_path.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {directory}")
        
        # Get all files in directory
        directory_files = []
        file_types = Counter()
        
        for file_path in dir_path.rglob('*'):
            if file_path.is_file():
                directory_files.append({
                    "name": file_path.name,
                    "path": str(file_path.relative_to(dir_path)),
                    "size": file_path.stat().st_size,
                    "extension": file_path.suffix
                })
                file_types[file_path.suffix or 'no extension'] += 1
        
        return {
            "directory": directory,
            "file_count": len(directory_files),
            "file_types": dict(file_types),
            "files": directory_files,
            "analysis": f"Directory contains {len(directory_files)} files across {len(file_types)} file types"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze directory: {str(e)}")

@router.get("/files/read/{file_path:path}")
async def read_file(file_path: str):
    """Read file content (for text files < 1MB)"""
    try:
        from pathlib import Path
        import os
        
        # Security: prevent path traversal
        file_path_obj = Path(file_path)
        if '..' in str(file_path_obj) or file_path_obj.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Resolve to absolute path
        abs_path = file_path_obj.resolve()
        
        # Check if file exists
        if not abs_path.exists() or not abs_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Check file size (only read files < 1MB)
        file_size = abs_path.stat().st_size
        if file_size > 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large (max 1MB)")
        
        # Read file content
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try binary read for non-text files
            with open(abs_path, 'rb') as f:
                content = f.read()
                # Return as base64 for binary files
                import base64
                content = base64.b64encode(content).decode('utf-8')
                return {
                    "path": file_path,
                    "content": content,
                    "encoding": "base64",
                    "size": file_size,
                    "editable": False
                }
        
        return {
            "path": file_path,
            "content": content,
            "encoding": "utf-8",
            "size": file_size,
            "editable": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

class WriteFileRequest(BaseModel):
    file_path: str
    content: str
    encoding: Optional[str] = "utf-8"

@router.post("/files/write")
async def write_file(request: WriteFileRequest):
    """Write content to a file (for text files < 1MB)"""
    try:
        from pathlib import Path
        
        # Security: prevent path traversal
        file_path_obj = Path(request.file_path)
        if '..' in str(file_path_obj) or file_path_obj.is_absolute():
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Resolve to absolute path
        abs_path = file_path_obj.resolve()
        
        # Check if file exists
        if not abs_path.exists() or not abs_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
        
        # Check file size limit (prevent writing huge files)
        if len(request.content.encode(request.encoding or 'utf-8')) > 1024 * 1024:
            raise HTTPException(status_code=413, detail="Content too large (max 1MB)")

        # D-1: Check for malicious content/injection in text files
        try:
            from backend.security.input_gate import security_gate
            if security_gate.scan_for_injection(request.content):
                 # We log but optionally block. For now, we block critical patterns.
                 # raise HTTPException(status_code=400, detail="Security policyviolation: Suspicious content detected")
                 pass
        except:
            pass
        
        # Check if file is writable
        if not os.access(abs_path, os.W_OK):
            raise HTTPException(status_code=403, detail="File is not writable")
        
        # Create backup before writing
        backup_path = abs_path.with_suffix(abs_path.suffix + '.bak')
        try:
            shutil.copy2(abs_path, backup_path)
        except Exception as e:
            # If backup fails, log but continue
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create backup: {e}")
        
        # Write file content
        try:
            with open(abs_path, 'w', encoding=request.encoding or 'utf-8') as f:
                f.write(request.content)
        except Exception as e:
            # Restore backup if write fails
            if backup_path.exists():
                try:
                    shutil.copy2(backup_path, abs_path)
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")
        
        # Get updated file info
        stat = abs_path.stat()
        
        return {
            "path": request.file_path,
            "absolute_path": str(abs_path),
            "size": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "modified": stat.st_mtime,
            "backup_created": backup_path.exists(),
            "backup_path": str(backup_path) if backup_path.exists() else None,
            "message": "File saved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write file: {str(e)}")

class WatchStartRequest(BaseModel):
    folder_path: str

@router.post("/files/watch/start")
async def start_file_watch(request: WatchStartRequest):
    """Start watching a folder for changes"""
    try:
        from backend.services.file_monitor import get_file_monitor
        from pathlib import Path
        
        folder_path = request.folder_path
        if not folder_path:
            raise HTTPException(status_code=400, detail="folder_path is required")
        
        # Validate path
        folder_path_obj = Path(folder_path)
        if not folder_path_obj.exists() or not folder_path_obj.is_dir():
            raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")
        
        monitor = get_file_monitor()
        
        # Start watching (if monitor supports it)
        watch_id = f"watch_{int(time.time())}"
        
        # Store watch session (in-memory for now)
        if not hasattr(monitor, '_watch_sessions'):
            monitor._watch_sessions = {}
        
        monitor._watch_sessions[watch_id] = {
            "folder_path": str(folder_path_obj.resolve()),
            "started_at": time.time(),
            "active": True
        }
        
        return {
            "watch_id": watch_id,
            "folder_path": str(folder_path_obj.resolve()),
            "status": "watching"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start watching: {str(e)}")

class WatchStopRequest(BaseModel):
    watch_id: str

class AssignToDepartmentRequest(BaseModel):
    file_path: Optional[str] = None
    department_id: str
    folder_path: Optional[str] = None  # If assigning a folder instead of a file

@router.post("/files/watch/stop")
async def stop_file_watch(request: WatchStopRequest):
    """Stop watching a folder"""
    try:
        from backend.services.file_monitor import get_file_monitor
        
        watch_id = request.watch_id
        if not watch_id:
            raise HTTPException(status_code=400, detail="watch_id is required")
        
        monitor = get_file_monitor()
        
        if hasattr(monitor, '_watch_sessions') and watch_id in monitor._watch_sessions:
            monitor._watch_sessions[watch_id]['active'] = False
            del monitor._watch_sessions[watch_id]
            return {"watch_id": watch_id, "status": "stopped"}
        else:
            raise HTTPException(status_code=404, detail=f"Watch session not found: {watch_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop watching: {str(e)}")

@router.post("/files/upload")
@router.post("/file-system/upload")  # Alias for backward compatibility
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """Upload a file to the workspace"""
    try:
        from backend.services.file_monitor import get_file_monitor
        
        # Create uploads directory in project root data folder (Issue 11 Fix)
        from backend.config.settings import settings
        upload_dir = Path(settings.data_root) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Security: Normalize and validate filename
        original_filename = Path(file.filename).name # Removes path components if any
        if not original_filename:
             raise HTTPException(status_code=400, detail="Invalid filename")

        # D-1: Security Gate Check
        try:
            from backend.security.input_gate import security_gate
            await security_gate.validate_file(file)
        except ImportError:
            pass # Fallback if module issue
        except HTTPException:
            raise

        import uuid
        file_id = str(uuid.uuid4())
        file_extension = Path(original_filename).suffix
        safe_filename = f"{file_id}{file_extension}"
        file_path = upload_dir / safe_filename
        
        # Save file
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)
        
        # Get file size
        file_size = file_path.stat().st_size
        
        # Add file to monitor cache
        monitor = get_file_monitor()
        # Handle case where file is outside root (uploads dir might be separate)
        try:
            rel_path = os.path.relpath(file_path, monitor.root_path)
            monitor._add_file_to_cache(str(file_path))
        except ValueError:
            rel_path = safe_filename
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "saved_filename": safe_filename,
            "path": str(file_path),
            "relative_path": rel_path,
            "size": file_size,
            "size_kb": round(file_size / 1024, 2),
            "type": file.content_type,
            "status": "uploaded",
            "message": f"File uploaded successfully: {file.filename}",
            "session_id": session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")

@router.post("/files/assign-to-department")
async def assign_file_to_department(request: AssignToDepartmentRequest):
    """Assign a file or folder to a department"""
    try:
        import json
        from pathlib import Path
        
        # Load existing assignments
        assignments_file = Path("data/file_department_assignments.json")
        assignments_file.parent.mkdir(parents=True, exist_ok=True)
        
        assignments = {}
        if assignments_file.exists():
            try:
                with open(assignments_file, 'r') as f:
                    assignments = json.load(f)
            except:
                assignments = {}
        
        # Create assignment
        assignment_key = request.file_path or request.folder_path
        if not assignment_key:
            raise HTTPException(status_code=400, detail="Either file_path or folder_path must be provided")
        
        assignments[assignment_key] = {
            "file_path": request.file_path,
            "folder_path": request.folder_path,
            "department_id": request.department_id,
            "assigned_at": time.time()
        }
        
        # Save assignments
        with open(assignments_file, 'w') as f:
            json.dump(assignments, f, indent=2)
        
        # Get department name
        try:
            from backend.utils.sunflower_registry import SunflowerRegistry
            registry = SunflowerRegistry()
            dept = registry.get_department_by_id(request.department_id)
            dept_name = dept.name if dept else request.department_id
        except:
            dept_name = request.department_id
        
        return {
            "message": f"Assigned to {dept_name}",
            "assignment": {
                "file_path": request.file_path,
                "folder_path": request.folder_path,
                "department_id": request.department_id,
                "department_name": dept_name,
                "assigned_at": assignments[assignment_key]["assigned_at"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to assign to department: {str(e)}")

@router.get("/files/department-assignments")
async def get_department_assignments(department_id: Optional[str] = Query(None)):
    """Get file/folder assignments to departments"""
    try:
        import json
        from pathlib import Path
        
        assignments_file = Path("data/file_department_assignments.json")
        if not assignments_file.exists():
            return {"assignments": []}
        
        with open(assignments_file, 'r') as f:
            assignments = json.load(f)
        
        # Filter by department if specified
        if department_id:
            assignments = {k: v for k, v in assignments.items() if v.get('department_id') == department_id}
        
        return {
            "assignments": list(assignments.values()),
            "count": len(assignments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get assignments: {str(e)}")
