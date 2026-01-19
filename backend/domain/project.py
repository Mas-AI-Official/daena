"""
Project System Models
Defines the structure for Projects
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ProjectMember(BaseModel):
    agent_id: str
    role: str

class ProjectFinance(BaseModel):
    budget: float
    spent: float
    currency: str = "USD"

class Project(BaseModel):
    id: str
    name: str
    description: str
    status: str  # active, planning, completed, paused
    progress: int  # 0-100
    start_date: datetime
    deadline: Optional[datetime]
    finance: ProjectFinance
    team: List[ProjectMember]
    tags: List[str]

# Mock Data
INITIAL_PROJECTS = [
    Project(
        id="proj_1",
        name="Daena Core Upgrade",
        description="Migrating core architecture to hexagonal system",
        status="active",
        progress=75,
        start_date=datetime.now(),
        deadline=None,
        finance=ProjectFinance(budget=50000, spent=32000),
        team=[ProjectMember(agent_id="tech_1", role="Lead"), ProjectMember(agent_id="tech_3", role="Dev")],
        tags=["infrastructure", "backend"]
    ),
    Project(
        id="proj_2",
        name="Global Marketing Campaign",
        description="Q1 2026 Brand Awareness Push",
        status="planning",
        progress=15,
        start_date=datetime.now(),
        deadline=None,
        finance=ProjectFinance(budget=120000, spent=5000),
        team=[ProjectMember(agent_id="mktg_1", role="Strategist")],
        tags=["marketing", "branding"]
    ),
    Project(
        id="proj_3",
        name="Legal Compliance Audit",
        description="Annual GDPR and CCPA review",
        status="active",
        progress=40,
        start_date=datetime.now(),
        deadline=None,
        finance=ProjectFinance(budget=25000, spent=10000),
        team=[ProjectMember(agent_id="legal_1", role="Auditor")],
        tags=["legal", "compliance"]
    )
]
