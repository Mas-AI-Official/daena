"""Routing health and metrics endpoint."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.utils.message_bus import message_bus
from backend.services.honeycomb_routing import honeycomb_routing
from backend.utils.sunflower_registry import sunflower_registry
import time

router = APIRouter(prefix="/health", tags=["routing"])

@router.get("/routing")
async def get_routing_health():
    """Get comprehensive routing health and metrics."""
    try:
        # Get message bus stats
        bus_stats = message_bus.get_stats()
        
        # Get honeycomb routing stats
        honeycomb_stats = honeycomb_routing.get_adjacency_stats()
        
        # Get sunflower registry stats
        registry_stats = {
            "departments": len(sunflower_registry.departments),
            "agents": len(sunflower_registry.agents),
            "projects": len(sunflower_registry.projects),
            "cells": len(sunflower_registry.cells),
            "adjacency_cache_size": len(sunflower_registry.adjacency_cache)
        }
        
        # Calculate routing efficiency
        total_messages = bus_stats.get("total_messages", 0)
        local_routes = bus_stats.get("local_routes", 0)
        neighbor_routes = bus_stats.get("neighbor_routes", 0)
        cmp_fallbacks = bus_stats.get("cmp_fallbacks", 0)
        
        if total_messages > 0:
            local_efficiency = round((local_routes / total_messages) * 100, 2)
            neighbor_efficiency = round((neighbor_routes / total_messages) * 100, 2)
            cmp_efficiency = round((cmp_fallbacks / total_messages) * 100, 2)
        else:
            local_efficiency = neighbor_efficiency = cmp_efficiency = 0.0
        
        # Health status
        health_status = "healthy"
        if cmp_efficiency > 50:
            health_status = "degraded"
        if cmp_efficiency > 80:
            health_status = "critical"
        
        # Performance metrics
        current_time = time.time()
        performance_metrics = {
            "uptime_seconds": current_time - bus_stats.get("start_time", current_time),
            "messages_per_second": total_messages / max(1, (current_time - bus_stats.get("start_time", current_time))),
            "queue_depth": bus_stats.get("queue_count", 0),
            "active_agents": bus_stats.get("agent_count", 0),
            "neighbor_connections": bus_stats.get("neighbor_count", 0)
        }
        
        # Routing topology
        routing_topology = {
            "total_cells": honeycomb_stats.get("total_cells", 0),
            "total_neighbors": honeycomb_stats.get("total_neighbors", 0),
            "average_neighbors": honeycomb_stats.get("average_neighbors", 0),
            "max_neighbors": honeycomb_stats.get("max_neighbors", 0),
            "connectivity_score": round(
                honeycomb_stats.get("total_neighbors", 0) / 
                max(1, honeycomb_stats.get("total_cells", 1)) / 6 * 100, 2
            )
        }
        
        # Sample adjacency for verification
        sample_adjacency = {}
        if sunflower_registry.adjacency_cache:
            sample_items = list(sunflower_registry.adjacency_cache.items())[:3]
            for cell_id, neighbors in sample_items:
                sample_adjacency[cell_id] = {
                    "neighbors": neighbors,
                    "neighbor_count": len(neighbors),
                    "position": honeycomb_routing.get_cell_position(cell_id)
                }
        
        return {
            "success": True,
            "timestamp": time.time(),
            "health_status": health_status,
            "message_bus": {
                **bus_stats,
                "efficiency": {
                    "local_routes": local_efficiency,
                    "neighbor_routes": neighbor_efficiency,
                    "cmp_fallbacks": cmp_efficiency
                }
            },
            "honeycomb_routing": honeycomb_stats,
            "sunflower_registry": registry_stats,
            "performance": performance_metrics,
            "topology": routing_topology,
            "sample_adjacency": sample_adjacency,
            "recommendations": _generate_recommendations(
                local_efficiency, neighbor_efficiency, cmp_efficiency, routing_topology
            )
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get routing health: {str(e)}")

def _generate_recommendations(local_eff: float, neighbor_eff: float, 
                            cmp_eff: float, topology: Dict[str, Any]) -> list:
    """Generate routing optimization recommendations."""
    recommendations = []
    
    if local_eff < 30:
        recommendations.append("Low local routing efficiency - consider optimizing local handlers")
    
    if neighbor_eff < 20:
        recommendations.append("Low neighbor routing - check adjacency relationships")
    
    if cmp_eff > 50:
        recommendations.append("High CMP fallback usage - investigate local routing failures")
    
    if topology.get("connectivity_score", 0) < 70:
        recommendations.append("Low connectivity score - consider rebuilding adjacency")
    
    if topology.get("average_neighbors", 0) < 3:
        recommendations.append("Low average neighbors - may impact routing efficiency")
    
    if not recommendations:
        recommendations.append("Routing system is performing optimally")
    
    return recommendations

@router.get("/routing/simple")
async def get_simple_routing_health():
    """Get simplified routing health status."""
    try:
        bus_stats = message_bus.get_stats()
        total_messages = bus_stats.get("total_messages", 0)
        local_routes = bus_stats.get("local_routes", 0)
        cmp_fallbacks = bus_stats.get("cmp_fallbacks", 0)
        
        if total_messages == 0:
            return {
                "status": "idle",
                "message": "No routing activity yet"
            }
        
        local_ratio = local_routes / total_messages if total_messages > 0 else 0
        cmp_ratio = cmp_fallbacks / total_messages if total_messages > 0 else 0
        
        if local_ratio > 0.7:
            status = "excellent"
        elif local_ratio > 0.5:
            status = "good"
        elif local_ratio > 0.3:
            status = "fair"
        else:
            status = "poor"
        
        return {
            "status": status,
            "total_messages": total_messages,
            "local_routing_ratio": round(local_ratio, 3),
            "cmp_fallback_ratio": round(cmp_ratio, 3),
            "efficiency_score": round(local_ratio * 100, 1)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        } 