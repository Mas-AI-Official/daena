"""
Pricing Lab - Metrics Tracking and Experimentation

Add-On 5: Pricing experiments, A/B testing, and revenue metrics.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pricing", tags=["Pricing Lab"])


# ═══════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════

class PricingExperiment(BaseModel):
    id: str
    name: str
    description: str
    segment: str  # e.g., "new_users", "enterprise"
    status: str  # active, paused, completed
    variants: List[Dict]  # [{"name": "A", "price": 299}, {"name": "B", "price": 349}]
    start_date: datetime = Field(default_factory=datetime.utcnow)
    end_date: Optional[datetime] = None


class ExperimentResult(BaseModel):
    experiment_id: str
    variant: str
    views: int
    conversions: int
    revenue: float
    conversion_rate: float
    revenue_per_user: float


class RevenueMetrics(BaseModel):
    total_revenue: float
    mrr: float
    arr: float
    cac: float
    ltv: float
    churn_rate: float
    active_customers: int


# ═══════════════════════════════════════════════════════════════════════
# Storage
# ═══════════════════════════════════════════════════════════════════════

EXPERIMENTS = {}
RESULTS = {}  # experiment_id -> {variant -> stats}


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

@router.post("/experiments")
async def create_experiment(experiment: PricingExperiment):
    """Create a new pricing experiment"""
    EXPERIMENTS[experiment.id] = experiment
    
    # Initialize results
    RESULTS[experiment.id] = {}
    for variant in experiment.variants:
        RESULTS[experiment.id][variant["name"]] = {
            "views": 0,
            "conversions": 0,
            "revenue": 0.0
        }
    
    return {"success": True, "id": experiment.id}


@router.get("/experiments")
async def list_experiments():
    """List all experiments"""
    return list(EXPERIMENTS.values())


@router.get("/experiments/{experiment_id}/results")
async def get_experiment_results(experiment_id: str):
    """Get results for an experiment"""
    if experiment_id not in EXPERIMENTS:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    raw_results = RESULTS.get(experiment_id, {})
    formatted_results = []
    
    for variant, stats in raw_results.items():
        views = stats["views"]
        conversions = stats["conversions"]
        revenue = stats["revenue"]
        
        formatted_results.append(ExperimentResult(
            experiment_id=experiment_id,
            variant=variant,
            views=views,
            conversions=conversions,
            revenue=revenue,
            conversion_rate=round((conversions / views * 100) if views > 0 else 0, 2),
            revenue_per_user=round((revenue / conversions) if conversions > 0 else 0, 2)
        ))
    
    return {"results": formatted_results}


@router.post("/experiments/{experiment_id}/track")
async def track_event(
    experiment_id: str,
    variant: str = Body(...),
    event_type: str = Body(...),  # view, conversion
    revenue: float = Body(0.0)
):
    """Track an event for an experiment"""
    if experiment_id not in EXPERIMENTS:
        raise HTTPException(status_code=404, detail="Experiment not found")
    
    if variant not in RESULTS[experiment_id]:
        raise HTTPException(status_code=400, detail="Invalid variant")
    
    stats = RESULTS[experiment_id][variant]
    
    if event_type == "view":
        stats["views"] += 1
    elif event_type == "conversion":
        stats["conversions"] += 1
        stats["revenue"] += revenue
    
    return {"success": True}


@router.get("/metrics")
async def get_revenue_metrics():
    """Get overall revenue metrics"""
    # Mock data for now
    return RevenueMetrics(
        total_revenue=125000.0,
        mrr=15000.0,
        arr=180000.0,
        cac=450.0,
        ltv=2500.0,
        churn_rate=2.5,
        active_customers=120
    )


@router.get("/suggestions")
async def get_pricing_suggestions():
    """Get AI-generated pricing suggestions"""
    return {
        "suggestions": [
            {
                "title": "Increase Enterprise Tier",
                "reasoning": "Enterprise users have 0% churn and high usage. Price elasticity suggests room for 20% increase.",
                "confidence": "High",
                "impact": "+$5k MRR"
            },
            {
                "title": "Introduce Starter Plan",
                "reasoning": "High drop-off at pricing page for small teams. $49/mo plan could capture this segment.",
                "confidence": "Medium",
                "impact": "+$2k MRR"
            }
        ]
    }
