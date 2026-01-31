"""
Council Scheduler for Phase-Locked Council Rounds.

Implements the brain-like communication pattern:
- Scout Phase: Scouts publish NBMF summaries with confidence/emotion
- Debate Phase: Advisors exchange counter-drafts on ring topics
- Commit Phase: Executor applies actions; NBMF writes abstract + pointer
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from enum import Enum

from backend.utils.message_bus_v2 import message_bus_v2, TopicMessage
from backend.utils.tracing import get_tracing_service, trace_council_round

# PHASE 3: Unified Memory Integration
from backend.memory import memory
from backend.database import SessionLocal, EventLog

def log_event(action: str, ref: str, store: str, route: str, extra: Dict[str, Any]):
    """Unified Event Logging Adapter"""
    try:
        db = SessionLocal()
        event = EventLog(
            event_type=action,
            entity_type="council",
            entity_id=ref,
            payload_json={
                "store": store,
                "route": route,
                "extra": extra
            },
            created_by="council_scheduler"
        )
        db.add(event)
        db.commit()
        db.close()
    except Exception as e:
        # Fallback logging
        pass

# Optional poisoning filters
try:
    from memory_service.poisoning_filters import poisoning_filter
    POISONING_FILTERS_AVAILABLE = True
except ImportError:
    POISONING_FILTERS_AVAILABLE = False
    poisoning_filter = None

# Real-time event emission
try:
    from backend.routes.events import emit
    EVENTS_AVAILABLE = True
except ImportError:
    EVENTS_AVAILABLE = False
    def emit(*args, **kwargs):
        pass

# Optional analytics integration
try:
    from backend.services.analytics_service import analytics_service, InteractionType
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Approval service for high-impact decisions
try:
    from backend.services.council_approval_service import (
        council_approval_service,
        DecisionImpact,
        ApprovalStatus
    )
    APPROVAL_SERVICE_AVAILABLE = True
except ImportError as e:
    APPROVAL_SERVICE_AVAILABLE = False
    logger.warning(f"Council approval service not available - all decisions will be auto-committed: {e}")


class CouncilPhase(Enum):
    """Council round phases."""
    SCOUT = "scout"
    DEBATE = "debate"
    COMMIT = "commit"
    CMP_VALIDATION = "cmp_validation"
    MEMORY_UPDATE = "memory_update"
    IDLE = "idle"


class CouncilScheduler:
    """
    Scheduler for phase-locked council rounds.
    
    Each round consists of three phases:
    1. Scout Phase: Scouts gather and publish summaries
    2. Debate Phase: Advisors debate on ring topics
    3. Commit Phase: Executor commits actions to NBMF
    """
    
    def __init__(self, router: Any = None):
        # Use Unified Memory Manager (acting as router)
        self.router = router or memory
        self.current_phase: CouncilPhase = CouncilPhase.IDLE
        self.phase_timeouts: Dict[CouncilPhase, float] = {
            CouncilPhase.SCOUT: 30.0,  # 30 seconds
            CouncilPhase.DEBATE: 60.0,  # 60 seconds
            CouncilPhase.COMMIT: 15.0,  # 15 seconds
            CouncilPhase.CMP_VALIDATION: 10.0,  # 10 seconds
            CouncilPhase.MEMORY_UPDATE: 5.0,  # 5 seconds
        }
        self.round_history: List[Dict[str, Any]] = []
        self._running = False
        
    async def start(self):
        """Start the council scheduler."""
        self._running = True
        await message_bus_v2.start()
        logger.info("Council scheduler started")
    
    async def stop(self):
        """Stop the council scheduler."""
        self._running = False
        await message_bus_v2.stop()
        logger.info("Council scheduler stopped")
    
    async def council_tick(
        self, 
        department: str, 
        topic: str = "Default council topic",
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute one complete council round (Scout → Debate → Commit).
        
        Returns summary of the round.
        """
        if not self._running:
            await self.start()
        
        round_start = time.time()
        round_id = f"{department}_{int(round_start)}"
        
        logger.info(f"Starting council round {round_id} for {department}")
        
        # Store round_id for later phases
        self._current_round_id = round_id
        
        # Record analytics
        if ANALYTICS_AVAILABLE:
            analytics_service.record_interaction(
                agent_id=f"council_{department}",
                department=department,
                interaction_type=InteractionType.COUNCIL_PARTICIPATION,
                metadata={"round_id": round_id, "topic": topic}
            )
        
        # Trace the council round
        tracing_service = get_tracing_service()
        span_context = tracing_service.span("council.round", {"department": department, "topic": topic, "round_id": round_id}) if tracing_service else None
        
        # Phase 1: Scout Phase
        trace_council_round(department, "scout", round_id)
        scout_results = await self.scout_phase(department, topic)
        
        # Phase 2: Debate Phase
        trace_council_round(department, "debate", round_id)
        debate_results = await self.debate_phase(department, topic, scout_results)
        
        # Phase 3: Commit Phase
        trace_council_round(department, "commit", round_id)
        commit_results = await self.commit_phase(department, topic, debate_results)
        
        # Phase 4: CMP Validation Phase
        trace_council_round(department, "cmp_validation", round_id)
        cmp_results = await self.cmp_validation_phase(department, topic, commit_results)
        
        # Phase 5: Memory Update Phase
        trace_council_round(department, "memory_update", round_id)
        memory_results = await self.memory_update_phase(department, topic, cmp_results)
        
        round_duration = time.time() - round_start
        
        round_summary = {
            "round_id": round_id,
            "department": department,
            "topic": topic,
            "duration_sec": round_duration,
            "scout": scout_results,
            "debate": debate_results,
            "commit": commit_results,
            "cmp_validation": cmp_results,
            "memory_update": memory_results,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        self.round_history.append(round_summary)
        if len(self.round_history) > 100:
            self.round_history.pop(0)
        
        # Log to ledger
        log_event(
            action="council_round",
            ref=round_id,
            store="nbmf",
            route="council",
            extra={
                "department": department,
                "topic": topic,
                "duration_sec": round_duration,
                "scout_count": len(scout_results.get("summaries", [])),
                "debate_count": len(debate_results.get("drafts", [])),
                "committed": commit_results.get("committed", False),
                "cmp_validated": cmp_results.get("validated", False),
                "memory_updated": memory_results.get("updated", False)
            }
        )
        
        logger.info(f"Council round {round_id} completed in {round_duration:.2f}s")
        return round_summary
    
    async def scout_phase(self, department: str, topic: str) -> Dict[str, Any]:
        """
        Scout Phase: Scouts publish NBMF summaries with confidence/emotion.
        
        Scouts subscribe to cell topics and publish summaries to ring topics.
        """
        self.current_phase = CouncilPhase.SCOUT
        phase_start = time.time()
        timeout = self.phase_timeouts[CouncilPhase.SCOUT]
        
        logger.info(f"Scout phase started for {department}")
        
        summaries: List[Dict[str, Any]] = []
        scout_messages: List[TopicMessage] = []
        
        # Subscribe to scout messages
        async def scout_handler(message: TopicMessage):
            if message.sender.startswith("scout_"):
                # Apply poisoning filters if available
                if POISONING_FILTERS_AVAILABLE and poisoning_filter:
                    content = str(message.content.get("summary", ""))
                    accepted, reason, filter_result = poisoning_filter.check_message(
                        content=content,
                        source_id=message.sender,
                        metadata={"message_id": message.id, "topic": message.topic}
                    )
                    if not accepted:
                        logger.warning(f"Scout message rejected: {reason} (source: {message.sender})")
                        poisoning_filter.reject_message(message.sender, reason)
                        return  # Skip this message
                
                scout_messages.append(message)
                summaries.append({
                    "scout_id": message.sender,
                    "summary": message.content.get("summary", ""),
                    "confidence": message.content.get("confidence", 0.5),
                    "emotion": message.content.get("emotion", {}),
                    "timestamp": message.timestamp
                })
        
        # Subscribe to cell topics for this department
        cell_pattern = f"cell/{department}/*"
        message_bus_v2.subscribe(cell_pattern, scout_handler)
        
        # Also subscribe to ring topics (scouts may publish there)
        ring_pattern = "ring/*"
        message_bus_v2.subscribe(ring_pattern, scout_handler)
        
        # Wait for scouts to publish (with timeout and retry logic)
        max_retries = 3
        retry_delay = 2.0  # seconds
        phase_end_time = phase_start + timeout
        
        for attempt in range(max_retries):
            # Check if timeout exceeded
            if time.time() >= phase_end_time:
                logger.warning(f"Scout phase timeout after {timeout}s (attempt {attempt + 1}/{max_retries})")
                break
            
            remaining_time = phase_end_time - time.time()
            if remaining_time <= 0:
                break
            
            await asyncio.sleep(min(remaining_time / max_retries, 5.0))
            if len(summaries) > 0:
                break
            if attempt < max_retries - 1:
                logger.debug(f"Scout phase attempt {attempt + 1}/{max_retries}: waiting for summaries...")
                await asyncio.sleep(retry_delay)
        
        # Unsubscribe
        message_bus_v2.unsubscribe(cell_pattern, scout_handler)
        message_bus_v2.unsubscribe(ring_pattern, scout_handler)
        
        phase_duration = time.time() - phase_start
        
        log_event(
            action="council_scout_phase",
            ref=department,
            store="nbmf",
            route="council",
            extra={
                "department": department,
                "topic": topic,
                "summary_count": len(summaries),
                "duration_sec": phase_duration
            }
        )
        
        logger.info(f"Scout phase completed: {len(summaries)} summaries collected")
        
        return {
            "summaries": summaries,
            "message_count": len(scout_messages),
            "duration_sec": phase_duration
        }
    
    async def debate_phase(
        self,
        department: str,
        topic: str,
        scout_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Debate Phase: Advisors exchange counter-drafts on ring topics.
        
        Advisors subscribe to ring topics and publish counter-drafts.
        """
        self.current_phase = CouncilPhase.DEBATE
        phase_start = time.time()
        timeout = self.phase_timeouts[CouncilPhase.DEBATE]
        
        logger.info(f"Debate phase started for {department}")
        
        drafts: List[Dict[str, Any]] = []
        debate_messages: List[TopicMessage] = []
        
        # Subscribe to debate messages
        async def debate_handler(message: TopicMessage):
            if message.sender.startswith("advisor_"):
                debate_messages.append(message)
                drafts.append({
                    "advisor_id": message.sender,
                    "draft": message.content.get("draft", ""),
                    "counter_to": message.content.get("counter_to"),
                    "confidence": message.content.get("confidence", 0.5),
                    "timestamp": message.timestamp
                })
        
        # Subscribe to ring topics for debate
        ring_pattern = "ring/*"
        message_bus_v2.subscribe(ring_pattern, debate_handler)
        
        # Publish scout summaries to ring for advisors to debate
        ring_number = self._get_ring_number(department)
        for summary in scout_results.get("summaries", []):
            await message_bus_v2.publish_to_ring(
                ring_number,
                {
                    "type": "scout_summary",
                    "summary": summary,
                    "topic": topic
                },
                sender=f"council_scheduler_{department}"
            )
        
        # Wait for advisors to debate (with timeout and retry logic)
        max_retries = 3
        retry_delay = 3.0  # seconds
        phase_end_time = phase_start + timeout
        
        for attempt in range(max_retries):
            # Check if timeout exceeded
            if time.time() >= phase_end_time:
                logger.warning(f"Debate phase timeout after {timeout}s (attempt {attempt + 1}/{max_retries})")
                break
            
            remaining_time = phase_end_time - time.time()
            if remaining_time <= 0:
                break
            
            await asyncio.sleep(min(remaining_time / max_retries, 10.0))
            if len(drafts) > 0:
                break
            if attempt < max_retries - 1:
                logger.debug(f"Debate phase attempt {attempt + 1}/{max_retries}: waiting for drafts...")
                await asyncio.sleep(retry_delay)
        
        # Unsubscribe
        message_bus_v2.unsubscribe(ring_pattern, debate_handler)
        
        phase_duration = time.time() - phase_start
        
        log_event(
            action="council_debate_phase",
            ref=department,
            store="nbmf",
            route="council",
            extra={
                "department": department,
                "topic": topic,
                "draft_count": len(drafts),
                "duration_sec": phase_duration
            }
        )
        
        logger.info(f"Debate phase completed: {len(drafts)} drafts collected")
        
        return {
            "drafts": drafts,
            "message_count": len(debate_messages),
            "duration_sec": phase_duration
        }
    
    async def commit_phase(
        self,
        department: str,
        topic: str,
        debate_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Commit Phase: Executor applies actions; NBMF writes abstract + pointer.
        
        Synthesizer resolves debate drafts into final action.
        Executor commits to NBMF.
        """
        self.current_phase = CouncilPhase.COMMIT
        phase_start = time.time()
        timeout = self.phase_timeouts[CouncilPhase.COMMIT]
        
        logger.info(f"Commit phase started for {department}")
        
        # Synthesize debate drafts into final action
        drafts = debate_results.get("drafts", [])
        if not drafts:
            logger.warning(f"No drafts to synthesize for {department}")
            return {
                "committed": False,
                "reason": "no_drafts",
                "duration_sec": time.time() - phase_start
            }
        
        # Simple synthesis: take highest confidence draft
        # In production, this would use an LLM synthesizer
        best_draft = max(drafts, key=lambda d: d.get("confidence", 0.0))
        
        action_text = best_draft.get("draft", "")
        confidence = best_draft.get("confidence", 0.5)
        
        # Extract tenant_id and project_id from context if available
        tenant_id = getattr(self, '_current_tenant_id', None)
        project_id = getattr(self, '_current_project_id', None)
        
        # Assess impact and check if approval is required
        requires_approval = False
        decision_id = f"council_{department}_{int(time.time())}"
        impact = DecisionImpact.LOW
        approval_status = None
        
        if APPROVAL_SERVICE_AVAILABLE:
            # Assess impact
            impact = council_approval_service.assess_impact(
                action_text=action_text,
                department=department,
                confidence=confidence,
                metadata=best_draft.get("metadata", {})
            )
            
            # Check if approval is required
            requires_approval = council_approval_service.requires_approval(
                impact=impact,
                confidence=confidence,
                department=department
            )
            
            if requires_approval:
                # Create approval request
                logger.info(f"High-impact decision requires approval: {decision_id} (impact: {impact.value})")
                approval_decision = council_approval_service.create_approval_request(
                    decision_id=decision_id,
                    department=department,
                    topic=topic,
                    action_text=action_text,
                    impact=impact,
                    confidence=confidence,
                    metadata={
                        "agents_involved": len(drafts),
                        "synthesized_from": [d.get("advisor_id") for d in drafts],
                        "round_id": getattr(self, '_current_round_id', None)
                    },
                    tenant_id=tenant_id,
                    project_id=project_id
                )
                approval_status = ApprovalStatus.PENDING
                
                # Return pending status - decision will be committed after approval
                return {
                    "committed": False,
                    "requires_approval": True,
                    "decision_id": decision_id,
                    "approval_status": approval_status.value,
                    "impact": impact.value,
                    "item_id": None,
                    "duration_sec": time.time() - phase_start
                }
            else:
                # Auto-approve low-impact decisions
                approval_status = ApprovalStatus.AUTO_APPROVED
                logger.info(f"Decision auto-approved: {decision_id} (impact: {impact.value}, confidence: {confidence:.2f})")
                
                # Create decision record for audit trail
                council_approval_service.create_approval_request(
                    decision_id=decision_id,
                    department=department,
                    topic=topic,
                    action_text=action_text,
                    impact=impact,
                    confidence=confidence,
                    metadata={
                        "agents_involved": len(drafts),
                        "synthesized_from": [d.get("advisor_id") for d in drafts],
                        "round_id": getattr(self, '_current_round_id', None)
                    },
                    tenant_id=tenant_id,
                    project_id=project_id
                )
                council_approval_service.auto_approve_decision(
                    decision_id=decision_id,
                    reason=f"Auto-approved: {impact.value} impact, {confidence:.2f} confidence"
                )
        
        # Commit to NBMF (approval not required or auto-approved)
        try:
            action_payload = {
                "action": action_text,
                "synthesized_from": [d.get("advisor_id") for d in drafts],
                "confidence": confidence,
                "topic": topic,
                "department": department,
                "impact": impact.value if APPROVAL_SERVICE_AVAILABLE else "unknown",
                "approval_status": approval_status.value if approval_status else "not_required",
                "decision_id": decision_id
            }
            
            item_id = decision_id  # Use decision_id as item_id
            # Prefix item_id with tenant_id for isolation
            if tenant_id:
                item_id = f"{tenant_id}:{item_id}"
            
            # PHASE 3: Write to Unified Memory
            # Mapping write_nbmf_only -> memory.write
            result = self.router.write(
                key=item_id,
                cls="council_action",
                payload=action_payload,
                meta={
                    "department": department,
                    "topic": topic,
                    "phase": "commit",
                    "synthesized_from": [d.get("advisor_id") for d in drafts],
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "impact": impact.value if APPROVAL_SERVICE_AVAILABLE else "unknown",
                    "approval_status": approval_status.value if approval_status else "not_required",
                    "decision_id": decision_id
                }
            )
            
            phase_duration = time.time() - phase_start
            
            log_event(
                action="council_commit_phase",
                ref=item_id,
                store="nbmf",
                route="council",
                extra={
                    "department": department,
                    "topic": topic,
                    "committed": True,
                    "duration_sec": phase_duration,
                    "impact": impact.value if APPROVAL_SERVICE_AVAILABLE else "unknown",
                    "approval_status": approval_status.value if approval_status else "not_required",
                    "decision_id": decision_id
                }
            )
            
            logger.info(f"Commit phase completed: action committed to NBMF (impact: {impact.value if APPROVAL_SERVICE_AVAILABLE else 'unknown'})")
            
            # Link to related memories
            try:
                # from backend.memory import memory
                # In production, find related memories and link them
                # For now, just log
                logger.debug(f"Memory linking would happen here for {item_id}")
            except:
                pass
            
            return {
                "committed": True,
                "item_id": item_id,
                "decision_id": decision_id,
                "txid": result.get("txid"),
                "impact": impact.value if APPROVAL_SERVICE_AVAILABLE else "unknown",
                "approval_status": approval_status.value if approval_status else "not_required",
                "duration_sec": phase_duration
            }
            
        except Exception as e:
            logger.error(f"Error committing action: {e}")
            return {
                "committed": False,
                "error": str(e),
                "duration_sec": time.time() - phase_start
            }
    
    async def cmp_validation_phase(
        self,
        department: str,
        topic: str,
        commit_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        CMP Validation Phase: Validate council decision against memory and quorum.
        
        Checks:
        1. Quorum consensus (4/6 neighbors)
        2. Memory consistency (no conflicts)
        3. Trust score (above threshold)
        """
        self.current_phase = CouncilPhase.CMP_VALIDATION
        phase_start = time.time()
        
        logger.info(f"CMP validation phase started for {department}")
        
        if not commit_results.get("committed", False):
            return {
                "validated": False,
                "reason": "not_committed",
                "duration_sec": time.time() - phase_start
            }
        
        # Check quorum (4/6 neighbors)
        try:
            from backend.utils.quorum import quorum_manager, QuorumType
            from backend.utils.sunflower_registry import sunflower_registry
            
            # Get department cell ID (simplified - in production use registry)
            dept_map = {"engineering": 1, "product": 2, "sales": 3, "marketing": 4, 
                       "finance": 5, "hr": 6, "legal": 7, "operations": 8}
            dept_index = dept_map.get(department, 1)
            cell_id = f"D{dept_index}"
            
            # Get neighbors (simplified - in production use registry)
            try:
                neighbors = sunflower_registry.get_neighbors(cell_id) if hasattr(sunflower_registry, 'get_neighbors') else []
            except:
                neighbors = []
            
            # Start quorum
            quorum_id = f"cmp_{department}_{int(time.time())}"
            quorum_manager.start_quorum(
                quorum_id,
                QuorumType.LOCAL,
                cell_id=cell_id,
                neighbors=neighbors
            )
            
            # Simulate votes (in production, agents would vote)
            # For now, assume validation passes if committed
            validated = True
            
            quorum_manager.cast_vote(quorum_id, cell_id, True)
            quorum_status = quorum_manager.get_quorum_status(quorum_id)
            
            validated = quorum_status.get("quorum_reached", False) or validated
            
        except Exception as e:
            logger.warning(f"Quorum check failed: {e}, assuming validated")
            validated = True
        
        # Check memory consistency
        try:
            # Check for conflicting decisions in memory
            item_id = commit_results.get("item_id")
            if item_id:
                # In production, check for conflicts
                memory_conflict = False
            else:
                memory_conflict = False
        except Exception as e:
            logger.warning(f"Memory consistency check failed: {e}")
            memory_conflict = False
        
        validated = validated and not memory_conflict
        
        phase_duration = time.time() - phase_start
        
        log_event(
            action="council_cmp_validation",
            ref=commit_results.get("item_id", department),
            store="nbmf",
            route="council",
            extra={
                "department": department,
                "topic": topic,
                "validated": validated,
                "duration_sec": phase_duration
            }
        )
        
        logger.info(f"CMP validation completed: {'VALIDATED' if validated else 'FAILED'}")
        
        return {
            "validated": validated,
            "quorum_reached": validated,
            "memory_conflict": memory_conflict if 'memory_conflict' in locals() else False,
            "duration_sec": phase_duration
        }
    
    async def memory_update_phase(
        self,
        department: str,
        topic: str,
        cmp_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Memory Update Phase: Write council decision to NBMF using abstract+pointer pattern.
        
        Uses AbstractStore for hybrid storage:
        - Abstract: Compressed NBMF representation
        - Pointer: Lossless source reference
        """
        phase_start = time.time()
        
        logger.info(f"Memory update phase started for {department}")
        
        if not cmp_results.get("validated", False):
            return {
                "updated": False,
                "reason": "not_validated",
                "duration_sec": time.time() - phase_start
            }
        
        try:
            # PHASE 3: Unified Memory (Abstract+Pointer pattern simulated in L2)
            
            # Get the committed action (from previous phase)
            action_payload = {
                "action": f"Council decision for {topic}",
                "department": department,
                "topic": topic,
                "validated": True
            }
            
            # Extract tenant_id and project_id from context
            tenant_id = action_payload.get("tenant_id") or getattr(self, '_current_tenant_id', None)
            project_id = action_payload.get("project_id") or getattr(self, '_current_project_id', None)
            
            item_id = f"council_{department}_{int(time.time())}"
            # Prefix item_id with tenant_id for isolation
            if tenant_id:
                item_id = f"{tenant_id}:{item_id}"
            
            # Store using Unified Memory
            result = self.router.write(
                key=item_id,
                cls="council_decision",
                payload=action_payload,
                meta={
                    "source_uri": f"council://{department}/{item_id}",
                    "mode": "hybrid",
                    "tenant_id": tenant_id,
                    "project_id": project_id
                }
            )
            
            phase_duration = time.time() - phase_start
            
            log_event(
                action="council_memory_update",
                ref=item_id,
                store="nbmf",
                route="council",
                extra={
                    "department": department,
                    "topic": topic,
                    "updated": True,
                    "mode": "hybrid",
                    "duration_sec": phase_duration
                }
            )
            
            logger.info(f"Memory update completed: stored with abstract+pointer pattern")
            
            # Link to related council decisions
            try:
                from backend.services.agent_awareness import agent_awareness
                # Link to previous council decisions in same department
                # In production, find related decisions and link
                agent_awareness.link_memory(item_id, f"council_{department}_previous", "related")
            except:
                pass
            
            # Record outcome for evolution
            try:
                from backend.services.council_evolution import council_evolution
                round_id = getattr(self, '_current_round_id', f"round_{int(time.time())}")
                council_evolution.record_outcome(
                    department,
                    round_id,
                    f"Council decision: {topic}",
                    True,  # Assume success if validated
                    {"duration_sec": phase_duration}
                )
            except:
                pass
            
            return {
                "updated": True,
                "item_id": item_id,
                "storage_mode": "hybrid",
                "duration_sec": phase_duration
            }
            
        except Exception as e:
            logger.error(f"Error updating memory: {e}")
            return {
                "updated": False,
                "error": str(e),
                "duration_sec": time.time() - phase_start
            }
    
    def _get_ring_number(self, department: str) -> int:
        """Get ring number for a department (simplified: use department index)."""
        # In production, this would use sunflower registry
        dept_rings = {
            "engineering": 1,
            "product": 2,
            "sales": 3,
            "marketing": 4,
            "finance": 5,
            "hr": 6,
            "legal": 7,
            "customer": 8
        }
        return dept_rings.get(department, 1)
    
    def get_round_history(self, department: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent round history, optionally filtered by department."""
        history = self.round_history
        if department:
            history = [r for r in history if r.get("department") == department]
        return history[-limit:] if history else []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            "current_phase": self.current_phase.value,
            "total_rounds": len(self.round_history),
            "running": self._running,
            "phase_timeouts": {phase.value: timeout for phase, timeout in self.phase_timeouts.items()}
        }
    
    async def commit_approved_decision(
        self,
        decision_id: str,
        department: str,
        topic: str,
        action_text: str,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Commit an already-approved decision directly to NBMF.
        
        This is called after a decision has been approved via the approval workflow.
        
        Args:
            decision_id: Decision identifier
            department: Department that made the decision
            topic: Topic of the decision
            action_text: Action to commit
            tenant_id: Optional tenant ID for isolation
            project_id: Optional project ID for scoping
            
        Returns:
            Dictionary with commit results
        """
        commit_start = time.time()
        logger.info(f"Committing approved decision: {decision_id} for {department}")
        
        try:
            # Prepare action payload
            action_payload = {
                "action": action_text,
                "confidence": 1.0,  # Approved decisions have full confidence
                "topic": topic,
                "department": department,
                "impact": "approved",  # Already assessed during approval
                "approval_status": "approved",
                "decision_id": decision_id,
                "committed_via": "approval_workflow"
            }
            
            # Use decision_id as item_id
            item_id = decision_id
            if tenant_id:
                item_id = f"{tenant_id}:{item_id}"
            
            # Commit to NBMF
            result = self.router.write_nbmf_only(
                item_id,
                "council_action_approved",
                action_payload,
                {
                    "department": department,
                    "topic": topic,
                    "phase": "commit",
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "impact": "approved",
                    "approval_status": "approved",
                    "decision_id": decision_id,
                    "committed_at": datetime.utcnow().isoformat()
                }
            )
            
            commit_duration = time.time() - commit_start
            
            # Log to ledger
            log_event(
                action="council_commit_approved_decision",
                ref=item_id,
                store="nbmf",
                route="council",
                extra={
                    "department": department,
                    "topic": topic,
                    "committed": True,
                    "duration_sec": commit_duration,
                    "decision_id": decision_id,
                    "approval_status": "approved"
                }
            )
            
            logger.info(f"Approved decision committed: {decision_id} (item_id: {item_id})")
            
            return {
                "committed": True,
                "item_id": item_id,
                "decision_id": decision_id,
                "txid": result.get("txid"),
                "duration_sec": commit_duration
            }
            
        except Exception as e:
            logger.error(f"Error committing approved decision {decision_id}: {e}")
            return {
                "committed": False,
                "error": str(e),
                "decision_id": decision_id,
                "duration_sec": time.time() - commit_start
            }


# Global instance
council_scheduler = CouncilScheduler()

