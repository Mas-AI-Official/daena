"""
Containment API for Guardian / Incident response.

- GET status: blocked IPs, recent playbook log.
- POST block-ip, unblock-ip: add/remove IP from blocklist.
- POST playbook: run action (lockdown, block_ip, unblock_ip).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from backend.services.security_containment import (
    get_status as containment_status,
    get_blocked_ips,
    block_ip as containment_block_ip,
    unblock_ip as containment_unblock_ip,
    run_playbook as containment_run_playbook,
)

router = APIRouter(prefix="/api/v1/security/containment", tags=["security-containment"])
logger = logging.getLogger(__name__)


class BlockIpBody(BaseModel):
    ip: str
    reason: Optional[str] = "manual"


class UnblockIpBody(BaseModel):
    ip: str


class PlaybookBody(BaseModel):
    action: str  # lockdown | block_ip | unblock_ip
    payload: Optional[Dict[str, Any]] = None


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """Return containment status: blocked IPs, recent playbook log, config."""
    return containment_status()


@router.post("/block-ip")
async def block_ip(body: BlockIpBody) -> Dict[str, Any]:
    """Add IP to blocklist (403 for subsequent requests)."""
    containment_block_ip(body.ip, reason=body.reason or "manual")
    return {"ok": True, "ip": body.ip, "message": "IP blocked"}


@router.post("/unblock-ip")
async def unblock_ip(body: UnblockIpBody) -> Dict[str, Any]:
    """Remove IP from blocklist."""
    containment_unblock_ip(body.ip)
    return {"ok": True, "ip": body.ip, "message": "IP unblocked"}


@router.post("/playbook")
async def playbook(body: PlaybookBody) -> Dict[str, Any]:
    """Run containment playbook: lockdown, block_ip, unblock_ip."""
    result = containment_run_playbook(body.action, body.payload or {})
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Playbook failed"))
    return result
