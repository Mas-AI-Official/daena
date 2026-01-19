"""
Manus-Style Workspace Router
Handles local folder connection, file tree, and content reading.
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
import os
from pathlib import Path

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])

class ConnectRequest(BaseModel):
    path: str

class FileNode(BaseModel):
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: Optional[str] = None

@router.post("/connect")
async def connect_folder(request: ConnectRequest):
    """Connect a local folder as a project context."""
    path = Path(request.path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid directory path")
    
    # In a real app, we'd persist this connection in a DB
    return {"status": "connected", "path": str(path), "name": path.name}

@router.get("/tree")
async def get_tree(project_path: str):
    """Get file tree for a connected project."""
    path = Path(project_path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=400, detail="Invalid project path")
    
    try:
        items = []
        for entry in os.scandir(path):
            if entry.name.startswith('.'): continue
            items.append({
                "name": entry.name,
                "path": entry.path,
                "type": "directory" if entry.is_dir() else "file",
                "size": f"{entry.stat().st_size / 1024:.1f} KB" if entry.is_file() else None
            })
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/file")
async def get_file(path: str):
    """Read content of a file."""
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Safety check: ensure we are reading text files only for now
        if file_path.suffix.lower() not in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json']:
             return {"content": "[Binary or unsupported file type]"}

        return {"content": file_path.read_text(encoding='utf-8', errors='replace')}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
