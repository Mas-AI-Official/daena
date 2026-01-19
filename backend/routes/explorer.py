"""
Explorer Bridge API endpoints.

Human-in-the-loop consultation mode:
- NO APIs
- NO automation
- NO scraping
- User copies prompt, pastes response
"""

from __future__ import annotations

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.explorer_bridge import explorer_bridge
from backend.config.settings import get_settings

router = APIRouter(prefix="/api/v1/explorer", tags=["explorer"])


class BuildPromptRequest(BaseModel):
    task: str
    target: str = "chatgpt"  # "chatgpt" | "gemini" | "claude"
    context: Optional[Dict[str, Any]] = None


class ParseResponseRequest(BaseModel):
    text: str
    target: str = "chatgpt"


class MergeResponseRequest(BaseModel):
    daena_response: str
    explorer_response: Dict[str, Any]


@router.post("/build_prompt")
async def build_prompt(req: BuildPromptRequest):
    """
    Build a formatted prompt for user to paste into external LLM UI.
    
    Requires ENABLE_EXPLORER_MODE=1 (default: True).
    """
    settings = get_settings()
    if not getattr(settings, "enable_explorer_mode", True):
        raise HTTPException(
            status_code=403,
            detail="Explorer Mode disabled. Set ENABLE_EXPLORER_MODE=1 to enable."
        )
    
    result = explorer_bridge.build_prompt(
        task=req.task,
        target=req.target,
        context=req.context,
    )
    
    return {
        "success": True,
        **result
    }


@router.post("/parse_response")
async def parse_response(req: ParseResponseRequest):
    """
    Parse a response pasted from external LLM UI.
    
    Requires ENABLE_EXPLORER_MODE=1 (default: True).
    """
    settings = get_settings()
    if not getattr(settings, "enable_explorer_mode", True):
        raise HTTPException(
            status_code=403,
            detail="Explorer Mode disabled. Set ENABLE_EXPLORER_MODE=1 to enable."
        )
    
    result = explorer_bridge.parse_response(
        text=req.text,
        target=req.target,
    )
    
    return {
        "success": True,
        **result
    }


@router.post("/merge")
async def merge_responses(req: MergeResponseRequest):
    """
    Merge explorer response with Daena's response.
    
    Requires ENABLE_EXPLORER_MODE=1 (default: True).
    """
    settings = get_settings()
    if not getattr(settings, "enable_explorer_mode", True):
        raise HTTPException(
            status_code=403,
            detail="Explorer Mode disabled. Set ENABLE_EXPLORER_MODE=1 to enable."
        )
    
    result = explorer_bridge.merge_with_daena_response(
        daena_response=req.daena_response,
        explorer_response=req.explorer_response,
    )
    
    return {
        "success": True,
        **result
    }


@router.get("/status")
async def explorer_status():
    """Get Explorer Mode status."""
    settings = get_settings()
    enabled = getattr(settings, "enable_explorer_mode", True)
    
    return {
        "success": True,
        "enabled": enabled,
        "supported_targets": explorer_bridge.SUPPORTED_TARGETS,
        "description": "Human-in-the-loop consultation mode (NO APIs, NO automation)",
    }









