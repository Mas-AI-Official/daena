"""
Real-Time Metrics Stream Service
Publishes live metrics via SSE for dashboard consumption.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List
from collections import deque

from sqlalchemy.orm import Session
from sqlalchemy import or_
from backend.database import SessionLocal, Department, Agent
from backend.config.council_config import COUNCIL_CONFIG
from backend.routes.events import emit

# Circular buffer for latency measurements (last 1000 samples)
_latency_buffer: Dict[str, deque] = {
    'nbmf_encode': deque(maxlen=1000),
    'nbmf_decode': deque(maxlen=1000),
    'council_decision': deque(maxlen=100),
    'message_bus': deque(maxlen=1000)
}


class RealtimeMetricsStream:
    """Manages real-time metrics streaming for dashboard."""
    
    def __init__(self):
        self.update_interval = 2.0  # seconds
        self.last_update = 0
        self._running = False
        self._task = None
    
    async def start(self):
        """Start the metrics stream background task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._metrics_loop())
    
    async def stop(self):
        """Stop the metrics stream."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _metrics_loop(self):
        """Main loop that publishes metrics every interval."""
        while self._running:
            try:
                metrics = await self._collect_metrics()
                emit("system_metrics", metrics)
                # Also emit council health for frontend sync
                if metrics.get("council"):
                    emit("council_health", {
                        "departments": metrics["council"]["departments"],
                        "agents": metrics["council"]["agents"],
                        "roles_per_department": metrics["council"]["roles_per_department"],
                        "validation": metrics["council"].get("validation", {})
                    })
                
                # Emit SEC-Loop metrics for frontend
                if metrics.get("sec_loop"):
                    emit("sec_loop_status", metrics["sec_loop"])
                self.last_update = time.time()
            except Exception as e:
                print(f"Error in metrics loop: {e}")
            
            await asyncio.sleep(self.update_interval)
    
    async def _collect_metrics(self) -> Dict[str, Any]:
        """Collect all real-time metrics."""
        db = SessionLocal()
        try:
            # Council structure metrics
            dept_count = db.query(Department).filter(Department.status == "active").count()
            agent_count = db.query(Agent).filter(Agent.is_active == True).count()
            
            # Calculate roles per department
            roles_per_dept = {}
            for dept in db.query(Department).filter(Department.status == "active").all():
                agents = db.query(Agent).filter(
                    Agent.is_active == True,
                    or_(
                        Agent.department_id == dept.id,
                        Agent.department == dept.slug,
                    ),
                ).count()
                roles_per_dept[dept.slug] = agents
            
            # NBMF metrics (from latency buffer)
            nbmf_encode_p95 = self._calculate_percentile(_latency_buffer['nbmf_encode'], 95)
            nbmf_encode_p99 = self._calculate_percentile(_latency_buffer['nbmf_encode'], 99)
            nbmf_decode_p95 = self._calculate_percentile(_latency_buffer['nbmf_decode'], 95)
            nbmf_decode_p99 = self._calculate_percentile(_latency_buffer['nbmf_decode'], 99)
            
            # Council decision metrics
            council_decision_p95 = self._calculate_percentile(_latency_buffer['council_decision'], 95)
            council_decision_p99 = self._calculate_percentile(_latency_buffer['council_decision'], 99)
            
            # Message bus queue depth
            try:
                from backend.utils.message_bus_v2 import message_bus
                queue_depth = len(message_bus.message_history)
                max_queue_size = getattr(message_bus, 'max_queue_size', 10000)
                queue_utilization = queue_depth / max_queue_size if max_queue_size > 0 else 0
            except:
                queue_depth = 0
                queue_utilization = 0
            
            # L1 hit rate (from memory router if available)
            try:
                from memory_service.router import memory_router
                l1_hits = getattr(memory_router, 'l1_hits', 0)
                l1_total = getattr(memory_router, 'l1_total', 1)
                l1_hit_rate = l1_hits / l1_total if l1_total > 0 else 0
            except:
                l1_hit_rate = 0
            
            # Ledger throughput (approximate from ledger service)
            try:
                from memory_service.ledger import ledger_service
                ledger_entries = getattr(ledger_service, 'total_entries', 0)
                ledger_throughput = getattr(ledger_service, 'writes_per_second', 0)
            except:
                ledger_throughput = 0
            
            # DeviceManager status
            try:
                from Core.device_manager import DeviceManager
                device_mgr = DeviceManager()
                current_device = device_mgr.get_device()
                device_info = {
                    "device_id": current_device.device_id,
                    "device_type": current_device.device_type.value,
                    "available": current_device.available,
                    "memory_gb": current_device.memory_gb
                }
            except:
                device_info = {"device_id": "unknown", "device_type": "cpu", "available": False}
            
            # SEC-Loop metrics (if available)
            sec_loop_metrics = {}
            try:
                from self_evolve.policy import CouncilPolicy
                policy = CouncilPolicy()
                pending_decisions = policy.get_pending_decisions()
                sec_loop_metrics = {
                    "pending_decisions": len(pending_decisions),
                    "total_cycles": 0,  # Would track from metrics
                    "total_promoted": 0,  # Would track from metrics
                    "total_rejected": 0  # Would track from metrics
                }
            except:
                sec_loop_metrics = {"pending_decisions": 0}
            
            # Heartbeat timestamp for live-state badge
            heartbeat_timestamp = time.time()
            heartbeat_age_sec = time.time() - self.last_update if self.last_update > 0 else 0
            heartbeat_status = "live" if heartbeat_age_sec < 10 else ("degraded" if heartbeat_age_sec < 30 else "stale")
            
            # Calculate average roles per department
            avg_roles = sum(roles_per_dept.values()) / len(roles_per_dept) if roles_per_dept else 0
            roles_per_department = int(avg_roles)
            
            # Validate structure
            validation = COUNCIL_CONFIG.validate_structure(
                departments=dept_count,
                agents=agent_count,
                roles_per_dept=roles_per_department
            )
            
            return {
                "timestamp": datetime.now().isoformat(),
                "council": {
                    "departments": dept_count,
                    "agents": agent_count,
                    "roles_per_department": roles_per_department,
                    "roles_per_dept": roles_per_dept,
                    "expected": {
                        "departments": COUNCIL_CONFIG.TOTAL_DEPARTMENTS,
                        "agents": COUNCIL_CONFIG.TOTAL_AGENTS,
                        "roles_per_department": COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT
                    },
                    "validation": validation,
                    "valid": validation.get("structure_valid", False)
                },
                "nbmf": {
                    "encode_p95_ms": nbmf_encode_p95,
                    "encode_p99_ms": nbmf_encode_p99,
                    "decode_p95_ms": nbmf_decode_p95,
                    "decode_p99_ms": nbmf_decode_p99,
                    "samples": {
                        "encode": len(_latency_buffer['nbmf_encode']),
                        "decode": len(_latency_buffer['nbmf_decode'])
                    }
                },
                "council_performance": {
                    "decision_p95_ms": council_decision_p95,
                    "decision_p99_ms": council_decision_p99,
                    "samples": len(_latency_buffer['council_decision'])
                },
                "message_bus": {
                    "queue_depth": queue_depth,
                    "queue_utilization": queue_utilization,
                    "backpressure_active": queue_utilization > 0.8
                },
                "memory": {
                    "l1_hit_rate": l1_hit_rate,
                    "ledger_throughput_per_sec": ledger_throughput
                },
                "device": device_info,
                "sec_loop": sec_loop_metrics,
                "heartbeat": {
                    "timestamp": heartbeat_timestamp,
                    "age_sec": heartbeat_age_sec,
                    "status": heartbeat_status
                }
            }
        finally:
            db.close()
    
    def _calculate_percentile(self, values: deque, percentile: int) -> float:
        """Calculate percentile from deque of values."""
        if not values:
            return 0.0
        
        sorted_vals = sorted(values)
        index = int(len(sorted_vals) * percentile / 100)
        if index >= len(sorted_vals):
            index = len(sorted_vals) - 1
        return sorted_vals[index] if sorted_vals else 0.0


# Global instance
realtime_metrics_stream = RealtimeMetricsStream()


# Public API for recording latencies
def record_latency(metric_type: str, latency_ms: float):
    """Record a latency measurement."""
    if metric_type in _latency_buffer:
        _latency_buffer[metric_type].append(latency_ms)


def record_nbmf_encode(latency_ms: float):
    """Record NBMF encode latency."""
    record_latency('nbmf_encode', latency_ms)


def record_nbmf_decode(latency_ms: float):
    """Record NBMF decode latency."""
    record_latency('nbmf_decode', latency_ms)


def record_council_decision(latency_ms: float):
    """Record council decision latency."""
    record_latency('council_decision', latency_ms)


def record_message_bus(latency_ms: float):
    """Record message bus latency."""
    record_latency('message_bus', latency_ms)

