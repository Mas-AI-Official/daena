
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from backend.services.shadow.obsidian_circle import ObsidianCircle

# Instantiate Service
obsidian_service = ObsidianCircle()

router = APIRouter()

class HoneypotRequest(BaseModel):
    target: str

class RedTeamRequest(BaseModel):
    target: str
    attack_vector: str

@router.get("/shadow/stats")
async def get_stats():
    return {
        "honeypots_active": len(obsidian_service.honeypots),
        "threats_detected": 0, # Mock
        "red_team_tests": 0
    }

@router.post("/shadow/honeypots")
async def deploy_honeypot(request: HoneypotRequest):
    """Deploy a new honeypot"""
    result = await obsidian_service.deploy_honeypot(request.target)
    return result

@router.get("/shadow/honeypots")
async def list_honeypots():
    return obsidian_service.honeypots

@router.post("/shadow/red-team")
async def run_red_team(request: RedTeamRequest):
    """Run a red team test"""
    result = await obsidian_service.red_team_test(request.target, request.attack_vector)
    return result
