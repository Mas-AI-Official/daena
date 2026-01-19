"""
Change Control V2 API - Incremental Backup & Change Tracking

Provides REST API for the incremental backup system with:
- File-level backups (only changed files)
- Diff storage (not full copies)
- Fast rollback
- Complete audit trail
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

from backend.services.change_tracker import change_tracker

router = APIRouter(prefix="/api/v1/changes", tags=["Change Control V2"])


# Pydantic Models
class PrepareBackupRequest(BaseModel):
    file_path: str
    change_type: str  # 'create', 'modify', 'delete'
    actor: str  # 'masoud', 'daena', 'agent_id'
    reason: str


class CommitChangeRequest(BaseModel):
    backup_id: str
    success: bool
    new_content: Optional[str] = None


class RollbackRequest(BaseModel):
    backup_id: str


@router.post("/prepare")
async def prepare_backup(request: PrepareBackupRequest):
    """
    Prepare a backup before making a file change
    
    This MUST be called before modifying any file. It creates a backup
    and returns a backup_id to use when committing the change.
    
    Example:
        backup_id = prepare_backup("main.py", "modify", "masoud", "fixing bug #123")
        # ... make changes to file ...
        commit_change(backup_id, success=True, new_content=file_content)
    """
    try:
        backup_id = change_tracker.before_change(
            file_path=request.file_path,
            change_type=request.change_type,
            actor=request.actor,
            reason=request.reason
        )
        
        return {
            "success": True,
            "backup_id": backup_id,
            "message": "Backup prepared successfully",
            "file_path": request.file_path,
            "change_type": request.change_type,
            "actor": request.actor
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare backup: {str(e)}")


@router.post("/commit")
async def commit_change(request: CommitChangeRequest):
    """
    Commit a file change and store the diff
    
    Call this after making changes to mark the backup as complete
    and optionally store the diff for audit purposes.
    """
    try:
        change_tracker.after_change(
            backup_id=request.backup_id,
            success=request.success,
            new_content=request.new_content
        )
        
        return {
            "success": True,
            "backup_id": request.backup_id,
            "message": "Change committed successfully",
            "status": "complete" if request.success else "failed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to commit change: {str(e)}")


@router.post("/rollback")
async def rollback_change(request: RollbackRequest):
    """
    Rollback a file to a previous backup
    
    This will restore the file to the state it was in when the backup was created.
    Use this to undo changes that caused problems.
    """
    try:
        success = change_tracker.rollback(request.backup_id)
        
        if success:
            return {
                "success": True,
                "backup_id": request.backup_id,
                "message": "File rolled back successfully"
            }
        else:
            raise HTTPException(status_code=400, detail="Rollback failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.get("/history")
async def get_change_history(
    file_path: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = 50
):
    """
    Get change history with optional filters
    
    Query params:
        file_path: Filter by specific file
        actor: Filter by who made the change
        limit: Max number of results (default 50)
    """
    try:
        history = change_tracker.get_history(
            file_path=file_path,
            actor=actor,
            limit=limit
        )
        
        return {
            "success": True,
            "count": len(history),
            "changes": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/{backup_id}")
async def get_change_detail(backup_id: str):
    """
    Get details about a specific change/backup
    """
    try:
        history = change_tracker.get_history(limit=1000)
        
        for change in history:
            if change["backup_id"] == backup_id:
                return {
                    "success": True,
                    "change": change
                }
        
        raise HTTPException(status_code=404, detail=f"Backup {backup_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get change detail: {str(e)}")


@router.get("/stats")
async def get_backup_stats():
    """
    Get statistics about the backup system
    
    Returns:
        - Total number of backups
        - Total storage used
        - Breakdown by actor and change type
        - Oldest/newest backups
    """
    try:
        stats = change_tracker.get_stats()
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/recent")
async def get_recent_changes(limit: int = 10):
    """
    Get most recent changes for dashboard display
    """
    try:
        recent = change_tracker.get_history(limit=limit)
        
        return {
            "success": True,
            "count": len(recent),
            "recent_changes": recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get recent changes: {str(e)}")


@router.get("/file")
async def get_file_history(file_path: str, limit: int = 20):
    """
    Get all changes for a specific file
    """
    try:
        file_history = change_tracker.get_history(file_path=file_path, limit=limit)
        
        return {
            "success": True,
            "file_path": file_path,
            "change_count": len(file_history),
            "changes": file_history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file history: {str(e)}")


@router.get("/actor/{actor}")
async def get_actor_changes(actor: str, limit: int = 50):
    """
    Get all changes made by a specific actor (user/agent)
    """
    try:
        actor_changes = change_tracker.get_history(actor=actor, limit=limit)
        
        return {
            "success": True,
            "actor": actor,
            "change_count": len(actor_changes),
            "changes": actor_changes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get actor changes: {str(e)}")
