"""
Human Relay Explorer API endpoints.

Manual copy/paste bridge for external LLMs (ChatGPT/Gemini).
NO automation, NO scraping, NO login automation.
"""

from __future__ import annotations

import os
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.human_relay_explorer import human_relay_explorer
from backend.config.settings import get_settings

router = APIRouter(prefix="/api/v1/human-relay", tags=["human-relay-explorer"])


class GeneratePromptRequest(BaseModel):
    provider: str  # "chatgpt" | "gemini"
    task: str
    context: Optional[Dict[str, Any]] = None


class IngestResponseRequest(BaseModel):
    relay_id: str
    provider: str
    pasted_answer: str


class SynthesizeRequest(BaseModel):
    task: str
    insight_ids: List[str]
    mode: str = "assist_only"  # "assist_only" = Daena uses insights as reference, not truth


@router.post("/prompt")
async def generate_prompt(req: GeneratePromptRequest):
    """
    Generate a copy/paste-ready prompt for external LLM UI.
    
    Requires ENABLE_HUMAN_RELAY_EXPLORER=1 (default: enabled for local dev).
    """
    settings = get_settings()
    enable_explorer = getattr(settings, "enable_human_relay_explorer", True) if settings else (os.getenv("ENABLE_HUMAN_RELAY_EXPLORER", "1") == "1")
    
    if not enable_explorer:
        raise HTTPException(
            status_code=403,
            detail="Human Relay Explorer disabled. Set ENABLE_HUMAN_RELAY_EXPLORER=1 to enable."
        )
    
    result = human_relay_explorer.generate_prompt(
        provider=req.provider,
        task=req.task,
        context=req.context,
    )
    
    return {
        "success": True,
        **result
    }


@router.post("/ingest")
async def ingest_response(req: IngestResponseRequest):
    """
    Ingest a pasted response from external LLM UI.
    
    Requires ENABLE_HUMAN_RELAY_EXPLORER=1 (default: enabled for local dev).
    """
    settings = get_settings()
    enable_explorer = getattr(settings, "enable_human_relay_explorer", True) if settings else (os.getenv("ENABLE_HUMAN_RELAY_EXPLORER", "1") == "1")
    
    if not enable_explorer:
        raise HTTPException(
            status_code=403,
            detail="Human Relay Explorer disabled. Set ENABLE_HUMAN_RELAY_EXPLORER=1 to enable."
        )
    
    result = human_relay_explorer.ingest_response(
        relay_id=req.relay_id,
        provider=req.provider,
        pasted_answer=req.pasted_answer,
    )
    
    return {
        "success": True,
        **result
    }


@router.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    """
    Synthesize external insights with Daena's brain.
    
    This calls the canonical Daena brain with insights as context.
    Mode "assist_only" means Daena uses insights as reference, not definitive truth.
    
    Requires ENABLE_HUMAN_RELAY_EXPLORER=1 (default: enabled for local dev).
    """
    settings = get_settings()
    enable_explorer = getattr(settings, "enable_human_relay_explorer", True) if settings else (os.getenv("ENABLE_HUMAN_RELAY_EXPLORER", "1") == "1")
    
    if not enable_explorer:
        raise HTTPException(
            status_code=403,
            detail="Human Relay Explorer disabled. Set ENABLE_HUMAN_RELAY_EXPLORER=1 to enable."
        )
    
    result = await human_relay_explorer.synthesize(
        task=req.task,
        insight_ids=req.insight_ids,
        mode=req.mode,
    )
    
    return {
        "success": True,
        **result
    }


@router.get("/status")
async def explorer_status():
    """Get Human Relay Explorer status"""
    settings = get_settings()
    enabled = getattr(settings, "enable_human_relay_explorer", True) if settings else (os.getenv("ENABLE_HUMAN_RELAY_EXPLORER", "1") == "1")
    
    return {
        "success": True,
        "enabled": enabled,
        "supported_providers": human_relay_explorer.SUPPORTED_PROVIDERS,
        "description": "Manual copy/paste bridge for external LLMs (NO automation, NO scraping)",
    }

