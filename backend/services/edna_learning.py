"""
E-DNA Learning Engine
=====================

Evolutionary DNA for agents.
This service allows agents to learn from every action, extracting patterns of success and failure.
It enables self-optimization over time.
"""

import time
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class EDNALearningEngine:
    """
    E-DNA = Evolutionary DNA for agents
    Every action → pattern → learning → improvement
    """
    
    def __init__(self, memory_service):
        self.memory = memory_service
        self.patterns = {}  # Learned patterns cache
        logger.info("✅ E-DNA Learning Engine initialized")
    
    async def observe(self, action: dict):
        """
        Observe an action and extract patterns.
        
        Args:
            action: Dictionary containing action details:
                - agent: str (agent id)
                - type: str (action type)
                - result: dict (must contain "status")
                - params: dict (input parameters)
                - duration: float (optional)
        """
        # Store in episodic memory (L2) happens in automation layer mostly, 
        # but we ensure learning pattern is stored.
        
        agent_id = action.get("agent", "unknown")
        action_type = action.get("type", "unknown")
        
        # Extract pattern key
        pattern_key = f"{agent_id}_{action_type}"
        
        # Initialize pattern if new
        if pattern_key not in self.patterns:
            self.patterns[pattern_key] = {
                "count": 0,
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "common_params": {}
            }
        
        # Update pattern stats
        pattern = self.patterns[pattern_key]
        pattern["count"] += 1
        
        # Update success rate
        is_success = action.get("result", {}).get("status") == "success"
        current_rate = pattern["success_rate"]
        count = pattern["count"]
        
        # Running average: new_rate = (old_rate * (n-1) + new_val) / n
        new_val = 1.0 if is_success else 0.0
        pattern["success_rate"] = (current_rate * (count - 1) + new_val) / count
        
        # Update duration if present
        duration = action.get("duration")
        if duration is not None:
            avg_dur = pattern.get("avg_duration", 0.0)
            pattern["avg_duration"] = (avg_dur * (count - 1) + duration) / count
            
        # Store updated pattern in long-term memory (L3)
        try:
            self.memory.write(
                key=pattern_key,
                value={
                    "type": "pattern",
                    "pattern_key": pattern_key,
                    "stats": pattern,
                    "last_updated": time.time(),
                    "agent": agent_id
                },
                tier="T3"  # Institutional/Long-term
            )
        except Exception as e:
            logger.error(f"Failed to store learning pattern: {e}")
            
    async def suggest_optimization(self, agent_id: str, task_type: str) -> Dict[str, Any]:
        """
        Suggest optimization based on learned patterns.
        Returns a suggestion dict.
        """
        pattern_key = f"{agent_id}_{task_type}"
        
        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            
            # Suggest improvements for low success rates
            if pattern["success_rate"] < 0.7:
                return {
                    "suggestion": "low_success_rate",
                    "message": "Success rate is low (< 70%). Consider reviewing task approach or adding error handling.",
                    "current_rate": pattern["success_rate"],
                    "stats": pattern
                }
                
            # Suggest speed improvements
            if pattern.get("avg_duration", 0) > 30.0:  # arbitrary threshold
                 return {
                    "suggestion": "slow_execution",
                    "message": "Action is taking longer than usual (> 30s). Consider optimizing.",
                    "avg_duration": pattern["avg_duration"]
                 }
                 
        return {"suggestion": "none"}

# Global instance integration helpers
_edna_instance = None

def get_edna_learning():
    return _edna_instance

def set_edna_learning(instance):
    global _edna_instance
    _edna_instance = instance
