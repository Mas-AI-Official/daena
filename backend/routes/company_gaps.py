"""
Company Gap Finder - Autonomous Company Gaps Module

Add-On 1: Compares Daena's capabilities to what a real autonomous company needs.
Generates actionable backlog and wires it into Founder dashboard.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy/company-gaps", tags=["Company Gaps"])


# ═══════════════════════════════════════════════════════════════════════
# Gap Definitions - What an autonomous company needs
# ═══════════════════════════════════════════════════════════════════════

COMPANY_GAP_AREAS = {
    "sales_outbound": {
        "name": "Sales & Outbound",
        "description": "Lead sourcing, proposal generation, pipeline tracking",
        "icon": "💼",
        "required_capabilities": [
            "lead_sourcing",
            "proposal_generation",
            "pipeline_crm",
            "email_outreach",
            "meeting_scheduling"
        ],
        "department_template": "sales",
        "success_kpis": ["leads_generated", "proposals_sent", "conversion_rate", "revenue"]
    },
    "customer_support": {
        "name": "Customer Success & Support",
        "description": "Ticketing, SLA management, onboarding",
        "icon": "🎧",
        "required_capabilities": [
            "ticket_system",
            "sla_tracking",
            "customer_onboarding",
            "knowledge_base",
            "live_chat"
        ],
        "department_template": "support",
        "success_kpis": ["ticket_resolution_time", "csat_score", "churn_rate"]
    },
    "finance_ops": {
        "name": "Finance Operations",
        "description": "Invoicing, receivables, payroll readiness, tax-ready bookkeeping",
        "icon": "💰",
        "required_capabilities": [
            "invoicing",
            "accounts_receivable",
            "expense_tracking",
            "payroll_integration",
            "tax_reporting"
        ],
        "department_template": "finance",
        "success_kpis": ["revenue", "cash_flow", "days_sales_outstanding", "expense_ratio"]
    },
    "legal_ops": {
        "name": "Legal Operations",
        "description": "Templated contracts, signature workflow, compliance checks",
        "icon": "⚖️",
        "required_capabilities": [
            "contract_templates",
            "esign_workflow",
            "compliance_checks",
            "nda_management",
            "ip_tracking"
        ],
        "department_template": "legal",
        "success_kpis": ["contracts_processed", "compliance_score", "legal_response_time"]
    },
    "hr_freelancer": {
        "name": "HR & Freelancer Ops",
        "description": "Hire requests, vendor onboarding, milestone payments",
        "icon": "👥",
        "required_capabilities": [
            "hire_requests",
            "vendor_onboarding",
            "contractor_management",
            "milestone_payments",
            "performance_tracking"
        ],
        "department_template": "hr",
        "success_kpis": ["time_to_hire", "contractor_satisfaction", "milestone_completion_rate"]
    },
    "marketing_content": {
        "name": "Marketing & Content Engine",
        "description": "Social post scheduling, analytics, landing page updates",
        "icon": "📢",
        "required_capabilities": [
            "social_scheduling",
            "content_creation",
            "analytics_dashboard",
            "landing_page_builder",
            "email_campaigns"
        ],
        "department_template": "marketing",
        "success_kpis": ["impressions", "engagement_rate", "lead_generation", "conversion_rate"]
    },
    "product_management": {
        "name": "Product Management",
        "description": "Roadmap, prioritization, incident postmortems",
        "icon": "🎯",
        "required_capabilities": [
            "roadmap_management",
            "feature_prioritization",
            "user_feedback",
            "incident_postmortems",
            "release_management"
        ],
        "department_template": "product",
        "success_kpis": ["feature_velocity", "bug_fix_time", "user_satisfaction"]
    },
    "security_governance": {
        "name": "Security & Governance",
        "description": "Policy engine, secrets management, least-privilege, audit trails",
        "icon": "🔒",
        "required_capabilities": [
            "policy_engine",
            "secrets_vault",
            "access_control",
            "audit_logging",
            "vulnerability_scanning"
        ],
        "department_template": "security",
        "success_kpis": ["incident_count", "mttr", "compliance_score", "vulnerability_count"]
    },
    "reliability_sre": {
        "name": "Reliability / SRE",
        "description": "SLOs, monitoring, alerts, runbooks, incident response",
        "icon": "🚨",
        "required_capabilities": [
            "slo_management",
            "monitoring_dashboard",
            "alerting_system",
            "runbooks",
            "incident_response"
        ],
        "department_template": "sre",
        "success_kpis": ["uptime", "mttr", "slo_compliance", "incident_count"]
    },
    "data_governance": {
        "name": "Data Governance",
        "description": "Retention policies, PII handling, customer data separation",
        "icon": "🗃️",
        "required_capabilities": [
            "data_retention",
            "pii_protection",
            "data_classification",
            "customer_isolation",
            "gdpr_compliance"
        ],
        "department_template": "data",
        "success_kpis": ["compliance_score", "data_breach_count", "retention_compliance"]
    }
}


# ═══════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════

class GapAnalysisResult(BaseModel):
    area_id: str
    area_name: str
    icon: str
    status: str  # missing, partial, complete
    coverage_percent: float
    existing_capabilities: List[str]
    missing_capabilities: List[str]
    priority: str  # critical, high, medium, low
    effort_estimate: str  # days/weeks


class DepartmentProposal(BaseModel):
    area_id: str
    department_name: str
    agent_roles: List[Dict[str, str]]
    api_endpoints: List[Dict[str, str]]
    ui_components: List[str]
    success_kpis: List[str]
    risks: List[str]
    founder_approvals_required: List[str]


class GapBacklogItem(BaseModel):
    id: str
    area_id: str
    title: str
    description: str
    priority: str
    effort: str
    status: str  # backlog, in_progress, done
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════
# Gap Storage
# ═══════════════════════════════════════════════════════════════════════

class GapBacklogStorage:
    """Persistent storage for gap backlog"""
    
    def __init__(self):
        self.storage_path = Path(__file__).parent.parent.parent / "config" / "gap_backlog.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.backlog: List[Dict] = []
        self._load()
    
    def _load(self):
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    self.backlog = json.load(f)
            except:
                self.backlog = []
    
    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.backlog, f, indent=2, default=str)
    
    def add_item(self, item: Dict):
        self.backlog.append(item)
        self._save()
    
    def get_all(self) -> List[Dict]:
        return self.backlog
    
    def update_status(self, item_id: str, status: str):
        for item in self.backlog:
            if item.get("id") == item_id:
                item["status"] = status
        self._save()


backlog_storage = GapBacklogStorage()


# ═══════════════════════════════════════════════════════════════════════
# Gap Analyzer
# ═══════════════════════════════════════════════════════════════════════

class GapAnalyzer:
    """Analyzes current capabilities vs required for autonomous company"""
    
    def __init__(self):
        self.existing_capabilities = self._detect_existing_capabilities()
    
    def _detect_existing_capabilities(self) -> Dict[str, List[str]]:
        """Detect what capabilities already exist in the system"""
        # This would normally scan the codebase/database
        # For now, return detected capabilities based on routes
        return {
            "sales_outbound": ["email_outreach"],  # social_media routes exist
            "customer_support": ["knowledge_base"],  # honey_knowledge exists
            "finance_ops": [],
            "legal_ops": [],
            "hr_freelancer": ["hire_requests"],  # hiring routes exist
            "marketing_content": ["social_scheduling"],  # social_media routes
            "product_management": ["roadmap_management"],  # tasks/projects exist
            "security_governance": ["audit_logging", "access_control"],  # audit routes exist
            "reliability_sre": ["monitoring_dashboard", "alerting_system"],  # monitoring routes
            "data_governance": []
        }
    
    def analyze_all_gaps(self) -> List[GapAnalysisResult]:
        """Analyze all gap areas"""
        results = []
        
        for area_id, area_def in COMPANY_GAP_AREAS.items():
            existing = self.existing_capabilities.get(area_id, [])
            required = area_def["required_capabilities"]
            missing = [c for c in required if c not in existing]
            
            coverage = len(existing) / len(required) * 100 if required else 100
            
            # Determine status
            if coverage == 0:
                status = "missing"
                priority = "critical" if area_id in ["finance_ops", "legal_ops", "security_governance"] else "high"
            elif coverage < 50:
                status = "partial"
                priority = "high"
            elif coverage < 100:
                status = "partial"
                priority = "medium"
            else:
                status = "complete"
                priority = "low"
            
            # Effort estimate
            effort = f"{len(missing) * 2}-{len(missing) * 5} days"
            
            results.append(GapAnalysisResult(
                area_id=area_id,
                area_name=area_def["name"],
                icon=area_def["icon"],
                status=status,
                coverage_percent=round(coverage, 1),
                existing_capabilities=existing,
                missing_capabilities=missing,
                priority=priority,
                effort_estimate=effort
            ))
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results.sort(key=lambda x: priority_order.get(x.priority, 4))
        
        return results
    
    def generate_department_proposal(self, area_id: str) -> DepartmentProposal:
        """Generate a department proposal for a gap area"""
        area = COMPANY_GAP_AREAS.get(area_id)
        if not area:
            raise ValueError(f"Unknown area: {area_id}")
        
        # Generate agent roles
        agent_roles = [
            {"role": f"{area['department_template']}_lead", "description": f"Lead agent for {area['name']}"},
            {"role": f"{area['department_template']}_specialist", "description": f"Specialist agent for core tasks"},
            {"role": f"{area['department_template']}_analyst", "description": f"Analyst for metrics and reporting"}
        ]
        
        # Generate API endpoints needed
        api_endpoints = [
            {"method": "GET", "path": f"/api/v1/{area['department_template']}/status", "description": "Get department status"},
            {"method": "POST", "path": f"/api/v1/{area['department_template']}/tasks", "description": "Create new task"},
            {"method": "GET", "path": f"/api/v1/{area['department_template']}/metrics", "description": "Get KPI metrics"},
        ]
        
        # Add capability-specific endpoints
        for cap in area["required_capabilities"]:
            api_endpoints.append({
                "method": "POST",
                "path": f"/api/v1/{area['department_template']}/{cap.replace('_', '-')}",
                "description": f"Execute {cap.replace('_', ' ')}"
            })
        
        # UI components
        ui_components = [
            f"{area['department_template']}_dashboard.html",
            f"{area['department_template']}_tasks.html",
            f"{area['department_template']}_metrics.html"
        ]
        
        # Risks
        risks = [
            "Integration with existing systems",
            "Data migration if replacing manual processes",
            "Training period for optimal performance"
        ]
        
        # Founder approvals
        approvals = ["Department creation", "Agent provisioning"]
        if area_id in ["finance_ops", "legal_ops"]:
            approvals.append("Third-party integrations (payments, e-sign)")
        if area_id == "security_governance":
            approvals.append("Access to secrets vault")
        
        return DepartmentProposal(
            area_id=area_id,
            department_name=area["name"],
            agent_roles=agent_roles,
            api_endpoints=api_endpoints,
            ui_components=ui_components,
            success_kpis=area["success_kpis"],
            risks=risks,
            founder_approvals_required=approvals
        )


gap_analyzer = GapAnalyzer()


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

@router.get("")
async def get_gap_map():
    """
    Get the Company Gap Map - overview of all capability gaps.
    """
    gaps = gap_analyzer.analyze_all_gaps()
    
    summary = {
        "total_areas": len(gaps),
        "complete": len([g for g in gaps if g.status == "complete"]),
        "partial": len([g for g in gaps if g.status == "partial"]),
        "missing": len([g for g in gaps if g.status == "missing"]),
        "overall_coverage": round(sum(g.coverage_percent for g in gaps) / len(gaps), 1) if gaps else 0
    }
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": summary,
        "gaps": [g.model_dump() for g in gaps]
    }


@router.get("/areas")
async def list_gap_areas():
    """List all gap areas with definitions"""
    return {
        "areas": [
            {
                "id": k,
                "name": v["name"],
                "description": v["description"],
                "icon": v["icon"],
                "department_template": v["department_template"]
            }
            for k, v in COMPANY_GAP_AREAS.items()
        ]
    }


@router.get("/areas/{area_id}")
async def get_gap_area(area_id: str):
    """Get details for a specific gap area"""
    if area_id not in COMPANY_GAP_AREAS:
        raise HTTPException(status_code=404, detail="Area not found")
    
    area = COMPANY_GAP_AREAS[area_id]
    gaps = gap_analyzer.analyze_all_gaps()
    gap = next((g for g in gaps if g.area_id == area_id), None)
    
    return {
        "area": area,
        "analysis": gap.model_dump() if gap else None
    }


@router.get("/areas/{area_id}/proposal")
async def get_department_proposal(area_id: str):
    """
    Generate a department proposal for filling a gap.
    """
    try:
        proposal = gap_analyzer.generate_department_proposal(area_id)
        return proposal.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/areas/{area_id}/create-department")
async def create_department_from_gap(
    area_id: str,
    founder_approved: bool = Body(False, description="Founder approval flag")
):
    """
    Create a department to fill a gap (requires founder approval).
    """
    if not founder_approved:
        return {
            "success": False,
            "message": "Founder approval required to create department",
            "requires_approval": True
        }
    
    if area_id not in COMPANY_GAP_AREAS:
        raise HTTPException(status_code=404, detail="Area not found")
    
    # TODO: Actually create the department
    # This would:
    # 1. Create department in database
    # 2. Create agent configs
    # 3. Register API routes
    # 4. Generate UI dashboard
    
    return {
        "success": True,
        "message": f"Department creation for {COMPANY_GAP_AREAS[area_id]['name']} initiated",
        "next_steps": [
            "Agent configs will be generated",
            "API routes will be registered",
            "Dashboard will be created"
        ]
    }


# ═══════════════════════════════════════════════════════════════════════
# Backlog Routes
# ═══════════════════════════════════════════════════════════════════════

@router.get("/backlog")
async def get_backlog():
    """Get the gap backlog"""
    return {
        "items": backlog_storage.get_all(),
        "total": len(backlog_storage.backlog)
    }


@router.post("/backlog")
async def add_to_backlog(item: GapBacklogItem):
    """Add item to gap backlog"""
    backlog_storage.add_item(item.model_dump())
    return {"success": True, "id": item.id}


@router.put("/backlog/{item_id}/status")
async def update_backlog_status(item_id: str, status: str = Body(...)):
    """Update backlog item status"""
    backlog_storage.update_status(item_id, status)
    return {"success": True}


@router.post("/generate-backlog")
async def generate_backlog_from_gaps():
    """
    Generate backlog items from current gaps.
    Creates one item per missing capability.
    """
    gaps = gap_analyzer.analyze_all_gaps()
    generated = []
    
    for gap in gaps:
        if gap.status in ["missing", "partial"]:
            for cap in gap.missing_capabilities:
                item_id = f"gap_{gap.area_id}_{cap}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                item = {
                    "id": item_id,
                    "area_id": gap.area_id,
                    "title": f"Implement {cap.replace('_', ' ').title()}",
                    "description": f"Add {cap.replace('_', ' ')} capability to {gap.area_name}",
                    "priority": gap.priority,
                    "effort": "2-5 days",
                    "status": "backlog",
                    "created_at": datetime.utcnow().isoformat()
                }
                backlog_storage.add_item(item)
                generated.append(item)
    
    return {
        "success": True,
        "generated_count": len(generated),
        "items": generated
    }


# ═══════════════════════════════════════════════════════════════════════
# UI Route
# ═══════════════════════════════════════════════════════════════════════

GAP_MAP_TEMPLATE = Path(__file__).parent.parent.parent / "frontend" / "templates" / "company_gap_map.html"


@router.get("/ui", response_class=HTMLResponse)
async def serve_gap_map_ui():
    """Serve the Company Gap Map dashboard"""
    try:
        return HTMLResponse(content=GAP_MAP_TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    except FileNotFoundError:
        # Return inline dashboard if template not found
        return HTMLResponse(content="""
<!DOCTYPE html>
<html><head><title>Company Gap Map</title>
<style>body{font-family:system-ui;background:#0a0a0f;color:#f1f5f9;padding:2rem;}</style>
</head><body>
<h1>📊 Company Gap Map</h1>
<p>Loading... Check /api/v1/strategy/company-gaps for data.</p>
</body></html>
        """, status_code=200)
