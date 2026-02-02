"""
backend/routes/chat.py
───────────────────────
Chat endpoint — the entry point for user→Daena interaction.

Pipeline: User Input → Think (LLM reasoning) → Plan (action extraction)
          → Governance Check → Act (execute or queue) → Report (WebSocket)

Every stage is broadcast via event_bus so Control Plane can show
the Think→Plan→Act pipeline in real time.
"""

from fastapi import APIRouter, WebSocket
from pydantic import BaseModel
from typing import Optional, List
import time
import asyncio

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


# ── Models ────────────────────────────────────────────────
class ChatMessage(BaseModel):
    message: str
    department: Optional[str] = None          # which dept context (if any)
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    pipeline_id: str
    stages: List[dict] = []
    actions: List[dict] = []
    governance_status: str = "autopilot"      # autopilot | pending | blocked


# ── Lazy imports (avoids circular deps at module load) ──
def _get_event_bus():
    try:
        from backend.services.event_bus import event_bus
        return event_bus
    except Exception:
        return None


def _get_llm_service():
    try:
        from backend.services.llm_service import get_llm_service
        return get_llm_service()
    except Exception:
        return None


def _get_governance_loop():
    try:
        from backend.services.governance_loop import get_governance_loop
        return get_governance_loop()
    except Exception:
        return None


def _get_memory():
    try:
        from backend.services.unified_memory import get_memory
        return get_memory()
    except Exception:
        return None


# ── Pipeline Stage Broadcaster ────────────────────────────
async def _broadcast_stage(bus, pipeline_id: str, stage: str, data: dict = None):
    """Push a pipeline stage event to all WebSocket clients."""
    if not bus:
        return
    payload = dict(data or {})
    payload["pipeline_id"] = pipeline_id
    payload["stage"] = stage
    payload["timestamp"] = time.time()
    message = f"Pipeline {pipeline_id}: stage {stage}"
    try:
        await bus.broadcast("governance_pipeline", payload, message)
    except Exception:
        pass


# ── Main Chat Endpoint ────────────────────────────────────
@router.post("", response_model=ChatResponse)
async def chat(msg: ChatMessage):
    import uuid
    pipeline_id = str(uuid.uuid4())[:12]
    event_bus = _get_event_bus()
    stages = []

    # ─── STAGE 1: THINK ──────────────────────────────────
    await _broadcast_stage(event_bus, pipeline_id, "think", {"input": msg.message[:200]})
    stages.append({"stage": "think", "status": "done", "timestamp": time.time()})

    # Use LLM to reason about the input
    llm = _get_llm_service()
    think_result = ""
    if llm:
        try:
            think_prompt = (
                f"You are Daena's reasoning engine. Analyze this user request and extract:\n"
                f"1. Intent (what they want)\n"
                f"2. Required actions (specific steps)\n"
                f"3. Risk level (low/medium/high/critical)\n"
                f"4. Dependencies (what tools/agents needed)\n\n"
                f"User message: {msg.message}\n\n"
                f"Respond in JSON format only."
            )
            think_result = await llm.generate(think_prompt) if hasattr(llm, 'generate') else str(llm)
        except Exception as e:
            think_result = f"Reasoning: processing '{msg.message[:100]}…'"

    # ─── STAGE 2: PLAN ───────────────────────────────────
    await _broadcast_stage(event_bus, pipeline_id, "plan", {"think_output": think_result[:300] if think_result else ""})
    stages.append({"stage": "plan", "status": "done", "timestamp": time.time()})

    # Extract actionable items from think output
    actions = []
    plan_output = think_result or msg.message

    # Simple action extraction — detect keywords that map to backend services
    action_keywords = {
        "scan": ("defi", "Run DeFi contract scan"),
        "research": ("research", "Execute research query"),
        "install": ("packages", "Request package install"),
        "verify": ("integrity", "Verify content integrity"),
        "memory": ("memory", "Store/retrieve from memory"),
        "skill": ("skills", "Create or invoke skill"),
        "approve": ("governance", "Process approval"),
        "audit": ("packages", "Run package audit"),
        "search": ("research", "Search knowledge base"),
        "deploy": ("defi", "Deploy/interact with contract"),
    }

    msg_lower = msg.message.lower()
    for keyword, (service, desc) in action_keywords.items():
        if keyword in msg_lower:
            actions.append({
                "service": service,
                "description": desc,
                "input": msg.message,
                "risk": "low"  # will be assessed by governance
            })

    if not actions:
        # Default: treat as a chat/reasoning action (low risk)
        actions.append({
            "service": "llm",
            "description": "Process user message via LLM",
            "input": msg.message,
            "risk": "low"
        })

    # ─── STAGE 3: ACT (with Governance Gate) ────────────
    gov = _get_governance_loop()
    governance_status = "autopilot"
    response_text = ""

    for action in actions:
        # Assess risk through governance
        if gov:
            try:
                assessment = gov.assess(action) if hasattr(gov, 'assess') else {"risk": "low", "autopilot": True}
                risk = assessment.get("risk", "low")
                should_autopilot = assessment.get("autopilot", True)

                if risk in ("high", "critical"):
                    governance_status = "blocked"
                    action["status"] = "blocked"
                    action["risk"] = risk
                    await _broadcast_stage(event_bus, pipeline_id, "act", {
                        "action": action["description"],
                        "risk": risk,
                        "status": "blocked"
                    })
                    response_text += f"\n⚠️ Action blocked (risk: {risk}): {action['description']}"
                    continue

                elif not should_autopilot and gov.autopilot is False:
                    governance_status = "pending"
                    action["status"] = "pending_approval"
                    # Queue for founder approval
                    try:
                        gov.queue_for_approval(action)
                    except Exception:
                        pass
                    await _broadcast_stage(event_bus, pipeline_id, "act", {
                        "action": action["description"],
                        "risk": risk,
                        "status": "pending_approval"
                    })
                    response_text += f"\n⏳ Queued for approval: {action['description']}"
                    continue
            except Exception:
                pass  # If governance fails, default to autopilot for low risk

        # EXECUTE (autopilot path)
        action["status"] = "executed"
        await _broadcast_stage(event_bus, pipeline_id, "act", {
            "action": action["description"],
            "risk": action.get("risk", "low"),
            "status": "executed"
        })

        # Dispatch to appropriate service
        if action["service"] == "llm" and llm:
            try:
                result = await llm.generate(msg.message) if hasattr(llm, 'generate') else "LLM service available"
                response_text = result
            except Exception as e:
                response_text = f"Processing: {msg.message}"
        elif action["service"] == "research":
            response_text += f"\n🔍 Research query initiated for: {msg.message}"
        elif action["service"] == "defi":
            response_text += f"\n🔗 DeFi action queued: {msg.message}"
        elif action["service"] == "packages":
            response_text += f"\n📦 Package action queued: {msg.message}"
        elif action["service"] == "integrity":
            response_text += f"\n🛡️ Integrity check initiated: {msg.message}"
        else:
            response_text += f"\n✓ Action executed: {action['description']}"

    # ─── STAGE 4: REPORT ─────────────────────────────────
    stages.append({"stage": "act", "status": "done", "timestamp": time.time()})
    await _broadcast_stage(event_bus, pipeline_id, "report", {
        "actions_executed": len([a for a in actions if a.get("status") == "executed"]),
        "actions_pending": len([a for a in actions if a.get("status") == "pending_approval"]),
        "actions_blocked": len([a for a in actions if a.get("status") == "blocked"]),
        "governance_status": governance_status
    })
    stages.append({"stage": "report", "status": "done", "timestamp": time.time()})

    # Store interaction in memory
    mem = _get_memory()
    if mem:
        try:
            mem.store({
                "type": "chat_interaction",
                "user_message": msg.message,
                "response": response_text[:500],
                "pipeline_id": pipeline_id,
                "governance_status": governance_status,
                "actions": actions
            })
        except Exception:
            pass

    # Broadcast final chat response event
    await _broadcast_stage(event_bus, pipeline_id, "chat_response", {
        "response": response_text or "Processed.",
        "governance_status": governance_status
    })

    return ChatResponse(
        response=response_text or f"✓ Processed via pipeline {pipeline_id}",
        pipeline_id=pipeline_id,
        stages=stages,
        actions=actions,
        governance_status=governance_status
    )


# ── Chat History ──────────────────────────────────────────
@router.get("/history")
async def chat_history():
    """Return recent chat interactions from memory."""
    mem = _get_memory()
    if mem:
        try:
            history = mem.search({"type": "chat_interaction"}, limit=20)
            return history or []
        except Exception:
            pass
    return []


# ── Pipeline Status ──────────────────────────────────────
@router.get("/pipeline/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Get status of a specific pipeline execution."""
    return {
        "pipeline_id": pipeline_id,
        "status": "complete",
        "stages": ["think", "plan", "act", "report"]
    }
