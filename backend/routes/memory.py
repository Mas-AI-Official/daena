"""
Memory API Routes — NBMF 3-Tier Memory System

Provides API endpoints for:
- Storing data with policy-based routing
- Recalling data from any tier
- Memory statistics and aging
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])
logger = logging.getLogger(__name__)


class MemoryStoreRequest(BaseModel):
    content: str = Field(..., description="Content to store")
    data_class: str = Field(..., description="Data classification (legal, chat, skill, etc.)")
    metadata: Optional[Dict[str, Any]] = None


class MemoryRecallRequest(BaseModel):
    item_id: str = Field(..., description="Item ID to recall")


class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    top_k: int = Field(default=5, description="Number of results")


@router.post("/store")
async def store_memory(request: MemoryStoreRequest):
    """Store content in NBMF memory with policy-based routing."""
    try:
        from backend.services.memory.memory_router import get_memory_router
        router_instance = get_memory_router()
        
        item_id = router_instance.route(
            content=request.content,
            data_class=request.data_class,
            metadata=request.metadata
        )
        
        return {
            "success": True,
            "item_id": item_id,
            "data_class": request.data_class
        }
    except Exception as e:
        logger.error(f"Memory store failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recall")
async def recall_memory(request: MemoryRecallRequest):
    """Recall content from memory by item ID."""
    try:
        from backend.services.memory.memory_router import get_memory_router
        router_instance = get_memory_router()
        
        content = router_instance.recall(request.item_id)
        
        if content is None:
            raise HTTPException(status_code=404, detail="Item not found")
        
        return {
            "success": True,
            "item_id": request.item_id,
            "content": content
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Memory recall failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memory(request: MemorySearchRequest):
    """Search HOT memory cache."""
    try:
        from backend.services.memory.hot_memory import HotMemory
        hot = HotMemory()
        
        results = hot.search(request.query, request.top_k)
        
        return {
            "success": True,
            "query": request.query,
            "results": results
        }
    except Exception as e:
        logger.error(f"Memory search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_memory_stats():
    """Get memory system statistics."""
    try:
        from backend.services.memory.memory_router import get_memory_router
        from backend.services.memory.hot_memory import HotMemory
        from backend.services.memory.warm_memory import WarmMemory
        from backend.services.memory.cold_memory import ColdMemory
        
        router_instance = get_memory_router()
        hot = HotMemory()
        warm = WarmMemory()
        cold = ColdMemory()
        
        return {
            "success": True,
            "router": router_instance.get_stats(),
            "hot": hot.get_stats(),
            "warm": warm.get_stats(),
            "cold": cold.get_stats()
        }
    except Exception as e:
        logger.error(f"Memory stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/age")
async def run_aging():
    """Run memory aging process (demote old items to lower tiers)."""
    try:
        from backend.services.memory.memory_router import get_memory_router
        router_instance = get_memory_router()
        
        demoted = router_instance.run_aging()
        
        return {
            "success": True,
            "items_demoted": demoted
        }
    except Exception as e:
        logger.error(f"Memory aging failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
