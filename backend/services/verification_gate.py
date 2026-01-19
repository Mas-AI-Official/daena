"""
Verification Gate - Enforced Fact Checking for Daena

This is a MANDATORY gate in the autonomous execution loop.
No factual claim passes to execution without verification.

Scout -> Verify -> Synthesize is required for:
- Market data
- Statistics
- External claims
- Scraped content
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class SourceGrade(str, Enum):
    """Source quality grades"""
    A = "A"  # Primary source, verified
    B = "B"  # Trusted secondary source
    C = "C"  # Unverified but cited
    F = "F"  # Rejected - cannot use


class UncertaintyLevel(str, Enum):
    """Uncertainty classification"""
    LOW = "low"           # High confidence
    MEDIUM = "medium"     # Some doubt
    HIGH = "high"         # Significant uncertainty
    CRITICAL = "critical" # Cannot proceed without clarification


@dataclass
class VerifiedFact:
    """A verified fact that can be used in execution"""
    fact_id: str
    claim: str
    source: str
    source_grade: SourceGrade
    verified_at: datetime
    evidence: Optional[str] = None
    uncertainty: UncertaintyLevel = UncertaintyLevel.LOW
    verifier_notes: Optional[str] = None


@dataclass
class RejectedClaim:
    """A claim that failed verification"""
    claim: str
    source: str
    reason: str
    rejected_at: datetime
    alternative: Optional[str] = None


@dataclass
class VerificationResult:
    """Result of verification gate"""
    approved_facts: List[VerifiedFact]
    rejected_claims: List[RejectedClaim]
    uncertainty_flags: List[Dict[str, Any]]
    overall_grade: SourceGrade
    passed: bool
    summary: str


class VerificationGate:
    """
    Enforced verification gate for factual claims.
    
    This gate MUST be passed before any execution step that
    uses external data or makes factual claims.
    """
    
    def __init__(self):
        self.verification_history: List[VerificationResult] = []
        
        # Trusted sources by category
        self.trusted_sources = {
            "internal": ["backend_state", "config", "database", "system_status"],
            "official": ["gov", ".edu", "ieee.org", "arxiv.org"],
            "business": ["bloomberg.com", "reuters.com", "sec.gov"],
            "tech": ["github.com", "stackoverflow.com", "docs.python.org"]
        }
        
        # Patterns that require extra scrutiny
        self.scrutiny_patterns = [
            "million", "billion", "%", "growth", "revenue",
            "first", "best", "only", "guaranteed", "proven"
        ]
    
    async def verify_project_data(self, acquired_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify all data acquired by scouts before execution.
        
        Args:
            acquired_data: Data gathered by scout agents
            
        Returns:
            Verification result with approved facts and rejected claims
        """
        logger.info("🔍 VERIFICATION GATE: Processing acquired data")
        
        approved_facts = []
        rejected_claims = []
        uncertainty_flags = []
        
        for source_key, data in acquired_data.items():
            if not isinstance(data, dict):
                continue
            
            items = data.get("items", [])
            sources = data.get("sources", [])
            
            for item in items:
                result = await self._verify_item(item, sources)
                
                if result.get("approved"):
                    approved_facts.append(VerifiedFact(
                        fact_id=f"fact-{len(approved_facts):04d}",
                        claim=item.get("content", str(item)),
                        source=result.get("source", source_key),
                        source_grade=SourceGrade(result.get("grade", "C")),
                        verified_at=datetime.utcnow(),
                        evidence=result.get("evidence"),
                        uncertainty=UncertaintyLevel(result.get("uncertainty", "low"))
                    ))
                    
                    if result.get("uncertainty") in ["medium", "high"]:
                        uncertainty_flags.append({
                            "claim": item.get("content", str(item))[:100],
                            "uncertainty": result.get("uncertainty"),
                            "reason": result.get("reason")
                        })
                else:
                    rejected_claims.append(RejectedClaim(
                        claim=item.get("content", str(item)),
                        source=source_key,
                        reason=result.get("reason", "Failed verification"),
                        rejected_at=datetime.utcnow(),
                        alternative=result.get("alternative")
                    ))
        
        # Calculate overall grade
        if not approved_facts:
            overall_grade = SourceGrade.F
        elif all(f.source_grade == SourceGrade.A for f in approved_facts):
            overall_grade = SourceGrade.A
        elif any(f.source_grade == SourceGrade.F for f in approved_facts):
            overall_grade = SourceGrade.C
        else:
            overall_grade = SourceGrade.B
        
        passed = len(rejected_claims) == 0 or len(approved_facts) > len(rejected_claims)
        
        result = VerificationResult(
            approved_facts=approved_facts,
            rejected_claims=rejected_claims,
            uncertainty_flags=uncertainty_flags,
            overall_grade=overall_grade,
            passed=passed,
            summary=self._generate_summary(approved_facts, rejected_claims, uncertainty_flags)
        )
        
        self.verification_history.append(result)
        
        logger.info(f"✅ Verification complete: {len(approved_facts)} approved, {len(rejected_claims)} rejected, grade: {overall_grade.value}")
        
        return {
            "approved_facts": [
                {
                    "fact_id": f.fact_id,
                    "claim": f.claim,
                    "source": f.source,
                    "grade": f.source_grade.value,
                    "uncertainty": f.uncertainty.value
                }
                for f in approved_facts
            ],
            "rejected_claims": [
                {
                    "claim": r.claim[:100],
                    "reason": r.reason
                }
                for r in rejected_claims
            ],
            "uncertainty_flags": uncertainty_flags,
            "overall_grade": overall_grade.value,
            "passed": passed,
            "summary": result.summary
        }
    
    async def _verify_item(self, item: Dict[str, Any], sources: List[str]) -> Dict[str, Any]:
        """Verify a single data item"""
        claim = item.get("content", str(item))
        item_source = item.get("source", sources[0] if sources else "unknown")
        
        # Check if from internal trusted source
        if self._is_internal_source(item_source):
            return {
                "approved": True,
                "source": item_source,
                "grade": "A",
                "uncertainty": "low",
                "evidence": "Internal system data"
            }
        
        # Check for scrutiny patterns
        requires_scrutiny = any(pattern in claim.lower() for pattern in self.scrutiny_patterns)
        
        # Check source trust level
        source_trust = self._check_source_trust(item_source)
        
        # Verify based on patterns and trust
        if source_trust == "untrusted":
            return {
                "approved": False,
                "reason": f"Source not trusted: {item_source}",
                "alternative": "Use only verified internal data or trusted sources"
            }
        
        if requires_scrutiny and source_trust != "trusted":
            return {
                "approved": True,
                "source": item_source,
                "grade": "C",
                "uncertainty": "high",
                "reason": "Contains claims requiring verification",
                "evidence": None
            }
        
        # Default approval with medium confidence
        return {
            "approved": True,
            "source": item_source,
            "grade": "B" if source_trust == "trusted" else "C",
            "uncertainty": "low" if source_trust == "trusted" else "medium"
        }
    
    def _is_internal_source(self, source: str) -> bool:
        """Check if source is internal"""
        internal_keywords = self.trusted_sources.get("internal", [])
        return any(keyword in source.lower() for keyword in internal_keywords)
    
    def _check_source_trust(self, source: str) -> str:
        """Check trust level of source"""
        source_lower = source.lower()
        
        # Check all trusted categories
        for category, sources in self.trusted_sources.items():
            for trusted in sources:
                if trusted in source_lower:
                    return "trusted"
        
        # Check for known unreliable patterns
        unreliable_patterns = ["random", "example", "test", "fake", "mock"]
        if any(pattern in source_lower for pattern in unreliable_patterns):
            return "untrusted"
        
        return "unverified"
    
    def _generate_summary(
        self,
        approved: List[VerifiedFact],
        rejected: List[RejectedClaim],
        uncertainties: List[Dict]
    ) -> str:
        """Generate verification summary"""
        parts = []
        parts.append(f"Verified {len(approved)} facts")
        if rejected:
            parts.append(f"rejected {len(rejected)} claims")
        if uncertainties:
            parts.append(f"{len(uncertainties)} items flagged for uncertainty")
        return ", ".join(parts)
    
    # =========================================================================
    # CLAIM VALIDATION (for use during execution)
    # =========================================================================
    
    def validate_claim(self, claim: str, source: str = "execution") -> Dict[str, Any]:
        """
        Validate a single claim before use in a deliverable.
        
        This should be called before including any factual statement
        in outputs like landing pages, emails, etc.
        """
        requires_scrutiny = any(pattern in claim.lower() for pattern in self.scrutiny_patterns)
        
        if requires_scrutiny:
            return {
                "valid": False,
                "warning": "Claim contains patterns requiring verification",
                "patterns_found": [p for p in self.scrutiny_patterns if p in claim.lower()],
                "recommendation": "Provide source or rephrase as opinion/goal"
            }
        
        return {"valid": True}
    
    def get_compliance_notes(self) -> List[str]:
        """Get list of claims to avoid without proof"""
        return [
            "Avoid specific percentages or statistics without cited sources",
            "Avoid 'first', 'best', 'only' claims without evidence",
            "Avoid revenue/growth projections without data",
            "Avoid 'guaranteed' or 'proven' without test results",
            "Avoid celebrity or expert endorsements without permission",
            "Avoid competitor comparisons without documentation"
        ]


# Global singleton
verification_gate = VerificationGate()
