"""
Council API Routes
Manage the Expert Councils
Now using SQLite persistence instead of in-memory storage
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.database import get_db, CouncilCategory, CouncilMember
from backend.domain.council import Council, Expert, INITIAL_COUNCILS
from backend.services.event_bus import event_bus
from backend.core.websocket_manager import websocket_manager
from datetime import datetime
import logging

router = APIRouter(prefix="/api/v1/council", tags=["council"])
logger = logging.getLogger(__name__)

def _council_category_to_domain(category: CouncilCategory, db: Session) -> Council:
    """Convert DB CouncilCategory to domain Council model"""
    try:
        # Ensure we have valid category data
        if not category:
            raise ValueError("Category is None")
        
        # Get members for this category
        members = db.query(CouncilMember).filter(
            CouncilMember.category_id == category.id
        ).order_by(CouncilMember.display_order.asc()).all()
        
        experts = []
        for member in members:
            try:
                # Safely get settings
                settings = member.settings_json if member.settings_json else {}
                if not isinstance(settings, dict):
                    settings = {}
                
                # Create expert with safe defaults
                expert = Expert(
                    id=f"{category.name.lower().replace(' ', '_')}_{member.id}",
                    name=member.name if member.name else "Unknown Expert",
                    role=settings.get("role", "") if isinstance(settings.get("role"), str) else "",
                    inspiration=member.persona_source if member.persona_source else "",
                    avatar=settings.get("avatar", "fa-user") if isinstance(settings.get("avatar"), str) else "fa-user",
                    status="active" if (member.enabled if member.enabled is not None else True) else "inactive",
                    expertise=settings.get("expertise", []) if isinstance(settings.get("expertise"), list) else []
                )
                experts.append(expert)
            except Exception as e:
                logger.warning(f"Error creating expert for member {member.id if member else 'unknown'}: {e}")
                continue
        
        # Safely get metadata
        metadata = category.metadata_json if category.metadata_json else {}
        if not isinstance(metadata, dict):
            metadata = {}
        
        # Create council ID from name
        council_id = category.name.lower().replace(" ", "_").replace("-", "_") if category.name else "unknown"
        
        return Council(
            id=council_id,
            name=category.name if category.name else "Unknown Council",
            description=metadata.get("description", "") if isinstance(metadata.get("description"), str) else "",
            icon=metadata.get("icon", "fa-users") if isinstance(metadata.get("icon"), str) else "fa-users",
            color=metadata.get("color", "#6B7280") if isinstance(metadata.get("color"), str) else "#6B7280",
            experts=experts,
            status="active" if (category.enabled if category.enabled is not None else True) else "inactive"
        )
    except Exception as e:
        logger.error(f"Error converting council category {category.id if category else 'unknown'} to domain: {e}", exc_info=True)
        # Return a minimal council instead of raising
        return Council(
            id=category.name.lower().replace(" ", "_") if category and category.name else "unknown",
            name=category.name if category and category.name else "Unknown Council",
            description="",
            icon="fa-users",
            color="#6B7280",
            experts=[],
            status="inactive"
        )

def _ensure_initial_councils(db: Session):
    """Ensure initial councils exist in DB"""
    try:
        logger.info(f"🌱 _ensure_initial_councils: Starting with {len(INITIAL_COUNCILS)} initial councils")
        councils_created = 0
        councils_existing = 0
        
        for council in INITIAL_COUNCILS:
            # Check if category exists
            category = db.query(CouncilCategory).filter(
                CouncilCategory.name == council.name
            ).first()
            
            if not category:
                logger.info(f"  Creating new council: {council.name}")
                # Create category
                category = CouncilCategory(
                    name=council.name,
                    enabled=(council.status == "active"),
                    metadata_json={
                        "description": council.description,
                        "icon": council.icon,
                        "color": council.color
                    }
                )
                db.add(category)
                db.flush()
                
                # Create members
                members_created = 0
                for idx, expert in enumerate(council.experts):
                    try:
                        member = CouncilMember(
                            category_id=category.id,
                            name=expert.name,
                            persona_source=expert.inspiration,
                            enabled=(expert.status == "active"),
                            settings_json={
                                "role": expert.role,
                                "avatar": expert.avatar,
                                "expertise": expert.expertise
                            },
                            display_order=idx
                        )
                        db.add(member)
                        members_created += 1
                    except Exception as member_error:
                        logger.error(f"    Error creating member {expert.name}: {member_error}")
                
                logger.info(f"  Created council '{council.name}' with {members_created} members")
                councils_created += 1
            else:
                councils_existing += 1
                logger.debug(f"  Council '{council.name}' already exists (id: {category.id})")
        
        if councils_created > 0:
            db.commit()
            logger.info(f"✅ Created {councils_created} new councils, {councils_existing} already existed")
        else:
            # Even if no new councils, ensure commit
            db.commit()
            logger.info(f"✅ All {councils_existing} councils already exist, no new ones created")
        
        # Verify councils exist
        total_categories = db.query(CouncilCategory).count()
        total_members = db.query(CouncilMember).count()
        logger.info(f"📊 Database state: {total_categories} categories, {total_members} members")
        
    except Exception as e:
        logger.error(f"❌ Error ensuring initial councils: {e}", exc_info=True)
        db.rollback()
        # Don't raise - allow graceful degradation
        pass

@router.get("/list")
async def list_councils(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all councils from database"""
    try:
        logger.info("📋 list_councils: Starting")
        
        # Ensure councils are seeded first - do this multiple times if needed
        max_attempts = 3
        for attempt in range(max_attempts):
            _ensure_initial_councils(db)
            db.commit()
            db.expire_all()
            
            categories = db.query(CouncilCategory).all()
            if categories:
                logger.info(f"  Attempt {attempt + 1}: Found {len(categories)} council categories")
                break
            else:
                logger.warning(f"  Attempt {attempt + 1}: No categories found, retrying seed...")
        
        categories = db.query(CouncilCategory).all()
        logger.info(f"  Final: Found {len(categories)} council categories in DB")
        
        if categories:
            logger.info(f"  Category names: {[c.name for c in categories]}")
        
        councils = []
        conversion_errors = []
        
        # Build councils list with error handling for each category
        for cat in categories:
            try:
                logger.debug(f"  Converting category {cat.id} ({cat.name})")
                council = _council_category_to_domain(cat, db)
                council_dict = council.dict()
                councils.append(council_dict)
                logger.debug(f"    ✓ Successfully converted '{cat.name}' to domain model")
            except Exception as e:
                error_msg = f"Error converting council category {cat.id} ({cat.name}) to domain: {e}"
                logger.error(f"    ❌ {error_msg}", exc_info=True)
                conversion_errors.append(error_msg)
                # Continue with other councils even if one fails
                continue
        
        # If still no councils, try to return raw data as fallback
        if not councils and categories:
            logger.warning(f"⚠️ No councils converted, but {len(categories)} categories exist. Returning raw data.")
            councils = [{
                "id": cat.name.lower().replace(' ', '_').replace('-', '_'),
                "name": cat.name,
                "description": (cat.metadata_json or {}).get("description", "") if isinstance(cat.metadata_json, dict) else "",
                "icon": (cat.metadata_json or {}).get("icon", "fa-users") if isinstance(cat.metadata_json, dict) else "fa-users",
                "color": (cat.metadata_json or {}).get("color", "#6B7280") if isinstance(cat.metadata_json, dict) else "#6B7280",
                "status": "active" if cat.enabled else "inactive",
                "experts": []
            } for cat in categories]
        
        if not councils:
            logger.error(f"⚠️ No councils found. Categories in DB: {len(categories)}")
            if categories:
                logger.error(f"  Category details:")
                for cat in categories:
                    members = db.query(CouncilMember).filter(CouncilMember.category_id == cat.id).all()
                    logger.error(f"    - {cat.name} (id: {cat.id}, enabled: {cat.enabled}, members: {len(members)}, metadata: {cat.metadata_json})")
                
                # Fallback: return raw category data if conversion fails
                logger.warning("  Attempting fallback: returning raw category data")
                for cat in categories:
                    try:
                        members = db.query(CouncilMember).filter(CouncilMember.category_id == cat.id).order_by(CouncilMember.display_order).all()
                        raw_council = {
                            "id": cat.name.lower().replace(" ", "_"),
                            "name": cat.name,
                            "description": (cat.metadata_json or {}).get("description", ""),
                            "icon": (cat.metadata_json or {}).get("icon", "fa-users"),
                            "color": (cat.metadata_json or {}).get("color", "#6B7280"),
                            "status": "active" if cat.enabled else "inactive",
                            "experts": [
                                {
                                    "id": f"{cat.name.lower().replace(' ', '_')}_{m.id}",
                                    "name": m.name or "Unknown",
                                    "role": (m.settings_json or {}).get("role", ""),
                                    "inspiration": m.persona_source or "",
                                    "avatar": (m.settings_json or {}).get("avatar", "fa-user"),
                                    "status": "active" if m.enabled else "inactive",
                                    "expertise": (m.settings_json or {}).get("expertise", [])
                                }
                                for m in members
                            ]
                        }
                        councils.append(raw_council)
                        logger.info(f"    ✓ Added raw council '{cat.name}' as fallback")
                    except Exception as fallback_error:
                        logger.error(f"    ❌ Fallback also failed for {cat.name}: {fallback_error}")
            
            if conversion_errors:
                logger.error(f"  Conversion errors: {conversion_errors}")
        
        if councils:
            logger.info(f"✅ Returning {len(councils)} councils")
        else:
            logger.error("❌ No councils to return after all attempts")
        
        return councils
    except Exception as e:
        logger.error(f"❌ Error listing councils: {e}", exc_info=True)
        # Return empty list instead of 500 error
        return []

@router.get("/{council_id}")
async def get_council(council_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get specific council details from database"""
    _ensure_initial_councils(db)
    
    # Find category by name (council_id is like "finance", "tech")
    category = db.query(CouncilCategory).filter(
        CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Council not found")
    
    council = _council_category_to_domain(category, db)
    return council.dict()

@router.post("/{council_id}/toggle")
async def toggle_council(
    council_id: str, 
    enabled: bool = Query(False, description="Enable (true) or disable (false) the council"),
    db: Session = Depends(get_db)
):
    """Enable/Disable a council
    
    Accepts enabled as query parameter: ?enabled=true or ?enabled=false
    """
    from fastapi import Query
    
    logger.info(f"🔄 toggle_council: Toggling '{council_id}' to enabled={enabled}")
    
    # Ensure councils are seeded first
    _ensure_initial_councils(db)
    db.commit()
    db.expire_all()
    
    # Try multiple ways to find the council
    # 1. By exact name match (e.g., "Finance Council")
    category = db.query(CouncilCategory).filter(
        CouncilCategory.name == council_id.replace('_', ' ').title() + " Council"
    ).first()
    
    # 2. By name containing the council_id (e.g., "finance" -> "Finance Council")
    if not category:
        category = db.query(CouncilCategory).filter(
            CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
        ).first()
    
    # 3. Try by ID if council_id is numeric
    if not category and council_id.isdigit():
        category = db.query(CouncilCategory).filter(
            CouncilCategory.id == int(council_id)
        ).first()
    
    # 4. Try exact match without "Council" suffix
    if not category:
        category = db.query(CouncilCategory).filter(
            CouncilCategory.name == council_id.replace('_', ' ').title()
        ).first()
    
    if not category:
        # List all available councils for debugging
        all_categories = db.query(CouncilCategory).all()
        available_names = [c.name for c in all_categories]
        logger.error(f"❌ Council '{council_id}' not found. Available councils: {available_names}")
        
        # If no councils exist, try to seed again
        if not all_categories:
            logger.warning("  No councils in DB, attempting emergency seed...")
            _ensure_initial_councils(db)
            db.commit()
            db.expire_all()
            all_categories = db.query(CouncilCategory).all()
            available_names = [c.name for c in all_categories]
            logger.info(f"  After emergency seed: {len(all_categories)} councils")
            
            # Try to find again
            category = db.query(CouncilCategory).filter(
                CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
            ).first()
        
        if not category:
            raise HTTPException(
                status_code=404, 
                detail=f"Council '{council_id}' not found. Available: {available_names}"
            )
    
    # Toggle the council
    old_status = category.enabled
    category.enabled = enabled
    category.updated_at = datetime.utcnow()
    db.commit()
    
    # Emit WebSocket event via unified event bus
    await event_bus.publish("council.updated", "council", council_id, {
        "council_id": council_id,
        "enabled": enabled
    })
    
    logger.info(f"✅ Toggled council '{category.name}' (id: {category.id}) from {old_status} to {enabled}")
    
    return {
        "success": True, 
        "status": "active" if enabled else "inactive", 
        "council_id": council_id,
        "council_name": category.name
    }

@router.post("/{council_id}/expert/{expert_id}/toggle")
async def toggle_expert(council_id: str, expert_id: str, enabled: bool, db: Session = Depends(get_db)):
    """Enable/Disable a specific expert"""
    _ensure_initial_councils(db)
    
    category = db.query(CouncilCategory).filter(
        CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Council not found")
    
    # Find member by ID (expert_id is like "fin_1", extract numeric part)
    member_id = int(expert_id.split("_")[-1]) if expert_id.split("_")[-1].isdigit() else None
    if member_id:
        member = db.query(CouncilMember).filter(
            CouncilMember.category_id == category.id,
            CouncilMember.id == member_id
        ).first()
    else:
        # Fallback: search by name
        member = db.query(CouncilMember).filter(
            CouncilMember.category_id == category.id,
            CouncilMember.name.ilike(f"%{expert_id}%")
        ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Expert not found")
    
    member.enabled = enabled
    member.updated_at = datetime.utcnow()
    db.commit()
    
    # Emit WebSocket event
    await event_bus.publish("council.member.updated", "council", council_id, {
        "council_id": council_id,
        "expert_id": expert_id,
        "enabled": enabled
    })
    
    return {"success": True, "expert_status": "active" if enabled else "inactive"}

@router.post("/create")
async def create_council(
    name: str,
    description: str = "",
    icon: str = "fa-users",
    color: str = "#6B7280",
    db: Session = Depends(get_db)
):
    """Create a new council"""
    # Check if council already exists
    existing = db.query(CouncilCategory).filter(CouncilCategory.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Council '{name}' already exists")
    
    category = CouncilCategory(
        name=name,
        enabled=True,
        metadata_json={
            "description": description,
            "icon": icon,
            "color": color
        }
    )
    
    db.add(category)
    db.commit()
    db.refresh(category)
    
    council_dict = _council_category_to_domain(category, db).dict()
    
    # Emit WebSocket event
    await websocket_manager.publish_event(
        event_type="council.created",
        entity_type="council",
        entity_id=council_dict["id"],
        payload={"council": council_dict}
    )
    
    return {
        "success": True,
        "council": council_dict
    }

@router.post("/{council_id}/debate/start")
async def start_debate(
    council_id: str,
    topic: str,
    db: Session = Depends(get_db)
):
    """Start a debate session for a council"""
    from backend.services.chat_service import chat_service
    
    _ensure_initial_councils(db)
    
    category = db.query(CouncilCategory).filter(
        CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Council not found")
    
    # Create debate session in chat storage
    session = chat_service.create_session(
        db=db,
        title=f"Debate: {topic}",
        category="council",
        scope_type="council",
        scope_id=str(category.id),
        context={
            "council_id": council_id,
            "council_name": category.name,
            "topic": topic,
            "type": "debate"
        }
    )
    
    # Emit WebSocket event
    await event_bus.publish_chat_event("council.debate.started", session.session_id, {
        "council_id": council_id,
        "session_id": session.session_id,
        "topic": topic
    })
    
    return {
        "success": True,
        "session_id": session.session_id,
        "council_id": council_id,
        "topic": topic
    }

@router.post("/{council_id}/debate/{session_id}/message")
async def debate_message(
    council_id: str,
    session_id: str,
    expert_id: str,
    message: str,
    db: Session = Depends(get_db)
):
    """Add a message to a debate session"""
    from backend.services.chat_service import chat_service
    
    _ensure_initial_councils(db)
    
    # Verify session exists and belongs to this council
    session = chat_service.get_session(db, session_id)
    if not session or session.scope_type != "council":
        raise HTTPException(status_code=404, detail="Debate session not found")
    
    # Get expert name
    category = db.query(CouncilCategory).filter(
        CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Council not found")
    
    member_id = int(expert_id.split("_")[-1]) if expert_id.split("_")[-1].isdigit() else None
    expert_name = "Unknown Expert"
    if member_id:
        member = db.query(CouncilMember).filter(
            CouncilMember.category_id == category.id,
            CouncilMember.id == member_id
        ).first()
        if member:
            expert_name = member.name
    
    # Add message to debate session
    chat_service.add_message(
        db=db,
        session_id=session_id,
        sender=expert_name,
        content=message,
        model="council_debate"
    )
    
    # Emit WebSocket event via unified event bus
    await event_bus.publish_chat_event("council.debate.message", session_id, {
        "council_id": council_id,
        "session_id": session_id,
        "expert_id": expert_id,
        "expert_name": expert_name,
        "sender": expert_name,
        "content": message
    })
    
    return {"success": True, "message": "Debate message added"}

@router.get("/{council_id}/debate/{session_id}")
async def get_debate(
    council_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get debate session details and messages"""
    from backend.services.chat_service import chat_service
    
    _ensure_initial_councils(db)
    
    session = chat_service.get_session(db, session_id)
    if not session or session.scope_type != "council":
        raise HTTPException(status_code=404, detail="Debate session not found")
    
    messages = chat_service.get_session_messages(db, session_id)
    
    return {
        "success": True,
        "session_id": session_id,
        "council_id": council_id,
        "topic": session.context_json.get("topic", ""),
        "messages": [
            {
                "sender": msg.sender,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    }

@router.post("/{council_id}/debate/{session_id}/synthesize")
async def synthesize_debate(
    council_id: str,
    session_id: str,
    db: Session = Depends(get_db)
):
    """Synthesize debate into final decision/recommendation"""
    from backend.services.chat_service import chat_service
    from backend.services.llm_service import llm_service
    
    _ensure_initial_councils(db)
    
    session = chat_service.get_session(db, session_id)
    if not session or session.scope_type != "council":
        raise HTTPException(status_code=404, detail="Debate session not found")
    
    messages = chat_service.get_session_messages(db, session_id)
    
    # Build synthesis prompt
    debate_text = "\n".join([f"{msg.sender}: {msg.content}" for msg in messages])
    synthesis_prompt = f"""You are the council synthesizer for MAS-AI. You are NOT Alibaba Cloud, NOT Qwen. Do not use "Subject:", "Dear Team", or formal letter format. Do not sign with "[Your Name]" or "Knowledge Synthesizer" or "Alibaba Cloud".

Synthesize this debate into a short, clear recommendation (2-5 paragraphs). No formal memo style.

Topic: {session.context_json.get('topic', 'Unknown')}

Debate Transcript:
{debate_text}

Provide:
1. Key points from participants
2. Agreement and disagreement
3. Clear, actionable recommendation
4. Caveats if any"""
    
    if llm_service.is_ollama_available():
        synthesis = await llm_service.generate_response(synthesis_prompt, max_tokens=800, temperature=0.6)
        if synthesis and ("Alibaba Cloud" in synthesis or "Qwen" in synthesis):
            synthesis = synthesis.replace("Alibaba Cloud", "the council").replace("Qwen", "we")
    else:
        synthesis = f"Synthesis for debate on '{session.context_json.get('topic', 'Unknown')}': The debate transcript contains {len(messages)} messages. In offline mode, please review the debate transcript manually to synthesize the key points and recommendations."
    
    # Store synthesis as a message
    chat_service.add_message(
        db=db,
        session_id=session_id,
        sender="Synthesis",
        content=synthesis,
        model="synthesis"
    )
    
    # Emit WebSocket event
    await event_bus.publish_chat_event("council.debate.synthesized", session_id, {
        "council_id": council_id,
        "session_id": session_id,
        "synthesis": synthesis
    })
    
    return {
        "success": True,
        "session_id": session_id,
        "synthesis": synthesis
    }

@router.put("/{council_id}/expert/{expert_id}")
async def update_expert(
    council_id: str,
    expert_id: str,
    name: str = None,
    role: str = None,
    inspiration: str = None,
    expertise: List[str] = None,
    db: Session = Depends(get_db)
):
    """Update expert details (rename, change training notes, etc.)"""
    from backend.core.websocket_manager import websocket_manager
    
    _ensure_initial_councils(db)
    
    category = db.query(CouncilCategory).filter(
        CouncilCategory.name.ilike(f"%{council_id.replace('_', ' ')}%")
    ).first()
    
    if not category:
        raise HTTPException(status_code=404, detail="Council not found")
    
    # Find member
    member_id = int(expert_id.split("_")[-1]) if expert_id.split("_")[-1].isdigit() else None
    if member_id:
        member = db.query(CouncilMember).filter(
            CouncilMember.category_id == category.id,
            CouncilMember.id == member_id
        ).first()
    else:
        member = db.query(CouncilMember).filter(
            CouncilMember.category_id == category.id,
            CouncilMember.name.ilike(f"%{expert_id}%")
        ).first()
    
    if not member:
        raise HTTPException(status_code=404, detail="Expert not found")
    
    # Update fields
    if name:
        member.name = name
    if inspiration:
        member.persona_source = inspiration
    
    # Update settings
    settings = member.settings_json if member.settings_json else {}
    if role:
        settings["role"] = role
    if expertise:
        settings["expertise"] = expertise
    
    member.settings_json = settings
    member.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(member)
    
    expert_data = {
        "id": expert_id,
        "name": member.name,
        "role": settings.get("role", ""),
        "inspiration": member.persona_source
    }
    
    # Emit WebSocket event
    await websocket_manager.publish_event(
        event_type="council.member.updated",
        entity_type="council_member",
        entity_id=expert_id,
        payload={
            "council_id": council_id,
            "expert": expert_data
        }
    )
    
    return {
        "success": True,
        "expert": expert_data
    }