"""
Memory abstractor: Generates lossless pointers (NBMF key + ledger txid + Merkle proof) 
and human-readable abstracts for UI/search.
"""

import hashlib
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MemoryAbstractor:
    """
    Generates abstracts and lossless pointers for memory items.
    
    Policy:
    - For sensitive docs → NBMF only
    - For non-sensitive docs → allow OCR fallback only when layout fidelity is required
    - Always store the NBMF pointer
    """
    
    def __init__(self):
        self.sensitive_classes = {
            "legal", "finance", "pii", "health", "confidential", "proprietary"
        }
    
    def generate_abstract(
        self,
        content: Any,
        item_id: str,
        cls: str,
        nbmf_key: str,
        ledger_txid: str,
        merkle_proof: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a human-readable abstract and lossless pointer.
        
        Args:
            content: Original content (text, dict, etc.)
            item_id: Memory item identifier
            cls: Content class
            nbmf_key: NBMF storage key
            ledger_txid: NBMF ledger transaction ID
            merkle_proof: Optional Merkle proof hash
        
        Returns:
            Dict with abstract and pointer
        """
        # Extract text for abstract
        text_content = self._extract_text(content)
        
        # Generate abstract (first 500 chars or summary)
        abstract = self._generate_text_abstract(text_content, max_length=500)
        
        # Build lossless pointer
        pointer = {
            "nbmf_key": nbmf_key,
            "ledger_txid": ledger_txid,
            "merkle_proof": merkle_proof,
            "item_id": item_id,
            "class": cls,
            "pointer_hash": self._compute_pointer_hash(nbmf_key, ledger_txid, item_id)
        }
        
        return {
            "abstract": abstract,
            "pointer": pointer,
            "metadata": {
                "item_id": item_id,
                "class": cls,
                "is_sensitive": cls.lower() in self.sensitive_classes,
                "generated_at": datetime.utcnow().isoformat(),
                "content_length": len(text_content) if isinstance(text_content, str) else 0
            }
        }
    
    def _extract_text(self, content: Any) -> str:
        """Extract text from content for abstract generation."""
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            # Try common text fields
            for field in ["text", "content", "message", "body", "description"]:
                if field in content and isinstance(content[field], str):
                    return content[field]
            # Fallback: JSON string representation
            return json.dumps(content, ensure_ascii=False)
        elif isinstance(content, list):
            # Join list items if they're strings
            if all(isinstance(item, str) for item in content):
                return " ".join(content)
            return json.dumps(content, ensure_ascii=False)
        else:
            return str(content)
    
    def _generate_text_abstract(self, text: str, max_length: int = 500) -> str:
        """Generate a human-readable abstract from text."""
        if not text:
            return ""
        
        # Simple truncation with sentence boundary detection
        if len(text) <= max_length:
            return text
        
        # Try to cut at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        last_exclamation = truncated.rfind('!')
        last_question = truncated.rfind('?')
        last_newline = truncated.rfind('\n')
        
        cut_point = max(last_period, last_exclamation, last_question, last_newline)
        if cut_point > max_length * 0.7:  # Only use if we're not cutting too early
            return truncated[:cut_point + 1] + "..."
        
        return truncated + "..."
    
    def _compute_pointer_hash(self, nbmf_key: str, ledger_txid: str, item_id: str) -> str:
        """Compute cryptographic hash for pointer verification."""
        payload = json.dumps({
            "nbmf_key": nbmf_key,
            "ledger_txid": ledger_txid,
            "item_id": item_id
        }, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
    
    def should_use_ocr_fallback(
        self,
        cls: str,
        content: Any,
        nbmf_confidence: Optional[float] = None
    ) -> Tuple[bool, str]:
        """
        Determine if OCR fallback should be used.
        
        Policy:
        - Sensitive docs → NBMF only (no OCR)
        - Non-sensitive docs → OCR only if layout fidelity required AND confidence low
        
        Returns:
            (should_use_ocr, reason)
        """
        cls_lower = cls.lower()
        
        # Never use OCR for sensitive content
        if cls_lower in self.sensitive_classes:
            return False, "sensitive_content_nbmf_only"
        
        # Check if layout fidelity is required (e.g., tables, forms, structured docs)
        requires_layout = self._requires_layout_fidelity(content)
        
        # Use OCR only if:
        # 1. Layout fidelity is required
        # 2. NBMF confidence is low (if provided)
        if requires_layout:
            if nbmf_confidence is not None and nbmf_confidence < 0.7:
                return True, "low_confidence_layout_required"
            elif nbmf_confidence is None:
                # If confidence not provided, allow OCR for layout-sensitive content
                return True, "layout_fidelity_required"
        
        return False, "nbmf_sufficient"
    
    def _requires_layout_fidelity(self, content: Any) -> bool:
        """Check if content requires layout fidelity (tables, forms, etc.)."""
        if isinstance(content, dict):
            # Check for table indicators
            if "table" in str(content).lower() or "rows" in content or "columns" in content:
                return True
            # Check for form indicators
            if "form" in str(content).lower() or "fields" in content:
                return True
        
        if isinstance(content, str):
            # Check for table-like structures
            if "|" in content and "\n" in content:  # Markdown table
                return True
            if "\t" in content and content.count("\t") > 5:  # Tab-separated
                return True
        
        return False
    
    def create_abstract_with_pointer(
        self,
        content: Any,
        item_id: str,
        cls: str,
        nbmf_key: str,
        ledger_txid: str,
        merkle_proof: Optional[str] = None,
        nbmf_confidence: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create abstract and pointer, with OCR fallback decision.
        
        Returns:
            Dict with abstract, pointer, and OCR fallback recommendation
        """
        abstract_data = self.generate_abstract(
            content=content,
            item_id=item_id,
            cls=cls,
            nbmf_key=nbmf_key,
            ledger_txid=ledger_txid,
            merkle_proof=merkle_proof
        )
        
        # Determine OCR fallback
        use_ocr, reason = self.should_use_ocr_fallback(cls, content, nbmf_confidence)
        
        return {
            **abstract_data,
            "ocr_fallback": {
                "recommended": use_ocr,
                "reason": reason,
                "policy": "sensitive_nbmf_only" if cls.lower() in self.sensitive_classes else "hybrid_allowed"
            }
        }

