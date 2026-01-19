"""
Agent State Persistence Service.

Persists agent state to survive restarts and crashes.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentStatePersistence:
    """
    Persists agent state to disk for recovery.
    
    State includes:
    - Current task
    - Task progress
    - Context/memory
    - Status
    - Last update timestamp
    """
    
    def __init__(self, state_dir: str = "data/agent_states"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.states: Dict[str, Dict[str, Any]] = {}
    
    def save_state(
        self,
        agent_id: str,
        state: Dict[str, Any]
    ) -> bool:
        """
        Save agent state to disk.
        
        Args:
            agent_id: Agent identifier
            state: State dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add metadata
            state_with_meta = {
                **state,
                "saved_at": datetime.utcnow().isoformat() + "Z",
                "agent_id": agent_id
            }
            
            # Save to file
            state_file = self.state_dir / f"{agent_id}.json"
            with state_file.open("w", encoding="utf-8") as f:
                json.dump(state_with_meta, f, indent=2, ensure_ascii=False)
            
            # Cache in memory
            self.states[agent_id] = state_with_meta
            
            logger.debug(f"Saved state for agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save state for agent {agent_id}: {e}")
            return False
    
    def load_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Load agent state from disk.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            State dictionary or None if not found
        """
        try:
            # Check cache first
            if agent_id in self.states:
                return self.states[agent_id]
            
            # Load from file
            state_file = self.state_dir / f"{agent_id}.json"
            if not state_file.exists():
                return None
            
            with state_file.open("r", encoding="utf-8") as f:
                state = json.load(f)
            
            # Cache in memory
            self.states[agent_id] = state
            
            logger.debug(f"Loaded state for agent {agent_id}")
            return state
            
        except Exception as e:
            logger.error(f"Failed to load state for agent {agent_id}: {e}")
            return None
    
    def delete_state(self, agent_id: str) -> bool:
        """
        Delete agent state.
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Remove from cache
            if agent_id in self.states:
                del self.states[agent_id]
            
            # Remove file
            state_file = self.state_dir / f"{agent_id}.json"
            if state_file.exists():
                state_file.unlink()
            
            logger.debug(f"Deleted state for agent {agent_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete state for agent {agent_id}: {e}")
            return False
    
    def list_agents_with_state(self) -> list[str]:
        """
        List all agents that have persisted state.
        
        Returns:
            List of agent IDs
        """
        try:
            agent_ids = []
            for state_file in self.state_dir.glob("*.json"):
                agent_id = state_file.stem
                agent_ids.append(agent_id)
            return agent_ids
        except Exception as e:
            logger.error(f"Failed to list agent states: {e}")
            return []
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get summary of all persisted states.
        
        Returns:
            Summary dictionary
        """
        agent_ids = self.list_agents_with_state()
        
        summary = {
            "total_agents": len(agent_ids),
            "agents": []
        }
        
        for agent_id in agent_ids:
            state = self.load_state(agent_id)
            if state:
                summary["agents"].append({
                    "agent_id": agent_id,
                    "saved_at": state.get("saved_at"),
                    "status": state.get("status", "unknown"),
                    "has_task": "current_task" in state
                })
        
        return summary


# Global instance
agent_state_persistence = AgentStatePersistence()





