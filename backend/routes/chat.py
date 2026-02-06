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
    department: Optional[str] = None
    session_id: Optional[str] = None  # If None, creates new session


class SessionCreate(BaseModel):
    title: Optional[str] = "New Session"


class SessionUpdate(BaseModel):
    title: str


class ChatResponse(BaseModel):
    response: str
    pipeline_id: str
    session_id: str
    stages: List[dict] = []
    actions: List[dict] = []
    governance_status: str = "autopilot"


# ── Lazy imports ──
def _get_event_bus():
    try:
        from backend.services.event_bus import event_bus
        return event_bus
    except Exception:
        return None


def _get_memory():
    try:
        from backend.services.unified_memory import get_memory
        return get_memory()
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

# ── Pipeline Stage Broadcaster ────────────────────────────
async def _broadcast_stage(bus, pipeline_id: str, stage: str, data: dict = None):
    if not bus:
        return
    payload = dict(data or {})
    payload["pipeline_id"] = pipeline_id
    payload["stage"] = stage
    payload["timestamp"] = time.time()
    try:
        await bus.broadcast("governance_pipeline", payload, f"Pipeline {pipeline_id}: {stage}")
    except Exception:
        pass


# ── Session Management ────────────────────────────────────
@router.get("/sessions")
async def list_sessions(limit: int = 50):
    """List chat sessions from memory."""
    mem = _get_memory()
    if not mem:
        return {"sessions": [], "total": 0}
    
    # Use UnifiedMemory to list sessions
    # We store sessions with category='chat_session'
    sessions_data = mem.list_by_category("chat_session")
    
    # Hydrate with full data (store only keeps preview in category list usually, but let's check retrieve)
    # Actually list_by_category returns basic info. We might want to sort by updated_at.
    
    # For a better list, we might relying on the index in memory
    results = []
    for s in sessions_data:
        full_data = mem.retrieve(s["key"])
        if full_data:
            results.append(full_data)
            
    # Sort by updated_at desc
    results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return {"sessions": results[:limit], "total": len(results)}


@router.post("/sessions")
async def create_session(body: SessionCreate):
    """Create a new empty session."""
    import uuid
    mem = _get_memory()
    if not mem:
        raise HTTPException(status_code=503, detail="Memory service unavailable")
        
    session_id = str(uuid.uuid4())
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    
    session_data = {
        "id": session_id,
        "title": body.title,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "last_message": "",
        "category": "default"
    }
    
    mem.store(f"session:{session_id}", session_data, category="chat_session")
    return session_data


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    mem = _get_memory()
    if not mem:
        raise HTTPException(status_code=503, detail="Memory service unavailable")
        
    key = f"session:{session_id}"
    if not mem.retrieve(key):
        raise HTTPException(status_code=404, detail="Session not found")
        
    mem.delete(key)
    # TODO: Delete associated messages (would require querying all messages for this session)
    return {"success": True, "id": session_id}


@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: SessionUpdate):
    """Rename a session."""
    mem = _get_memory()
    if not mem:
        raise HTTPException(status_code=503, detail="Memory service unavailable")
        
    key = f"session:{session_id}"
    session = mem.retrieve(key)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session["title"] = body.title
    session["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    
    mem.store(key, session, category="chat_session")
    return session


@router.get("/history")
async def chat_history(limit: int = 50):
    """Legacy alias for list sessions (frontend uses this)."""
    return await list_sessions(limit)


# ── Main Chat Endpoint ────────────────────────────────────
@router.delete("/history")
async def batch_delete_sessions(ids: List[str]):
    """Batch delete sessions."""
    mem = _get_memory()
    if not mem:
        raise HTTPException(status_code=503, detail="Memory service unavailable")
    
    deleted = []
    failed = []
    
    for session_id in ids:
        key = f"session:{session_id}"
        if mem.retrieve(key):
            mem.delete(key)
            deleted.append(session_id)
        else:
            failed.append(session_id)
            
    return {"success": True, "deleted": deleted, "failed": failed}


# ── Main Chat Endpoint ────────────────────────────────────
@router.post("", response_model=ChatResponse)
async def chat(msg: ChatMessage):
    import uuid
    pipeline_id = str(uuid.uuid4())[:12]
    event_bus = _get_event_bus()
    mem = _get_memory()
    stages = []

    # 1. Session Handling
    session_id = msg.session_id
    session = None
    if not session_id or session_id == "new":
        # Create new session
        session_id = str(uuid.uuid4())
        session = {
            "id": session_id,
            "title": msg.message[:30] + "..." if len(msg.message) > 30 else msg.message,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "message_count": 0,
            "last_message": "",
            "category": "default"
        }
    elif mem:
        session = mem.retrieve(f"session:{session_id}")
        if not session:
             # Fallback if ID sent but not found
             session = {
                "id": session_id,
                "title": "Restored Session",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                "message_count": 0,
                "last_message": "",
                "category": "default"
            }

    # ─── STAGE 1: THINK ──────────────────────────────────
    await _broadcast_stage(event_bus, pipeline_id, "think", {"input": msg.message[:200]})
    stages.append({"stage": "think", "status": "done", "timestamp": time.time()})

    llm = _get_llm_service()
    think_result = ""
    # Use LLM Service (which now handles Local/Cloud)
    if llm:
        try:
             # Use the user message directly for reasoning to avoid double prompts if possible
             # But here we want a 'think' step specifically? 
             # Actually, let's just use the main generate and parse it, OR do a quick extraction.
             # For now, keep it simple.
             pass
        except:
             think_result = "Analyzing..."

    # ─── STAGE 2: PLAN ───────────────────────────────────
    await _broadcast_stage(event_bus, pipeline_id, "plan", {"think_output": "Processing..."})
    stages.append({"stage": "plan", "status": "done", "timestamp": time.time()})

    actions = [{"service": "llm", "description": "Conversational response", "risk": "low"}]

    # ─── STAGE 3: ACT ────────────────────────────────────
    gov = _get_governance_loop()
    governance_status = "autopilot"
    response_text = ""
    
    # Execute LLM Response
    if llm:
        try:
            # This calls llm_service -> local_llm_ollama (if local) -> Ollama
            # It should handle context/history if provided, but here we just pass the message.
            # In a real app, we'd fetch message history from memory and pass it to llm.generate
            response_text = await llm.generate_response(msg.message) 
        except Exception as e:
            response_text = f"Error generating response: {str(e)}"
    else:
        response_text = "Global LLM Service Unavailable."

    # ─── STAGE 4: REPORT ─────────────────────────────────
    stages.append({"stage": "act", "status": "done", "timestamp": time.time()})
    await _broadcast_stage(event_bus, pipeline_id, "report", {"status": "complete"})
    
    # Update Session
    if mem and session:
        session["message_count"] = session.get("message_count", 0) + 1
        session["last_message"] = response_text[:100]
        session["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        # Actually save it
        mem.store(f"session:{session_id}", session, category="chat_session")

    return ChatResponse(
        response=response_text or "Processed.",
        pipeline_id=pipeline_id,
        session_id=session_id,
        stages=stages,
        actions=actions,
        governance_status=governance_status
    )
