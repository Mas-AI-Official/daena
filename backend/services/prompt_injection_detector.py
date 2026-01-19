"""
Enhanced prompt injection detection for Immune system.
Detects and scores prompt injection attempts.
"""

import re
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

from backend.models.enterprise_dna import ThreatSignal, ThreatLevel

logger = logging.getLogger(__name__)


class PromptInjectionDetector:
    """
    Detects prompt injection attempts in user inputs.
    Feeds into Immune system for threat signal generation.
    """
    
    def __init__(self):
        # Pattern-based detection
        self.patterns = [
            # Instruction override patterns
            (r"ignore\s+(previous|all|the)\s+instructions?", 0.8),
            (r"forget\s+(everything|all|previous)", 0.8),
            (r"you\s+are\s+now", 0.7),
            (r"new\s+instructions?", 0.6),
            (r"disregard\s+(previous|all)", 0.7),
            
            # Role manipulation
            (r"pretend\s+to\s+be", 0.7),
            (r"act\s+as\s+if", 0.6),
            (r"roleplay\s+as", 0.6),
            (r"simulate\s+being", 0.6),
            
            # Command injection
            (r"execute\s+(code|command|script)", 0.9),
            (r"run\s+(code|command|script)", 0.9),
            (r"eval\s*\(", 0.95),
            (r"exec\s*\(", 0.95),
            (r"__import__", 0.9),
            (r"subprocess", 0.85),
            (r"shell\s*=\s*True", 0.9),
            
            # Encoding attempts
            (r"base64\s*\.\s*(b64encode|decode)", 0.8),
            (r"decode\s*\(['\"]base64", 0.8),
            
            # HTML/JS injection
            (r"<script", 0.9),
            (r"javascript:", 0.9),
            (r"data:text/html", 0.9),
            (r"onerror\s*=", 0.85),
            (r"onload\s*=", 0.85),
            
            # System prompts
            (r"system\s*:", 0.5),
            (r"assistant\s*:", 0.5),
            (r"user\s*:", 0.4),
            
            # Bypass attempts
            (r"bypass\s+(security|safety|filter)", 0.8),
            (r"jailbreak", 0.9),
            (r"override\s+(safety|security)", 0.8),
        ]
        
        # Context-based heuristics
        self.suspicious_contexts = [
            "ignore",
            "forget",
            "override",
            "bypass",
            "jailbreak",
            "execute",
            "eval",
            "exec",
            "system:",
            "assistant:"
        ]
    
    def detect(self, text: str, context: Dict[str, Any] = None) -> Tuple[float, List[str], ThreatLevel]:
        """
        Detect prompt injection in text.
        
        Args:
            text: Input text to analyze
            context: Additional context (user_id, source, etc.)
        
        Returns:
            (score, detected_patterns, threat_level)
            - score: 0.0 to 1.0 (injection confidence)
            - detected_patterns: List of matched patterns
            - threat_level: ThreatLevel enum
        """
        if not text:
            return 0.0, [], ThreatLevel.LOW
        
        text_lower = text.lower()
        detected_patterns = []
        total_score = 0.0
        max_score = 0.0
        
        # Check each pattern
        for pattern, weight in self.patterns:
            matches = re.finditer(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                detected_patterns.append(match.group(0))
                total_score += weight
                max_score = max(max_score, weight)
        
        # Normalize score (0.0 to 1.0)
        # Use weighted average: max pattern weight + average of all matches
        if detected_patterns:
            avg_score = total_score / len(detected_patterns)
            final_score = min(1.0, (max_score * 0.6 + avg_score * 0.4))
        else:
            final_score = 0.0
        
        # Check for suspicious context (multiple suspicious keywords)
        suspicious_count = sum(1 for keyword in self.suspicious_contexts if keyword in text_lower)
        if suspicious_count >= 3:
            final_score = min(1.0, final_score + 0.2)
            detected_patterns.append(f"multiple_suspicious_keywords({suspicious_count})")
        
        # Determine threat level
        if final_score >= 0.8:
            threat_level = ThreatLevel.CRITICAL
        elif final_score >= 0.6:
            threat_level = ThreatLevel.HIGH
        elif final_score >= 0.4:
            threat_level = ThreatLevel.MEDIUM
        else:
            threat_level = ThreatLevel.LOW
        
        return final_score, detected_patterns, threat_level
    
    def create_threat_signal(
        self,
        text: str,
        tenant_id: str,
        source: str,
        context: Dict[str, Any] = None
    ) -> ThreatSignal:
        """
        Create a ThreatSignal for prompt injection detection.
        
        Args:
            text: Input text
            tenant_id: Tenant identifier
            source: Source agent/system
            context: Additional context
        
        Returns:
            ThreatSignal object
        """
        score, patterns, threat_level = self.detect(text, context)
        
        return ThreatSignal(
            signal_id=f"prompt_injection_{datetime.utcnow().timestamp()}",
            tenant_id=tenant_id,
            threat_type="prompt_injection",
            threat_level=threat_level,
            score=score,
            detected_at=datetime.utcnow(),
            source=source,
            details={
                "detected_patterns": patterns,
                "text_length": len(text),
                "text_preview": text[:100] if len(text) > 100 else text,
                "context": context or {}
            },
            recommended_action="quarantine" if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL] else "degrade"
        )


# Global instance
_prompt_injection_detector: PromptInjectionDetector = None


def get_prompt_injection_detector() -> PromptInjectionDetector:
    """Get or create global prompt injection detector."""
    global _prompt_injection_detector
    if _prompt_injection_detector is None:
        _prompt_injection_detector = PromptInjectionDetector()
    return _prompt_injection_detector

