"""
Agent-Brain Connection Router
Connects each agent to the LLM brain for intelligent responses
Each agent can invoke the brain with their specialized context
"""
from typing import Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentBrainRouter:
    """
    Routes agent requests to the appropriate brain model
    Each agent has a specialized context based on their department and role
    """
    
    def __init__(self):
        self.active_connections: Dict[str, datetime] = {}
    
    def get_agent_context(self, agent_cell_id: str, department: str, role: str) -> Dict[str, Any]:
        """
        Build specialized context for an agent based on their department and role
        This context is sent to the brain along with user queries
        """
        # Role-based capabilities
        role_capabilities = {
            "advisor_a": "Strategic planning, executive recommendations, high-level decision making",
            "advisor_b": "Tactical advice, process optimization, operational guidance",
            "scout_internal": "Internal analysis, resource assessment, team coordination",
            "scout_external": "Market research, competitor analysis, trend monitoring",
            "synth": "Knowledge synthesis, report generation, information aggregation",
            "executor": "Action execution, task completion, implementation assistance"
        }
        
        # Department-specific expertise
        dept_expertise = {
            "engineering": "Software development, infrastructure, DevOps, code review, architecture",
            "product": "Product strategy, roadmaps, UX, feature prioritization, user research",
            "sales": "Client acquisition, deal closing, pipeline management, revenue optimization",
            "marketing": "Brand strategy, campaigns, growth hacking, content, SEO/SEM",
            "finance": "Financial planning, budgeting, forecasting, accounting, investment",
            "hr": "Talent acquisition, culture, training, benefits, organizational development",
            "legal": "Contracts, compliance, IP protection, risk management, regulations",
            "customer": "Customer success, support tickets, retention, satisfaction, onboarding",
            "chakra": "Organizational energy, alignment, balance, spiritual intelligence, flow",
            "blackops": "Competitive intelligence, covert ops, strategic advantage, shadow operations",
            "security": "Cybersecurity, threat detection, protection, incident response, auditing",
            "rdlab": "Research, innovation, AI experiments, future tech, prototyping"
        }
        
        return {
            "agent_id": agent_cell_id,
            "department": department,
            "role": role,
            "capabilities": role_capabilities.get(role, "General assistance"),
            "expertise": dept_expertise.get(department, "General business operations"),
            "system_prompt": f"""You are an AI agent specialized in {department} operations.
Your role is: {role_capabilities.get(role, 'General assistance')}.
Your expertise: {dept_expertise.get(department, 'General business')}.
Always respond professionally and with department-specific knowledge.
If asked about topics outside your expertise, acknowledge your limitations."""
        }
    
    async def invoke_brain(
        self,
        agent_cell_id: str,
        department: str,
        role: str,
        user_message: str,
        session_context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Invoke the brain on behalf of an agent
        Returns the brain's response with agent context applied
        """
        # Get agent-specific context
        agent_context = self.get_agent_context(agent_cell_id, department, role)
        
        # Track connection
        self.active_connections[agent_cell_id] = datetime.utcnow()
        
        try:
            # Use the canonical LLM service (same as Daena) for consistent Ollama checking
            from backend.services.llm_service import llm_service
            
            # NEW: Use intelligent router for optimal model selection
            try:
                from backend.services.intelligent_router import intelligent_router
                routing_decision = await intelligent_router.route(user_message, session_context)
                logger.info(f"Router decision for {agent_cell_id}: {routing_decision.model_name} ({routing_decision.reason})")
            except Exception as e:
                logger.warning(f"Intelligent router failed, using default: {e}")
                routing_decision = None
            
            # NEW: Check for tool intents before LLM call
            try:
                from backend.services.agent_tool_detector import agent_tool_detector
                tool_intent = agent_tool_detector.detect(user_message)
                if tool_intent and tool_intent.confidence > 0.7:
                    logger.info(f"High-confidence tool detected: {tool_intent.category.value}.{tool_intent.action}")
                    # Execute tool via unified executor
                    from backend.services.unified_tool_executor import unified_executor, ExecutorType
                    tool_result = await unified_executor.execute(
                        tool_name=tool_intent.category.value,
                        action=tool_intent.action,
                        args=tool_intent.args,
                        executor_id=agent_cell_id,
                        executor_type=ExecutorType.AGENT,
                        department=department
                    )
                    if tool_result.get("status") == "executed":
                        return {
                            "success": True,
                            "response": f"Tool executed: {tool_intent.category.value}.{tool_intent.action}\n\nResult: {tool_result.get('result', 'Completed')}",
                            "agent_id": agent_cell_id,
                            "department": department,
                            "brain_model": "tool_execution",
                            "tool_used": f"{tool_intent.category.value}.{tool_intent.action}",
                            "timestamp": datetime.utcnow().isoformat()
                        }
            except Exception as e:
                logger.debug(f"Tool detection/execution skipped: {e}")
            
            # Build system prompt with agent context
            system_prompt = agent_context["system_prompt"]
            
            # Combine system prompt with user message
            full_prompt = f"{system_prompt}\n\nUser: {user_message}\nAgent:"
            
            # Use llm_service which handles Ollama checking consistently
            # It will check Ollama first, then fallback to cloud or deterministic response
            # context mapping
            context = session_context or {}
            context["skip_gate"] = True
            
            response_text = await llm_service.generate_response(
                prompt=full_prompt,
                context=context,
                max_tokens=800,
                temperature=0.7
            )
            
            # Determine brain model based on response
            # If response contains offline indicators, mark as offline
            if "offline mode" in response_text.lower() or "ollama" in response_text.lower() and "not reachable" in response_text.lower():
                brain_model = "offline"
            else:
                brain_model = "ollama"  # Assume Ollama if we got a real response
            
            return {
                "success": True,
                "response": response_text,
                "agent_id": agent_cell_id,
                "department": department,
                "brain_model": brain_model,
                "timestamp": datetime.utcnow().isoformat()
            }
                
        except Exception as e:
            logger.error(f"Brain invocation failed: {e}")
            # Use deterministic offline response instead of mock
            return {
                "success": True,
                "response": f"Hello! I'm {agent_cell_id}, {role} in {department}. I'm currently operating in offline mode (brain connection unavailable). Your message has been received. Please start Ollama to enable full AI capabilities.",
                "agent_id": agent_cell_id,
                "department": department,
                "brain_model": "offline",
                "timestamp": datetime.utcnow().isoformat(),
                "note": "Brain is currently offline, using deterministic fallback response"
            }
    
    def _generate_mock_response(
        self,
        agent_cell_id: str,
        department: str,
        role: str,
        user_message: str
    ) -> Dict[str, Any]:
        """Generate a mock response when brain is offline"""
        responses = {
            "engineering": f"From an engineering perspective, I'd analyze the technical requirements and propose an implementation plan for: {user_message[:50]}...",
            "product": f"Looking at this from a product standpoint, we should consider user value and roadmap alignment for: {user_message[:50]}...",
            "sales": f"In terms of revenue impact and client relationships, here's my take on: {user_message[:50]}...",
            "marketing": f"From a marketing and brand perspective, I'd suggest we approach this with: {user_message[:50]}...",
            "finance": f"Analyzing the financial implications and budget considerations for: {user_message[:50]}...",
            "hr": f"Considering our people and culture, here's my recommendation regarding: {user_message[:50]}...",
            "legal": f"From a compliance and risk management perspective on: {user_message[:50]}...",
            "customer": f"Focusing on customer success and satisfaction for: {user_message[:50]}...",
            "chakra": f"Aligning organizational energy and spiritual balance regarding: {user_message[:50]}...",
            "blackops": f"Strategic intelligence analysis indicates we should consider: {user_message[:50]}...",
            "security": f"Threat assessment and security analysis for: {user_message[:50]}...",
            "rdlab": f"From an innovation and research perspective, exploring: {user_message[:50]}..."
        }
        
        return {
            "success": True,
            "response": responses.get(department, f"Agent response for: {user_message[:50]}..."),
            "agent_id": agent_cell_id,
            "department": department,
            "brain_model": "offline_mock",
            "timestamp": datetime.utcnow().isoformat(),
            "note": "Brain is currently offline, using fallback response"
        }
    
    def get_connection_status(self, agent_cell_id: str) -> Dict[str, Any]:
        """Check if an agent is connected to the brain"""
        last_seen = self.active_connections.get(agent_cell_id)
        
        if last_seen:
            seconds_ago = (datetime.utcnow() - last_seen).total_seconds()
            connected = seconds_ago < 300  # 5 minute threshold
        else:
            connected = False
            seconds_ago = None
        
        return {
            "agent_id": agent_cell_id,
            "connected": connected,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "seconds_ago": seconds_ago
        }
    
    def get_all_connections(self) -> Dict[str, Any]:
        """Get all agent connections"""
        now = datetime.utcnow()
        connections = {}
        
        for agent_id, last_seen in self.active_connections.items():
            seconds_ago = (now - last_seen).total_seconds()
            connections[agent_id] = {
                "last_seen": last_seen.isoformat(),
                "seconds_ago": seconds_ago,
                "active": seconds_ago < 300
            }
        
        return {
            "total_tracked": len(self.active_connections),
            "active_count": sum(1 for c in connections.values() if c["active"]),
            "connections": connections
        }


# Global singleton
agent_brain_router = AgentBrainRouter()
