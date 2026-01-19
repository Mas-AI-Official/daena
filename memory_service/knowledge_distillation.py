"""
Knowledge Distillation Layer for Multi-Tenant Experience Transfer.

Implements the rule: "Agents transfer experience, NOT raw data. 
The path to that experience must be erased."

This module extracts patterns, insights, and experience vectors from tenant data
without retaining any identifiers or raw customer content.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class PatternType(str, Enum):
    """
    Canonical pattern types used by the Experience-Without-Data pipeline.
    Kept here so `memory_service.experience_pipeline` can type against it.
    """

    DECISION_PATTERN = "decision_pattern"
    SUCCESS_PATTERN = "success_pattern"
    FAILURE_PATTERN = "failure_pattern"
    OPTIMIZATION_PATTERN = "optimization_pattern"
    RISK_PATTERN = "risk_pattern"
    COLLABORATION_PATTERN = "collaboration_pattern"


@dataclass
class ExperienceVector:
    """An experience vector representing distilled knowledge."""
    vector_id: str
    pattern_type: str  # PatternType values serialized as strings
    features: Dict[str, float]  # Feature vector (normalized)
    confidence: float
    source_count: int  # Number of sources this was distilled from
    metadata: Dict[str, Any]  # Pattern metadata (no identifiers)
    created_at: str
    tenant_id: Optional[str] = None  # Only for tracking, not in pattern
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding tenant_id from pattern."""
        result = {
            "vector_id": self.vector_id,
            "pattern_type": self.pattern_type,
            "features": self.features,
            "confidence": self.confidence,
            "source_count": self.source_count,
            "metadata": self._sanitize_metadata(),
            "created_at": self.created_at
        }
        return result
    
    def _sanitize_metadata(self) -> Dict[str, Any]:
        """Remove any identifiers from metadata."""
        sanitized = {}
        for key, value in self.metadata.items():
            # Skip identifier fields
            if key in ["tenant_id", "customer_id", "user_id", "project_id", "email", "name", "company"]:
                continue
            # Skip raw content
            if isinstance(value, str) and len(value) > 100:
                continue
            sanitized[key] = value
        return sanitized


class KnowledgeDistiller:
    """
    Distills experience from raw data without retaining identifiers.
    
    Pipeline: Trust → Quarantine → Distill → Approve → Publish
    """
    
    def __init__(self):
        self.experience_vectors: Dict[str, ExperienceVector] = {}
        self.pattern_types = [pt.value for pt in PatternType]
        self.min_confidence = 0.7
        self.min_sources = 2  # Minimum sources to create pattern
    
    def extract_patterns(
        self,
        data_items: List[Dict[str, Any]],
        tenant_id: Optional[str] = None
    ) -> List[ExperienceVector]:
        """
        Extract patterns from data items.
        
        Args:
            data_items: List of data items to analyze
            tenant_id: Tenant ID (for tracking only, not in pattern)
            
        Returns:
            List of experience vectors
        """
        if len(data_items) < self.min_sources:
            logger.debug(f"Insufficient sources ({len(data_items)}) for pattern extraction")
            return []
        
        patterns: List[ExperienceVector] = []
        
        # Group by pattern type
        for pattern_type in self.pattern_types:
            pattern = self._extract_pattern_type(data_items, pattern_type, tenant_id)
            if pattern and pattern.confidence >= self.min_confidence:
                patterns.append(pattern)
        
        return patterns
    
    def _extract_pattern_type(
        self,
        data_items: List[Dict[str, Any]],
        pattern_type: str,
        tenant_id: Optional[str] = None
    ) -> Optional[ExperienceVector]:
        """Extract a specific pattern type from data items."""
        # Sanitize data items (remove identifiers)
        sanitized_items = [self._sanitize_item(item) for item in data_items]
        
        # Extract features based on pattern type
        features = self._extract_features(sanitized_items, pattern_type)
        
        if not features:
            return None
        
        # Calculate confidence based on consistency
        confidence = self._calculate_confidence(sanitized_items, features)
        
        # Generate vector ID (hash of features, not tenant_id)
        vector_id = self._generate_vector_id(features, pattern_type)
        
        # Extract metadata (no identifiers)
        metadata = self._extract_metadata(sanitized_items, pattern_type)
        
        vector = ExperienceVector(
            vector_id=vector_id,
            pattern_type=pattern_type,
            features=features,
            confidence=confidence,
            source_count=len(data_items),
            metadata=metadata,
            created_at=datetime.utcnow().isoformat() + "Z",
            tenant_id=tenant_id  # Only for tracking, not in pattern
        )
        
        return vector
    
    def _sanitize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Remove all identifiers from data item."""
        sanitized = {}
        for key, value in item.items():
            # Skip identifier fields
            if key in ["tenant_id", "customer_id", "user_id", "project_id", "email", "name", "company", "id"]:
                continue
            # Skip raw content (keep only summaries)
            if isinstance(value, str) and len(value) > 200:
                # Keep only first 100 chars as summary
                sanitized[key] = value[:100] + "..."
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_item(value)
            elif isinstance(value, list):
                sanitized[key] = [self._sanitize_item(v) if isinstance(v, dict) else v for v in value[:10]]  # Limit list size
            else:
                sanitized[key] = value
        return sanitized
    
    def _extract_features(
        self,
        items: List[Dict[str, Any]],
        pattern_type: str
    ) -> Dict[str, float]:
        """Extract feature vector from sanitized items."""
        features = {}
        
        if pattern_type == "decision_pattern":
            # Extract decision-making features
            features["avg_decision_time"] = self._avg_numeric(items, "decision_time", 0.0)
            features["consensus_rate"] = self._avg_numeric(items, "consensus_score", 0.0)
            features["risk_awareness"] = self._avg_numeric(items, "risk_score", 0.0)
            
        elif pattern_type == "success_pattern":
            # Extract success indicators
            features["completion_rate"] = self._avg_numeric(items, "completion_rate", 0.0)
            features["quality_score"] = self._avg_numeric(items, "quality_score", 0.0)
            features["efficiency"] = self._avg_numeric(items, "efficiency", 0.0)
            
        elif pattern_type == "failure_pattern":
            # Extract failure indicators
            features["error_rate"] = self._avg_numeric(items, "error_rate", 0.0)
            features["timeout_rate"] = self._avg_numeric(items, "timeout_rate", 0.0)
            features["retry_count"] = self._avg_numeric(items, "retry_count", 0.0)
            
        elif pattern_type == "optimization_pattern":
            # Extract optimization features
            features["improvement_rate"] = self._avg_numeric(items, "improvement", 0.0)
            features["resource_efficiency"] = self._avg_numeric(items, "resource_efficiency", 0.0)
            
        # Normalize features to 0-1 range
        features = {k: max(0.0, min(1.0, v)) for k, v in features.items()}
        
        return features
    
    def _avg_numeric(self, items: List[Dict[str, Any]], key: str, default: float = 0.0) -> float:
        """Calculate average of numeric values from items."""
        values = []
        for item in items:
            value = item.get(key)
            if isinstance(value, (int, float)):
                values.append(value)
            elif isinstance(value, dict) and key in value:
                if isinstance(value[key], (int, float)):
                    values.append(value[key])
        
        if not values:
            return default
        return sum(values) / len(values)
    
    def _calculate_confidence(
        self,
        items: List[Dict[str, Any]],
        features: Dict[str, float]
    ) -> float:
        """Calculate confidence based on feature consistency."""
        if len(items) < 2:
            return 0.0
        
        # Calculate variance in features across items
        variances = []
        for feature_name, feature_value in features.items():
            item_values = []
            for item in items:
                value = item.get(feature_name)
                if isinstance(value, (int, float)):
                    item_values.append(value)
            
            if len(item_values) > 1:
                mean = sum(item_values) / len(item_values)
                variance = sum((v - mean) ** 2 for v in item_values) / len(item_values)
                # Normalize variance (lower = more consistent = higher confidence)
                normalized_variance = min(1.0, variance)
                variances.append(1.0 - normalized_variance)
        
        if not variances:
            return 0.5  # Default confidence
        
        # Confidence is average of (1 - variance) for each feature
        confidence = sum(variances) / len(variances)
        return confidence
    
    def _generate_vector_id(self, features: Dict[str, float], pattern_type: str) -> str:
        """Generate vector ID from features (no tenant_id)."""
        # Create hash from features and pattern type
        feature_str = json.dumps(features, sort_keys=True)
        hash_input = f"{pattern_type}:{feature_str}"
        vector_id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return f"exp_{pattern_type}_{vector_id}"
    
    def _extract_metadata(
        self,
        items: List[Dict[str, Any]],
        pattern_type: str
    ) -> Dict[str, Any]:
        """Extract metadata without identifiers."""
        metadata = {
            "pattern_type": pattern_type,
            "source_count": len(items),
            "extracted_at": datetime.utcnow().isoformat() + "Z"
        }
        
        # Extract common metadata (no identifiers)
        if items:
            first_item = items[0]
            # Only include non-identifying metadata
            for key in ["category", "type", "status", "priority"]:
                if key in first_item:
                    metadata[key] = first_item[key]
        
        return metadata
    
    def approve_pattern(self, vector_id: str) -> bool:
        """Approve a pattern for publishing (governance filter)."""
        vector = self.experience_vectors.get(vector_id)
        if not vector:
            return False
        
        # Approval criteria
        if vector.confidence < self.min_confidence:
            return False
        
        if vector.source_count < self.min_sources:
            return False
        
        # Check if pattern contains any identifiers (should not)
        if any(key in vector.metadata for key in ["tenant_id", "customer_id", "user_id"]):
            logger.warning(f"Pattern {vector_id} contains identifiers, rejecting")
            return False
        
        return True
    
    def publish_pattern(self, vector_id: str) -> Optional[ExperienceVector]:
        """Publish an approved pattern (make available for cross-tenant use)."""
        if not self.approve_pattern(vector_id):
            return None
        
        vector = self.experience_vectors.get(vector_id)
        if not vector:
            return None
        
        # Remove tenant_id from published pattern
        published = vector.to_dict()
        
        logger.info(f"Published pattern {vector_id} (confidence: {vector.confidence:.2f})")
        return vector
    
    def store_vector(self, vector: ExperienceVector) -> str:
        """Store an experience vector."""
        self.experience_vectors[vector.vector_id] = vector
        return vector.vector_id
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: Optional[float] = None
    ) -> List[ExperienceVector]:
        """Get published patterns."""
        patterns = list(self.experience_vectors.values())
        
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        
        if min_confidence:
            patterns = [p for p in patterns if p.confidence >= min_confidence]
        
        # Only return approved patterns
        approved = [p for p in patterns if self.approve_pattern(p.vector_id)]
        
        return approved
    
    def find_similar_patterns(
        self,
        query_features: Dict[str, float],
        pattern_type: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.7
    ) -> List[Tuple[ExperienceVector, float]]:
        """
        Find similar patterns based on feature vector similarity.
        
        Uses cosine similarity to match patterns.
        
        Args:
            query_features: Feature vector to search for
            pattern_type: Filter by pattern type (optional)
            top_k: Number of top similar patterns to return
            similarity_threshold: Minimum similarity score (0.0-1.0)
            
        Returns:
            List of tuples (pattern, similarity_score) sorted by similarity
        """
        patterns = self.get_patterns(pattern_type=pattern_type)
        if not patterns or not query_features:
            return []
        
        similarities = []
        query_norm = sum(v ** 2 for v in query_features.values()) ** 0.5
        
        if query_norm == 0:
            return []
        
        for pattern in patterns:
            # Calculate cosine similarity
            dot_product = sum(
                query_features.get(k, 0.0) * pattern.features.get(k, 0.0)
                for k in set(query_features.keys()) | set(pattern.features.keys())
            )
            
            pattern_norm = sum(v ** 2 for v in pattern.features.values()) ** 0.5
            if pattern_norm == 0:
                continue
            
            similarity = dot_product / (query_norm * pattern_norm)
            
            if similarity >= similarity_threshold:
                similarities.append((pattern, similarity))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def auto_publish_high_confidence_patterns(self, min_confidence: float = 0.9) -> int:
        """
        Automatically publish patterns that meet high-confidence criteria.
        
        Args:
            min_confidence: Minimum confidence for auto-publishing
            
        Returns:
            Number of patterns auto-published
        """
        published_count = 0
        
        for vector_id, vector in self.experience_vectors.items():
            # Skip if already published
            if not self.approve_pattern(vector_id):
                continue
            
            # Auto-publish if confidence is very high
            if vector.confidence >= min_confidence and vector.source_count >= self.min_sources:
                published = self.publish_pattern(vector_id)
                if published:
                    published_count += 1
                    logger.info(f"Auto-published high-confidence pattern {vector_id} (confidence: {vector.confidence:.2f})")
        
        return published_count
    
    def recommend_patterns(
        self,
        context: Dict[str, Any],
        pattern_type: Optional[str] = None,
        top_k: int = 3
    ) -> List[Tuple[ExperienceVector, float]]:
        """
        Recommend patterns based on context.
        
        Args:
            context: Context information (features, metadata, etc.)
            pattern_type: Filter by pattern type (optional)
            top_k: Number of recommendations
            
        Returns:
            List of recommended patterns with relevance scores
        """
        # Extract features from context
        query_features = {}
        for key in ["decision_time", "consensus_score", "risk_score", "completion_rate", 
                   "quality_score", "efficiency", "error_rate", "improvement"]:
            if key in context:
                value = context[key]
                if isinstance(value, (int, float)):
                    query_features[key] = min(1.0, max(0.0, float(value)))
        
        if not query_features:
            # Fallback: use metadata to infer features
            query_features = {"decision_time": 0.5, "consensus_score": 0.5, "risk_score": 0.5}
        
        # Find similar patterns
        similar = self.find_similar_patterns(
            query_features=query_features,
            pattern_type=pattern_type,
            top_k=top_k,
            similarity_threshold=0.5
        )
        
        return similar


# Global distiller instance
knowledge_distiller = KnowledgeDistiller()




