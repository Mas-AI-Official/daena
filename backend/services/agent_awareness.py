"""
Cross-Agent Awareness System for Council.

Tracks what each agent knows about others, enabling better collaboration.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AgentAwareness:
    """
    Tracks cross-agent awareness and shared context.
    
    Features:
    - Agent knowledge tracking (what each agent knows)
    - Shared context (common knowledge between agents)
    - Awareness graph (who knows what about whom)
    - Memory links (connections between agent decisions)
    """
    
    def __init__(self):
        # agent_id -> {knowledge_items}
        self.agent_knowledge: Dict[str, Set[str]] = defaultdict(set)
        
        # agent_id -> {other_agent_id: awareness_score}
        self.awareness_graph: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # item_id -> {linked_item_ids}
        self.memory_links: Dict[str, Set[str]] = defaultdict(set)
        
        # agent_id -> {context_items}
        self.shared_context: Dict[str, Set[str]] = defaultdict(set)
        
        # Track agent interactions
        self.interactions: List[Dict[str, Any]] = []
    
    def record_agent_knowledge(self, agent_id: str, knowledge_item: str):
        """Record that an agent knows something."""
        self.agent_knowledge[agent_id].add(knowledge_item)
        logger.debug(f"Agent {agent_id} knows: {knowledge_item}")
    
    def get_agent_knowledge(self, agent_id: str) -> Set[str]:
        """Get all knowledge items for an agent."""
        return self.agent_knowledge.get(agent_id, set())
    
    def update_awareness(self, agent_id: str, other_agent_id: str, awareness_score: float):
        """
        Update awareness score between agents.
        
        Args:
            agent_id: The agent whose awareness is being updated
            other_agent_id: The agent being observed
            awareness_score: Awareness level (0.0 to 1.0)
        """
        if agent_id not in self.awareness_graph:
            self.awareness_graph[agent_id] = {}
        self.awareness_graph[agent_id][other_agent_id] = max(0.0, min(1.0, awareness_score))
        logger.debug(f"Agent {agent_id} awareness of {other_agent_id}: {awareness_score}")
    
    def get_awareness(self, agent_id: str, other_agent_id: str) -> float:
        """Get awareness score between two agents."""
        return self.awareness_graph.get(agent_id, {}).get(other_agent_id, 0.0)
    
    def link_memory(self, item_id: str, linked_item_id: str, link_type: str = "related"):
        """
        Link two memory items together.
        
        Args:
            item_id: Source memory item
            linked_item_id: Target memory item
            link_type: Type of link (related, depends_on, conflicts_with, etc.)
        """
        self.memory_links[item_id].add(linked_item_id)
        # Bidirectional link
        self.memory_links[linked_item_id].add(item_id)
        logger.debug(f"Linked memory {item_id} <-> {linked_item_id} ({link_type})")
    
    def get_linked_memories(self, item_id: str) -> Set[str]:
        """Get all memory items linked to this one."""
        return self.memory_links.get(item_id, set())
    
    def add_shared_context(self, agent_id: str, context_item: str):
        """Add shared context item for an agent."""
        self.shared_context[agent_id].add(context_item)
    
    def get_shared_context(self, agent_ids: List[str]) -> Set[str]:
        """Get context shared by multiple agents."""
        if not agent_ids:
            return set()
        
        shared = self.shared_context.get(agent_ids[0], set())
        for agent_id in agent_ids[1:]:
            shared = shared & self.shared_context.get(agent_id, set())
        return shared
    
    def record_interaction(self, agent_id: str, other_agent_id: str, interaction_type: str, metadata: Dict[str, Any] = None):
        """Record an interaction between agents."""
        interaction = {
            "agent_id": agent_id,
            "other_agent_id": other_agent_id,
            "interaction_type": interaction_type,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        self.interactions.append(interaction)
        
        # Update awareness based on interaction
        if interaction_type in ["debate", "collaborate", "agree"]:
            self.update_awareness(agent_id, other_agent_id, 0.8)
        elif interaction_type in ["disagree", "conflict"]:
            self.update_awareness(agent_id, other_agent_id, 0.5)
        else:
            self.update_awareness(agent_id, other_agent_id, 0.3)
    
    def get_agent_awareness_summary(self, agent_id: str) -> Dict[str, Any]:
        """Get comprehensive awareness summary for an agent."""
        return {
            "agent_id": agent_id,
            "knowledge_count": len(self.agent_knowledge.get(agent_id, set())),
            "awareness_of_others": self.awareness_graph.get(agent_id, {}),
            "shared_context_count": len(self.shared_context.get(agent_id, set())),
            "interaction_count": len([i for i in self.interactions if i["agent_id"] == agent_id])
        }
    
    def get_collaboration_graph(self) -> Dict[str, Any]:
        """Get graph of agent collaborations."""
        graph = {
            "nodes": [],
            "edges": []
        }
        
        # Add nodes (agents)
        all_agents = set(self.agent_knowledge.keys()) | set(self.awareness_graph.keys())
        for agent_id in all_agents:
            graph["nodes"].append({
                "id": agent_id,
                "knowledge_count": len(self.agent_knowledge.get(agent_id, set())),
                "awareness_count": len(self.awareness_graph.get(agent_id, {}))
            })
        
        # Add edges (awareness relationships)
        for agent_id, awareness in self.awareness_graph.items():
            for other_agent_id, score in awareness.items():
                graph["edges"].append({
                    "source": agent_id,
                    "target": other_agent_id,
                    "weight": score,
                    "type": "awareness"
                })
        
        return graph


# Global instance
agent_awareness = AgentAwareness()

