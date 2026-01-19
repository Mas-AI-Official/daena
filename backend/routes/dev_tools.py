"""
Development Tools API
Endpoints for development/testing - protected by DAENA_DEV_MODE environment variable
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
import logging

router = APIRouter(prefix="/api/v1/dev", tags=["development"])
logger = logging.getLogger(__name__)


def check_dev_mode():
    """Ensure dev mode is enabled"""
    if os.environ.get("DAENA_DEV_MODE") != "1":
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in development mode. Set DAENA_DEV_MODE=1"
        )


@router.post("/reset")
async def reset_to_defaults() -> Dict[str, Any]:
    """
    Reset database to defaults - ONLY available in dev mode.
    
    Set environment variable DAENA_DEV_MODE=1 to enable.
    
    This will:
    1. Clear all agents, tasks, chat sessions, messages
    2. Reseed departments and default agents
    3. Broadcast reset event to all WebSocket clients
    """
    check_dev_mode()
    
    logger.warning("🔄 DEV RESET: Starting database reset to defaults...")
    
    try:
        from backend.database import SessionLocal
        from backend.services.db_seeder import reset_and_seed
        
        db = SessionLocal()
        result = reset_and_seed(db)
        db.close()
        
        # Broadcast reset event
        try:
            from backend.services.event_bus import event_bus
            import asyncio
            await event_bus.publish_system_reset()
        except Exception as e:
            logger.warning(f"Could not broadcast reset event: {e}")
        
        logger.info(f"✅ DEV RESET: Complete - {result}")
        
        return {
            "success": True,
            "message": "System reset to defaults",
            "seeded": result
        }
    
    except Exception as e:
        logger.error(f"❌ DEV RESET: Failed - {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_dev_status() -> Dict[str, Any]:
    """Get development status and environment info"""
    from backend.database import SessionLocal, Department, Agent
    from backend.routes.websocket import get_ws_status
    
    db = SessionLocal()
    dept_count = db.query(Department).count()
    agent_count = db.query(Agent).count()
    db.close()
    
    return {
        "dev_mode": os.environ.get("DAENA_DEV_MODE") == "1",
        "environment": os.environ.get("ENV", "development"),
        "database": {
            "departments": dept_count,
            "agents": agent_count
        },
        "websocket": get_ws_status()
    }


@router.post("/seed")
async def seed_database() -> Dict[str, Any]:
    """
    Seed database with defaults (without clearing existing data).
    Only adds missing entries.
    """
    check_dev_mode()
    
    try:
        from backend.database import SessionLocal
        from backend.services.db_seeder import seed_all
        
        db = SessionLocal()
        result = seed_all(db)
        db.close()
        
        return {
            "success": True,
            "message": "Database seeded",
            "seeded": result
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-event")
async def publish_test_event(event_type: str = "test.ping", message: str = "Hello!") -> Dict[str, Any]:
    """Publish a test event to WebSocket clients"""
    check_dev_mode()
    
    try:
        from backend.services.event_bus import event_bus
        await event_bus.publish(
            event_type,
            "test",
            "test-1",
            {"message": message},
            log_to_db=False  # Don't log test events
        )
        
        return {
            "success": True,
            "event_type": event_type,
            "message": message,
            "connections": event_bus.get_connection_count()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
