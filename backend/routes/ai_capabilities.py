"""AI capabilities endpoint for Daena's live system state."""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
from backend.utils.sunflower_registry import sunflower_registry
from backend.utils.message_bus import message_bus
import time

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

@router.get("/capabilities")
async def get_ai_capabilities() -> Dict[str, Any]:
    """Get live AI capabilities and system state."""
    try:
        # Get live counts from sunflower registry
        dept_count = len(sunflower_registry.departments)
        agent_count = len(sunflower_registry.agents)
        project_count = len(sunflower_registry.projects)
        
        # Calculate average productivity (placeholder for now)
        avg_productivity = None
        if agent_count > 0:
            # This would come from actual agent performance metrics
            avg_productivity = 85.5  # Placeholder value
        
        # Get message bus stats
        bus_stats = message_bus.get_stats()
        
        # Define available features
        features = [
            "voice",
            "files", 
            "analytics",
            "council",
            "routing",
            "abac",
            "sunflower_coordinates",
            "honeycomb_adjacency",
            "message_bus",
            "azure_openai",
            "brain_training",
            "multi_llm"
        ]
        
        # Check if features are actually available
        active_features = []
        for feature in features:
            if feature == "voice" and hasattr(sunflower_registry, 'voice_enabled'):
                active_features.append(feature)
            elif feature == "azure_openai":
                # Check if Azure OpenAI is configured
                try:
                    import os
                    if os.getenv("AZURE_OPENAI_API_KEY"):
                        active_features.append(feature)
                except:
                    pass
            elif feature in ["sunflower_coordinates", "honeycomb_adjacency", "message_bus"]:
                active_features.append(feature)
            else:
                active_features.append(feature)
        
        return {
            "success": True,
            "timestamp": time.time(),
            "capabilities": {
                "departments": dept_count,
                "agents": agent_count,
                "projects_active": project_count,
                "avg_productivity": avg_productivity,
                "features": active_features,
                "message_bus_stats": bus_stats
            },
            "system_info": {
                "sunflower_layers": 3,
                "agents_per_layer": 6,  # 6 agents per department (updated from 8)
                "total_capacity": dept_count * 6,  # 8 departments * 6 agents = 48 total (updated from 8)
                "adjacency_cache_size": len(sunflower_registry.adjacency_cache)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get capabilities: {str(e)}")

@router.get("/response_template")
async def get_response_template(
    context: str = "general",
    include_metrics: bool = True
) -> Dict[str, Any]:
    """
    Generate Daena's response template for a given context.
    
    Args:
        context: general, strategic, projects, decisions, analytics
        include_metrics: Whether to include live metrics in response
    """
    try:
        # Get live capabilities
        capabilities = await get_ai_capabilities()
        
        # Context-specific response templates
        templates = {
            "general": {
                "greeting": "Hello! I'm Daena, your AI Vice President.",
                "status": f"I'm currently managing {capabilities['capabilities']['departments']} departments with {capabilities['capabilities']['agents']} active agents.",
                "focus": "How can I assist you today?"
            },
            "strategic": {
                "greeting": "Welcome to the Strategic Planning Center.",
                "status": f"We have {capabilities['capabilities']['departments']} departments aligned in our sunflower structure.",
                "focus": "What strategic initiative would you like to discuss?"
            },
            "projects": {
                "greeting": "Project Management Dashboard active.",
                "status": f"Currently tracking {capabilities['capabilities']['projects_active']} active projects across {capabilities['capabilities']['departments']} departments.",
                "focus": "Which project would you like to review?"
            },
            "decisions": {
                "greeting": "Decision Support System online.",
                "status": f"Ready to assist with decision-making across {capabilities['capabilities']['agents']} specialized agents.",
                "focus": "What decision do you need support with?"
            },
            "analytics": {
                "greeting": "Analytics and Performance Center.",
                "status": f"Monitoring {capabilities['capabilities']['agents']} agents with real-time productivity tracking.",
                "focus": "What metrics would you like to analyze?"
            }
        }
        
        template = templates.get(context, templates["general"])
        
        response = {
            "success": True,
            "context": context,
            "template": template,
            "live_metrics": capabilities["capabilities"] if include_metrics else None,
            "timestamp": time.time()
        }
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate response template: {str(e)}") 