"""
API endpoints for message queue persistence management.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, Dict, Any
import logging

from backend.services.message_queue_persistence import (
    get_message_queue_persistence,
    init_message_queue_persistence
)
from backend.routes.monitoring import verify_monitoring_auth

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/message-queue/stats")
async def get_message_queue_stats(_: bool = Depends(verify_monitoring_auth)):
    """Get message queue statistics."""
    mq = get_message_queue_persistence()
    if not mq:
        raise HTTPException(
            status_code=503,
            detail="Message queue persistence not initialized"
        )
    
    return mq.get_stats()


@router.get("/message-queue/dead-letter")
async def get_dead_letter_queue(_: bool = Depends(verify_monitoring_auth)):
    """Get messages in dead letter queue."""
    mq = get_message_queue_persistence()
    if not mq:
        raise HTTPException(
            status_code=503,
            detail="Message queue persistence not initialized"
        )
    
    return {
        "dead_letter_messages": [
            msg.to_dict() for msg in mq.dead_letter_queue
        ],
        "count": len(mq.dead_letter_queue)
    }


@router.post("/message-queue/enqueue")
async def enqueue_message(
    topic: str = Body(...),
    content: Dict[str, Any] = Body(...),
    sender: str = Body(...),
    metadata: Optional[Dict[str, Any]] = Body(None),
    _: bool = Depends(verify_monitoring_auth)
):
    """Enqueue a message for persistent delivery."""
    mq = get_message_queue_persistence()
    if not mq:
        raise HTTPException(
            status_code=503,
            detail="Message queue persistence not initialized"
        )
    
    message_id = await mq.enqueue(topic, content, sender, metadata)
    return {
        "status": "enqueued",
        "message_id": message_id
    }


@router.post("/message-queue/{message_id}/acknowledge")
async def acknowledge_message(
    message_id: str,
    _: bool = Depends(verify_monitoring_auth)
):
    """Acknowledge successful processing of a message."""
    mq = get_message_queue_persistence()
    if not mq:
        raise HTTPException(
            status_code=503,
            detail="Message queue persistence not initialized"
        )
    
    await mq.acknowledge(message_id)
    return {"status": "acknowledged"}


@router.post("/message-queue/{message_id}/fail")
async def fail_message(
    message_id: str,
    error: str = Body(...),
    _: bool = Depends(verify_monitoring_auth)
):
    """Mark a message as failed."""
    mq = get_message_queue_persistence()
    if not mq:
        raise HTTPException(
            status_code=503,
            detail="Message queue persistence not initialized"
        )
    
    await mq.fail(message_id, error)
    return {"status": "failed"}

