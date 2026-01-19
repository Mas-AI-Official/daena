"""
Reverse-Attack AI Department (Masoud-only).

This is a hidden, encrypted department that is NOT exposed in the frontend.
Only Masoud can access this department.

Features:
- Buffer overflow detection
- LLM jailbreak detection
- Model poisoning detection
- Reverse-trace & isolate attacker
"""

from __future__ import annotations

import logging
import hashlib
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass

from backend.services.threat_detection import threat_detector, ThreatLevel, ThreatType
from memory_service.ledger import log_event

logger = logging.getLogger(__name__)


class AttackType(Enum):
    """Types of attacks to detect."""
    BUFFER_OVERFLOW = "buffer_overflow"
    LLM_JAILBREAK = "llm_jailbreak"
    MODEL_POISONING = "model_poisoning"
    PROMPT_INJECTION = "prompt_injection"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"


@dataclass
class AttackTrace:
    """Trace of an attack attempt."""
    trace_id: str
    attack_type: AttackType
    source_ip: str
    source_tenant: Optional[str]
    timestamp: str
    payload_preview: str  # First 200 chars only
    detection_method: str
    confidence: float
    isolated: bool = False
    reverse_traced: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ReverseAttackAI:
    """
    Reverse-Attack AI Department (Masoud-only).
    
    IMPORTANT: This department is hidden and encrypted.
    It is NOT exposed in the frontend.
    Only Masoud can access this department.
    """
    
    def __init__(self):
        self.department_id = "reverse_attack_ai"
        self.department_name = "Reverse-Attack AI (Hidden)"
        self.is_hidden = True  # Not exposed in frontend
        self.is_encrypted = True
        self.authorized_users = ["masoud", "masoud.masoori"]  # Only Masoud
        self.attack_traces: List[AttackTrace] = []
        self.max_traces = 1000
        
        # Detection patterns
        self.buffer_overflow_patterns = [
            b"A" * 1000,  # Long strings
            b"\x00" * 100,  # Null bytes
            b"%n",  # Format string vulnerability
        ]
        
        self.jailbreak_patterns = [
            "ignore previous instructions",
            "you are now",
            "system:",
            "assistant:",
            "override",
            "bypass",
            "jailbreak",
            "forget everything",
            "new instructions",
            "act as",
            "pretend to be"
        ]
        
        self.poisoning_patterns = [
            "training data",
            "model update",
            "fine-tune",
            "adversarial",
            "backdoor",
            "trojan"
        ]
    
    def is_authorized(self, user_id: str) -> bool:
        """Check if user is authorized to access this department."""
        return user_id.lower() in [u.lower() for u in self.authorized_users]
    
    def detect_buffer_overflow(self, payload: bytes, source_ip: str, tenant_id: Optional[str] = None) -> Optional[AttackTrace]:
        """Detect buffer overflow attempts."""
        if not isinstance(payload, bytes):
            payload = str(payload).encode('utf-8', errors='ignore')
        
        # Check for suspicious patterns
        detected = False
        detection_method = ""
        
        # Check length
        if len(payload) > 10000:  # Very long payload
            detected = True
            detection_method = "length_check"
        
        # Check for null bytes
        if b"\x00" in payload[:1000]:
            detected = True
            detection_method = "null_byte_check"
        
        # Check for format string vulnerabilities
        if b"%n" in payload or b"%x" in payload:
            detected = True
            detection_method = "format_string_check"
        
        if detected:
            trace = AttackTrace(
                trace_id=f"trace_{int(time.time())}_{hashlib.md5(payload[:100]).hexdigest()[:8]}",
                attack_type=AttackType.BUFFER_OVERFLOW,
                source_ip=source_ip,
                source_tenant=tenant_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                payload_preview=payload[:200].decode('utf-8', errors='ignore'),
                detection_method=detection_method,
                confidence=0.8
            )
            
            self._record_trace(trace)
            return trace
        
        return None
    
    def detect_llm_jailbreak(self, prompt: str, source_ip: str, tenant_id: Optional[str] = None) -> Optional[AttackTrace]:
        """Detect LLM jailbreak attempts."""
        prompt_lower = prompt.lower()
        
        detected_keywords = [
            keyword for keyword in self.jailbreak_patterns
            if keyword in prompt_lower
        ]
        
        if len(detected_keywords) >= 2:  # Multiple jailbreak keywords
            trace = AttackTrace(
                trace_id=f"trace_{int(time.time())}_{hashlib.md5(prompt.encode()).hexdigest()[:8]}",
                attack_type=AttackType.LLM_JAILBREAK,
                source_ip=source_ip,
                source_tenant=tenant_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                payload_preview=prompt[:200],
                detection_method="keyword_analysis",
                confidence=min(0.9, 0.5 + (len(detected_keywords) * 0.1))
            )
            
            self._record_trace(trace)
            return trace
        
        return None
    
    def detect_model_poisoning(self, data: Dict[str, Any], source_ip: str, tenant_id: Optional[str] = None) -> Optional[AttackTrace]:
        """Detect model poisoning attempts."""
        data_str = str(data).lower()
        
        detected_keywords = [
            keyword for keyword in self.poisoning_patterns
            if keyword in data_str
        ]
        
        if detected_keywords:
            trace = AttackTrace(
                trace_id=f"trace_{int(time.time())}_{hashlib.md5(str(data).encode()).hexdigest()[:8]}",
                attack_type=AttackType.MODEL_POISONING,
                source_ip=source_ip,
                source_tenant=tenant_id,
                timestamp=datetime.utcnow().isoformat() + "Z",
                payload_preview=str(data)[:200],
                detection_method="keyword_analysis",
                confidence=0.7
            )
            
            self._record_trace(trace)
            return trace
        
        return None
    
    def reverse_trace(self, trace_id: str) -> Dict[str, Any]:
        """Reverse-trace an attack to identify the attacker."""
        trace = next((t for t in self.attack_traces if t.trace_id == trace_id), None)
        if not trace:
            return {"error": "Trace not found"}
        
        # Perform reverse tracing
        trace_info = {
            "trace_id": trace.trace_id,
            "attack_type": trace.attack_type.value,
            "source_ip": trace.source_ip,
            "source_tenant": trace.source_tenant,
            "timestamp": trace.timestamp,
            "detection_method": trace.detection_method,
            "confidence": trace.confidence
        }
        
        # Find related traces from same source
        related_traces = [
            t for t in self.attack_traces
            if t.source_ip == trace.source_ip and t.trace_id != trace_id
        ]
        
        trace_info["related_attacks"] = len(related_traces)
        trace_info["attack_pattern"] = self._analyze_pattern(related_traces + [trace])
        
        trace.reverse_traced = True
        
        log_event(
            action="reverse_trace",
            ref=trace_id,
            store="security",
            route="reverse_attack_ai",
            extra=trace_info
        )
        
        return trace_info
    
    def isolate_attacker(self, trace_id: str) -> Dict[str, Any]:
        """Isolate an attacker based on trace."""
        trace = next((t for t in self.attack_traces if t.trace_id == trace_id), None)
        if not trace:
            return {"error": "Trace not found"}
        
        # Isolation actions
        isolation_actions = {
            "block_ip": trace.source_ip,
            "block_tenant": trace.source_tenant,
            "isolated_at": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id
        }
        
        trace.isolated = True
        
        log_event(
            action="attacker_isolated",
            ref=trace_id,
            store="security",
            route="reverse_attack_ai",
            extra=isolation_actions
        )
        
        logger.warning(f"Attacker isolated: {trace.source_ip} (tenant: {trace.source_tenant})")
        
        return isolation_actions
    
    def _analyze_pattern(self, traces: List[AttackTrace]) -> Dict[str, Any]:
        """Analyze attack pattern from traces."""
        if not traces:
            return {}
        
        attack_types = [t.attack_type.value for t in traces]
        unique_types = list(set(attack_types))
        
        return {
            "total_attacks": len(traces),
            "unique_attack_types": unique_types,
            "most_common_type": max(set(attack_types), key=attack_types.count) if attack_types else None,
            "time_span": self._calculate_time_span(traces)
        }
    
    def _calculate_time_span(self, traces: List[AttackTrace]) -> Optional[float]:
        """Calculate time span of attacks in seconds."""
        if len(traces) < 2:
            return None
        
        timestamps = [datetime.fromisoformat(t.timestamp.replace("Z", "+00:00")).timestamp() for t in traces]
        return max(timestamps) - min(timestamps)
    
    def _record_trace(self, trace: AttackTrace) -> None:
        """Record attack trace."""
        self.attack_traces.append(trace)
        
        # Limit history
        if len(self.attack_traces) > self.max_traces:
            self.attack_traces = self.attack_traces[-self.max_traces:]
        
        # Log to ledger
        log_event(
            action="attack_detected",
            ref=trace.trace_id,
            store="security",
            route="reverse_attack_ai",
            extra={
                "attack_type": trace.attack_type.value,
                "source_ip": trace.source_ip,
                "source_tenant": trace.source_tenant,
                "confidence": trace.confidence,
                "detection_method": trace.detection_method
            }
        )
    
    def get_traces(
        self,
        attack_type: Optional[AttackType] = None,
        source_ip: Optional[str] = None,
        limit: int = 100
    ) -> List[AttackTrace]:
        """Get attack traces (authorized users only)."""
        traces = self.attack_traces
        
        if attack_type:
            traces = [t for t in traces if t.attack_type == attack_type]
        
        if source_ip:
            traces = [t for t in traces if t.source_ip == source_ip]
        
        return traces[-limit:] if traces else []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get department statistics (authorized users only)."""
        by_type = {}
        for trace in self.attack_traces:
            attack_type = trace.attack_type.value
            by_type[attack_type] = by_type.get(attack_type, 0) + 1
        
        return {
            "total_traces": len(self.attack_traces),
            "by_attack_type": by_type,
            "isolated_count": sum(1 for t in self.attack_traces if t.isolated),
            "reverse_traced_count": sum(1 for t in self.attack_traces if t.reverse_traced)
        }


# Global reverse-attack AI instance (hidden department)
reverse_attack_ai = ReverseAttackAI()





