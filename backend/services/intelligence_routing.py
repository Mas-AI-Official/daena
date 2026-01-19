"""
Intelligence Routing Layer
Routes queries to appropriate agents/models based on intelligence dimension needs:
- IQ (Intellectual Quotient): Analytical, logical, problem-solving
- EQ (Emotional Quotient): Empathy, relationships, emotional intelligence
- AQ (Adaptability Quotient): Flexibility, learning, change management
- Execution: Action-oriented, implementation, task completion
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class IntelligenceDimension(str, Enum):
    """Intelligence dimensions for routing"""
    IQ = "iq"  # Intellectual Quotient
    EQ = "eq"  # Emotional Quotient
    AQ = "aq"  # Adaptability Quotient
    EXECUTION = "execution"  # Execution/Implementation


@dataclass
class IntelligenceScores:
    """Intelligence dimension scores for a query"""
    iq: float = 0.0  # 0.0-1.0
    eq: float = 0.0  # 0.0-1.0
    aq: float = 0.0  # 0.0-1.0
    execution: float = 0.0  # 0.0-1.0
    
    def get_primary_dimension(self) -> IntelligenceDimension:
        """Get the dimension with the highest score"""
        scores = {
            IntelligenceDimension.IQ: self.iq,
            IntelligenceDimension.EQ: self.eq,
            IntelligenceDimension.AQ: self.aq,
            IntelligenceDimension.EXECUTION: self.execution
        }
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary"""
        return {
            "iq": self.iq,
            "eq": self.eq,
            "aq": self.aq,
            "execution": self.execution
        }


class IntelligenceRouter:
    """Routes queries based on intelligence dimension needs"""
    
    def __init__(self):
        # Keywords that indicate intelligence dimension needs
        self.iq_keywords = [
            "analyze", "calculate", "solve", "logic", "reasoning", "data", "statistics",
            "algorithm", "optimize", "efficiency", "performance", "architecture", "design",
            "strategy", "plan", "research", "study", "evaluate", "assess", "compare"
        ]
        
        self.eq_keywords = [
            "feel", "emotion", "relationship", "team", "collaborate", "empathy",
            "support", "help", "understand", "concern", "worried", "frustrated",
            "happy", "satisfied", "communication", "conflict", "negotiate", "persuade"
        ]
        
        self.aq_keywords = [
            "adapt", "change", "learn", "flexible", "pivot", "evolve", "transform",
            "uncertainty", "unknown", "new", "different", "alternative", "option",
            "experiment", "try", "explore", "discover", "innovate", "creative"
        ]
        
        self.execution_keywords = [
            "do", "implement", "execute", "action", "task", "complete", "finish",
            "build", "create", "make", "deliver", "produce", "run", "start",
            "deploy", "launch", "ship", "deliver", "accomplish", "achieve"
        ]
        
        # Agent role to intelligence dimension mapping
        self.role_to_intelligence = {
            "advisor_a": IntelligenceDimension.IQ,  # Strategic thinking
            "advisor_b": IntelligenceDimension.IQ,  # Tactical analysis
            "scout_internal": IntelligenceDimension.AQ,  # Internal adaptation
            "scout_external": IntelligenceDimension.AQ,  # External learning
            "synth": IntelligenceDimension.IQ,  # Knowledge synthesis
            "executor": IntelligenceDimension.EXECUTION  # Action execution
        }
        
        # Department to intelligence dimension mapping
        self.dept_to_intelligence = {
            "engineering": IntelligenceDimension.IQ,
            "product": IntelligenceDimension.IQ,
            "finance": IntelligenceDimension.IQ,
            "legal": IntelligenceDimension.IQ,
            "marketing": IntelligenceDimension.EQ,
            "sales": IntelligenceDimension.EQ,
            "hr": IntelligenceDimension.EQ,
            "customer": IntelligenceDimension.EQ
        }
    
    def score_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> IntelligenceScores:
        """
        Score a query on intelligence dimensions
        
        Args:
            query: The user query
            context: Optional context (department, role, etc.)
        
        Returns:
            IntelligenceScores with dimension scores
        """
        query_lower = query.lower()
        
        # Count keyword matches
        iq_matches = sum(1 for kw in self.iq_keywords if kw in query_lower)
        eq_matches = sum(1 for kw in self.eq_keywords if kw in query_lower)
        aq_matches = sum(1 for kw in self.aq_keywords if kw in query_lower)
        exec_matches = sum(1 for kw in self.execution_keywords if kw in query_lower)
        
        # Normalize scores (0.0-1.0)
        total_matches = iq_matches + eq_matches + aq_matches + exec_matches
        if total_matches == 0:
            # Default to IQ if no matches
            return IntelligenceScores(iq=0.5, eq=0.0, aq=0.0, execution=0.0)
        
        scores = IntelligenceScores(
            iq=min(iq_matches / max(total_matches, 1), 1.0),
            eq=min(eq_matches / max(total_matches, 1), 1.0),
            aq=min(aq_matches / max(total_matches, 1), 1.0),
            execution=min(exec_matches / max(total_matches, 1), 1.0)
        )
        
        # Adjust based on context
        if context:
            # Boost based on department
            dept = context.get("department", "").lower()
            if dept in self.dept_to_intelligence:
                dim = self.dept_to_intelligence[dept]
                if dim == IntelligenceDimension.IQ:
                    scores.iq = min(scores.iq + 0.2, 1.0)
                elif dim == IntelligenceDimension.EQ:
                    scores.eq = min(scores.eq + 0.2, 1.0)
                elif dim == IntelligenceDimension.AQ:
                    scores.aq = min(scores.aq + 0.2, 1.0)
            
            # Boost based on role
            role = context.get("role", "").lower()
            if role in self.role_to_intelligence:
                dim = self.role_to_intelligence[role]
                if dim == IntelligenceDimension.IQ:
                    scores.iq = min(scores.iq + 0.2, 1.0)
                elif dim == IntelligenceDimension.EQ:
                    scores.eq = min(scores.eq + 0.2, 1.0)
                elif dim == IntelligenceDimension.AQ:
                    scores.aq = min(scores.aq + 0.2, 1.0)
                elif dim == IntelligenceDimension.EXECUTION:
                    scores.execution = min(scores.execution + 0.2, 1.0)
        
        return scores
    
    def select_agents(
        self,
        scores: IntelligenceScores,
        available_agents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Select agents based on intelligence scores
        
        Args:
            scores: Intelligence dimension scores
            available_agents: List of available agents with department/role info
        
        Returns:
            List of selected agents sorted by relevance
        """
        primary_dim = scores.get_primary_dimension()
        
        # Score each agent
        agent_scores = []
        for agent in available_agents:
            dept = agent.get("department", "").lower()
            role = agent.get("role", "").lower()
            
            score = 0.0
            
            # Check if agent matches primary dimension
            if dept in self.dept_to_intelligence:
                if self.dept_to_intelligence[dept] == primary_dim:
                    score += 0.5
            
            if role in self.role_to_intelligence:
                if self.role_to_intelligence[role] == primary_dim:
                    score += 0.5
            
            agent_scores.append((agent, score))
        
        # Sort by score (descending)
        agent_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top agents (at least 1, up to 3)
        selected = [agent for agent, score in agent_scores[:3] if score > 0]
        if not selected:
            # Fallback: return first agent
            return [available_agents[0]] if available_agents else []
        
        return selected
    
    async def route_and_merge(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        available_agents: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Route query to appropriate agents and merge responses
        
        Args:
            query: User query
            context: Optional context
            available_agents: List of available agents
        
        Returns:
            Merged response with intelligence scores and agent contributions
        """
        # Score the query
        scores = self.score_query(query, context)
        
        # Select agents
        if available_agents:
            selected_agents = self.select_agents(scores, available_agents)
        else:
            selected_agents = []
        
        # Generate responses from selected agents
        from backend.services.llm_service import llm_service
        
        responses = []
        agent_contributions = []
        
        for agent in selected_agents:
            try:
                # Build agent-specific prompt
                agent_context = {
                    "department": agent.get("department", ""),
                    "role": agent.get("role", ""),
                    "name": agent.get("name", "")
                }
                if context:
                    agent_context.update(context)
                
                # Generate response
                response = await llm_service.generate_response(
                    prompt=query,
                    context=agent_context,
                    max_tokens=500
                )
                
                responses.append(response)
                agent_contributions.append({
                    "agent_id": agent.get("id", ""),
                    "agent_name": agent.get("name", ""),
                    "department": agent.get("department", ""),
                    "role": agent.get("role", ""),
                    "response": response,
                    "dimension": scores.get_primary_dimension().value
                })
            except Exception as e:
                logger.warning(f"Failed to get response from agent {agent.get('id', 'unknown')}: {e}")
        
        # Merge responses
        if responses:
            merged_response = self._merge_responses(responses, scores)
        else:
            # Fallback: single response
            merged_response = await llm_service.generate_response(
                prompt=query,
                context=context,
                max_tokens=1000
            )
        
        # Store in audit log
        self._log_intelligence_scores(query, scores, agent_contributions)
        
        return {
            "response": merged_response,
            "intelligence_scores": scores.to_dict(),
            "primary_dimension": scores.get_primary_dimension().value,
            "agent_contributions": agent_contributions,
            "agents_used": len(agent_contributions)
        }
    
    def _merge_responses(self, responses: List[str], scores: IntelligenceScores) -> str:
        """Merge multiple agent responses into a single response"""
        if len(responses) == 1:
            return responses[0]
        
        # Simple merging: combine with dimension-aware synthesis
        primary_dim = scores.get_primary_dimension()
        
        if primary_dim == IntelligenceDimension.IQ:
            # Analytical synthesis
            return f"Based on analysis from {len(responses)} perspectives:\n\n" + "\n\n".join(responses)
        elif primary_dim == IntelligenceDimension.EQ:
            # Empathetic synthesis
            return f"Considering multiple viewpoints:\n\n" + "\n\n".join(responses)
        elif primary_dim == IntelligenceDimension.AQ:
            # Adaptive synthesis
            return f"Exploring {len(responses)} approaches:\n\n" + "\n\n".join(responses)
        else:  # EXECUTION
            # Action-oriented synthesis
            return f"Action plan from {len(responses)} experts:\n\n" + "\n\n".join(responses)
    
    def _log_intelligence_scores(
        self,
        query: str,
        scores: IntelligenceScores,
        agent_contributions: List[Dict[str, Any]]
    ):
        """Store intelligence scores in audit log"""
        try:
            from backend.database import SessionLocal, EventLog
            db = SessionLocal()
            try:
                log_entry = EventLog(
                    event_type="intelligence.routing",
                    entity_type="query",
                    entity_id="",
                    payload_json={
                        "query": query[:200],  # Truncate for storage
                        "intelligence_scores": scores.to_dict(),
                        "primary_dimension": scores.get_primary_dimension().value,
                        "agents_used": len(agent_contributions),
                        "agent_ids": [a.get("agent_id") for a in agent_contributions]
                    }
                )
                db.add(log_entry)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to log intelligence scores: {e}")


# Global singleton instance
_intelligence_router: Optional[IntelligenceRouter] = None


def get_intelligence_router() -> IntelligenceRouter:
    """Get the global intelligence router instance"""
    global _intelligence_router
    if _intelligence_router is None:
        _intelligence_router = IntelligenceRouter()
    return _intelligence_router

