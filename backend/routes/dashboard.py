
from fastapi import APIRouter, Depends
import math
from typing import List, Dict, Any

router = APIRouter()

# --- Shared Constants/Stubs ---
DEPARTMENTS = [
  { "id": 'engineering', "name": 'Engineering', "color": '#3B82F6' },
  { "id": 'sales', "name": 'Sales', "color": '#10B981' },
  { "id": 'marketing', "name": 'Marketing', "color": '#F59E0B' },
  { "id": 'product', "name": 'Product', "color": '#8B5CF6' },
  { "id": 'legal', "name": 'Legal', "color": '#EF4444' },
  { "id": 'hr', "name": 'HR', "color": '#EC4899' },
  { "id": 'operations', "name": 'Operations', "color": '#06B6D4' },
  { "id": 'shadow', "name": 'Shadow', "color": '#1F2937' },
]

async def get_agent_count(dept_id): return 6
async def get_dept_status(dept_id): return "active"
async def get_dept_tools(dept_id): return ["tool1", "tool2"]
async def get_pending_approval_count(): return 3

def generate_metatron_connections(depts):
     # Simple mock for visualization data
    return []

@router.get("/dashboard/sunflower")
async def get_sunflower_data():
    """Get 3D dashboard data with Fibonacci positioning"""
    
    departments_data = []
    for i, dept in enumerate(DEPARTMENTS):
        # Fibonacci positioning logic mirrored from frontend for consistency
        angle = i * 137.5  # Golden angle
        radius = 3 * (i ** 0.5) * 1.618  # Golden ratio
        
        departments_data.append({
            "id": dept["id"],
            "name": dept["name"],
            "color": dept["color"],
            "position": {
                "x": radius * math.cos(math.radians(angle)),
                "y": radius * math.sin(math.radians(angle)),
                "z": math.sin(i * 0.5) * 2,
            },
            "agents": await get_agent_count(dept["id"]),
            "status": await get_dept_status(dept["id"]),
            "tools": await get_dept_tools(dept["id"]),
        })
    
    return {
        "core": {
            "status": "active",
            "active_agents": sum(d["agents"] for d in departments_data),
            "pending_approvals": await get_pending_approval_count(),
        },
        "departments": departments_data,
        "connections": generate_metatron_connections(departments_data),
    }
