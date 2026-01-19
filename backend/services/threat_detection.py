"""
Threat Detection System for Daena AI VP.
Defensive cybersecurity - detects and logs suspicious patterns, anomalies, and potential attacks.
All logic is internal and defensive - no external scanning or attacks.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from enum import Enum
from dataclasses import dataclass

from memory_service.ledger import log_event

# Optional reverse-attack AI integration
try:
    from backend.services.reverse_attack_ai import reverse_attack_ai
    REVERSE_ATTACK_AVAILABLE = True
except ImportError:
    REVERSE_ATTACK_AVAILABLE = False
    reverse_attack_ai = None

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Types of threats detected."""
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_LOGIN_PATTERN = "suspicious_login_pattern"
    UNEXPECTED_PROMPT_INJECTION = "unexpected_prompt_injection"
    ANOMALOUS_ACCESS_PATTERN = "anomalous_access_pattern"
    UNUSUAL_MEMORY_ACCESS = "unusual_memory_access"
    COUNCIL_MANIPULATION_ATTEMPT = "council_manipulation_attempt"
    TENANT_ISOLATION_VIOLATION = "tenant_isolation_violation"
    UNAUTHORIZED_ACTION = "unauthorized_action"
    MODEL_POISONING_SUSPECTED = "model_poisoning_suspected"
    BUFFER_OVERFLOW_ATTEMPT = "buffer_overflow_attempt"


@dataclass
class ThreatSignal:
    """A detected threat signal."""
    threat_id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    description: str
    tenant_id: Optional[str]
    source: str  # IP, user_id, agent_id, etc.
    metadata: Dict[str, Any]
    timestamp: str
    detected_by: str  # Which detector found it
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "threat_id": self.threat_id,
            "threat_type": self.threat_type.value,
            "threat_level": self.threat_level.value,
            "description": self.description,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "detected_by": self.detected_by
        }


class ThreatDetector:
    """
    Detects threats and anomalies in Daena system.
    
    All detection is defensive and internal - no external scanning.
    """
    
    def __init__(self):
        self.threat_history: List[ThreatSignal] = []
        self.rate_limit_violations: Dict[str, List[float]] = defaultdict(list)
        self.login_patterns: Dict[str, List[float]] = defaultdict(list)
        self.access_patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.prompt_injection_keywords = [
            "ignore previous instructions",
            "forget everything",
            "you are now",
            "system:",
            "assistant:",
            "override",
            "bypass",
            "jailbreak",
            "disregard",
            "ignore all",
            "new instructions",
            "forget all",
            "pretend to be",
            "act as if",
            "roleplay",
            "simulate",
            "you must",
            "you will",
            "you should",
            "execute",
            "run code",
            "eval(",
            "exec(",
            "import os",
            "subprocess",
            "shell=True",
            "base64",
            "decode",
            "<!--",
            "<script>",
            "javascript:",
            "data:text/html"
        ]
        self.max_history = 1000
        
        # Honeytoken traps - fake sensitive data to detect unauthorized access
        self.honeytokens: Dict[str, Dict[str, Any]] = {}
        self.honeytoken_accesses: List[Dict[str, Any]] = []
        
        # Real-time kill-switch state
        self.kill_switch_active: bool = False
        self.kill_switch_reason: Optional[str] = None
        self.kill_switch_activated_at: Optional[str] = None
        self.kill_switch_activated_by: Optional[str] = None
        
    def detect_rate_limit_violation(
        self,
        tenant_id: str,
        endpoint: str,
        request_count: int,
        time_window: float
    ) -> Optional[ThreatSignal]:
        """
        Detect rate limit violations.
        
        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint
            request_count: Number of requests in window
            time_window: Time window in seconds
            
        Returns:
            ThreatSignal if violation detected, None otherwise
        """
        # Track violations
        now = time.time()
        self.rate_limit_violations[tenant_id].append(now)
        
        # Clean old violations (older than 1 hour)
        cutoff = now - 3600
        self.rate_limit_violations[tenant_id] = [
            t for t in self.rate_limit_violations[tenant_id] if t > cutoff
        ]
        
        # Check for pattern (multiple violations in short time)
        violations = self.rate_limit_violations[tenant_id]
        if len(violations) > 10:  # More than 10 violations in last hour
            threat_level = ThreatLevel.HIGH if len(violations) > 20 else ThreatLevel.MEDIUM
            
            threat = ThreatSignal(
                threat_id=f"rate_limit_{tenant_id}_{int(now)}",
                threat_type=ThreatType.RATE_LIMIT_EXCEEDED,
                threat_level=threat_level,
                description=f"Rate limit violations detected: {len(violations)} violations in last hour",
                tenant_id=tenant_id,
                source=tenant_id,
                metadata={
                    "endpoint": endpoint,
                    "request_count": request_count,
                    "time_window": time_window,
                    "violation_count": len(violations)
                },
                timestamp=datetime.utcnow().isoformat() + "Z",
                detected_by="rate_limit_detector"
            )
            
            self._record_threat(threat)
            return threat
        
        return None
    
    def detect_prompt_injection(
        self,
        prompt: str,
        tenant_id: Optional[str],
        source: str
    ) -> Optional[ThreatSignal]:
                """
                Detect potential prompt injection attempts.
                
                Args:
                    prompt: User prompt to check
                    tenant_id: Tenant identifier
                    source: Source of the prompt (user_id, agent_id, etc.)
                    
                Returns:
                    ThreatSignal if injection detected, None otherwise
                """
                prompt_lower = prompt.lower()
                
                # Check for injection keywords
                detected_keywords = [
                    keyword for keyword in self.prompt_injection_keywords
                    if keyword in prompt_lower
                ]
                
                if detected_keywords:
                    threat_level = ThreatLevel.MEDIUM
                    if len(detected_keywords) > 3:
                        threat_level = ThreatLevel.HIGH
                    
                    threat = ThreatSignal(
                        threat_id=f"prompt_injection_{source}_{int(time.time())}",
                        threat_type=ThreatType.UNEXPECTED_PROMPT_INJECTION,
                        threat_level=threat_level,
                        description=f"Potential prompt injection detected: {len(detected_keywords)} suspicious keywords",
                        tenant_id=tenant_id,
                        source=source,
                        metadata={
                            "detected_keywords": detected_keywords,
                            "prompt_length": len(prompt),
                            "prompt_preview": prompt[:200]  # First 200 chars only
                        },
                        timestamp=datetime.utcnow().isoformat() + "Z",
                        detected_by="prompt_injection_detector"
                    )
                    
                    self._record_threat(threat)
                    
                    # Forward to reverse-attack AI for LLM jailbreak detection
                    if REVERSE_ATTACK_AVAILABLE:
                        try:
                            # Extract source IP from source if available
                            source_ip = source.split(":")[-1] if ":" in source else "unknown"
                            reverse_attack_ai.detect_llm_jailbreak(prompt, source_ip, tenant_id)
                        except Exception as e:
                            logger.debug(f"Reverse-attack AI error (non-critical): {e}")
                    
                    return threat
                
                return None
    
    def detect_tenant_isolation_violation(
        self,
        tenant_id: str,
        attempted_access: str,
        source: str
    ) -> Optional[ThreatSignal]:
        """
        Detect attempts to access data from another tenant.
        
        Args:
            tenant_id: Tenant making the request
            attempted_access: Tenant ID being accessed
            source: Source of the request
            
        Returns:
            ThreatSignal if violation detected, None otherwise
        """
        if tenant_id != attempted_access and attempted_access != "default":
            threat = ThreatSignal(
                threat_id=f"tenant_violation_{tenant_id}_{int(time.time())}",
                threat_type=ThreatType.TENANT_ISOLATION_VIOLATION,
                threat_level=ThreatLevel.CRITICAL,
                description=f"Tenant isolation violation: {tenant_id} attempted to access {attempted_access}",
                tenant_id=tenant_id,
                source=source,
                metadata={
                    "requested_tenant": attempted_access,
                    "requesting_tenant": tenant_id
                },
                timestamp=datetime.utcnow().isoformat() + "Z",
                detected_by="tenant_isolation_detector"
            )
            
            self._record_threat(threat)
            return threat
        
        return None
    
    def detect_anomalous_access(
        self,
        tenant_id: str,
        endpoint: str,
        access_pattern: Dict[str, Any],
        source: str
    ) -> Optional[ThreatSignal]:
        """
        Detect anomalous access patterns.
        
        Args:
            tenant_id: Tenant identifier
            endpoint: API endpoint accessed
            access_pattern: Access pattern metadata
            source: Source of the access
            
        Returns:
            ThreatSignal if anomaly detected, None otherwise
        """
        now = time.time()
        self.access_patterns[tenant_id].append({
            "timestamp": now,
            "endpoint": endpoint,
            "pattern": access_pattern
        })
        
        # Clean old patterns (older than 24 hours)
        cutoff = now - 86400
        self.access_patterns[tenant_id] = [
            p for p in self.access_patterns[tenant_id] if p["timestamp"] > cutoff
        ]
        
        patterns = self.access_patterns[tenant_id]
        
        # Check for unusual patterns
        # Example: Accessing many different endpoints in short time
        if len(patterns) > 50:  # More than 50 accesses in 24 hours
            unique_endpoints = len(set(p["endpoint"] for p in patterns))
            if unique_endpoints > 20:  # More than 20 different endpoints
                threat = ThreatSignal(
                    threat_id=f"anomalous_access_{tenant_id}_{int(now)}",
                    threat_type=ThreatType.ANOMALOUS_ACCESS_PATTERN,
                    threat_level=ThreatLevel.MEDIUM,
                    description=f"Anomalous access pattern: {unique_endpoints} unique endpoints in 24h",
                    tenant_id=tenant_id,
                    source=source,
                    metadata={
                        "total_accesses": len(patterns),
                        "unique_endpoints": unique_endpoints,
                        "time_window_hours": 24
                    },
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    detected_by="anomalous_access_detector"
                )
                
                self._record_threat(threat)
                return threat
        
        return None
    
    def _record_threat(self, threat: ThreatSignal) -> None:
        """Record threat in history and ledger."""
        self.threat_history.append(threat)
        
        # Limit history size
        if len(self.threat_history) > self.max_history:
            self.threat_history = self.threat_history[-self.max_history:]
        
        # Log to ledger
        log_event(
            action="threat_detected",
            ref=threat.threat_id,
            store="nbmf",
            route="security",
            extra={
                "threat_type": threat.threat_type.value,
                "threat_level": threat.threat_level.value,
                "tenant_id": threat.tenant_id,
                "source": threat.source,
                "detected_by": threat.detected_by
            }
        )
        
        logger.warning(f"Threat detected: {threat.threat_type.value} ({threat.threat_level.value}) - {threat.description}")
    
    def get_threats(
        self,
        tenant_id: Optional[str] = None,
        threat_level: Optional[ThreatLevel] = None,
        hours: int = 24
    ) -> List[ThreatSignal]:
        """
        Get threats matching criteria.
        
        Args:
            tenant_id: Filter by tenant (None for all)
            threat_level: Filter by threat level (None for all)
            hours: Look back N hours
            
        Returns:
            List of matching threats
        """
        cutoff = time.time() - (hours * 3600)
        
        threats = [
            t for t in self.threat_history
            if datetime.fromisoformat(t.timestamp.replace("Z", "+00:00")).timestamp() > cutoff
        ]
        
        if tenant_id:
            threats = [t for t in threats if t.tenant_id == tenant_id]
        
        if threat_level:
            threats = [t for t in threats if t.threat_level == threat_level]
        
        return threats
    
    def get_threat_summary(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get threat summary statistics."""
        threats = self.get_threats(tenant_id=tenant_id, hours=24)
        
        by_level = defaultdict(int)
        by_type = defaultdict(int)
        
        for threat in threats:
            by_level[threat.threat_level.value] += 1
            by_type[threat.threat_type.value] += 1
        
        return {
            "total_threats_24h": len(threats),
            "by_level": dict(by_level),
            "by_type": dict(by_type),
            "critical_count": by_level.get("critical", 0),
            "high_count": by_level.get("high", 0)
        }
    
    def create_honeytoken(
        self,
        token_type: str,
        fake_data: Dict[str, Any],
        tenant_id: Optional[str] = None
    ) -> str:
        """
        Create a honeytoken trap to detect unauthorized access.
        
        Args:
            token_type: Type of honeytoken (api_key, file_id, memory_id, etc.)
            fake_data: Fake sensitive data to use as bait
            tenant_id: Tenant ID (optional)
            
        Returns:
            Honeytoken ID
        """
        import uuid
        token_id = f"honeytoken_{uuid.uuid4().hex[:16]}"
        
        self.honeytokens[token_id] = {
            "token_id": token_id,
            "token_type": token_type,
            "fake_data": fake_data,
            "tenant_id": tenant_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "accessed": False,
            "access_count": 0
        }
        
        log_event(
            action="honeytoken_created",
            ref=token_id,
            store="security",
            route="threat_detection",
            extra={
                "token_type": token_type,
                "tenant_id": tenant_id
            }
        )
        
        logger.info(f"Honeytoken created: {token_id} (type: {token_type})")
        return token_id
    
    def check_honeytoken_access(
        self,
        token_id: str,
        source: str,
        tenant_id: Optional[str] = None
    ) -> Optional[ThreatSignal]:
        """
        Check if a honeytoken was accessed (unauthorized access detected).
        
        Args:
            token_id: Honeytoken ID to check
            source: Source of the access (IP, user_id, etc.)
            tenant_id: Tenant making the access
            
        Returns:
            ThreatSignal if honeytoken accessed, None otherwise
        """
        if token_id not in self.honeytokens:
            return None
        
        token = self.honeytokens[token_id]
        
        # Mark as accessed
        token["accessed"] = True
        token["access_count"] += 1
        
        # Record access
        access_record = {
            "token_id": token_id,
            "source": source,
            "tenant_id": tenant_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "token_type": token["token_type"]
        }
        self.honeytoken_accesses.append(access_record)
        
        # Limit access history
        if len(self.honeytoken_accesses) > 1000:
            self.honeytoken_accesses = self.honeytoken_accesses[-1000:]
        
        # Create threat signal
        threat = ThreatSignal(
            threat_id=f"honeytoken_breach_{token_id}_{int(time.time())}",
            threat_type=ThreatType.UNAUTHORIZED_ACTION,
            threat_level=ThreatLevel.CRITICAL,
            description=f"Honeytoken breach detected: {token['token_type']} accessed by unauthorized source",
            tenant_id=tenant_id,
            source=source,
            metadata={
                "honeytoken_id": token_id,
                "token_type": token["token_type"],
                "expected_tenant": token.get("tenant_id"),
                "accessing_tenant": tenant_id,
                "access_count": token["access_count"]
            },
            timestamp=datetime.utcnow().isoformat() + "Z",
            detected_by="honeytoken_detector"
        )
        
        self._record_threat(threat)
        
        log_event(
            action="honeytoken_breach",
            ref=token_id,
            store="security",
            route="threat_detection",
            extra={
                "source": source,
                "tenant_id": tenant_id,
                "token_type": token["token_type"]
            }
        )
        
        logger.critical(f"HONEYTOKEN BREACH: {token_id} accessed by {source} (tenant: {tenant_id})")
        
        return threat
    
    def get_honeytoken_stats(self) -> Dict[str, Any]:
        """Get honeytoken statistics."""
        total_tokens = len(self.honeytokens)
        accessed_tokens = sum(1 for t in self.honeytokens.values() if t["accessed"])
        
        by_type = defaultdict(int)
        for token in self.honeytokens.values():
            by_type[token["token_type"]] += 1
        
        return {
            "total_tokens": total_tokens,
            "accessed_tokens": accessed_tokens,
            "breach_rate": accessed_tokens / total_tokens if total_tokens > 0 else 0.0,
            "by_type": dict(by_type),
            "total_accesses": len(self.honeytoken_accesses)
        }
    
    def activate_kill_switch(
        self,
        reason: str,
        activated_by: str
    ) -> bool:
        """
        Activate real-time kill-switch to immediately stop all operations.
        
        Args:
            reason: Reason for activation
            activated_by: Who activated it (user_id, system, etc.)
            
        Returns:
            True if activated, False if already active
        """
        if self.kill_switch_active:
            logger.warning("Kill-switch already active, cannot activate again")
            return False
        
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self.kill_switch_activated_at = datetime.utcnow().isoformat() + "Z"
        self.kill_switch_activated_by = activated_by
        
        log_event(
            action="kill_switch_activated",
            ref="system",
            store="security",
            route="threat_detection",
            extra={
                "reason": reason,
                "activated_by": activated_by,
                "timestamp": self.kill_switch_activated_at
            }
        )
        
        logger.critical(f"KILL-SWITCH ACTIVATED by {activated_by}: {reason}")
        return True
    
    def deactivate_kill_switch(
        self,
        deactivated_by: str
    ) -> bool:
        """
        Deactivate kill-switch to resume operations.
        
        Args:
            deactivated_by: Who deactivated it
            
        Returns:
            True if deactivated, False if not active
        """
        if not self.kill_switch_active:
            logger.warning("Kill-switch not active, cannot deactivate")
            return False
        
        self.kill_switch_active = False
        deactivated_at = datetime.utcnow().isoformat() + "Z"
        
        log_event(
            action="kill_switch_deactivated",
            ref="system",
            store="security",
            route="threat_detection",
            extra={
                "deactivated_by": deactivated_by,
                "was_active_for": self.kill_switch_activated_at,
                "timestamp": deactivated_at
            }
        )
        
        logger.info(f"Kill-switch deactivated by {deactivated_by}")
        
        # Clear state
        self.kill_switch_reason = None
        self.kill_switch_activated_at = None
        self.kill_switch_activated_by = None
        
        return True
    
    def is_kill_switch_active(self) -> bool:
        """Check if kill-switch is currently active."""
        return self.kill_switch_active
    
    def get_kill_switch_status(self) -> Dict[str, Any]:
        """Get kill-switch status."""
        return {
            "active": self.kill_switch_active,
            "reason": self.kill_switch_reason,
            "activated_at": self.kill_switch_activated_at,
            "activated_by": self.kill_switch_activated_by
        }


# Global threat detector instance
threat_detector = ThreatDetector()

