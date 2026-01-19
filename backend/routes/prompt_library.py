"""
Prompt Library API endpoints (Phase E).
"""

import json
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from backend.services.prompt_library import prompt_library

router = APIRouter(prefix="/api/v1/prompts", tags=["Prompt Library"])


class RegisterTemplateRequest(BaseModel):
    domain: str
    name: str
    template: str
    version: str = "1.0.0"
    variables: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class RenderTemplateRequest(BaseModel):
    template_id: str
    variables: Dict[str, Any]


class RecordOutcomeRequest(BaseModel):
    prompt_id: str
    task: str
    result: str
    metrics: Dict[str, Any]
    success: bool


class ProposeUpgradeRequest(BaseModel):
    template_id: str
    improved_template: str
    reason: str
    evidence: Optional[Dict[str, Any]] = None


@router.get("/")
async def list_templates(domain: Optional[str] = None) -> Dict[str, Any]:
    """List all prompt templates, optionally filtered by domain"""
    templates = prompt_library.list_templates(domain=domain)
    return {
        "templates": [
            {
                "id": t.id,
                "domain": t.domain,
                "name": t.name,
                "version": t.version,
                "evaluation_score": t.evaluation_score,
                "usage_count": t.usage_count,
                "success_count": t.success_count,
                "variables": t.variables,
            }
            for t in templates
        ],
        "domains": list(set(t.domain for t in prompt_library.templates.values()))
    }


@router.get("/domains")
async def list_domains() -> Dict[str, Any]:
    """List all domains"""
    domains = list(set(t.domain for t in prompt_library.templates.values()))
    return {"domains": domains}


@router.get("/domains/{domain}/best")
async def get_best_template(domain: str) -> Dict[str, Any]:
    """Get the best template for a domain"""
    template = prompt_library.get_best_template(domain)
    if not template:
        raise HTTPException(status_code=404, detail=f"No templates found for domain: {domain}")
    
    return {
        "id": template.id,
        "domain": template.domain,
        "name": template.name,
        "version": template.version,
        "template": template.template,
        "evaluation_score": template.evaluation_score,
        "usage_count": template.usage_count,
        "success_count": template.success_count,
        "variables": template.variables,
    }


@router.get("/{template_id}")
async def get_template(template_id: str) -> Dict[str, Any]:
    """Get a prompt template by ID"""
    template = prompt_library.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "id": template.id,
        "domain": template.domain,
        "name": template.name,
        "version": template.version,
        "template": template.template,
        "evaluation_score": template.evaluation_score,
        "usage_count": template.usage_count,
        "success_count": template.success_count,
        "variables": template.variables,
        "metadata": template.metadata,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.post("/register")
async def register_template(request: RegisterTemplateRequest) -> Dict[str, Any]:
    """Register a new prompt template"""
    template = prompt_library.register_template(
        domain=request.domain,
        name=request.name,
        template=request.template,
        version=request.version,
        variables=request.variables,
        metadata=request.metadata
    )
    
    return {
        "id": template.id,
        "domain": template.domain,
        "name": template.name,
        "version": template.version,
        "status": "registered"
    }


@router.post("/render")
async def render_template(request: RenderTemplateRequest) -> Dict[str, Any]:
    """Render a prompt template with variables"""
    try:
        rendered = prompt_library.render_template(request.template_id, request.variables)
        return {
            "template_id": request.template_id,
            "rendered": rendered,
            "variables_used": request.variables
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/outcome")
async def record_outcome(request: RecordOutcomeRequest) -> Dict[str, Any]:
    """Record the outcome of using a prompt template"""
    outcome = prompt_library.record_outcome(
        prompt_id=request.prompt_id,
        task=request.task,
        result=request.result,
        metrics=request.metrics,
        success=request.success
    )
    
    return {
        "status": "recorded",
        "prompt_id": outcome.prompt_id,
        "success": outcome.success,
        "timestamp": outcome.timestamp
    }


@router.post("/propose-upgrade")
async def propose_upgrade(request: ProposeUpgradeRequest) -> Dict[str, Any]:
    """Propose an upgrade to a prompt template"""
    result = prompt_library.propose_upgrade(
        template_id=request.template_id,
        improved_template=request.improved_template,
        reason=request.reason,
        evidence=request.evidence
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/proposals")
async def list_proposals() -> Dict[str, Any]:
    """List pending upgrade proposals"""
    proposals_file = prompt_library.storage_path / "proposals.json"
    if not proposals_file.exists():
        return {"proposals": []}
    
    try:
        proposals = json.loads(proposals_file.read_text(encoding="utf-8"))
        return {
            "proposals": [
                {
                    "id": str(i),
                    **proposal
                }
                for i, proposal in enumerate(proposals)
            ]
        }
    except Exception as e:
        return {"error": str(e), "proposals": []}


@router.post("/approve-upgrade/{proposal_id}")
async def approve_upgrade(proposal_id: str, approved_by: str = "daena_vp") -> Dict[str, Any]:
    """Approve and apply a prompt upgrade (governance-gated)"""
    result = prompt_library.approve_upgrade(proposal_id, approved_by)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Get prompt library statistics"""
    templates = list(prompt_library.templates.values())
    outcomes = prompt_library.outcomes
    
    return {
        "total_templates": len(templates),
        "total_domains": len(set(t.domain for t in templates)),
        "total_outcomes": len(outcomes),
        "domains": {
            domain: {
                "count": len([t for t in templates if t.domain == domain]),
                "avg_score": sum(t.evaluation_score for t in templates if t.domain == domain) / max(1, len([t for t in templates if t.domain == domain]))
            }
            for domain in set(t.domain for t in templates)
        }
    }

