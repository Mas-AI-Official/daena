"""
Complexity Scorer - Model Selection Rubric
Computes a complexity score (0-10) to determine which model tier to use.
"""

import re
import logging
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class ComplexityTier(str, Enum):
    """Model complexity tiers"""
    NO_LLM = "no_llm"  # 0-2: Deterministic gate handles
    CHEAP = "cheap"  # 3-5: Local small model
    STRONG = "strong"  # 6-8: Strong model
    DEEP_RESEARCH = "deep_research"  # 9-10: Strong + evaluator loop


class ComplexityScorer:
    """
    Scores task complexity to determine appropriate model tier.
    """
    
    def __init__(
        self,
        no_llm_max: int = 2,
        cheap_max: int = 5,
        strong_max: int = 8
    ):
        self.no_llm_max = no_llm_max
        self.cheap_max = cheap_max
        self.strong_max = strong_max
        
        # High-complexity keywords
        self.complex_keywords = {
            "audit": 2,
            "architecture": 2,
            "security": 2,
            "websocket": 1,
            "streaming": 1,
            "refactor": 2,
            "migrate": 2,
            "compare": 1,
            "analyze": 1,
            "design": 1,
            "strategy": 1,
            "governance": 2,
            "compliance": 2,
            "legal": 2,
            "finance": 1,
            "production": 1,
            "deployment": 1,
            "scalability": 1,
            "performance": 1,
            "optimization": 1,
            "multi-file": 2,
            "cross-department": 1,
            "synthesis": 1,
        }
        
        # Trivial patterns (reduce score)
        self.trivial_patterns = [
            r'^hi\b',
            r'^hello\b',
            r'^hey\b',
            r'^thanks?\b',
            r'^thank you\b',
            r'^ok\b',
            r'^okay\b',
            r'^yes\b',
            r'^no\b',
        ]
    
    def score(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compute complexity score (0-10).
        
        Returns:
            {
                score: int (0-10),
                tier: ComplexityTier,
                reasons: List[str]
            }
        """
        score = 0
        reasons = []
        input_lower = user_input.lower()
        input_length = len(user_input.split())
        
        # Base score from length
        if input_length < 5:
            score += 0
            reasons.append("Very short input")
        elif input_length < 15:
            score += 1
            reasons.append("Short input")
        elif input_length < 50:
            score += 2
            reasons.append("Medium input")
        elif input_length < 150:
            score += 3
            reasons.append("Long input")
        else:
            score += 4
            reasons.append("Very long input")
        
        # Check for complex keywords
        keyword_score = 0
        for keyword, weight in self.complex_keywords.items():
            if keyword in input_lower:
                keyword_score += weight
                reasons.append(f"Complex keyword: {keyword}")
        
        # Cap keyword score contribution
        keyword_score = min(keyword_score, 4)
        score += keyword_score
        
        # Check for trivial patterns (reduce score)
        for pattern in self.trivial_patterns:
            if re.match(pattern, input_lower):
                score = max(0, score - 2)
                reasons.append("Trivial pattern detected")
                break
        
        # Context-based adjustments
        if context:
            # Multi-file or production flags
            if context.get("multi_file") or context.get("production"):
                score += 2
                reasons.append("Production/multi-file context")
            
            # Finance/legal flags
            if context.get("department") in ["Finance", "Legal"]:
                score += 1
                reasons.append("Finance/legal context")
            
            # Requires tools
            if context.get("requires_tools"):
                score += 1
                reasons.append("Requires tool execution")
            
            # High priority
            if context.get("priority") == "high":
                score += 1
                reasons.append("High priority task")
        
        # Constraint count (more constraints = more complex)
        constraint_indicators = [
            "must", "require", "cannot", "should not", "never", "always",
            "constraint", "restriction", "limit"
        ]
        constraint_count = sum(1 for word in constraint_indicators if word in input_lower)
        if constraint_count > 0:
            score += min(constraint_count, 2)
            reasons.append(f"{constraint_count} constraints detected")
        
        # Cap at 10
        score = min(score, 10)
        
        # Determine tier
        if score <= self.no_llm_max:
            tier = ComplexityTier.NO_LLM
        elif score <= self.cheap_max:
            tier = ComplexityTier.CHEAP
        elif score <= self.strong_max:
            tier = ComplexityTier.STRONG
        else:
            tier = ComplexityTier.DEEP_RESEARCH
        
        return {
            "score": score,
            "tier": tier.value,
            "reasons": reasons,
            "input_length": input_length,
            "keyword_score": keyword_score
        }


# Global instance
_complexity_scorer_instance: Optional[ComplexityScorer] = None

def get_complexity_scorer() -> ComplexityScorer:
    """Get singleton instance"""
    global _complexity_scorer_instance
    if _complexity_scorer_instance is None:
        from backend.config.settings import settings
        no_llm_max = getattr(settings, 'daena_complexity_no_llm_max', 2)
        cheap_max = getattr(settings, 'daena_complexity_cheap_max', 5)
        strong_max = getattr(settings, 'daena_complexity_strong_max', 8)
        _complexity_scorer_instance = ComplexityScorer(
            no_llm_max=no_llm_max,
            cheap_max=cheap_max,
            strong_max=strong_max
        )
    return _complexity_scorer_instance




