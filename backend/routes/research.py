"""
Research API Routes — Multi-Source Knowledge Gathering

Provides API endpoints for:
- Executing research queries
- Searching specific sources
- Managing research history
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import logging

router = APIRouter(prefix="/api/v1/research", tags=["research"])
logger = logging.getLogger(__name__)


class ResearchRequest(BaseModel):
    query: str = Field(..., description="Research query")
    sources: Optional[List[str]] = Field(
        default=None,
        description="Source types to search: web, local_kb, agent_memory, mcp_tool, document"
    )
    max_results: int = Field(default=10, description="Maximum findings to return")
    verify_facts: bool = Field(default=True, description="Verify findings via IntegrityShield")


class QuickSearchRequest(BaseModel):
    query: str = Field(..., description="Quick search query")
    source: str = Field(default="local_kb", description="Source to search")


@router.post("/query")
async def research_query(request: ResearchRequest):
    """Execute a research query across multiple sources."""
    try:
        from backend.agents.research_agent import get_research_agent, SourceType
        
        agent = get_research_agent()
        
        # Convert source strings to SourceType
        sources = None
        if request.sources:
            try:
                sources = [SourceType(s) for s in request.sources]
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid source type: {e}. Valid: web, local_kb, agent_memory, mcp_tool, document"
                )
        
        result = await agent.research(
            query=request.query,
            sources=sources,
            max_results=request.max_results,
            verify_facts=request.verify_facts
        )
        
        return {
            "success": True,
            **result.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Research query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick-search")
async def quick_search(request: QuickSearchRequest):
    """Quick search against a single source."""
    try:
        from backend.agents.research_agent import get_research_agent, SourceType
        
        agent = get_research_agent()
        
        try:
            source_type = SourceType(request.source)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source: {request.source}"
            )
        
        result = await agent.research(
            query=request.query,
            sources=[source_type],
            max_results=5,
            verify_facts=False  # Skip verification for quick search
        )
        
        return {
            "success": True,
            "query": request.query,
            "source": request.source,
            "findings": [f.to_dict() for f in result.findings],
            "count": len(result.findings)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quick search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_research_history(limit: int = 20):
    """Get recent research history."""
    try:
        from backend.agents.research_agent import get_research_agent
        
        agent = get_research_agent()
        history = agent.get_search_history(limit)
        
        return {
            "success": True,
            "history": history,
            "count": len(history)
        }
        
    except Exception as e:
        logger.error(f"Get history failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def list_sources():
    """List available research sources."""
    from backend.agents.research_agent import SourceType
    
    return {
        "success": True,
        "sources": [
            {
                "id": "web",
                "name": "Web Search",
                "description": "Search the web for relevant information",
                "trust_level": "variable"
            },
            {
                "id": "local_kb",
                "name": "Local Knowledge Base",
                "description": "Search NBMF memory for stored knowledge",
                "trust_level": "high"
            },
            {
                "id": "agent_memory",
                "name": "Agent Memory",
                "description": "Search unified agent memory",
                "trust_level": "high"
            },
            {
                "id": "mcp_tool",
                "name": "MCP Tools",
                "description": "Use MCP tools to gather information",
                "trust_level": "high"
            },
            {
                "id": "document",
                "name": "Documents",
                "description": "Search uploaded documents",
                "trust_level": "medium"
            }
        ]
    }
