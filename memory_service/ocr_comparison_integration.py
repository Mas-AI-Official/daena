"""
OCR Comparison Integration with NBMF Router

Provides integration between OCR service and NBMF router for:
- Confidence-based routing (NBMF vs OCR)
- Hybrid mode (NBMF + OCR verification)
- Comparison metrics collection
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Import OCR service if available
try:
    from .ocr_service import OCRService, OCRProvider, OCRResult
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    OCRService = None
    OCRProvider = None
    OCRResult = None


@dataclass
class ComparisonMetrics:
    """Metrics from OCR vs NBMF comparison."""
    nbmf_compression: float
    ocr_compression: float
    compression_advantage: float
    nbmf_latency_ms: float
    ocr_latency_ms: float
    latency_advantage: float
    nbmf_accuracy: float
    ocr_confidence: float
    storage_savings_percent: float


class OCRComparisonIntegration:
    """
    Integration layer for OCR comparison with NBMF.
    
    Features:
    - Confidence-based routing (NBMF vs OCR)
    - Hybrid mode (NBMF + OCR verification)
    - Comparison metrics collection
    - Automatic fallback logic
    """
    
    def __init__(
        self,
        ocr_provider: OCRProvider = OCRProvider.TESSERACT,
        confidence_threshold: float = 0.7,
        enable_hybrid: bool = True
    ):
        """
        Initialize OCR comparison integration.
        
        Args:
            ocr_provider: OCR provider to use
            confidence_threshold: Confidence threshold for NBMF routing (default: 0.7)
            enable_hybrid: Enable hybrid mode (NBMF + OCR verification)
        """
        self.confidence_threshold = confidence_threshold
        self.enable_hybrid = enable_hybrid
        
        if OCR_AVAILABLE:
            self.ocr_service = OCRService(provider=ocr_provider)
        else:
            self.ocr_service = None
            logger.warning("⚠️ OCR service not available. Install: pip install pytesseract pillow")
    
    def should_use_ocr_fallback(self, nbmf_confidence: float) -> bool:
        """
        Determine if OCR fallback should be used based on NBMF confidence.
        
        Args:
            nbmf_confidence: NBMF encoding confidence (0.0-1.0)
        
        Returns:
            True if OCR fallback should be used
        """
        return nbmf_confidence < self.confidence_threshold
    
    def compare_with_ocr(
        self,
        image_path: str,
        nbmf_result: Dict[str, Any],
        ocr_result: Optional[OCRResult] = None
    ) -> Optional[ComparisonMetrics]:
        """
        Compare NBMF encoding with OCR extraction.
        
        Args:
            image_path: Path to original image
            nbmf_result: NBMF encoding result
            ocr_result: Optional pre-computed OCR result
        
        Returns:
            ComparisonMetrics or None if OCR unavailable
        """
        if not self.ocr_service:
            return None
        
        try:
            if ocr_result is None:
                ocr_result = self.ocr_service.extract_text(image_path)
            
            # Get original size
            from pathlib import Path
            original_size = Path(image_path).stat().st_size if Path(image_path).exists() else 0
            
            # NBMF metrics
            nbmf_size = nbmf_result.get("size_bytes", 0)
            nbmf_compression = original_size / nbmf_size if nbmf_size > 0 else 1.0
            nbmf_latency_ms = nbmf_result.get("encode_latency_ms", 0)
            nbmf_accuracy = nbmf_result.get("accuracy", 1.0)
            
            # OCR metrics
            ocr_size = ocr_result.extracted_size_bytes
            ocr_compression = original_size / ocr_size if ocr_size > 0 else 1.0
            ocr_latency_ms = ocr_result.processing_time_ms
            
            # Calculate advantages
            compression_advantage = nbmf_compression / ocr_compression if ocr_compression > 0 else nbmf_compression
            latency_advantage = ocr_latency_ms / nbmf_latency_ms if nbmf_latency_ms > 0 else 1.0
            storage_savings = (1 - nbmf_size / ocr_size) * 100 if ocr_size > 0 else 0
            
            return ComparisonMetrics(
                nbmf_compression=nbmf_compression,
                ocr_compression=ocr_compression,
                compression_advantage=compression_advantage,
                nbmf_latency_ms=nbmf_latency_ms,
                ocr_latency_ms=ocr_latency_ms,
                latency_advantage=latency_advantage,
                nbmf_accuracy=nbmf_accuracy,
                ocr_confidence=ocr_result.confidence,
                storage_savings_percent=storage_savings
            )
        except Exception as e:
            logger.error(f"OCR comparison failed: {e}")
            return None
    
    def hybrid_mode(
        self,
        image_path: str,
        nbmf_result: Dict[str, Any],
        nbmf_confidence: float
    ) -> Dict[str, Any]:
        """
        Hybrid mode: Use NBMF with OCR verification.
        
        Args:
            image_path: Path to original image
            nbmf_result: NBMF encoding result
            nbmf_confidence: NBMF confidence score
        
        Returns:
            Hybrid result with both NBMF and OCR data
        """
        if not self.enable_hybrid or not self.ocr_service:
            return {
                "mode": "nbmf_only",
                "nbmf": nbmf_result,
                "confidence": nbmf_confidence
            }
        
        try:
            # Get OCR result
            ocr_result = self.ocr_service.extract_text(image_path)
            
            # Compare
            comparison = self.compare_with_ocr(image_path, nbmf_result, ocr_result)
            
            # Determine if OCR verification is needed
            use_ocr_verification = self.should_use_ocr_fallback(nbmf_confidence)
            
            return {
                "mode": "hybrid",
                "nbmf": nbmf_result,
                "ocr": {
                    "text": ocr_result.text,
                    "confidence": ocr_result.confidence,
                    "provider": ocr_result.provider,
                    "latency_ms": ocr_result.processing_time_ms
                },
                "comparison": comparison.__dict__ if comparison else None,
                "use_ocr_verification": use_ocr_verification,
                "nbmf_confidence": nbmf_confidence,
                "recommendation": "ocr_fallback" if use_ocr_verification else "nbmf_primary"
            }
        except Exception as e:
            logger.error(f"Hybrid mode failed: {e}")
            return {
                "mode": "nbmf_only",
                "nbmf": nbmf_result,
                "confidence": nbmf_confidence,
                "error": str(e)
            }


# Global instance
_default_ocr_comparison: Optional[OCRComparisonIntegration] = None


def get_ocr_comparison(
    ocr_provider: OCRProvider = OCRProvider.TESSERACT,
    confidence_threshold: float = 0.7,
    enable_hybrid: bool = True
) -> Optional[OCRComparisonIntegration]:
    """Get global OCR comparison integration instance."""
    global _default_ocr_comparison
    
    if not OCR_AVAILABLE:
        return None
    
    if _default_ocr_comparison is None:
        _default_ocr_comparison = OCRComparisonIntegration(
            ocr_provider=ocr_provider,
            confidence_threshold=confidence_threshold,
            enable_hybrid=enable_hybrid
        )
    
    return _default_ocr_comparison

