"""
Agent Automation API Routes for Daena AI VP

Exposes:
- Intelligent routing status and stats
- Tool detection and execution
- Concurrent task execution
- MCP connectivity
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/automation", tags=["Agent Automation"])


class ToolExecuteRequest(BaseModel):
    tool_name: str
    action: str
    args: Dict[str, Any] = {}
    executor_id: str = "daena"
    skip_approval: bool = False


class BatchExecuteRequest(BaseModel):
    tasks: List[Dict[str, Any]]
    executor_id: str = "daena"


class DetectToolRequest(BaseModel):
    message: str
    agent_id: str = "daena"


class RouteRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


@router.get("/status")
async def get_automation_status():
    """Get overall automation system status."""
    status = {
        "routing": {"available": False, "stats": {}},
        "tool_detection": {"available": False, "stats": {}},
        "tool_execution": {"available": False, "stats": {}},
        "ollama": {"available": False, "models": []},
    }
    
    # Check intelligent router
    try:
        from backend.services.intelligent_router import intelligent_router
        await intelligent_router.check_model_availability()
        status["routing"] = {
            "available": True,
            "stats": intelligent_router.get_routing_stats(),
        }
    except Exception as e:
        logger.warning(f"Router status check failed: {e}")
    
    # Check tool detector
    try:
        from backend.services.agent_tool_detector import agent_tool_detector
        status["tool_detection"] = {
            "available": True,
            "stats": agent_tool_detector.get_detection_stats(),
        }
    except Exception as e:
        logger.warning(f"Tool detector status check failed: {e}")
    
    # Check tool executor
    try:
        from backend.services.unified_tool_executor import unified_executor
        status["tool_execution"] = {
            "available": True,
            "stats": unified_executor.get_execution_stats(),
        }
    except Exception as e:
        logger.warning(f"Tool executor status check failed: {e}")
    
    # Check Ollama
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:11434/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                status["ollama"] = {
                    "available": True,
                    "models": models,
                    "has_reasoning": any("deepseek-r1" in m or "qwq" in m for m in models),
                }
    except Exception as e:
        logger.warning(f"Ollama status check failed: {e}")
    
    return status


@router.post("/route")
async def route_message(request: RouteRequest):
    """Route a message to the optimal LLM model."""
    try:
        from backend.services.intelligent_router import intelligent_router
        
        decision = await intelligent_router.route(request.message, request.context)
        
        return {
            "success": True,
            "model_tier": decision.model_tier.value,
            "model_name": decision.model_name,
            "provider": decision.provider,
            "reason": decision.reason,
            "fallback_chain": decision.fallback_chain,
        }
    except Exception as e:
        logger.error(f"Routing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-tool")
async def detect_tool(request: DetectToolRequest):
    """Detect tool intent from a message."""
    try:
        from backend.services.agent_tool_detector import detect_and_route_tool
        
        result = await detect_and_route_tool(request.message, request.agent_id)
        
        if result:
            return {
                "success": True,
                "detected": True,
                **result
            }
        else:
            return {
                "success": True,
                "detected": False,
                "message": "No tool intent detected"
            }
    except Exception as e:
        logger.error(f"Tool detection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_tool(request: ToolExecuteRequest):
    """Execute a single tool action."""
    try:
        from backend.services.unified_tool_executor import unified_executor, ExecutorType
        
        result = await unified_executor.execute(
            tool_name=request.tool_name,
            action=request.action,
            args=request.args,
            executor_id=request.executor_id,
            executor_type=ExecutorType.DAENA,
            skip_approval=request.skip_approval
        )
        
        return result
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute-batch")
async def execute_batch(request: BatchExecuteRequest):
    """Execute multiple tool actions concurrently."""
    try:
        from backend.services.unified_tool_executor import unified_executor, ExecutorType
        
        results = await unified_executor.execute_batch(
            tasks=request.tasks,
            executor_id=request.executor_id,
            executor_type=ExecutorType.DAENA
        )
        
        return {
            "success": True,
            "total_tasks": len(request.tasks),
            "results": results
        }
    except Exception as e:
        logger.error(f"Batch execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://127.0.0.1:11434/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = []
                for m in data.get("models", []):
                    models.append({
                        "name": m["name"],
                        "size": m.get("size", 0),
                        "is_reasoning": "deepseek-r1" in m["name"] or "qwq" in m["name"],
                    })
                return {"success": True, "models": models}
            else:
                return {"success": False, "error": "Ollama not responding"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/ollama/pull")
async def pull_ollama_model(model_name: str = "deepseek-r1:8b"):
    """Trigger download of an Ollama model."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=600.0) as client:  # Long timeout for download
            response = await client.post(
                "http://127.0.0.1:11434/api/pull",
                json={"name": model_name}
            )
            return {"success": True, "message": f"Pull started for {model_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

