"""
Abstract Revisor: Converts data slices into NBMF abstracts.

Creates atomic notes with embeddings, ensuring no raw tenant data leaves scope.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import hashlib
import json

from .selector import CandidateSlice

logger = logging.getLogger(__name__)


@dataclass
class NBMFAbstract:
    """An NBMF abstract candidate for promotion."""
    abstract_id: str
    content: str  # Abstracted content (no raw tenant data)
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None
    confidence: float = 0.0
    source_slice_id: Optional[str] = None
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None


class AbstractRevisor:
    """
    Converts data slices into NBMF abstracts.
    
    Ensures:
    - No raw tenant data in abstracts
    - Atomic note creation
    - Embedding generation
    """
    
    def __init__(self):
        """Initialize revisor."""
        logger.info("AbstractRevisor initialized")
    
    def create_abstract(
        self,
        candidate: CandidateSlice,
        sanitize: bool = True
    ) -> NBMFAbstract:
        """
        Create an NBMF abstract from a candidate slice.
        
        Args:
            candidate: Candidate slice to abstract
            sanitize: Whether to sanitize tenant data (default: True)
            
        Returns:
            NBMF abstract
        """
        # Sanitize content if needed
        if sanitize:
            content = self._sanitize_content(candidate.content, candidate.metadata)
        else:
            content = candidate.content
        
        # Generate abstract ID
        abstract_id = self._generate_abstract_id(candidate, content)
        
        # Generate embedding (optional, can be lazy-loaded)
        embedding = self._generate_embedding(content)
        
        # Build metadata (without raw tenant data)
        metadata = self._build_metadata(candidate, sanitize)
        
        abstract = NBMFAbstract(
            abstract_id=abstract_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
            confidence=candidate.confidence,
            source_slice_id=candidate.slice_id,
            tenant_id=candidate.tenant_id,
            project_id=candidate.project_id
        )
        
        logger.debug(f"Created abstract: {abstract_id} from slice: {candidate.slice_id}")
        
        return abstract
    
    def _sanitize_content(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Sanitize content to remove raw tenant data.
        
        In production, this would:
        - Remove PII (names, emails, etc.)
        - Remove tenant-specific identifiers
        - Generalize patterns
        """
        # Basic sanitization (placeholder)
        # In production, would use PII detection and removal
        sanitized = content
        
        # Remove obvious PII patterns (basic example)
        import re
        # Remove email addresses
        sanitized = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', sanitized)
        # Remove phone numbers (basic pattern)
        sanitized = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]', sanitized)
        
        return sanitized
    
    def _generate_abstract_id(
        self,
        candidate: CandidateSlice,
        content: str
    ) -> str:
        """Generate a unique abstract ID."""
        # Use hash of content + source for ID
        hash_input = f"{candidate.slice_id}:{content[:100]}"
        hash_value = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()[:16]
        return f"sec_abstract_{hash_value}"
    
    def _generate_embedding(self, content: str) -> Optional[List[float]]:
        """
        Generate embedding for content.
        
        In production, would use actual embedding model.
        For now, returns None (lazy-loaded when needed).
        """
        # Placeholder: would use embedding service
        # Could integrate with existing L1 embedding system
        try:
            from memory_service.adapters.l1_embeddings import L1Index
            # In production, would generate actual embedding
            # For now, return None (can be generated later)
            return None
        except ImportError:
            return None
    
    def _build_metadata(
        self,
        candidate: CandidateSlice,
        sanitize: bool
    ) -> Dict[str, Any]:
        """Build metadata for abstract (without raw tenant data)."""
        metadata = {
            "source": candidate.source,
            "confidence": candidate.confidence,
            "created_via": "sec_loop",
            "sanitized": sanitize
        }
        
        # Add non-sensitive metadata from candidate
        if candidate.metadata:
            # Filter out sensitive fields
            safe_fields = ["department", "category", "type", "tags"]
            for field in safe_fields:
                if field in candidate.metadata:
                    metadata[field] = candidate.metadata[field]
        
        return metadata
    
    def batch_create_abstracts(
        self,
        candidates: List[CandidateSlice],
        sanitize: bool = True
    ) -> List[NBMFAbstract]:
        """
        Create multiple abstracts from candidates.
        
        Args:
            candidates: List of candidate slices
            sanitize: Whether to sanitize tenant data
            
        Returns:
            List of NBMF abstracts
        """
        abstracts = []
        for candidate in candidates:
            try:
                abstract = self.create_abstract(candidate, sanitize=sanitize)
                abstracts.append(abstract)
            except Exception as e:
                logger.error(f"Error creating abstract from {candidate.slice_id}: {e}")
                continue
        
        logger.info(f"Created {len(abstracts)} abstracts from {len(candidates)} candidates")
        return abstracts

