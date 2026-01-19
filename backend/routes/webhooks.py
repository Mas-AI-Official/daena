"""
Webhook Handler API
Receives external triggers (n8n style) and dispatches events
"""
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json
import logging

from backend.core.websocket_manager import websocket_manager

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

# In-memory webhook registry (persist to DB in production)
# Format: {webhook_id: {config}}
_webhooks = {}

@router.post("/{webhook_id}")
async def handle_webhook(webhook_id: str, request: Request, background_tasks: BackgroundTasks):
    """
    Generic webhook receiver.
    Accepts any JSON payload and triggers associated actions.
    """
    try:
        payload = await request.json()
    except:
        payload = {"raw_body": (await request.body()).decode()}

    # Log receipt
    logger.info(f"Webhook received: {webhook_id}")
    
    # Emit real-time event
    await websocket_manager.publish_event(
        event_type="webhook.received",
        entity_type="webhook",
        entity_id=webhook_id,
        payload={
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload,
            "headers": dict(request.headers)
        }
    )
    
    # Process in background (placeholder for workflow engine)
    background_tasks.add_task(process_webhook_trigger, webhook_id, payload)
    
    return {"status": "received", "id": webhook_id, "timestamp": datetime.utcnow().isoformat()}

async def process_webhook_trigger(webhook_id: str, payload: Dict[str, Any]):
    """
    Process the webhook payload and trigger workflows
    """
    # TODO: Lookup workflow associated with this webhook_id
    # TODO: Execute workflow steps
    logger.info(f"Processing webhook {webhook_id} with payload: {json.dumps(payload)[:100]}...")
    
    # For now, just log it as a system event
    # In future: Trigger n8n-style workflow
    pass

@router.post("/register")
async def register_webhook(config: Dict[str, Any]):
    """
    Register a new webhook endpoint
    """
    webhook_id = str(uuid.uuid4())
    _webhooks[webhook_id] = {
        "id": webhook_id,
        "config": config,
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {
        "webhook_id": webhook_id,
        "url": f"/api/v1/webhooks/{webhook_id}",
        "full_url": f"http://localhost:8000/api/v1/webhooks/{webhook_id}"
    }
