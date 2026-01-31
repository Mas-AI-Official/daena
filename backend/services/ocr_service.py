"""
OCR Service (Unified Architecture).

Provides OCR capabilities for extracting text from images/documents.
Replaces legacy memory_service.ocr_fallback.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from pathlib import Path
from enum import Enum

from backend.database import SessionLocal, EventLog

logger = logging.getLogger(__name__)

def log_event(action: str, ref: str, store: str, route: str, extra: Dict[str, Any]):
    """Unified Event Logging Helper"""
    try:
        db = SessionLocal()
        event = EventLog(
            event_type=action,
            entity_type="ocr",
            entity_id=ref,
            payload_json={
                "store": store,
                "route": route,
                "extra": extra
            },
            created_by="ocr_service"
        )
        db.add(event)
        db.commit()
        db.close()
    except Exception as e:
        logger.warning(f"Failed to log event: {e}")

class OCRProvider(Enum):
    """OCR provider options."""
    TESSERACT = "tesseract"
    GOOGLE_VISION = "google_vision"
    AWS_TEXTRACT = "aws_textract"
    AZURE_COMPUTER_VISION = "azure_computer_vision"
    MOCK = "mock"

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

class OCRService:
    """
    OCR Service for content extraction.
    """
    
    def __init__(
        self,
        provider: OCRProvider = OCRProvider.MOCK,
        cache_enabled: bool = True,
        page_crop_enabled: bool = True
    ):
        self.provider = provider
        self.cache_enabled = cache_enabled
        self.page_crop_enabled = page_crop_enabled
        
        self.ocr_cache: Dict[str, OCRResult] = {}
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "successful_ocrs": 0,
            "failed_ocrs": 0,
            "total_processing_time_ms": 0.0
        }
        
    async def process_ocr(
        self,
        source_uri: str,
        page_crop: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False
    ) -> OCRResult:
        """
        Process OCR for a source URI.
        """
        self.stats["total_requests"] += 1
        
        # Check cache
        cache_key = self._get_cache_key(source_uri, page_crop)
        if self.cache_enabled and not force_refresh and cache_key in self.ocr_cache:
            self.stats["cache_hits"] += 1
            logger.info(f"OCR cache hit for {source_uri}")
            return self.ocr_cache[cache_key]
        
        self.stats["cache_misses"] += 1
        
        # Process OCR
        start_time = time.time()
        
        try:
            if self.provider == OCRProvider.MOCK:
                result = await self._mock_ocr(source_uri, page_crop)
            elif self.provider == OCRProvider.TESSERACT:
                result = await self._tesseract_ocr(source_uri, page_crop)
            else:
                # Default to mock for unimplemented providers
                logger.warning(f"Provider {self.provider} not implemented, falling back to mock")
                result = await self._mock_ocr(source_uri, page_crop)
            
            processing_time_ms = (time.time() - start_time) * 1000
            result.processing_time_ms = processing_time_ms
            
            self.stats["successful_ocrs"] += 1
            self.stats["total_processing_time_ms"] += processing_time_ms
            
            # Cache result
            if self.cache_enabled:
                self.ocr_cache[cache_key] = result
            
            # Log to ledger
            log_event(
                action="ocr_processed",
                ref=source_uri,
                store="ocr",
                route="service",
                extra={
                    "provider": self.provider.value,
                    "cache_hit": False,
                    "processing_time_ms": processing_time_ms,
                    "confidence": result.confidence
                }
            )
            
            return result
            
        except Exception as e:
            self.stats["failed_ocrs"] += 1
            log_event(
                action="ocr_error",
                ref=source_uri,
                store="ocr",
                route="service",
                extra={"error": str(e)}
            )
            logger.error(f"OCR failed for {source_uri}: {e}")
            raise

    async def _mock_ocr(self, source_uri: str, page_crop: Optional[Dict[str, Any]] = None) -> OCRResult:
        """Mock OCR."""
        await asyncio.sleep(0.1)
        mock_text = f"Mock OCR text extracted from {source_uri}"
        return OCRResult(
            source_uri=source_uri,
            text=mock_text,
            confidence=0.85,
            pages=[{"page": 1, "text": mock_text, "confidence": 0.85}],
            processing_time_ms=100.0,
            provider=self.provider.value,
            metadata={"mock": True}
        )

    async def _tesseract_ocr(self, source_uri: str, page_crop: Optional[Dict[str, Any]] = None) -> OCRResult:
        """Tesseract OCR (Simplified)."""
        try:
            import pytesseract
            from PIL import Image
            
            if source_uri.startswith("file://"):
                image_path = Path(source_uri.replace("file://", ""))
                if not image_path.exists():
                    raise FileNotFoundError(f"Image not found: {image_path}")
                
                image = Image.open(image_path)
                if page_crop and self.page_crop_enabled:
                    bbox = page_crop.get("bbox")
                    if bbox:
                        image = image.crop(bbox)
                
                text = pytesseract.image_to_string(image)
                return OCRResult(
                    source_uri=source_uri,
                    text=text,
                    confidence=0.9,
                    pages=[{"page": 1, "text": text, "confidence": 0.9}],
                    processing_time_ms=0.0,
                    provider=self.provider.value
                )
            else:
                raise ValueError("Only file:// URIs supported for Tesseract")
        except ImportError:
            logger.warning("pytesseract/PIL not installed, using mock")
            return await self._mock_ocr(source_uri, page_crop)

    def _get_cache_key(self, source_uri: str, page_crop: Optional[Dict[str, Any]] = None) -> str:
        if page_crop:
            return f"{source_uri}_{page_crop}"
        return source_uri
    
    def get_fallback_rate(self) -> float:
        """Get fallback rate (cache miss rate)."""
        if self.stats["total_requests"] == 0:
            return 0.0
        return self.stats["cache_misses"] / self.stats["total_requests"]

    def get_stats(self) -> Dict[str, Any]:
        return self.stats

# Global singleton
ocr_service = OCRService()
