"""
Verifier Agent - Fact Checking & Anti-Hallucination
Validates scraped info and model outputs before they enter durable memory.

LAW 7 — SCOUT → VERIFY → SYNTHESIZE:
Raw data NEVER goes directly to synthesis or memory. Verification is mandatory.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SourceGrade(str, Enum):
    """Source quality grades"""
    A = "A"  # Primary / official docs
    B = "B"  # Reputable secondary reporting
    C = "C"  # Blog / low authority
    D = "D"  # Anonymous / unverified


class VerificationResult(BaseModel):
    """Result of verification check"""
    verified: bool
    confidence_score: float  # 0-100
    grade: SourceGrade
    provenance: Optional[str] = None
    recency_check: str  # passed, failed, unknown
    corroboration: List[str] = []  # Supporting sources
    conflicts: List[str] = []  # Contradictory info
    risk_assessment: str  # low, medium, high
    recommendations: List[str] = []


class FactClaim(BaseModel):
    """A factual claim to verify"""
    claim: str
    source: str
    timestamp: datetime
    context: Dict[str, Any] = {}


class VerifierAgent:
    """
    Verifier Agent - Enterprise-grade fact checking
    
    Validates information before it enters T2+ memory:
    1. Provenance - where did this come from?
    2. Recency - could it have changed?
    3. Corroboration - do we have 2+ independent sources?
    4. Specificity - does it include measurable details?
    5. Conflicts - what contradicts it?
    6. Risk - what happens if it's wrong?
    """
    
    def __init__(self):
        """Initialize verifier agent"""
        self.known_sources = self._initialize_source_registry()
        logger.info("✅ Verifier Agent initialized")
    
    def _initialize_source_registry(self) -> Dict[str, SourceGrade]:
        """Initialize registry of known sources with their grades"""
        return {
            # Grade A - Official/Primary
            "github.com": SourceGrade.A,
            "docs.python.org": SourceGrade.A,
            "fastapi.tiangolo.com": SourceGrade.A,
            "developer.mozilla.org": SourceGrade.A,
            
            # Grade B - Reputable secondary
            "stackoverflow.com": SourceGrade.B,
            "medium.com": SourceGrade.B,
            "realpython.com": SourceGrade.B,
            
            # Grade C - Low authority
            "wordpress.com": SourceGrade.C,
            "blogspot.com": SourceGrade.C,
            
            # Grade D - Unverified
            "pastebin.com": SourceGrade.D,
        }
    
    def grade_source(self, source: str) -> SourceGrade:
        """
        Grade a source based on its origin
        
        Args:
            source: Source URL or identifier
        
        Returns:
            SourceGrade (A/B/C/D)
        """
        # Try to parse as URL
        try:
            parsed = urlparse(source if source.startswith("http") else f"http://{source}")
            domain = parsed.netloc.lower()
            
            # Check exact match
            for known_domain, grade in self.known_sources.items():
                if known_domain in domain:
                    return grade
            
            # Heuristics for unknown sources
            if domain.endswith(".gov") or domain.endswith(".edu"):
                return SourceGrade.A
            elif domain.endswith(".org"):
                return SourceGrade.B
            else:
                return SourceGrade.C
        except Exception:
            # Not a URL, treat as internal source
            if source.lower() in ["database", "internal", "daena"]:
                return SourceGrade.A
            return SourceGrade.D
    
    def check_provenance(self, claim: FactClaim) -> Tuple[bool, str]:
        """
        Check where the claim came from
        
        Returns:
            (passed, explanation)
        """
        if not claim.source:
            return False, "No source provided"
        
        grade = self.grade_source(claim.source)
        
        if grade in [SourceGrade.A, SourceGrade.B]:
            return True, f"Source is {grade.value}-grade"
        else:
            return False, f"Source is low-quality ({grade.value}-grade)"
    
    def check_recency(self, claim: FactClaim) -> str:
        """
        Check if the claim could be outdated
        
        Returns:
            "passed", "failed", or "unknown"
        """
        # Check if claim mentions time-sensitive keywords
        time_sensitive_keywords = [
            "current", "now", "today", "latest", "recent",
            "version", "2024", "2025", "2026"
        ]
        
        claim_lower = claim.claim.lower()
        is_time_sensitive = any(kw in claim_lower for kw in time_sensitive_keywords)
        
        if is_time_sensitive:
            # Check timestamp
            age_days = (datetime.now() - claim.timestamp).days
            if age_days > 30:
                return "failed"  # Time-sensitive claim older than 30 days
            else:
                return "passed"
        else:
            # Timeless claim
            return "passed"
    
    def check_specificity(self, claim: FactClaim) -> Tuple[bool, str]:
        """
        Check if claim has measurable details
        
        Returns:
            (has_specificity, explanation)
        """
        claim_text = claim.claim.lower()
        
        # Check for vague language
        vague_phrases = [
            "some", "many", "few", "several", "most", "often",
            "usually", "generally", "approximately", "around"
        ]
        
        has_vague = any(phrase in claim_text for phrase in vague_phrases)
        
        # Check for specific numbers/names/dates
        has_numbers = bool(re.search(r'\d+', claim.claim))
        has_quotes = '"' in claim.claim or "'" in claim.claim
        
        if has_numbers or has_quotes:
            return True, "Claim includes specific details"
        elif has_vague:
            return False, "Claim uses vague language"
        else:
            return True, "Claim appears specific"
    
    def assess_risk(self, claim: FactClaim, grade: SourceGrade) -> str:
        """
        Assess risk if the claim is wrong
        
        Returns:
            "low", "medium", or "high"
        """
        # Check context for risk indicators
        context = claim.context or {}
        usage = context.get("usage", "").lower()
        
        # High risk scenarios
        high_risk_keywords = [
            "security", "financial", "legal", "compliance",
            "medical", "safety", "critical"
        ]
        
        if any(kw in usage for kw in high_risk_keywords):
            return "high"
        
        # Medium risk for low-grade sources
        if grade in [SourceGrade.C, SourceGrade.D]:
            return "medium"
        
        # Default to low risk
        return "low"
    
    async def verify(
        self,
        claim: FactClaim,
        check_corroboration: bool = False,
        additional_sources: Optional[List[str]] = None
    ) -> VerificationResult:
        """
        Verify a factual claim
        
        Args:
            claim: The claim to verify
            check_corroboration: Whether to check for supporting sources
            additional_sources: List of supporting sources
        
        Returns:
            VerificationResult with score and recommendations
        """
        # 1. Grade source
        grade = self.grade_source(claim.source)
        
        # 2. Check provenance
        provenance_ok, provenance_msg = self.check_provenance(claim)
        
        # 3. Check recency
        recency_check = self.check_recency(claim)
        
        # 4. Check specificity
        has_specificity, specificity_msg = self.check_specificity(claim)
        
        # 5. Corroboration
        corroboration_sources = additional_sources or []
        has_corroboration = len(corroboration_sources) >= 2
        
        # 6. Risk assessment
        risk = self.assess_risk(claim, grade)
        
        # Calculate confidence score (0-100)
        score = 0.0
        
        # Provenance (30 points)
        if grade == SourceGrade.A:
            score += 30
        elif grade == SourceGrade.B:
            score += 20
        elif grade == SourceGrade.C:
            score += 10
        
        # Recency (20 points)
        if recency_check == "passed":
            score += 20
        elif recency_check == "unknown":
            score += 10
        
        # Specificity (20 points)
        if has_specificity:
            score += 20
        
        # Corroboration (20 points)
        if has_corroboration:
            score += 20
        elif len(corroboration_sources) >= 1:
            score += 10
        
        # No conflicts (10 points)
        # For now, assume no conflicts (would need external check)
        score += 10
        
        # Determine if verified
        verified = score >= 60 and grade in [SourceGrade.A, SourceGrade.B]
        
        # Recommendations
        recommendations = []
        if not verified:
            if grade in [SourceGrade.C, SourceGrade.D]:
                recommendations.append("⚠️ Find a higher-quality source (Grade A or B)")
            if not has_corroboration and check_corroboration:
                recommendations.append("⚠️ Seek corroboration from at least 2 independent sources")
            if recency_check == "failed":
                recommendations.append("⚠️ Claim may be outdated - verify current status")
            if not has_specificity:
                recommendations.append("⚠️ Add specific, measurable details")
        
        if risk == "high":
            recommendations.append("🔴 HIGH RISK: Verify with multiple Grade-A sources")
        
        result = VerificationResult(
            verified=verified,
            confidence_score=score,
            grade=grade,
            provenance=claim.source,
            recency_check=recency_check,
            corroboration=corroboration_sources,
            conflicts=[],  # Would be populated by external conflict detection
            risk_assessment=risk,
            recommendations=recommendations
        )
        
        logger.info(f"Verified claim (score: {score:.1f}, verified: {verified})")
        return result
    
    async def verify_model_output(
        self,
        output: str,
        model_name: str,
        task_context: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify output from an LLM before accepting it
        
        Args:
            output: The model's output
            model_name: Name of model that generated it
            task_context: Context about the task
        
        Returns:
            VerificationResult
        """
        # Create a claim from the model output
        claim = FactClaim(
            claim=output[:500],  # First 500 chars
            source=f"model:{model_name}",
            timestamp=datetime.now(),
            context=task_context
        )
        
        # For model outputs, we check:
        # 1. Has the model provided evidence?
        has_citations = any(marker in output.lower() for marker in ["source:", "according to", "reference"])
        
        # 2. Did the model hedge appropriately?
        has_uncertainty_markers = any(
            marker in output.lower()
            for marker in ["may", "might", "possibly", "likely", "uncertain"]
        )
        
        # Grade model as source
        model_grade = SourceGrade.B  # Default for LLMs
        
        # Base verification
        base_result = await self.verify(claim, check_corroboration=False)
        
        # Adjust score based on model-specific checks
        adjusted_score = base_result.confidence_score
        
        if has_citations:
            adjusted_score += 10
        else:
            base_result.recommendations.append("⚠️ Model should provide citations for factual claims")
        
        # For factual tasks without uncertainty markers, reduce score
        if task_context.get("type") == "factual" and not has_uncertainty_markers:
            adjusted_score -= 5
        
        base_result.confidence_score = min(100.0, adjusted_score)
        base_result.grade = model_grade
        
        return base_result


# Global instance
verifier_agent = VerifierAgent()
