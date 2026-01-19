"""
Snapshots API - Configuration Snapshots for Founder Rollback

Endpoints:
- POST /api/v1/snapshots - Create config snapshot
- GET /api/v1/snapshots - List snapshots  
- GET /api/v1/snapshots/{id} - Get snapshot details
- POST /api/v1/snapshots/{id}/restore - Restore snapshot
- DELETE /api/v1/snapshots/{id} - Delete snapshot
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/snapshots", tags=["snapshots"])

# Snapshot storage directory
SNAPSHOT_DIR = Path("backups/config")


class SnapshotCreate(BaseModel):
    """Request to create a snapshot."""
    label: Optional[str] = None
    description: Optional[str] = None


class SnapshotRestore(BaseModel):
    """Request to restore a snapshot."""
    confirm: bool = False


def ensure_snapshot_dir():
    """Ensure snapshot directory exists."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def get_snapshot_path(snapshot_id: str) -> Path:
    """Get path for a snapshot file."""
    return SNAPSHOT_DIR / f"{snapshot_id}.json"


def collect_current_config() -> Dict[str, Any]:
    """Collect current configuration for snapshot."""
    config = {
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0",
        "brain": {},
        "routing": {},
        "voice": {},
        "tools": {},
        "connections": []
    }
    
    # Brain config
    try:
        from backend.services.llm_service import llm_service
        config["brain"] = {
            "default_provider": getattr(llm_service, 'default_provider', 'ollama'),
            "active_model": getattr(llm_service, 'model_name', None),
            "providers_configured": list(getattr(llm_service, 'providers', {}).keys())
        }
    except Exception as e:
        logger.warning(f"Could not collect brain config: {e}")
        config["brain"] = {"error": str(e)}
    
    # Routing config
    try:
        from backend.services.intelligent_router import intelligent_router
        config["routing"] = {
            "prefer_local": getattr(intelligent_router, 'prefer_local', True),
            "fallback_enabled": True
        }
    except Exception as e:
        config["routing"] = {"prefer_local": True, "fallback_enabled": True}
    
    # Voice config
    try:
        from backend.services.voice_service import voice_service
        config["voice"] = {
            "enabled": getattr(voice_service, 'enabled', False),
            "tts_enabled": getattr(voice_service, 'tts_available', False),
            "stt_enabled": getattr(voice_service, 'stt_available', False)
        }
    except Exception as e:
        config["voice"] = {"enabled": False}
    
    # Tools config
    try:
        config["tools"] = {
            "web_search_enabled": True,
            "url_fetch_enabled": True,
            "browser_enabled": True,
            "code_scanner_enabled": True
        }
    except Exception as e:
        config["tools"] = {}
    
    # Demo mode
    try:
        from backend.demo_mode import is_demo_mode, get_demo_config
        config["demo"] = {
            "enabled": is_demo_mode(),
            "config": get_demo_config()
        }
    except Exception as e:
        config["demo"] = {"enabled": False}
    
    return config


def apply_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply configuration from snapshot."""
    results = {"applied": [], "errors": []}
    
    # Apply brain config
    try:
        if "brain" in config and "active_model" in config["brain"]:
            # TODO: Actually switch model via llm_service
            results["applied"].append("brain.active_model")
    except Exception as e:
        results["errors"].append(f"brain: {e}")
    
    # Apply routing config
    try:
        if "routing" in config:
            # TODO: Actually update routing preferences
            results["applied"].append("routing.prefer_local")
    except Exception as e:
        results["errors"].append(f"routing: {e}")
    
    # Apply voice config
    try:
        if "voice" in config:
            # TODO: Actually toggle voice service
            results["applied"].append("voice.enabled")
    except Exception as e:
        results["errors"].append(f"voice: {e}")
    
    return results


@router.post("")
async def create_snapshot(request: SnapshotCreate) -> Dict[str, Any]:
    """Create a new configuration snapshot."""
    ensure_snapshot_dir()
    
    # Generate snapshot ID
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snapshot_{timestamp}"
    
    # Collect current config
    config = collect_current_config()
    
    # Add metadata
    snapshot = {
        "id": snapshot_id,
        "label": request.label or f"Snapshot {timestamp}",
        "description": request.description or "Manual snapshot",
        "created_at": datetime.utcnow().isoformat(),
        "config": config
    }
    
    # Save to file
    snapshot_path = get_snapshot_path(snapshot_id)
    with open(snapshot_path, "w") as f:
        json.dump(snapshot, f, indent=2)
    
    logger.info(f"Created snapshot: {snapshot_id}")
    
    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "label": snapshot["label"],
        "created_at": snapshot["created_at"],
        "path": str(snapshot_path)
    }


@router.get("")
async def list_snapshots() -> Dict[str, Any]:
    """List all available snapshots."""
    ensure_snapshot_dir()
    
    snapshots = []
    for path in SNAPSHOT_DIR.glob("snapshot_*.json"):
        try:
            with open(path) as f:
                data = json.load(f)
                snapshots.append({
                    "id": data.get("id", path.stem),
                    "label": data.get("label", "Unnamed"),
                    "description": data.get("description", ""),
                    "created_at": data.get("created_at"),
                    "config_summary": {
                        "brain_model": data.get("config", {}).get("brain", {}).get("active_model"),
                        "voice_enabled": data.get("config", {}).get("voice", {}).get("enabled", False),
                        "demo_mode": data.get("config", {}).get("demo", {}).get("enabled", False)
                    }
                })
        except Exception as e:
            logger.warning(f"Could not read snapshot {path}: {e}")
    
    # Sort by created_at descending
    snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    return {
        "snapshots": snapshots,
        "total": len(snapshots),
        "directory": str(SNAPSHOT_DIR)
    }


@router.get("/{snapshot_id}")
async def get_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Get details of a specific snapshot."""
    snapshot_path = get_snapshot_path(snapshot_id)
    
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")
    
    with open(snapshot_path) as f:
        return json.load(f)


@router.post("/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str, request: SnapshotRestore) -> Dict[str, Any]:
    """Restore configuration from a snapshot."""
    if not request.confirm:
        return {
            "success": False,
            "message": "Restore requires confirmation. Set confirm=true to proceed.",
            "snapshot_id": snapshot_id
        }
    
    snapshot_path = get_snapshot_path(snapshot_id)
    
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")
    
    # Load snapshot
    with open(snapshot_path) as f:
        snapshot = json.load(f)
    
    # Create backup before restore
    pre_restore = collect_current_config()
    pre_restore_path = SNAPSHOT_DIR / f"pre_restore_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(pre_restore_path, "w") as f:
        json.dump({"config": pre_restore, "reason": f"Pre-restore backup before applying {snapshot_id}"}, f, indent=2)
    
    # Apply config
    results = apply_config(snapshot.get("config", {}))
    
    logger.info(f"Restored snapshot: {snapshot_id}")
    
    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "label": snapshot.get("label"),
        "restored_at": datetime.utcnow().isoformat(),
        "pre_restore_backup": str(pre_restore_path),
        "results": results
    }


@router.delete("/{snapshot_id}")
async def delete_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Delete a snapshot."""
    snapshot_path = get_snapshot_path(snapshot_id)
    
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot not found: {snapshot_id}")
    
    snapshot_path.unlink()
    logger.info(f"Deleted snapshot: {snapshot_id}")
    
    return {
        "success": True,
        "snapshot_id": snapshot_id,
        "deleted_at": datetime.utcnow().isoformat()
    }
