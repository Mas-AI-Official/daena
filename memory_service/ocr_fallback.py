"""
OCR Fallback Service for NBMF.

Implements OCR fallback when abstract NBMF confidence is low:
- OCR service integration
- Page-crop optimization (not full OCR text)
- Fallback rate tracking
- Integration with Abstract Store
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from pathlib import Path
from enum import Enum

from memory_service.metrics import incr
from memory_service.ledger import log_event

logger = logging.getLogger(__name__)


class OCRProvider(Enum):
    """OCR provider options."""
    TESSERACT = "tesseract"
    GOOGLE_VISION = "google_vision"
    AWS_TEXTRACT = "aws_textract"
    AZURE_COMPUTER_VISION = "azure_computer_vision"
    MOCK = "mock"  # For testing


@dataclass
class OCRResult:
    """OCR processing result."""
    source_uri: str
    text: str
    confidence: float
    pages: List[Dict[str, Any]]
    processing_time_ms: float
    provider: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class OCRFallbackService:
    """
    OCR Fallback Service for retrieving lossless content.
    
    Features:
    - Multiple OCR provider support
    - Page-crop optimization (extract specific regions)
    - Fallback rate tracking
    - Caching of OCR results
    """
    
    def __init__(
        self,
        provider: OCRProvider = OCRProvider.MOCK,
        cache_enabled: bool = True,
        page_crop_enabled: bool = True
    ):
        """
        Initialize OCR fallback service.
        
        Args:
            provider: OCR provider to use
            cache_enabled: Enable caching of OCR results
            page_crop_enabled: Enable page-crop optimization
        """
        self.provider = provider
        self.cache_enabled = cache_enabled
        self.page_crop_enabled = page_crop_enabled
        
        self.ocr_cache: Dict[str, OCRResult] = {}
        self.fallback_stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "successful_ocrs": 0,
            "failed_ocrs": 0,
            "total_processing_time_ms": 0.0
        }
        
    async def process_ocr_fallback(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False
    ) -> OCRResult:
        """
        Process OCR fallback for a source URI.
        
        Args:
            source_uri: URI to source document
            page_crop: Optional page/region to crop (e.g., {"page": 1, "bbox": [x, y, w, h]})
            force_refresh: Force OCR even if cached
        
        Returns:
            OCRResult with extracted text and metadata
        """
        self.fallback_stats["total_requests"] += 1
        incr("ocr_fallback_requests")
        
        # Check cache
        cache_key = self._get_cache_key(source_uri, page_crop)
        if self.cache_enabled and not force_refresh and cache_key in self.ocr_cache:
            self.fallback_stats["cache_hits"] += 1
            incr("ocr_cache_hit")
            logger.info(f"OCR cache hit for {source_uri}")
            return self.ocr_cache[cache_key]
        
        self.fallback_stats["cache_misses"] += 1
        incr("ocr_cache_miss")
        
        # Process OCR
        start_time = time.time()
        
        try:
            if self.provider == OCRProvider.MOCK:
                result = await self._mock_ocr(source_uri, page_crop)
            elif self.provider == OCRProvider.TESSERACT:
                result = await self._tesseract_ocr(source_uri, page_crop)
            elif self.provider == OCRProvider.GOOGLE_VISION:
                result = await self._google_vision_ocr(source_uri, page_crop)
            elif self.provider == OCRProvider.AWS_TEXTRACT:
                result = await self._aws_textract_ocr(source_uri, page_crop)
            elif self.provider == OCRProvider.AZURE_COMPUTER_VISION:
                result = await self._azure_ocr(source_uri, page_crop)
            else:
                raise ValueError(f"Unsupported OCR provider: {self.provider}")
            
            processing_time_ms = (time.time() - start_time) * 1000
            result.processing_time_ms = processing_time_ms
            
            self.fallback_stats["successful_ocrs"] += 1
            self.fallback_stats["total_processing_time_ms"] += processing_time_ms
            incr("ocr_success")
            
            # Cache result
            if self.cache_enabled:
                self.ocr_cache[cache_key] = result
            
            # Log to ledger
            log_event(
                action="ocr_fallback",
                ref=source_uri,
                store="ocr",
                route="fallback",
                extra={
                    "provider": self.provider.value,
                    "cache_hit": False,
                    "processing_time_ms": processing_time_ms,
                    "confidence": result.confidence,
                    "page_crop": page_crop is not None
                }
            )
            
            logger.info(f"OCR processed {source_uri} in {processing_time_ms:.1f}ms")
            return result
            
        except Exception as e:
            self.fallback_stats["failed_ocrs"] += 1
            incr("ocr_failure")
            
            log_event(
                action="ocr_fallback_error",
                ref=source_uri,
                store="ocr",
                route="fallback",
                extra={
                    "provider": self.provider.value,
                    "error": str(e)
                }
            )
            
            logger.error(f"OCR failed for {source_uri}: {e}")
            raise
    
    async def _mock_ocr(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Mock OCR for testing."""
        # Simulate OCR processing
        await asyncio.sleep(0.1)  # Simulate processing time
        
        mock_text = f"Mock OCR text extracted from {source_uri}"
        if page_crop:
            mock_text += f" (page {page_crop.get('page', 'unknown')})"
        
        return OCRResult(
            source_uri=source_uri,
            text=mock_text,
            confidence=0.85,
            pages=[{"page": 1, "text": mock_text, "confidence": 0.85}],
            processing_time_ms=100.0,
            provider=self.provider.value,
            metadata={"mock": True, "page_crop": page_crop}
        )
    
    async def _tesseract_ocr(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Tesseract OCR implementation."""
        try:
            import pytesseract
            from PIL import Image
            
            # Load image from URI
            if source_uri.startswith("file://"):
                image_path = Path(source_uri.replace("file://", ""))
                if not image_path.exists():
                    raise FileNotFoundError(f"Image not found: {image_path}")
                
                image = Image.open(image_path)
                
                # Apply page crop if specified
                if page_crop and self.page_crop_enabled:
                    bbox = page_crop.get("bbox")
                    if bbox:
                        image = image.crop(bbox)
                
                # Perform OCR
                text = pytesseract.image_to_string(image)
                confidence_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
                
                # Calculate average confidence
                confidences = [float(c) for c in confidence_data.get("conf", []) if c != "-1"]
                avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.5
                
                return OCRResult(
                    source_uri=source_uri,
                    text=text,
                    confidence=avg_confidence,
                    pages=[{"page": 1, "text": text, "confidence": avg_confidence}],
                    processing_time_ms=0.0,  # Will be set by caller
                    provider=self.provider.value,
                    metadata={"page_crop": page_crop}
                )
            else:
                raise ValueError(f"Unsupported URI scheme: {source_uri.split(':')[0]}")
                
        except ImportError:
            logger.warning("pytesseract not available, falling back to mock")
            return await self._mock_ocr(source_uri, page_crop)
    
    async def _google_vision_ocr(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Google Vision API OCR implementation."""
        # Placeholder for Google Vision API integration
        logger.info(f"Google Vision OCR requested for {source_uri}")
        return await self._mock_ocr(source_uri, page_crop)
    
    async def _aws_textract_ocr(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """AWS Textract OCR implementation."""
        # Placeholder for AWS Textract integration
        logger.info(f"AWS Textract OCR requested for {source_uri}")
        return await self._mock_ocr(source_uri, page_crop)
    
    async def _azure_ocr(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None
    ) -> OCRResult:
        """Azure Computer Vision OCR implementation."""
        # Placeholder for Azure OCR integration
        logger.info(f"Azure OCR requested for {source_uri}")
        return await self._mock_ocr(source_uri, page_crop)
    
    def _get_cache_key(self, source_uri: str, page_crop: Optional[Dict[str, Any]] = None) -> str:
        """Generate cache key for source URI and page crop."""
        if page_crop:
            crop_str = f"_{page_crop.get('page', '')}_{page_crop.get('bbox', '')}"
            return f"{source_uri}{crop_str}"
        return source_uri
    
    def get_fallback_rate(self) -> float:
        """Get OCR fallback rate (requests / total abstract retrievals)."""
        # This would be compared against total abstract retrievals
        # For now, return cache hit rate
        if self.fallback_stats["total_requests"] == 0:
            return 0.0
        
        cache_hit_rate = self.fallback_stats["cache_hits"] / self.fallback_stats["total_requests"]
        return 1.0 - cache_hit_rate  # Fallback rate (cache miss rate)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get OCR fallback statistics."""
        total = self.fallback_stats["total_requests"]
        avg_time = (
            self.fallback_stats["total_processing_time_ms"] / self.fallback_stats["successful_ocrs"]
            if self.fallback_stats["successful_ocrs"] > 0 else 0.0
        )
        
        return {
            "provider": self.provider.value,
            "total_requests": total,
            "cache_hits": self.fallback_stats["cache_hits"],
            "cache_misses": self.fallback_stats["cache_misses"],
            "cache_hit_rate": (
                self.fallback_stats["cache_hits"] / total if total > 0 else 0.0
            ),
            "successful_ocrs": self.fallback_stats["successful_ocrs"],
            "failed_ocrs": self.fallback_stats["failed_ocrs"],
            "success_rate": (
                self.fallback_stats["successful_ocrs"] / total if total > 0 else 0.0
            ),
            "avg_processing_time_ms": avg_time,
            "fallback_rate": self.get_fallback_rate(),
            "cache_enabled": self.cache_enabled,
            "page_crop_enabled": self.page_crop_enabled
        }


# Global instance
ocr_fallback_service = OCRFallbackService()


# Integration with Abstract Store
async def integrate_ocr_with_abstract_store():
    """Integrate OCR fallback with Abstract Store."""
    from memory_service.abstract_store import abstract_store
    
    # Override the _fetch_lossless_via_ocr method
    async def fetch_lossless_via_ocr(record):
        """Fetch lossless version via OCR."""
        if not record.lossless_pointer:
            return {
                "status": "no_pointer",
                "item_id": record.item_id,
                "message": "No lossless pointer available"
            }
        
        try:
            ocr_result = await ocr_fallback_service.process_ocr_fallback(
                source_uri=record.lossless_pointer
            )
            
            return {
                "status": "ocr_success",
                "item_id": record.item_id,
                "source_uri": record.lossless_pointer,
                "text": ocr_result.text,
                "confidence": ocr_result.confidence,
                "processing_time_ms": ocr_result.processing_time_ms,
                "provider": ocr_result.provider
            }
        except Exception as e:
            return {
                "status": "ocr_failed",
                "item_id": record.item_id,
                "error": str(e),
                "abstract_available": True,
                "abstract_data": record.abstract_nbmf
            }
    
    # Patch the method
    abstract_store._fetch_lossless_via_ocr = fetch_lossless_via_ocr

