"""
Experience-Without-Data Pipeline.

Implements the full pipeline for sharing experience patterns across tenants
without data leakage:
1. Distill patterns from tenant A tasks
2. Store abstracted patterns in shared pool
3. Keep cryptographic pointers to tenant A evidence in A's vault
4. Gate adoption for tenant B (confidence threshold, contamination scan, red-team probe)
5. Kill-switch to revoke patterns globally
"""

from __future__ import annotations

import hashlib
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from memory_service.knowledge_distillation import (
    KnowledgeDistiller,
    ExperienceVector,
    PatternType
)

logger = logging.getLogger(__name__)


class PatternStatus(str, Enum):
    """Status of a pattern in the shared pool."""
    DRAFT = "draft"  # Being distilled
    PENDING = "pending"  # Awaiting approval
    APPROVED = "approved"  # Available for adoption
    QUARANTINED = "quarantined"  # Suspended due to issues
    REVOKED = "revoked"  # Permanently removed


@dataclass
class CryptographicPointer:
    """Cryptographic pointer to tenant evidence in tenant's vault."""
    tenant_id: str
    evidence_hash: str  # SHA-256 hash of evidence
    evidence_location: str  # Path/URI in tenant's vault
    merkle_root: Optional[str] = None  # Merkle root for batch verification
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def verify(self, evidence_content: bytes) -> bool:
        """Verify that evidence content matches hash."""
        content_hash = hashlib.sha256(evidence_content).hexdigest()
        return content_hash == self.evidence_hash


@dataclass
class SharedPattern:
    """Pattern in the shared pool (no tenant data)."""
    pattern_id: str
    pattern_type: PatternType
    experience_vector: ExperienceVector
    confidence_score: float  # 0.0 to 1.0
    source_pointers: List[CryptographicPointer]  # Pointers to source evidence
    status: PatternStatus
    created_at: str
    approved_at: Optional[str] = None
    adoption_count: int = 0
    success_rate: float = 0.0  # Success rate across adoptions
    contamination_score: float = 0.0  # Risk of data leakage (0.0 = safe)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExperiencePipeline:
    """
    Main pipeline for experience-without-data sharing.
    
    Features:
    - Pattern distillation from tenant tasks
    - Cryptographic pointers to evidence
    - Adoption gating (confidence, contamination, red-team)
    - Kill-switch for pattern revocation
    """
    
    def __init__(self):
        self.distiller = KnowledgeDistiller()
        self.shared_pool: Dict[str, SharedPattern] = {}  # pattern_id -> SharedPattern
        self.tenant_vaults: Dict[str, Dict[str, bytes]] = {}  # tenant_id -> {evidence_hash: content}
        self.adoption_history: List[Dict[str, Any]] = []
        
        # Configuration
        self.min_confidence_threshold = 0.7  # Minimum confidence for pattern approval
        self.max_contamination_score = 0.1  # Maximum contamination allowed
        self.require_human_approval = False  # Require human approval for high-risk patterns
        
    def distill_pattern_from_tenant(
        self,
        tenant_id: str,
        task_data: Dict[str, Any],
        pattern_type: PatternType = PatternType.DECISION_PATTERN
    ) -> Tuple[Optional[SharedPattern], List[CryptographicPointer]]:
        """
        Distill a pattern from tenant A's task data.
        
        Args:
            tenant_id: Source tenant ID
            task_data: Task data (will be sanitized)
            pattern_type: Type of pattern to extract
        
        Returns:
            (SharedPattern, List[CryptographicPointer])
        """
        try:
            # 1. Distill pattern (removes all tenant identifiers)
            experience_vector = self.distiller.distill_experience(
                task_data=task_data,
                pattern_type=pattern_type
            )
            
            if not experience_vector:
                logger.warning(f"Failed to distill pattern from tenant {tenant_id}")
                return None, []
            
            # 2. Create cryptographic pointers to original evidence
            evidence_content = str(task_data).encode('utf-8')
            evidence_hash = hashlib.sha256(evidence_content).hexdigest()
            
            # Store evidence in tenant's vault
            if tenant_id not in self.tenant_vaults:
                self.tenant_vaults[tenant_id] = {}
            self.tenant_vaults[tenant_id][evidence_hash] = evidence_content
            
            # Create pointer
            pointer = CryptographicPointer(
                tenant_id=tenant_id,
                evidence_hash=evidence_hash,
                evidence_location=f"vault://{tenant_id}/{evidence_hash}",
                timestamp=datetime.utcnow().isoformat() + "Z"
            )
            
            # 3. Calculate confidence score
            confidence_score = self._calculate_confidence(experience_vector, task_data)
            
            # 4. Create shared pattern (no tenant data)
            pattern_id = f"pattern_{hashlib.sha256(str(experience_vector).encode()).hexdigest()[:16]}"
            
            shared_pattern = SharedPattern(
                pattern_id=pattern_id,
                pattern_type=pattern_type,
                experience_vector=experience_vector,
                confidence_score=confidence_score,
                source_pointers=[pointer],
                status=PatternStatus.DRAFT,
                created_at=datetime.utcnow().isoformat() + "Z",
                metadata={
                    "source_tenant": tenant_id,  # Only tenant ID, no other data
                    "pattern_type": pattern_type.value
                }
            )
            
            logger.info(f"Distilled pattern {pattern_id} from tenant {tenant_id} (confidence: {confidence_score:.2f})")
            return shared_pattern, [pointer]
            
        except Exception as e:
            logger.error(f"Error distilling pattern from tenant {tenant_id}: {e}")
            return None, []
    
    def _calculate_confidence(
        self,
        experience_vector: ExperienceVector,
        source_data: Dict[str, Any]
    ) -> float:
        """
        Calculate confidence score for a pattern.
        
        Factors:
        - Pattern completeness
        - Source data quality
        - Pattern clarity
        """
        # Simple confidence calculation
        # In production, use ML model or heuristics
        
        # Check if pattern has required fields
        completeness = 0.0
        if experience_vector.features:
            completeness += 0.3
        if experience_vector.outcome:
            completeness += 0.3
        if experience_vector.metadata:
            completeness += 0.2
        if experience_vector.confidence:
            completeness += 0.2
        
        # Source data quality (simplified)
        data_quality = 0.5  # Default
        if source_data.get("success", False):
            data_quality = 0.8
        if len(str(source_data)) > 100:
            data_quality = min(data_quality + 0.1, 1.0)
        
        confidence = (completeness + data_quality) / 2.0
        return min(max(confidence, 0.0), 1.0)
    
    def check_contamination(self, pattern: SharedPattern) -> float:
        """
        Check if pattern contains any tenant-specific data (contamination).
        
        Returns:
            Contamination score (0.0 = safe, 1.0 = high risk)
        """
        contamination_score = 0.0
        
        # Check experience vector for identifiers
        vector_str = str(pattern.experience_vector)
        
        # Common identifiers to check
        identifiers = [
            "@",  # Email addresses
            "http://", "https://",  # URLs (might contain tenant domains)
            "tenant_", "user_", "customer_",  # Common prefixes
        ]
        
        for identifier in identifiers:
            if identifier.lower() in vector_str.lower():
                contamination_score += 0.2
        
        # Check metadata
        if pattern.metadata:
            metadata_str = str(pattern.metadata)
            for identifier in identifiers:
                if identifier.lower() in metadata_str.lower():
                    contamination_score += 0.1
        
        # Check if pattern is too specific (might leak data)
        if len(pattern.experience_vector.features) > 50:
            contamination_score += 0.1  # Very detailed patterns might leak structure
        
        return min(contamination_score, 1.0)
    
    def approve_pattern(
        self,
        pattern: SharedPattern,
        human_approver: Optional[str] = None
    ) -> bool:
        """
        Approve a pattern for sharing (after contamination check).
        
        Args:
            pattern: Pattern to approve
            human_approver: Human approver ID (if required)
        
        Returns:
            True if approved, False otherwise
        """
        # 1. Check contamination
        contamination_score = self.check_contamination(pattern)
        pattern.contamination_score = contamination_score
        
        if contamination_score > self.max_contamination_score:
            logger.warning(f"Pattern {pattern.pattern_id} rejected: contamination score {contamination_score:.2f} > {self.max_contamination_score}")
            pattern.status = PatternStatus.QUARANTINED
            return False
        
        # 2. Check confidence threshold
        if pattern.confidence_score < self.min_confidence_threshold:
            logger.warning(f"Pattern {pattern.pattern_id} rejected: confidence {pattern.confidence_score:.2f} < {self.min_confidence_threshold}")
            pattern.status = PatternStatus.QUARANTINED
            return False
        
        # 3. Check if human approval required
        if self.require_human_approval and contamination_score > 0.05:
            if not human_approver:
                logger.warning(f"Pattern {pattern.pattern_id} requires human approval")
                pattern.status = PatternStatus.PENDING
                return False
        
        # 4. Approve pattern
        pattern.status = PatternStatus.APPROVED
        pattern.approved_at = datetime.utcnow().isoformat() + "Z"
        self.shared_pool[pattern.pattern_id] = pattern
        
        logger.info(f"Pattern {pattern.pattern_id} approved for sharing")
        return True
    
    def gate_adoption(
        self,
        pattern_id: str,
        target_tenant_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Gate adoption of a pattern for tenant B.
        
        Checks:
        - Confidence threshold
        - Contamination scan
        - Red-team probe (optional)
        - Human-in-the-loop flag (for high-risk domains)
        
        Returns:
            (allowed, reason, gate_result)
        """
        if pattern_id not in self.shared_pool:
            return False, "Pattern not found", {}
        
        pattern = self.shared_pool[pattern_id]
        
        # 1. Check pattern status
        if pattern.status != PatternStatus.APPROVED:
            return False, f"Pattern status is {pattern.status.value}", {}
        
        # 2. Check confidence threshold
        if pattern.confidence_score < self.min_confidence_threshold:
            return False, f"Confidence {pattern.confidence_score:.2f} below threshold {self.min_confidence_threshold}", {}
        
        # 3. Contamination scan
        contamination_score = self.check_contamination(pattern)
        if contamination_score > self.max_contamination_score:
            return False, f"Contamination score {contamination_score:.2f} exceeds limit {self.max_contamination_score}", {}
        
        # 4. Red-team probe (simplified - in production, run actual probe)
        red_team_result = self._red_team_probe(pattern, target_tenant_id)
        if not red_team_result["safe"]:
            return False, f"Red-team probe failed: {red_team_result['reason']}", red_team_result
        
        # 5. Human-in-the-loop check (for high-risk domains)
        if context and context.get("domain") in ["legal", "finance", "healthcare"]:
            if not context.get("human_approved", False):
                return False, "Human approval required for high-risk domain", {}
        
        # 6. Allow adoption
        pattern.adoption_count += 1
        
        # Log adoption
        self.adoption_history.append({
            "pattern_id": pattern_id,
            "target_tenant_id": target_tenant_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "confidence": pattern.confidence_score,
            "contamination": contamination_score
        })
        
        logger.info(f"Pattern {pattern_id} approved for adoption by tenant {target_tenant_id}")
        
        return True, "Adoption approved", {
            "pattern_id": pattern_id,
            "confidence": pattern.confidence_score,
            "contamination": contamination_score,
            "red_team": red_team_result
        }
    
    def _red_team_probe(
        self,
        pattern: SharedPattern,
        target_tenant_id: str
    ) -> Dict[str, Any]:
        """
        Red-team probe to test pattern safety.
        
        In production, this would:
        - Test pattern against known attack vectors
        - Check for data leakage risks
        - Verify tenant isolation
        
        Returns:
            {"safe": bool, "reason": str, "risks": List[str]}
        """
        risks = []
        
        # Check 1: Pattern doesn't contain target tenant's data
        if target_tenant_id in str(pattern.experience_vector):
            risks.append("Pattern may contain target tenant identifier")
        
        # Check 2: Source pointers don't point to target tenant
        for pointer in pattern.source_pointers:
            if pointer.tenant_id == target_tenant_id:
                risks.append("Pattern source points to target tenant (circular reference)")
        
        # Check 3: Pattern is not too specific
        if len(pattern.experience_vector.features) > 100:
            risks.append("Pattern is very specific (may leak structure)")
        
        safe = len(risks) == 0
        
        return {
            "safe": safe,
            "reason": "No risks detected" if safe else f"{len(risks)} risks found",
            "risks": risks
        }
    
    def revoke_pattern(
        self,
        pattern_id: str,
        reason: str,
        revoke_dependents: bool = True
    ) -> bool:
        """
        Kill-switch: Revoke a pattern globally and roll back dependents.
        
        Args:
            pattern_id: Pattern to revoke
            reason: Reason for revocation
            revoke_dependents: Also revoke patterns that depend on this one
        
        Returns:
            True if revoked, False if not found
        """
        if pattern_id not in self.shared_pool:
            logger.warning(f"Pattern {pattern_id} not found for revocation")
            return False
        
        pattern = self.shared_pool[pattern_id]
        pattern.status = PatternStatus.REVOKED
        
        # Revoke dependents (simplified - in production, track dependencies)
        if revoke_dependents:
            # Find patterns that reference this pattern
            for other_id, other_pattern in self.shared_pool.items():
                if other_id == pattern_id:
                    continue
                
                # Check if other pattern depends on this one
                if pattern_id in str(other_pattern.metadata.get("depends_on", [])):
                    logger.info(f"Revoking dependent pattern {other_id}")
                    other_pattern.status = PatternStatus.REVOKED
        
        logger.warning(f"Pattern {pattern_id} revoked globally: {reason}")
        return True
    
    def get_pattern_recommendations(
        self,
        tenant_id: str,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[SharedPattern]:
        """
        Get pattern recommendations for a tenant.
        
        Args:
            tenant_id: Target tenant
            context: Context for recommendations
            limit: Maximum number of recommendations
        
        Returns:
            List of recommended patterns
        """
        recommendations = []
        
        for pattern_id, pattern in self.shared_pool.items():
            if pattern.status != PatternStatus.APPROVED:
                continue
            
            # Check if pattern is suitable for this tenant
            allowed, reason, _ = self.gate_adoption(pattern_id, tenant_id, context)
            if allowed:
                recommendations.append(pattern)
        
        # Sort by confidence and success rate
        recommendations.sort(
            key=lambda p: (p.confidence_score + p.success_rate) / 2.0,
            reverse=True
        )
        
        return recommendations[:limit]
    
    def get_pattern_by_id(self, pattern_id: str) -> Optional[SharedPattern]:
        """Get a pattern by ID."""
        return self.shared_pool.get(pattern_id)
    
    def list_approved_patterns(self, limit: int = 100) -> List[SharedPattern]:
        """List all approved patterns."""
        return [
            pattern for pattern in self.shared_pool.values()
            if pattern.status == PatternStatus.APPROVED
        ][:limit]


# Global instance
experience_pipeline = ExperiencePipeline()

