"""
Proactive rules and events API.
GET /api/v1/proactive/rules, POST /api/v1/proactive/rules, POST /api/v1/proactive/run_once, GET /api/v1/proactive/events
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/v1/proactive", tags=["proactive"])

_rules: List[Dict[str, Any]] = [
    {"id": "rule_1", "name": "Backend health fail", "cron": None, "event_trigger": "health_fail", "enabled": True},
    {"id": "rule_2", "name": "Daily 9am summary", "cron": "0 9 * * *", "event_trigger": None, "enabled": True},
    {"id": "rule_3", "name": "Credit usage spike", "cron": None, "event_trigger": "credit_spike", "enabled": True},
    {"id": "rule_e2e", "name": "E2E regression check nightly", "cron": "0 2 * * *", "event_trigger": "e2e_regression", "enabled": True},
    {"id": "rule_health_notify", "name": "Notify on failing health checks", "cron": None, "event_trigger": "health_fail", "enabled": True},
]
_events: List[Dict[str, Any]] = []


class RuleBody(BaseModel):
    name: str
    cron: Optional[str] = None
    event_trigger: Optional[str] = None
    enabled: bool = True


@router.get("/rules")
async def get_rules() -> Dict[str, Any]:
    return {"success": True, "rules": _rules}


@router.post("/rules")
async def create_rule(body: RuleBody) -> Dict[str, Any]:
    r = {"id": f"rule_{uuid.uuid4().hex[:8]}", "name": body.name, "cron": body.cron, "event_trigger": body.event_trigger, "enabled": body.enabled}
    _rules.append(r)
    return {"success": True, "rule": r}


@router.post("/run_once")
async def run_once(rule_id: str) -> Dict[str, Any]:
    rule = next((r for r in _rules if r["id"] == rule_id), None)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    ev = {"id": str(uuid.uuid4()), "rule_id": rule_id, "ts": datetime.utcnow().isoformat() + "Z", "payload": {"trigger": "manual"}}
    _events.append(ev)
    return {"success": True, "event": ev}


@router.get("/events")
async def get_events(limit: int = 50) -> Dict[str, Any]:
    return {"success": True, "events": _events[-limit:][::-1]}
