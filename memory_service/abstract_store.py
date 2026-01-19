"""
Abstract + Lossless Pointer Pattern for NBMF.

Implements hybrid storage pattern:
- Abstract: Compressed NBMF representation (semantic)
- Lossless Pointer: Source URI to full document (for OCR fallback)
- Confidence-based routing to OCR when needed
- Provenance chain tracking
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from enum import Enum

from memory_service.router import MemoryRouter
from memory_service.ledger import log_event

logger = logging.getLogger(__name__)


class StorageMode(Enum):
    """Storage mode for memory items."""
    ABSTRACT_ONLY = "abstract_only"  # Only abstract NBMF
    ABSTRACT_POINTER = "abstract_pointer"  # Abstract + lossless pointer
    LOSSLESS_ONLY = "lossless_only"  # Only lossless (for critical data)
    HYBRID = "hybrid"  # Both abstract and lossless


@dataclass
class AbstractRecord:
    """An abstract record with optional lossless pointer."""
    item_id: str
    class_name: str
    abstract_nbmf: Dict[str, Any]  # Compressed NBMF representation
    lossless_pointer: Optional[str] = None  # URI to full document
    source_uri: Optional[str] = None  # Original source URI
    confidence: float = 1.0  # Confidence in abstract representation
    provenance: Dict[str, Any] = None  # Provenance chain
    tenant_id: Optional[str] = None  # Tenant isolation
    project_id: Optional[str] = None  # Project isolation
    
    def __post_init__(self):
        if self.provenance is None:
            self.provenance = {}


class AbstractStore:
    """
    Manages abstract + lossless pointer pattern for NBMF.
    
    Pattern:
    1. Store abstract NBMF (compressed, semantic)
    2. Store lossless pointer (source URI) if available
    3. Route to OCR fallback when confidence is low
    4. Track provenance chain (abstract_of: txid)
    """
    
    def __init__(self, router: Optional[MemoryRouter] = None):
        self.router = router or MemoryRouter()
        self.ocr_confidence_threshold = 0.7  # Below this, use OCR fallback
        self.abstract_records: Dict[str, AbstractRecord] = {}
        
    def store_abstract(
        self,
        item_id: str,
        class_name: str,
        payload: Any,
        source_uri: Optional[str] = None,
        lossless_pointer: Optional[str] = None,
        confidence: float = 1.0,
        mode: StorageMode = StorageMode.ABSTRACT_POINTER,
        tenant_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store abstract NBMF with optional lossless pointer.
        
        Args:
            item_id: Unique identifier
            class_name: Memory class
            payload: Data to store
            source_uri: Original source URI
            lossless_pointer: URI to lossless version
            confidence: Confidence in abstract (0.0 to 1.0)
            mode: Storage mode
        
        Returns:
            Dict with storage result and routing decision
        """
        # Encode as abstract NBMF (semantic mode for compression)
        from memory_service.nbmf_encoder import encode as nbmf_encode
        
        abstract_nbmf = nbmf_encode(payload, fidelity="semantic")
        
        # Determine if OCR fallback is needed
        use_ocr_fallback = confidence < self.ocr_confidence_threshold
        
        # Create abstract record
        record = AbstractRecord(
            item_id=item_id,
            class_name=class_name,
            abstract_nbmf=abstract_nbmf,
            lossless_pointer=lossless_pointer or source_uri,
            source_uri=source_uri,
            confidence=confidence,
            provenance={
                "created_at": time.time(),
                "mode": mode.value,
                "abstract_of": None  # Will be set if derived from another record
            }
        )
        
        # Store abstract to L2
        if mode in [StorageMode.ABSTRACT_ONLY, StorageMode.ABSTRACT_POINTER, StorageMode.HYBRID]:
            meta = {
                "class": class_name,
                "fidelity": "semantic",
                "abstract": True,
                "confidence": confidence,
                "source_uri": source_uri,
                "lossless_pointer": lossless_pointer,
                "created_at": time.time()
            }
            
            result = self.router.write_nbmf_only(item_id, class_name, payload, meta)
            record.provenance["abstract_txid"] = result.get("txid")
        
        # Store lossless pointer if provided
        if lossless_pointer and mode in [StorageMode.ABSTRACT_POINTER, StorageMode.HYBRID]:
            # Store pointer reference
            pointer_meta = {
                "class": class_name,
                "type": "lossless_pointer",
                "source_uri": lossless_pointer,
                "abstract_item_id": item_id,
                "created_at": time.time()
            }
            
            pointer_id = f"{item_id}_pointer"
            self.router.write_nbmf_only(pointer_id, class_name, {"uri": lossless_pointer}, pointer_meta)
            record.provenance["pointer_txid"] = pointer_id
        
        # Store lossless version if mode is HYBRID or LOSSLESS_ONLY
        if mode in [StorageMode.HYBRID, StorageMode.LOSSLESS_ONLY]:
            lossless_nbmf = nbmf_encode(payload, fidelity="lossless")
            lossless_meta = {
                "class": class_name,
                "fidelity": "lossless",
                "abstract_item_id": item_id,
                "created_at": time.time()
            }
            
            lossless_id = f"{item_id}_lossless"
            lossless_result = self.router.write_nbmf_only(lossless_id, class_name, payload, lossless_meta)
            record.provenance["lossless_txid"] = lossless_result.get("txid")
        
        # Cache record
        self.abstract_records[item_id] = record
        
        # Log to ledger
        log_event(
            action="abstract_store",
            ref=item_id,
            store="nbmf",
            route="abstract",
            extra={
                "class": class_name,
                "mode": mode.value,
                "confidence": confidence,
                "use_ocr_fallback": use_ocr_fallback,
                "has_pointer": lossless_pointer is not None
            }
        )
        
        return {
            "status": "stored",
            "item_id": item_id,
            "mode": mode.value,
            "confidence": confidence,
            "use_ocr_fallback": use_ocr_fallback,
            "lossless_pointer": lossless_pointer,
            "provenance": record.provenance
        }
    
    def retrieve_with_fallback(
        self,
        item_id: str,
        class_name: str,
        require_lossless: bool = False
    ) -> Dict[str, Any]:
        """
        Retrieve abstract record with OCR fallback if needed.
        
        Args:
            item_id: Item identifier
            class_name: Memory class
            require_lossless: If True, always fetch lossless version
        
        Returns:
            Dict with retrieved data and source information
        """
        # Try to get abstract record
        record = self.abstract_records.get(item_id)
        
        if not record:
            # Try to read from router
            abstract_data = self.router.read_nbmf_only(item_id, class_name)
            if abstract_data:
                # Reconstruct record
                record = AbstractRecord(
                    item_id=item_id,
                    class_name=class_name,
                    abstract_nbmf=abstract_data,
                    lossless_pointer=None,
                    confidence=1.0
                )
        
        if not record:
            return {
                "status": "not_found",
                "item_id": item_id
            }
        
        # Check if lossless is required or confidence is low
        use_lossless = require_lossless or record.confidence < self.ocr_confidence_threshold
        
        if use_lossless and record.lossless_pointer:
            # Fetch lossless version via OCR fallback
            return self._fetch_lossless_via_ocr(record)
        
        # Return abstract version
        return {
            "status": "abstract",
            "item_id": item_id,
            "data": record.abstract_nbmf,
            "confidence": record.confidence,
            "source": "abstract_nbmf",
            "lossless_available": record.lossless_pointer is not None
        }
    
    def _fetch_lossless_via_ocr(self, record: AbstractRecord) -> Dict[str, Any]:
        """
        Fetch lossless version via OCR fallback.
        
        Integrated with OCR fallback service.
        """
        if not record.lossless_pointer:
            return {
                "status": "no_pointer",
                "item_id": record.item_id,
                "message": "No lossless pointer available",
                "abstract_available": True,
                "abstract_data": record.abstract_nbmf
            }
        
        try:
            # Import OCR service (may not be available in all environments)
            try:
                from memory_service.ocr_fallback import ocr_fallback_service
                import asyncio
                
                # Run async OCR in sync context
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, create a task
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(ocr_fallback_service.process_ocr_fallback(record.lossless_pointer))
                        )
                        ocr_result = future.result(timeout=30)
                else:
                    ocr_result = loop.run_until_complete(
                        ocr_fallback_service.process_ocr_fallback(record.lossless_pointer)
                    )
                
                return {
                    "status": "ocr_success",
                    "item_id": record.item_id,
                    "source_uri": record.lossless_pointer,
                    "text": ocr_result.text,
                    "confidence": ocr_result.confidence,
                    "processing_time_ms": ocr_result.processing_time_ms,
                    "provider": ocr_result.provider,
                    "abstract_available": True,
                    "abstract_data": record.abstract_nbmf
                }
            except ImportError:
                logger.warning("OCR fallback service not available")
                return {
                    "status": "ocr_unavailable",
                    "item_id": record.item_id,
                    "source_uri": record.lossless_pointer,
                    "message": "OCR service not available",
                    "abstract_available": True,
                    "abstract_data": record.abstract_nbmf
                }
        except Exception as e:
            logger.error(f"OCR fallback failed for {record.item_id}: {e}")
            return {
                "status": "ocr_failed",
                "item_id": record.item_id,
                "error": str(e),
                "abstract_available": True,
                "abstract_data": record.abstract_nbmf
            }
    
    def create_provenance_chain(
        self,
        item_id: str,
        abstract_of: str
    ) -> Dict[str, Any]:
        """
        Create provenance chain linking abstract to source.
        
        Args:
            item_id: New abstract item ID
            abstract_of: Source item ID (txid or item_id)
        
        Returns:
            Provenance chain information
        """
        record = self.abstract_records.get(item_id)
        if not record:
            return {"error": "Record not found", "item_id": item_id}
        
        record.provenance["abstract_of"] = abstract_of
        
        # Log provenance chain
        log_event(
            action="provenance_chain",
            ref=item_id,
            store="nbmf",
            route="abstract",
            extra={
                "abstract_of": abstract_of,
                "provenance": record.provenance
            }
        )
        
        return {
            "status": "provenance_created",
            "item_id": item_id,
            "abstract_of": abstract_of,
            "provenance": record.provenance
        }
    
    def get_provenance(self, item_id: str) -> Dict[str, Any]:
        """Get provenance chain for an item."""
        record = self.abstract_records.get(item_id)
        if not record:
            return {"error": "Record not found", "item_id": item_id}
        
        return {
            "item_id": item_id,
            "provenance": record.provenance,
            "source_uri": record.source_uri,
            "lossless_pointer": record.lossless_pointer,
            "confidence": record.confidence
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get abstract store statistics."""
        total_records = len(self.abstract_records)
        with_pointers = sum(1 for r in self.abstract_records.values() if r.lossless_pointer)
        low_confidence = sum(1 for r in self.abstract_records.values() if r.confidence < self.ocr_confidence_threshold)
        
        return {
            "total_records": total_records,
            "records_with_pointers": with_pointers,
            "low_confidence_records": low_confidence,
            "ocr_threshold": self.ocr_confidence_threshold,
            "pointer_rate": with_pointers / total_records if total_records > 0 else 0.0
        }


# Global instance
abstract_store = AbstractStore()

