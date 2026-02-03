"""
Agent Onboarding Service
========================

Handles synchronization of new agents with the shared knowledge base (NBMF).
Ensures that when a new agent is created, it instantly "knows" what the collective knows.
"""

import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class AgentOnboardingService:
    """
    When new agent joins, sync all shared knowledge from NBMF.
    """
    
    def __init__(self, memory_service, sunflower_registry):
        self.memory = memory_service
        self.registry = sunflower_registry
        logger.info("✅ Agent Onboarding Service initialized")
    
    async def onboard_agent(self, agent_id: str, department: str) -> Dict[str, Any]:
        """
        Sync new agent with all shared knowledge.
        
        1. Retrieve shared knowledge (L3).
        2. Filter relevant knowledge for department.
        3. Create initial memory snapshot for agent.
        4. Inherit learned patterns.
        """
        try:
            # 1. Get all L3 (long-term) knowledge
            # NBMF Memory uses read_all for tier dump
            knowledge_base_dict = self.memory.read_all(tier="T3")
            knowledge_base = list(knowledge_base_dict.values())
            
            # 2. Filter by department (if department-specific knowledge exists)
            # Logic: If item has 'department' field, match it. If 'shared' is True, include it.
            dept_knowledge = []
            if knowledge_base:
                 dept_knowledge = [
                    k for k in knowledge_base
                    if k.get("department") == department or k.get("shared") == True or k.get("type") == "pattern"
                ]
            
            # 3. Create agent's personal knowledge index/snapshot
            self.memory.write(
                key=f"onboarding_{agent_id}_{int(time.time())}",
                value={
                    "agent": agent_id,
                    "type": "onboarding_snapshot",
                    "knowledge_snapshot_ids": [k.get("id") for k in dept_knowledge if k.get("id")],
                    "onboarded_at": time.time(),
                    "total_items": len(dept_knowledge)
                },
                tier="T2"
            )
            
            # 4. Get learned patterns for this department from other agents
            patterns = await self._get_department_patterns(department)
            
            # 5. Initialize agent with inherited patterns
            for i, pattern in enumerate(patterns):
                self.memory.write(
                    key=f"inherited_pattern_{agent_id}_{i}_{int(time.time())}",
                    value={
                        "agent": agent_id,
                        "type": "inherited_pattern",
                        "inherited_data": pattern,
                        "source": "department_learning"
                    },
                    tier="T3"
                )
            
            logger.info(f"✅ Agent {agent_id} onboarded with {len(dept_knowledge)} items and {len(patterns)} patterns.")
            
            return {
                "status": "onboarded",
                "knowledge_items": len(dept_knowledge),
                "patterns_inherited": len(patterns)
            }
            
        except Exception as e:
            logger.error(f"Failed to onboard agent {agent_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _get_department_patterns(self, department: str) -> List[Dict]:
        """Get all learned patterns from department agents"""
        # Query L3 memory for patterns (manual filter since search isn't available on NBMF yet)
        all_l3 = self.memory.read_all(tier="T3")
        
        patterns = []
        for key, value in all_l3.items():
            if value.get("department") == department and value.get("type") == "pattern":
                patterns.append(value)
            
        return patterns

# Global instance integration helpers
_onboarding_instance = None

def get_onboarding_service():
    return _onboarding_instance

def set_onboarding_service(instance):
    global _onboarding_instance
    _onboarding_instance = instance
