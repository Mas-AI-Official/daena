"""
Councils API - DB-backed council management with agent coordination
Replaced in-memory _councils dict with SQLite persistence
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/councils", tags=["councils"])


class CouncilCreate(BaseModel):
    name: str
    description: Optional[str] = None
    member_agent_ids: List[str] = []


class CouncilUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class CouncilChatRequest(BaseModel):
    message: str
    context: Dict[str, Any] = {}


def _seed_default_councils(db):
    """Seed default councils if table is empty"""
    from backend.database import Council
    
    if db.query(Council).count() > 0:
        return  # Already seeded
    
    default_councils = [
        {
            "council_id": "C1",
            "name": "Executive Council",
            "description": "Strategic decision-making and company direction",
            "member_agent_ids": [],  # Will be populated with real agent IDs
            "is_active": True
        },
        {
            "council_id": "C2",
            "name": "Technical Council",
            "description": "Technical architecture and engineering decisions",
            "member_agent_ids": [],
            "is_active": True
        }
    ]
    
    for c in default_councils:
        council = Council(**c)
        db.add(council)
    
    db.commit()
    logger.info("✅ Seeded default councils")


@router.get("")
@router.get("/list")
async def list_councils() -> Dict[str, Any]:
    """List all councils - DB-BACKED"""
    from backend.database import SessionLocal, Council
    
    db = SessionLocal()
    try:
        # Seed defaults if empty
        _seed_default_councils(db)
        
        councils = db.query(Council).filter(Council.is_active == True).all()
        
        council_list = []
        for c in councils:
            # Create expert stubs based on member_agent_ids
            member_ids = c.member_agent_ids or []
            experts = []
            for i, agent_id in enumerate(member_ids[:5]):  # Max 5 experts shown
                experts.append({
                    "id": agent_id,
                    "name": f"Expert {i+1}",
                    "role": "Council Member",
                    "inspiration": "",
                    "avatar": "fa-user",
                    "status": "active"
                })
            # Fill with placeholders if less than 5
            while len(experts) < 5:
                experts.append({
                    "id": f"{c.council_id}_expert_{len(experts)+1}",
                    "name": f"Expert {len(experts)+1}",
                    "role": "Council Member",
                    "inspiration": "",
                    "avatar": "fa-user",
                    "status": "inactive"
                })
            
            council_list.append({
                "id": c.council_id,
                "name": c.name,
                "description": c.description or "",
                "icon": getattr(c, 'icon', 'fa-users') or 'fa-users',
                "status": "active" if c.is_active else "inactive",
                "member_agent_ids": member_ids,
                "experts": experts,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None
            })
        
        return council_list  # Return list directly for frontend compatibility
    finally:
        db.close()


@router.get("/{council_id}")
async def get_council(council_id: str) -> Dict[str, Any]:
    """Get specific council details - DB-BACKED"""
    from backend.database import SessionLocal, Council, Agent
    
    db = SessionLocal()
    try:
        council = db.query(Council).filter(Council.council_id == council_id).first()
        if not council:
            raise HTTPException(status_code=404, detail=f"Council not found: {council_id}")
        
        # Get member details
        member_details = []
        for agent_id in (council.member_agent_ids or []):
            agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
            if agent:
                member_details.append({
                    "id": agent.cell_id or str(agent.id),
                    "name": agent.name,
                    "role": agent.role,
                    "department": agent.department
                })
        
        return {
            "success": True,
            "council": {
                "id": council.council_id,
                "name": council.name,
                "description": council.description,
                "member_agent_ids": council.member_agent_ids or [],
                "members": member_details,
                "is_active": council.is_active,
                "created_at": council.created_at.isoformat() if council.created_at else None,
                "updated_at": council.updated_at.isoformat() if council.updated_at else None
            }
        }
    finally:
        db.close()


@router.post("")
async def create_council(council_data: CouncilCreate) -> Dict[str, Any]:
    """Create a new council - DB-BACKED"""
    from backend.database import SessionLocal, Council
    
    db = SessionLocal()
    try:
        # Generate next council ID
        max_council = db.query(Council).order_by(Council.id.desc()).first()
        next_id = (max_council.id + 1) if max_council else 1
        council_id = f"C{next_id}"
        
        council = Council(
            council_id=council_id,
            name=council_data.name,
            description=council_data.description,
            member_agent_ids=council_data.member_agent_ids,
            is_active=True
        )
        
        db.add(council)
        db.commit()
        db.refresh(council)
        
        # Emit WebSocket event
        try:
            from backend.services.event_bus import event_bus
            await event_bus.publish_event("council.created", "council", council_id, {
                "id": council_id,
                "name": council.name
            })
        except Exception as e:
            logger.warning(f"Could not emit council.created event: {e}")
        
        return {
            "success": True,
            "council": {
                "id": council_id,
                "name": council.name,
                "description": council.description,
                "member_agent_ids": council.member_agent_ids or [],
                "is_active": council.is_active
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create council: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.put("/{council_id}")
async def update_council(council_id: str, update_data: CouncilUpdate) -> Dict[str, Any]:
    """Update council - DB-BACKED"""
    from backend.database import SessionLocal, Council
    
    db = SessionLocal()
    try:
        council = db.query(Council).filter(Council.council_id == council_id).first()
        if not council:
            raise HTTPException(status_code=404, detail=f"Council not found: {council_id}")
        
        if update_data.name:
            council.name = update_data.name
        if update_data.description is not None:
            council.description = update_data.description
        if update_data.is_active is not None:
            council.is_active = update_data.is_active
        
        council.updated_at = datetime.utcnow()
        db.commit()
        
        # Emit WebSocket event
        try:
            from backend.services.event_bus import event_bus
            await event_bus.publish_event("council.updated", "council", council_id, {
                "id": council_id,
                "name": council.name
            })
        except Exception as e:
            logger.warning(f"Could not emit council.updated event: {e}")
        
        return {
            "success": True,
            "council": {
                "id": council.council_id,
                "name": council.name,
                "description": council.description,
                "is_active": council.is_active
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update council: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.delete("/{council_id}")
async def delete_council(council_id: str) -> Dict[str, Any]:
    """Delete council - DB-BACKED (soft delete)"""
    from backend.database import SessionLocal, Council
    
    db = SessionLocal()
    try:
        council = db.query(Council).filter(Council.council_id == council_id).first()
        if not council:
            raise HTTPException(status_code=404, detail=f"Council not found: {council_id}")
        
        # Soft delete
        council.is_active = False
        council.updated_at = datetime.utcnow()
        db.commit()
        
        # Emit WebSocket event
        try:
            from backend.services.event_bus import event_bus
            await event_bus.publish_event("council.deleted", "council", council_id, {
                "id": council_id,
                "deleted": True
            })
        except Exception as e:
            logger.warning(f"Could not emit council.deleted event: {e}")
        
        return {
            "success": True,
            "message": f"Council {council_id} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete council: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/{council_id}/chat")
async def council_chat(council_id: str, request: CouncilChatRequest) -> Dict[str, Any]:
    """Chat with a council - coordinates responses from all member agents"""
    from backend.database import SessionLocal, Council, Agent
    
    db = SessionLocal()
    try:
        council = db.query(Council).filter(Council.council_id == council_id).first()
        if not council:
            raise HTTPException(status_code=404, detail=f"Council not found: {council_id}")
        
        member_ids = council.member_agent_ids or []
        
        if not member_ids:
            return {
                "success": False,
                "error": "Council has no members"
            }
        
        # Query each member agent
        member_responses = []
        
        for agent_id in member_ids:
            agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
            if not agent:
                continue
            
            # Call agent's chat endpoint
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"http://localhost:8000/api/v1/agents/{agent_id}/chat",
                        json={
                            "message": request.message,
                            "context": request.context
                        }
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("success"):
                            member_responses.append({
                                "agent_id": agent_id,
                                "agent_name": agent.name,
                                "agent_role": agent.role,
                                "response": data.get("response")
                            })
            except Exception as e:
                logger.error(f"Error querying agent {agent_id}: {e}")
                member_responses.append({
                    "agent_id": agent_id,
                    "agent_name": agent.name,
                    "error": str(e)
                })
        
        # Synthesize council decision
        council_decision = _synthesize_council_decision(member_responses, council.name)
        
        return {
            "success": True,
            "council": {
                "id": council_id,
                "name": council.name
            },
            "member_responses": member_responses,
            "council_decision": council_decision,
            "response_count": len(member_responses)
        }
    finally:
        db.close()


@router.get("/{council_id}/members")
async def get_council_members(council_id: str) -> Dict[str, Any]:
    """Get council members - DB-BACKED"""
    from backend.database import SessionLocal, Council, Agent
    
    db = SessionLocal()
    try:
        council = db.query(Council).filter(Council.council_id == council_id).first()
        if not council:
            raise HTTPException(status_code=404, detail=f"Council not found: {council_id}")
        
        members = []
        for agent_id in (council.member_agent_ids or []):
            agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
            if agent:
                members.append({
                    "id": agent.cell_id or str(agent.id),
                    "name": agent.name,
                    "role": agent.role,
                    "department": agent.department,
                    "status": agent.status
                })
        
        return {
            "success": True,
            "council_id": council_id,
            "members": members,
            "count": len(members)
        }
    finally:
        db.close()


@router.post("/{council_id}/members")
async def add_council_member(council_id: str, agent_id: str) -> Dict[str, Any]:
    """Add a member to a council - DB-BACKED"""
    from backend.database import SessionLocal, Council, Agent
    
    db = SessionLocal()
    try:
        council = db.query(Council).filter(Council.council_id == council_id).first()
        if not council:
            raise HTTPException(status_code=404, detail=f"Council not found: {council_id}")
        
        # Verify agent exists
        agent = db.query(Agent).filter(Agent.cell_id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
        
        # Add member if not already present
        member_ids = council.member_agent_ids or []
        if agent_id not in member_ids:
            member_ids.append(agent_id)
            council.member_agent_ids = member_ids
            council.updated_at = datetime.utcnow()
            db.commit()
        
        return {
            "success": True,
            "message": f"Agent {agent_id} added to council {council_id}",
            "member_count": len(member_ids)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to add council member: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


def _synthesize_council_decision(member_responses: List[Dict], council_name: str) -> str:
    """
    Synthesize a council decision from member responses
    TODO: Use LLM to synthesize intelligent consensus
    """
    if not member_responses:
        return "Council unable to reach decision - no member responses"
    
    # Simple synthesis for now
    decision_parts = [f"**{council_name} Decision:**\n"]
    
    for i, resp in enumerate(member_responses, 1):
        if "error" not in resp:
            decision_parts.append(f"{i}. **{resp['agent_name']}** ({resp['agent_role']}): {resp['response'][:200]}...")
    
    decision_parts.append(f"\n**Consensus**: Based on {len(member_responses)} member inputs.")
    
    return "\n\n".join(decision_parts)
