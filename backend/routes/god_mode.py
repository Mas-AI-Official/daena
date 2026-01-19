"""
God Mode API Routes
Unified API for NBMF, Router, Verifier, DCP, and Change Control systems
"""

from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime

# Import god mode systems
try:
    from Core.memory.nbmf_tiers import nbmf_system, MemoryTier, MemoryEntry
    from Core.routing.router_agent import router_agent, TaskType
    from Core.verify.verifier_agent import verifier_agent, FactClaim, SourceGrade
    from Core.governance.dcp_profiles import dcp_manager, DecisionConstraintProfile
    from Core.governance.change_control import change_control, ChangeProposal, ChangeProposalStatus
except ImportError as e:
    print(f"⚠️ God Mode imports failed: {e}")
    # Fallback for missing modules
    nbmf_system = None
    router_agent = None
    verifier_agent = None
    dcp_manager = None
    change_control = None

router = APIRouter(prefix="/api/v1/god-mode", tags=["God Mode System"])


# ========== Request/Response Models ==========

class MemoryStoreRequest(BaseModel):
    tier: str  # T0_EPHEMERAL, T1_WORKING, T2_PROJECT, etc.
    content: str
    source: str
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    evidence: Optional[List[str]] = None


class RouterDispatchRequest(BaseModel):
    task_type: str  # deep_reasoning, code_generation, etc.
    prompt: str
    constraints: Optional[Dict[str, Any]] = None


class VerifyRequest(BaseModel):
    claim: str
    source: str
    context: Optional[Dict[str, Any]] = None
    additional_sources: Optional[List[str]] = None


class ChangeProposalRequest(BaseModel):
    title: str
    description: str
    what_changes: str
    why_changes: str
    impact_analysis: str
    risks: List[str]
    rollback_plan: str
    evaluation_criteria: List[str]


class ApprovalRequest(BaseModel):
    proposal_id: str
    approver: str
    notes: Optional[str] = None


# ========== God Mode Status ==========

@router.get("/status")
async def get_god_mode_status():
    """Get overall god mode system status"""
    try:
        status = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "systems": {
                "nbmf": {
                    "available": nbmf_system is not None,
                    "stats": nbmf_system.get_stats() if nbmf_system else None
                },
                "router": {
                    "available": router_agent is not None,
                    "models_count": len(router_agent.models) if router_agent else 0
                },
                "verifier": {
                    "available": verifier_agent is not None,
                    "sources_registered": len(verifier_agent.known_sources) if verifier_agent else 0
                },
                "dcp": {
                    "available": dcp_manager is not None,
                    "profiles_count": len(dcp_manager.profiles) if dcp_manager else 0
                },
                "change_control": {
                    "available": change_control is not None,
                    "pending_approvals": len(change_control.get_pending_approvals()) if change_control else 0
                }
            },
            "laws_enforced": {
                "LAW_1_REALITY_FIRST": True,
                "LAW_2_EXECUTION_OVER_AESTHETICS": True,
                "LAW_3_NO_COSPLAY": True,
                "LAW_4_FOUNDER_OVERRIDE": True,
                "LAW_5_MEMORY_SANCTITY": True,
                "LAW_6_ROUTER_AWARENESS": True,
                "LAW_7_SCOUT_VERIFY_SYNTHESIZE": True,
                "LAW_8_SAFE_IMPROVEMENT": True,
                "LAW_9_LOW_LATENCY": True
            }
        }
        
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get god mode status: {str(e)}")


# ========== NBMF Memory Endpoints ==========

@router.get("/memory/tiers")
async def get_memory_tiers():
    """List all memory tiers and their stats"""
    if not nbmf_system:
        raise HTTPException(status_code=503, detail="NBMF system not available")
    
    try:
        stats = nbmf_system.get_stats()
        return {
            "success": True,
            "tiers": stats["tiers"],
            "total_entries": stats["total_entries"],
            "last_cleanup": stats["last_cleanup"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/store")
async def store_memory(request: MemoryStoreRequest):
    """Store a memory entry in specified tier"""
    if not nbmf_system:
        raise HTTPException(status_code=503, detail="NBMF system not available")
    
    try:
        # Parse tier
        tier = MemoryTier(request.tier)
        
        entry = nbmf_system.store(
            tier=tier,
            content=request.content,
            source=request.source,
            metadata=request.metadata,
            tags=request.tags,
            evidence=request.evidence
        )
        
        if not entry:
            raise HTTPException(status_code=403, detail=f"Permission denied: {request.source} cannot write to {tier}")
        
        return {
            "success": True,
            "entry_id": entry.id,
            "tier": entry.tier.value,
            "expires_at": entry.expires_at.isoformat() if entry.expires_at else None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/retrieve")
async def retrieve_memory(
    tier: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 100
):
    """Retrieve memory entries"""
    if not nbmf_system:
        raise HTTPException(status_code=503, detail="NBMF system not available")
    
    try:
        tier_enum = MemoryTier(tier) if tier else None
        tags_list = tags.split(",") if tags else None
        
        entries = nbmf_system.retrieve(
            tier=tier_enum,
            tags=tags_list,
            limit=limit
        )
        
        return {
            "success": True,
            "count": len(entries),
            "entries": [
                {
                    "id": e.id,
                    "tier": e.tier.value,
                    "content": e.content[:200] + "..." if len(e.content) > 200 else e.content,
                    "source": e.source,
                    "created_at": e.created_at.isoformat(),
                    "verified": e.verified,
                    "verification_score": e.verification_score,
                    "tags": e.tags
                }
                for e in entries
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/promote-to-t2")
async def promote_to_t2(
    entry_id: str = Body(...),
    agent_type: str = Body(...),
    verification_score: float = Body(...),
    evidence: List[str] = Body(...)
):
    """Promote T0/T1 entry to T2 (requires verifier or founder)"""
    if not nbmf_system:
        raise HTTPException(status_code=503, detail="NBMF system not available")
    
    try:
        success = nbmf_system.promote_to_t2(
            entry_id=entry_id,
            agent_type=agent_type,
            verification_score=verification_score,
            evidence=evidence
        )
        
        if not success:
            raise HTTPException(status_code=403, detail=f"{agent_type} cannot promote to T2 or entry not found")
        
        return {"success": True, "message": f"Promoted {entry_id} to T2"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Router Agent Endpoints ==========

@router.post("/router/dispatch")
async def dispatch_task(request: RouterDispatchRequest):
    """Route and execute task on optimal model"""
    if not router_agent:
        raise HTTPException(status_code=503, detail="Router agent not available")
    
    try:
        task_type = TaskType(request.task_type)
        
        result = await router_agent.route_and_execute(
            task_type=task_type,
            prompt=request.prompt,
            constraints=request.constraints
        )
        
        return {
            "success": result.get("success", False),
            "response": result.get("response"),
            "model_used": result.get("model_used"),
            "task_type": result.get("task_type"),
            "error": result.get("error")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {request.task_type}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/router/models")
async def list_models():
    """List available models and their capabilities"""
    if not router_agent:
        raise HTTPException(status_code=503, detail="Router agent not available")
    
    try:
        models_data = []
        for name, profile in router_agent.models.items():
            models_data.append({
                "name": profile.name,
                "provider": profile.provider,
                "capabilities": [c.value for c in profile.capabilities],
                "context_limit": profile.context_limit,
                "speed": profile.speed,
                "hallucination_tendency": profile.hallucination_tendency
            })
        
        return {
            "success": True,
            "count": len(models_data),
            "models": models_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Verifier Agent Endpoints ==========

@router.post("/verify")
async def verify_claim(request: VerifyRequest):
    """Verify a factual claim"""
    if not verifier_agent:
        raise HTTPException(status_code=503, detail="Verifier agent not available")
    
    try:
        claim = FactClaim(
            claim=request.claim,
            source=request.source,
            timestamp=datetime.now(),
            context=request.context or {}
        )
        
        result = await verifier_agent.verify(
            claim=claim,
            check_corroboration=bool(request.additional_sources),
            additional_sources=request.additional_sources
        )
        
        return {
            "success": True,
            "verified": result.verified,
            "confidence_score": result.confidence_score,
            "grade": result.grade.value,
            "provenance": result.provenance,
            "recency_check": result.recency_check,
            "risk_assessment": result.risk_assessment,
            "recommendations": result.recommendations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== DCP Profiles Endpoints ==========

@router.get("/dcp/profiles")
async def list_dcp_profiles():
    """List all available DCP profiles"""
    if not dcp_manager:
        raise HTTPException(status_code=503, detail="DCP manager not available")
    
    try:
        profiles_list = []
        for name, profile in dcp_manager.profiles.items():
            profiles_list.append({
                "name": profile.name,
                "description": profile.description,
                "objective_function": profile.objective_function,
                "weight": profile.weight,
                "constraints_count": len(profile.constraints),
                "rejection_triggers_count": len(profile.rejection_triggers)
            })
        
        return {
            "success": True,
            "count": len(profiles_list),
            "profiles": profiles_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dcp/profiles/{profile_name}")
async def get_dcp_profile(profile_name: str):
    """Get detailed DCP profile"""
    if not dcp_manager:
        raise HTTPException(status_code=503, detail="DCP manager not available")
    
    try:
        profile = dcp_manager.get_profile(profile_name)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_name}")
        
        return {
            "success": True,
            "profile": profile.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dcp/evaluate")
async def evaluate_decision(
    decision: str = Body(...),
    council_type: str = Body("default"),
    advisor_count: int = Body(5)
):
    """Evaluate a decision against DCP profiles"""
    if not dcp_manager:
        raise HTTPException(status_code=503, detail="DCP manager not available")
    
    try:
        # Get council profiles
        profiles = dcp_manager.get_council_profiles(
            council_type=council_type,
            count=advisor_count
        )
        
        # Evaluate
        result = dcp_manager.evaluate_decision(
            decision=decision,
            profiles=profiles,
            context={"council_type": council_type}
        )
        
        return {
            "success": True,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Change Control Endpoints ==========

@router.post("/change-control/propose")
async def propose_change(request: ChangeProposalRequest):
    """Create a new change proposal"""
    if not change_control:
        raise HTTPException(status_code=503, detail="Change control not available")
    
    try:
        proposal = change_control.create_proposal(
            title=request.title,
            description=request.description,
            what_changes=request.what_changes,
            why_changes=request.why_changes,
            impact_analysis=request.impact_analysis,
            risks=request.risks,
            rollback_plan=request.rollback_plan,
            evaluation_criteria=request.evaluation_criteria,
            proposed_by="api_user"  # TODO: Get from auth
        )
        
        # Auto-submit for approval
        change_control.submit_for_approval(proposal.id)
        
        return {
            "success": True,
            "proposal_id": proposal.id,
            "status": proposal.status.value,
            "message": "Proposal created and submitted for Founder approval"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/change-control/approve")
async def approve_change(request: ApprovalRequest):
    """Approve a change proposal (Founder only)"""
    if not change_control:
        raise HTTPException(status_code=503, detail="Change control not available")
    
    try:
        success = change_control.approve(
            proposal_id=request.proposal_id,
            approver=request.approver,
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(status_code=403, detail="Approval denied - only Founder can approve or proposal not found")
        
        return {
            "success": True,
            "message": "Proposal approved by Founder"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/change-control/pending")
async def get_pending_approvals():
    """Get all proposals pending Founder approval"""
    if not change_control:
        raise HTTPException(status_code=503, detail="Change control not available")
    
    try:
        pending = change_control.get_pending_approvals()
        
        return {
            "success": True,
            "count": len(pending),
            "proposals": [
                {
                    "id": p.id,
                    "title": p.title,
                    "proposed_by": p.proposed_by,
                    "proposed_at": p.proposed_at.isoformat(),
                    "risks_count": len(p.risks)
                }
                for p in pending
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/change-control/proposals/{proposal_id}")
async def get_proposal_details(proposal_id: str):
    """Get detailed proposal information"""
    if not change_control:
        raise HTTPException(status_code=503, detail="Change control not available")
    
    try:
        proposal = change_control.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal not found: {proposal_id}")
        
        return {
            "success": True,
            "proposal": proposal.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/change-control/hard-policies")
async def get_hard_policies():
    """Get all HARD-CODE policies"""
    if not change_control:
        raise HTTPException(status_code=503, detail="Change control not available")
    
    try:
        policies = change_control.get_hard_policies()
        
        return {
            "success": True,
            "count": len(policies),
            "policies": policies
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
