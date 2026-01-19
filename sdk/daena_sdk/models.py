"""
Data models for Daena SDK.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class Agent:
    """Represents a Daena AI agent."""
    agent_id: str
    name: str
    department: str
    role: str
    status: str
    capabilities: List[str]
    performance_metrics: Dict[str, Any]
    is_active: bool


@dataclass
class Department:
    """Represents a Daena department."""
    department_id: str
    name: str
    description: str
    agent_count: int
    active_agents: int
    status: str


@dataclass
class MemoryRecord:
    """Represents a memory record in NBMF."""
    record_id: str
    key: str
    class_name: str
    payload: Any
    metadata: Dict[str, Any]
    compression_ratio: float
    size_bytes: int
    created_at: str
    tenant_id: Optional[str] = None


@dataclass
class CouncilDecision:
    """Represents a council decision."""
    decision_id: str
    department: str
    topic: str
    decision: str
    confidence: float
    agents_involved: List[str]
    created_at: str
    status: str
    impact_level: Optional[str] = None


@dataclass
class ExperienceVector:
    """Represents a knowledge distillation experience vector."""
    vector_id: str
    pattern_type: str
    features: Dict[str, float]
    confidence: float
    source_count: int
    metadata: Dict[str, Any]
    created_at: str


@dataclass
class SystemMetrics:
    """Represents system metrics."""
    total_agents: int
    active_agents: int
    departments: int
    memory_usage: Dict[str, Any]
    api_calls_per_minute: float
    average_latency_ms: float
    error_rate: float
    timestamp: str

