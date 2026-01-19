"""
Self-Upgrade System
Allows Daena to propose code changes and request user confirmation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import subprocess
import os
import logging

router = APIRouter(prefix="/api/v1/self-upgrade", tags=["self-upgrade"])
logger = logging.getLogger(__name__)

class CodeChange(BaseModel):
    file_path: str
    description: str
    old_content: Optional[str]
    new_content: str
    reason: str

class UpgradeProposal(BaseModel):
    id: str
    title: str
    description: str
    changes: List[CodeChange]
    created_at: datetime
    status: str  # pending, approved, rejected, applied

# In-memory storage (would be DB in production)
proposals_db: Dict[str, UpgradeProposal] = {}

@router.post("/propose")
async def propose_upgrade(title: str, description: str, changes: List[CodeChange]):
    """Daena proposes a self-upgrade"""
    import uuid
    
    proposal_id = str(uuid.uuid4())
    proposal = UpgradeProposal(
        id=proposal_id,
        title=title,
        description=description,
        changes=changes,
        created_at=datetime.now(),
        status="pending"
    )
    
    proposals_db[proposal_id] = proposal
    
    logger.info(f"🤖 Daena proposed upgrade: {title}")
    
    return {
        "success": True,
        "proposal_id": proposal_id,
        "proposal": proposal,
        "message": "Upgrade proposal created. Awaiting user confirmation."
    }

@router.get("/proposals")
async def list_proposals():
    """List all upgrade proposals"""
    return {
        "proposals": list(proposals_db.values())
    }

@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str):
    """Get specific proposal details"""
    if proposal_id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposals_db[proposal_id]

@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str):
    """User approves a proposal"""
    if proposal_id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    proposal = proposals_db[proposal_id]
    proposal.status = "approved"
    
    # Apply changes via VSCode (or direct file write)
    try:
        results = []
        for change in proposal.changes:
            result = await apply_change_via_vscode(change)
            results.append(result)
        
        proposal.status = "applied"
        
        return {
            "success": True,
            "proposal_id": proposal_id,
            "results": results,
            "message": "Upgrade applied successfully!"
        }
    except Exception as e:
        proposal.status = "failed"
        logger.error(f"Failed to apply upgrade: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply upgrade: {str(e)}")

@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: str, reason: str = ""):
    """User rejects a proposal"""
    if proposal_id not in proposals_db:
        raise HTTPException(status_code=404, detail="Proposal not found")
    
    proposal = proposals_db[proposal_id]
    proposal.status = "rejected"
    
    logger.info(f"❌ User rejected upgrade: {proposal.title} - Reason: {reason}")
    
    return {
        "success": True,
        "proposal_id": proposal_id,
        "message": "Proposal rejected"
    }

async def apply_change_via_vscode(change: CodeChange):
    """Apply code change using VSCode or direct write"""
    try:
        # Method 1: Direct file write (safer)
        file_path = change.file_path
        
        # Backup original
        backup_path = f"{file_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                with open(backup_path, 'w', encoding='utf-8') as backup:
                    backup.write(f.read())
        
        # Write new content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(change.new_content)
        
        logger.info(f"✅ Applied change to {file_path}")
        
        return {
            "file": file_path,
            "success": True,
            "backup": backup_path
        }
        
    except Exception as e:
        logger.error(f"Failed to apply change to {change.file_path}: {e}")
        return {
            "file": change.file_path,
            "success": False,
            "error": str(e)
        }

# Example: Daena can call this internally to propose upgrades
async def daena_auto_propose_fix(issue_description: str, file_path: str, fix_code: str):
    """
    Daena's internal method to propose a fix
    This can be called when she detects issues or improvements
    """
    change = CodeChange(
        file_path=file_path,
        description=f"Auto-fix: {issue_description}",
        old_content=None,
        new_content=fix_code,
        reason=f"Detected issue: {issue_description}. Proposed automated fix."
    )
    
    proposal = await propose_upgrade(
        title=f"Auto-Fix: {issue_description}",
        description=f"Daena detected an issue in {file_path} and proposes this fix.",
        changes=[change]
    )
    
    return proposal
