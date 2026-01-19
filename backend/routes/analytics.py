"""
Analytics API Routes
Serve real-time system metrics and historical data
"""
from fastapi import APIRouter
from typing import Dict, List
import random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

@router.get("/metrics")
async def get_metrics():
    """Get current system metrics"""
    return {
        "efficiency": 94.2,
        "active_agents": 48,
        "tasks_completed": 1243,
        "uptime_hours": 72,
        "cost_saved": 15420.50
    }

@router.get("/history/efficiency")
async def get_efficiency_history():
    """Get efficiency history for line chart"""
    # Mock data for last 24 hours
    now = datetime.now()
    labels = [(now - timedelta(hours=i)).strftime("%H:00") for i in range(24, 0, -1)]
    data = [random.uniform(85, 98) for _ in range(24)]
    return {
        "labels": labels,
        "data": data
    }

@router.get("/department/performance")
async def get_dept_performance():
    """Get performance by department"""
    return {
        "labels": ["Eng", "Product", "Sales", "Mktg", "Finance", "HR", "Legal", "Success"],
        "data": [96, 92, 88, 91, 95, 89, 94, 93]
    }

@router.get("/tasks/distribution")
async def get_task_distribution():
    """Get task distribution by type"""
    return {
        "labels": ["Research", "Coding", "Communication", "Analysis", "Administrative"],
        "data": [30, 25, 20, 15, 10]
    }
