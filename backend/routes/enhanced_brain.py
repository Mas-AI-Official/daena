#!/usr/bin/env python3
"""
Enhanced Brain API Routes
Provides endpoints for local brain integration and deep search
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import json
from datetime import datetime

# Import enhanced brain components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from Core.llm.enhanced_local_brain_integration import get_enhanced_brain
from Core.deep.deep_search_engine import get_deep_search_engine

router = APIRouter(prefix="/api/enhanced-brain", tags=["Enhanced Brain"])

class BrainQuery(BaseModel):
    prompt: str
    force_deep_search: bool = False
    search_type: str = "general"

class DeepSearchRequest(BaseModel):
    query: str
    depth: int = 3
    search_type: str = "general"

class ProjectPlanningRequest(BaseModel):
    project_idea: str

class StrategicRoadmapRequest(BaseModel):
    strategic_goal: str

class BrainStatus(BaseModel):
    owner: str
    device: str
    models_available: int
    models_loaded: int
    loaded_models: List[str]
    consensus_threshold: float
    deep_search_enabled: bool
    h_drive_models: List[str]

@router.get("/status", response_model=BrainStatus)
async def get_brain_status():
    """Get enhanced brain status"""
    try:
        brain = await get_enhanced_brain()
        status = brain.get_brain_status()
        return BrainStatus(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting brain status: {str(e)}")

@router.post("/query")
async def brain_query(request: BrainQuery):
    """Query the enhanced brain with local models"""
    try:
        brain = await get_enhanced_brain()
        result = await brain.make_decision(request.prompt, force_deep_search=request.force_deep_search)
        
        return {
            "success": True,
            "decision": result['decision'],
            "confidence": result['confidence'],
            "models_used": result['models_used'],
            "deep_search_used": request.force_deep_search,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying brain: {str(e)}")

@router.post("/deep-search")
async def deep_search(request: DeepSearchRequest):
    """Perform deep search analysis"""
    try:
        search_engine = await get_deep_search_engine()
        result = await search_engine.deep_search_analysis(
            request.query, 
            depth=request.depth, 
            search_type=request.search_type
        )
        
        return {
            "success": True,
            "query": result.query,
            "depth": result.depth,
            "final_analysis": result.final_analysis,
            "rounds": result.rounds,
            "breadcrumbs": [b.__dict__ for b in result.breadcrumbs],
            "timestamp": result.timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing deep search: {str(e)}")

@router.post("/project-planning")
async def project_planning(request: ProjectPlanningRequest):
    """Enter project planning mode"""
    try:
        search_engine = await get_deep_search_engine()
        result = await search_engine.project_planning_mode(request.project_idea)
        
        return {
            "success": True,
            "project": result["project"],
            "stages": result["stages"],
            "roadmap": result["roadmap"],
            "timestamp": result["timestamp"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in project planning: {str(e)}")

@router.post("/strategic-roadmap")
async def strategic_roadmap(request: StrategicRoadmapRequest):
    """Build strategic roadmap"""
    try:
        search_engine = await get_deep_search_engine()
        result = await search_engine.strategic_roadmap_builder(request.strategic_goal)
        
        return {
            "success": True,
            "goal": result["goal"],
            "analysis": result["analysis"],
            "roadmap": result["roadmap"],
            "breadcrumbs": result["breadcrumbs"],
            "timestamp": result["timestamp"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error building strategic roadmap: {str(e)}")

@router.get("/search-history")
async def get_search_history():
    """Get deep search history"""
    try:
        search_engine = await get_deep_search_engine()
        history = search_engine.get_search_history()
        
        return {
            "success": True,
            "history": history,
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting search history: {str(e)}")

@router.get("/project-plans")
async def get_project_plans():
    """Get project plans history"""
    try:
        search_engine = await get_deep_search_engine()
        plans = search_engine.get_project_plans()
        
        return {
            "success": True,
            "plans": plans,
            "count": len(plans)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting project plans: {str(e)}")

@router.post("/should-deep-search")
async def should_use_deep_search(request: BrainQuery):
    """Check if a query should use deep search"""
    try:
        brain = await get_enhanced_brain()
        should_deep = await brain.should_use_deep_search(request.prompt)
        
        return {
            "success": True,
            "should_deep_search": should_deep,
            "prompt": request.prompt,
            "reasoning": "Based on keyword analysis and prompt length"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking deep search: {str(e)}")

@router.post("/load-model")
async def load_model(model_name: str):
    """Load a specific model"""
    try:
        brain = await get_enhanced_brain()
        success = await brain.load_model(model_name)
        
        return {
            "success": success,
            "model_name": model_name,
            "message": f"Model {'loaded' if success else 'failed to load'}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading model: {str(e)}")

@router.post("/load-priority-models")
async def load_priority_models():
    """Load high-priority models (R1, R2)"""
    try:
        brain = await get_enhanced_brain()
        await brain.load_priority_models()
        
        return {
            "success": True,
            "message": "Priority models loaded",
            "loaded_models": list(brain.models.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading priority models: {str(e)}") 