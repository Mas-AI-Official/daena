"""
Policy API — Configuration and management of system-wide DAENA policies.
Allows the Founder to live-edit NBMF, Governance, and Security settings.
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List
import yaml
import os
import logging
from pathlib import Path

router = APIRouter(prefix="/api/v1/policy", tags=["policy"])
logger = logging.getLogger(__name__)

POLICY_FILE = Path("config/memory_policy.yaml")

def _load_policy() -> Dict[str, Any]:
    """Helper to load the current policy YAML."""
    if not POLICY_FILE.exists():
        return {}
    try:
        with open(POLICY_FILE, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Failed to load policy file: {e}")
        return {}

def _save_policy(data: Dict[str, Any]):
    """Helper to save policy to YAML."""
    POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(POLICY_FILE, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    except Exception as e:
        logger.error(f"Failed to save policy file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save policy")

@router.get("/")
async def get_all_policies() -> Dict[str, Any]:
    """Get the entire system policy configuration."""
    return {
        "success": True,
        "config": _load_policy()
    }

@router.get("/memory")
async def get_memory_policies() -> Dict[str, Any]:
    """Get NBMF memory routing and fidelity policies."""
    cfg = _load_policy()
    return {
        "success": True,
        "classes": cfg.get("memory_policy", {}).get("classes", {}),
        "aging": cfg.get("memory_policy", {}).get("aging", [])
    }

@router.post("/update")
async def update_policy(data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Update a specific section of the policy."""
    # In a real enterprise app, we'd validate the schema here.
    # For Daena, we trust the Founder's direct input via the Policy Center.
    current = _load_policy()
    
    # Deep merge or simple update depending on requirement.
    # Here we just replace the memory_policy section if provided.
    if "memory_policy" in data:
        current["memory_policy"] = data["memory_policy"]
    
    _save_policy(current)
    return {"success": True, "message": "Policy updated successfully"}

@router.get("/security")
async def get_security_config() -> Dict[str, Any]:
    """Get security and encryption settings."""
    cfg = _load_policy()
    return {
        "success": True,
        "security": cfg.get("memory_policy", {}).get("security", {}),
        "slas": cfg.get("memory_policy", {}).get("slas", {})
    }
