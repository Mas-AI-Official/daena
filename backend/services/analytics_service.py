"""
Advanced Analytics Service for Daena AI.

Tracks and analyzes:
- Agent behavior patterns
- Communication patterns
- Efficiency metrics
- Anomaly detection
"""

from __future__ import annotations

import time
import logging
from collections import defaultdict, deque
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class InteractionType(Enum):
    """Types of agent interactions."""
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    COUNCIL_PARTICIPATION = "council_participation"
    MEMORY_WRITE = "memory_write"
    MEMORY_READ = "memory_read"
    LLM_CALL = "llm_call"
    DECISION_MADE = "decision_made"


@dataclass
class AgentInteraction:
    """Record of an agent interaction."""
    timestamp: float
    agent_id: str
    department: str
    interaction_type: str
    target_agent: Optional[str] = None
    target_department: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CommunicationPattern:
    """Pattern of communication between agents."""
    source_agent: str
    target_agent: str
    message_count: int
    avg_latency_ms: float
    last_interaction: float
    interaction_types: Dict[str, int]


@dataclass
class AgentEfficiencyMetrics:
    """Efficiency metrics for an agent."""
    agent_id: str
    department: str
    total_interactions: int
    avg_response_time_ms: float
    success_rate: float
    cas_hit_rate: float
    memory_efficiency: float
    llm_cost_per_interaction: float


class AnalyticsService:
    """
    Service for tracking and analyzing agent behavior and system patterns.
    """
    
    def __init__(self, max_history: int = 10000, window_minutes: int = 60):
        self.max_history = max_history
        self.window_minutes = window_minutes
        
        # Interaction history (sliding window)
        self.interactions: deque = deque(maxlen=max_history)
        
        # Agent statistics
        self.agent_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "interactions": 0,
            "successes": 0,
            "failures": 0,
            "total_latency_ms": 0.0,
            "llm_calls": 0,
            "memory_ops": 0,
            "last_activity": 0.0
        })
        
        # Communication patterns
        self.communication_matrix: Dict[Tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Efficiency tracking
        self.efficiency_metrics: Dict[str, AgentEfficiencyMetrics] = {}
        
        # Anomaly detection
        self.baseline_patterns: Dict[str, Dict[str, float]] = {}
        self.anomaly_threshold = 3.0  # Standard deviations
    
    def record_interaction(
        self,
        agent_id: str,
        department: str,
        interaction_type: InteractionType,
        target_agent: Optional[str] = None,
        target_department: Optional[str] = None,
        latency_ms: Optional[float] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record an agent interaction."""
        now = time.time()
        
        interaction = AgentInteraction(
            timestamp=now,
            agent_id=agent_id,
            department=department,
            interaction_type=interaction_type.value,
            target_agent=target_agent,
            target_department=target_department,
            metadata=metadata or {}
        )
        
        self.interactions.append(interaction)
        
        # Update agent statistics
        stats = self.agent_stats[agent_id]
        stats["interactions"] += 1
        stats["last_activity"] = now
        
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        if latency_ms is not None:
            stats["total_latency_ms"] += latency_ms
        
        if interaction_type == InteractionType.LLM_CALL:
            stats["llm_calls"] += 1
        
        if interaction_type in [InteractionType.MEMORY_WRITE, InteractionType.MEMORY_READ]:
            stats["memory_ops"] += 1
        
        # Track communication patterns
        if target_agent:
            key = (agent_id, target_agent)
            self.communication_matrix[key].append({
                "timestamp": now,
                "latency_ms": latency_ms or 0.0,
                "success": success,
                "type": interaction_type.value
            })
    
    def get_agent_interaction_graph(self, department: Optional[str] = None) -> Dict[str, Any]:
        """Get agent interaction graph data."""
        window_start = time.time() - (self.window_minutes * 60)
        
        # Filter interactions by window and department
        recent_interactions = [
            i for i in self.interactions
            if i.timestamp >= window_start and (not department or i.department == department)
        ]
        
        # Build graph
        nodes = {}
        edges = defaultdict(int)
        
        for interaction in recent_interactions:
            # Add source node
            if interaction.agent_id not in nodes:
                nodes[interaction.agent_id] = {
                    "id": interaction.agent_id,
                    "department": interaction.department,
                    "interactions": 0
                }
            nodes[interaction.agent_id]["interactions"] += 1
            
            # Add edge if target exists
            if interaction.target_agent:
                edge_key = (interaction.agent_id, interaction.target_agent)
                edges[edge_key] += 1
                
                # Add target node
                if interaction.target_agent not in nodes:
                    nodes[interaction.target_agent] = {
                        "id": interaction.target_agent,
                        "department": interaction.target_department or "unknown",
                        "interactions": 0
                    }
        
        return {
            "nodes": list(nodes.values()),
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "weight": count
                }
                for (source, target), count in edges.items()
            ],
            "window_minutes": self.window_minutes,
            "total_interactions": len(recent_interactions)
        }
    
    def get_communication_patterns(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get communication patterns for agents."""
        patterns = []
        
        for (source, target), interactions in self.communication_matrix.items():
            if agent_id and source != agent_id and target != agent_id:
                continue
            
            if not interactions:
                continue
            
            latencies = [i["latency_ms"] for i in interactions if i["latency_ms"] > 0]
            successes = sum(1 for i in interactions if i["success"])
            
            pattern = {
                "source_agent": source,
                "target_agent": target,
                "message_count": len(interactions),
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
                "success_rate": successes / len(interactions) if interactions else 0.0,
                "last_interaction": max(i["timestamp"] for i in interactions),
                "interaction_types": {}
            }
            
            # Count interaction types
            for interaction in interactions:
                itype = interaction["type"]
                pattern["interaction_types"][itype] = pattern["interaction_types"].get(itype, 0) + 1
            
            patterns.append(pattern)
        
        return sorted(patterns, key=lambda x: x["message_count"], reverse=True)
    
    def calculate_efficiency_metrics(self, agent_id: str) -> AgentEfficiencyMetrics:
        """Calculate efficiency metrics for an agent."""
        stats = self.agent_stats.get(agent_id, {})
        
        total_interactions = stats.get("interactions", 0)
        successes = stats.get("successes", 0)
        failures = stats.get("failures", 0)
        
        success_rate = successes / total_interactions if total_interactions > 0 else 0.0
        
        avg_response_time = (
            stats.get("total_latency_ms", 0.0) / total_interactions
            if total_interactions > 0 else 0.0
        )
        
        # Get CAS hit rate from metrics if available
        cas_hit_rate = 0.0
        try:
            from memory_service.metrics import snapshot
            metrics = snapshot()
            cas_hits = metrics.get("llm_cas_hit", 0)
            cas_misses = metrics.get("llm_cas_miss", 0)
            if cas_hits + cas_misses > 0:
                cas_hit_rate = cas_hits / (cas_hits + cas_misses)
        except ImportError:
            pass
        
        # Calculate memory efficiency (reads vs writes)
        memory_ops = stats.get("memory_ops", 0)
        memory_efficiency = 1.0 if memory_ops > 0 else 0.0
        
        # Estimate LLM cost per interaction
        llm_calls = stats.get("llm_calls", 0)
        llm_cost_per_interaction = 0.0
        if llm_calls > 0:
            try:
                from memory_service.metrics import snapshot
                metrics = snapshot()
                total_cost = metrics.get("total_cost_usd", 0.0)
                total_llm_requests = metrics.get("llm_cas_hit", 0) + metrics.get("llm_cas_miss", 0)
                if total_llm_requests > 0:
                    avg_cost_per_llm = total_cost / total_llm_requests
                    llm_cost_per_interaction = avg_cost_per_llm * (llm_calls / total_interactions if total_interactions > 0 else 0)
            except ImportError:
                pass
        
        # Get department from recent interactions
        department = "unknown"
        for interaction in reversed(self.interactions):
            if interaction.agent_id == agent_id:
                department = interaction.department
                break
        
        return AgentEfficiencyMetrics(
            agent_id=agent_id,
            department=department,
            total_interactions=total_interactions,
            avg_response_time_ms=avg_response_time,
            success_rate=success_rate,
            cas_hit_rate=cas_hit_rate,
            memory_efficiency=memory_efficiency,
            llm_cost_per_interaction=llm_cost_per_interaction
        )
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """Detect anomalies in agent behavior."""
        anomalies = []
        now = time.time()
        window_start = now - (self.window_minutes * 60)
        
        # Get recent interactions
        recent_interactions = [
            i for i in self.interactions
            if i.timestamp >= window_start
        ]
        
        # Calculate baseline patterns
        if not self.baseline_patterns:
            self._update_baseline_patterns(recent_interactions)
        
        # Detect anomalies
        agent_activity = defaultdict(int)
        for interaction in recent_interactions:
            agent_activity[interaction.agent_id] += 1
        
        # Check for unusual activity levels
        if self.baseline_patterns:
            avg_activity = sum(self.baseline_patterns.values()) / len(self.baseline_patterns) if self.baseline_patterns else 0
            std_activity = self._calculate_std(list(self.baseline_patterns.values())) if self.baseline_patterns else 0
            
            for agent_id, activity in agent_activity.items():
                baseline = self.baseline_patterns.get(agent_id, {}).get("avg_activity", avg_activity)
                
                if std_activity > 0:
                    z_score = abs(activity - baseline) / std_activity
                    if z_score > self.anomaly_threshold:
                        anomalies.append({
                            "agent_id": agent_id,
                            "type": "unusual_activity",
                            "severity": "high" if z_score > 5 else "medium",
                            "current_activity": activity,
                            "baseline_activity": baseline,
                            "z_score": round(z_score, 2),
                            "timestamp": now
                        })
        
        return anomalies
    
    def _update_baseline_patterns(self, interactions: List[AgentInteraction]):
        """Update baseline patterns for anomaly detection."""
        agent_activity = defaultdict(int)
        
        for interaction in interactions:
            agent_activity[interaction.agent_id] += 1
        
        for agent_id, activity in agent_activity.items():
            if agent_id not in self.baseline_patterns:
                self.baseline_patterns[agent_id] = {
                    "avg_activity": activity,
                    "sample_count": 1
                }
            else:
                baseline = self.baseline_patterns[agent_id]
                # Exponential moving average
                alpha = 0.1
                baseline["avg_activity"] = alpha * activity + (1 - alpha) * baseline["avg_activity"]
                baseline["sample_count"] += 1
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive analytics summary."""
        window_start = time.time() - (self.window_minutes * 60)
        recent_interactions = [
            i for i in self.interactions
            if i.timestamp >= window_start
        ]
        
        # Calculate overall metrics
        total_interactions = len(recent_interactions)
        unique_agents = len(set(i.agent_id for i in recent_interactions))
        
        # Get top agents by activity
        agent_activity = defaultdict(int)
        for interaction in recent_interactions:
            agent_activity[interaction.agent_id] += 1
        
        top_agents = sorted(
            agent_activity.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Get communication hotspots
        communication_counts = defaultdict(int)
        for interaction in recent_interactions:
            if interaction.target_agent:
                key = f"{interaction.agent_id} -> {interaction.target_agent}"
                communication_counts[key] += 1
        
        top_communications = sorted(
            communication_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Detect anomalies
        anomalies = self.detect_anomalies()
        
        return {
            "window_minutes": self.window_minutes,
            "total_interactions": total_interactions,
            "unique_agents": unique_agents,
            "top_agents": [
                {"agent_id": agent_id, "interactions": count}
                for agent_id, count in top_agents
            ],
            "top_communications": [
                {"path": path, "count": count}
                for path, count in top_communications
            ],
            "anomalies_detected": len(anomalies),
            "anomalies": anomalies[:5],  # Top 5 anomalies
            "timestamp": time.time()
        }


# Global analytics service instance
analytics_service = AnalyticsService()

