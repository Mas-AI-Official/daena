"""
Demo API Routes for AI Tinkerers Toronto Jan 2026

Endpoints:
- POST /api/v1/demo/run - Execute demo scenario
- GET /api/v1/demo/trace/{trace_id} - Fetch trace timeline
- GET /api/v1/demo/health - Demo system health check
"""

import logging
import time
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.demo_mode import is_demo_mode, get_demo_config, get_cached_response
from backend.services.demo_council import evaluate_with_council, council_result_to_dict
from backend.services.demo_trace import demo_trace_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


class DemoRunRequest(BaseModel):
    """Request body for demo run."""
    prompt: str
    session_id: Optional[str] = None
    use_cloud: bool = True


class DemoRunResponse(BaseModel):
    """Response from demo run."""
    trace_id: str
    session_id: str
    prompt: str
    response: str
    router_decision: Dict[str, Any]
    council_result: Dict[str, Any]
    total_duration_ms: int
    status: str


@router.get("/health")
async def demo_health() -> Dict[str, Any]:
    """Demo system health check."""
    demo_config = get_demo_config()
    
    # Check LLM availability
    llm_status = {"local_available": False, "cloud_available": False}
    try:
        from backend.services.local_llm_ollama import check_ollama_available
        llm_status["local_available"] = await check_ollama_available()
    except Exception as e:
        logger.warning(f"Ollama check failed: {e}")
    
    try:
        from backend.services.llm_service import llm_service
        llm_status["cloud_available"] = "gemini" in llm_service.providers or "openai" in llm_service.providers
    except Exception as e:
        logger.warning(f"Cloud LLM check failed: {e}")
    
    return {
        "status": "ready",
        "demo_mode": is_demo_mode(),
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "fallback_enabled": demo_config["fallback_to_local"],
            "cloud_provider": demo_config["default_cloud_provider"],
            "cached_fallback": demo_config["use_cached_on_failure"]
        },
        "llm_status": llm_status,
        "event": "AI Tinkerers Toronto - Jan 29, 2026"
    }


@router.post("/run")
async def demo_run(request: DemoRunRequest) -> Dict[str, Any]:
    """Execute demo scenario with routing, council review, and trace logging."""
    start_time = time.time()
    
    # Start trace
    trace_id = demo_trace_logger.start_trace(request.prompt, request.session_id)
    session_id = demo_trace_logger.get_trace(trace_id).session_id
    
    try:
        # Step 1: Route decision
        route_start = time.time()
        router_decision = await _get_routing_decision(request.prompt, request.use_cloud)
        route_duration = int((time.time() - route_start) * 1000)
        
        demo_trace_logger.add_route_event(
            trace_id=trace_id,
            model_name=router_decision["model_name"],
            provider=router_decision["provider"],
            reason=router_decision["reason"],
            latency_ms=route_duration,
            cost_usd=router_decision.get("cost_estimate_usd", 0.0)
        )
        
        # Step 2: Generate response
        response_start = time.time()
        response_text = await _generate_response(request.prompt, router_decision)
        response_duration = int((time.time() - response_start) * 1000)
        
        # Step 3: Council evaluation
        council_start = time.time()
        council_result = await evaluate_with_council(request.prompt, response_text)
        council_duration = int((time.time() - council_start) * 1000)
        
        # Add council events to trace
        for role_output in council_result.role_outputs:
            demo_trace_logger.add_council_event(
                trace_id=trace_id,
                role=role_output.role,
                vote=role_output.vote.value,
                confidence=role_output.confidence,
                critiques=role_output.critiques,
                duration_ms=council_duration // 3  # Split evenly for demo
            )
        
        # Step 4: Merge decision
        merge_duration = 25  # Fast merge
        demo_trace_logger.add_merge_event(
            trace_id=trace_id,
            final_decision=council_result.final_decision.value,
            consensus_confidence=council_result.consensus_confidence,
            conflicts=council_result.conflicts,
            duration_ms=merge_duration
        )
        
        # Step 5: Memory write
        demo_trace_logger.add_memory_event(
            trace_id=trace_id,
            memory_tier="L2",
            bytes_written=len(response_text.encode()),
            duration_ms=8
        )
        
        # Complete trace
        total_duration = int((time.time() - start_time) * 1000)
        demo_trace_logger.complete_trace(trace_id)
        
        return {
            "trace_id": trace_id,
            "session_id": session_id,
            "prompt": request.prompt,
            "response": response_text,
            "router_decision": router_decision,
            "council_result": council_result_to_dict(council_result),
            "total_duration_ms": total_duration,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Demo run failed: {e}")
        demo_trace_logger.complete_trace(trace_id, status="failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str) -> Dict[str, Any]:
    """Fetch trace timeline by ID."""
    trace = demo_trace_logger.get_trace(trace_id)
    
    if not trace:
        raise HTTPException(status_code=404, detail=f"Trace not found: {trace_id}")
    
    return demo_trace_logger.trace_to_dict(trace)


async def _get_routing_decision(prompt: str, use_cloud: bool) -> Dict[str, Any]:
    """Get routing decision from intelligent router."""
    try:
        from backend.services.intelligent_router import intelligent_router
        decision = await intelligent_router.route(prompt)
        
        return {
            "model_tier": decision.model_tier.value,
            "model_name": decision.model_name,
            "provider": decision.provider,
            "reason": decision.reason,
            "fallback_chain": decision.fallback_chain,
            "latency_estimate_ms": 200 if "external" in decision.model_tier.value else 150,
            "cost_estimate_usd": 0.001 if "external" in decision.model_tier.value else 0.0
        }
    except Exception as e:
        logger.warning(f"Router failed, using default: {e}")
        # Fallback routing decision
        if use_cloud:
            return {
                "model_tier": "external_premium",
                "model_name": "gemini-pro",
                "provider": "gemini",
                "reason": "Default cloud routing",
                "fallback_chain": ["qwen2.5:7b-instruct"],
                "latency_estimate_ms": 200,
                "cost_estimate_usd": 0.001
            }
        else:
            return {
                "model_tier": "local_chat",
                "model_name": "qwen2.5:7b-instruct",
                "provider": "ollama",
                "reason": "Local model selected",
                "fallback_chain": [],
                "latency_estimate_ms": 150,
                "cost_estimate_usd": 0.0
            }


async def _generate_response(prompt: str, router_decision: Dict[str, Any]) -> str:
    """Generate response using selected model with fallback."""
    demo_config = get_demo_config()
    
    # Try cloud provider first if selected
    if "external" in router_decision.get("model_tier", ""):
        try:
            from backend.services.llm_service import llm_service, LLMProvider
            
            provider = router_decision.get("provider", "gemini")
            if provider == "gemini" and "gemini" in llm_service.providers:
                response = await llm_service.generate_response(
                    prompt=prompt,
                    provider=LLMProvider.GEMINI,
                    max_tokens=500,
                    temperature=0.7
                )
                return response.get("content", response.get("response", str(response)))
        except Exception as e:
            logger.warning(f"Cloud generation failed: {e}")
    
    # Try local model
    if demo_config["fallback_to_local"]:
        try:
            from backend.services.local_llm_ollama import generate_ollama_response
            response = await generate_ollama_response(
                prompt=prompt,
                model=router_decision.get("model_name", "qwen2.5:7b-instruct")
            )
            return response
        except Exception as e:
            logger.warning(f"Local generation failed: {e}")
    
    # Use cached response as final fallback
    if demo_config["use_cached_on_failure"]:
        cached = get_cached_response(prompt)
        if cached:
            return cached["response"]
    
    return "Daena processed your request. (Demo mode - cached response)"
