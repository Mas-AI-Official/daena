"""
OCR Service for Baseline Comparison with NBMF

Provides OCR text extraction capabilities for comparing NBMF compression
against traditional OCR baseline. Supports multiple OCR providers.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OCRProvider(Enum):
    """OCR provider options."""
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    GOOGLE_VISION = "google_vision"
    MOCK = "mock"  # For testing


@dataclass
class OCRResult:
    """OCR extraction result."""
    text: str
    confidence: float
    provider: str
    processing_time_ms: float
    metadata: Dict[str, Any]
    original_size_bytes: int
    extracted_size_bytes: int


class OCRService:
    """
    OCR service for text extraction baseline comparison.
    
    Supports multiple OCR providers:
    - Tesseract (free, local)
    - EasyOCR (better accuracy, GPU-accelerated)
    - Google Vision (cloud, highest accuracy)
    """
    
    def __init__(self, provider: OCRProvider = OCRProvider.TESSERACT):
        """
        Initialize OCR service.
        
        Args:
            provider: OCR provider to use
        """
        self.provider = provider
        self.tesseract_available = False
        self.easyocr_available = False
        self.google_vision_available = False
        
        # Initialize provider
        self._init_provider()
    
    def _init_provider(self) -> None:
        """Initialize OCR provider."""
        if self.provider == OCRProvider.TESSERACT:
            try:
                import pytesseract
                from PIL import Image
                self.tesseract_available = True
                logger.info("✅ Tesseract OCR available")
            except ImportError:
                logger.warning("⚠️ Tesseract not available. Install: pip install pytesseract pillow")
                self.tesseract_available = False
        
        elif self.provider == OCRProvider.EASYOCR:
            try:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['en'], gpu=True)
                self.easyocr_available = True
                logger.info("✅ EasyOCR available")
            except ImportError:
                logger.warning("⚠️ EasyOCR not available. Install: pip install easyocr")
                self.easyocr_available = False
            except Exception as e:
                logger.warning(f"⚠️ EasyOCR initialization failed: {e}")
                self.easyocr_available = False
        
        elif self.provider == OCRProvider.GOOGLE_VISION:
            try:
                from google.cloud import vision
                self.google_vision_client = vision.ImageAnnotatorClient()
                self.google_vision_available = True
                logger.info("✅ Google Vision OCR available")
            except ImportError:
                logger.warning("⚠️ Google Vision not available. Install: pip install google-cloud-vision")
                self.google_vision_available = False
            except Exception as e:
                logger.warning(f"⚠️ Google Vision initialization failed: {e}")
                self.google_vision_available = False
    
    def extract_text(self, image_path: str, method: Optional[str] = None) -> OCRResult:
        """
        Extract text from image using OCR.
        
        Args:
            image_path: Path to image file
            method: Override provider method ("tesseract", "easyocr", "google_vision")
        
        Returns:
            OCRResult with extracted text, confidence, and metadata
        """
        method = method or self.provider.value
        
        # Get original file size
        original_size = Path(image_path).stat().st_size if Path(image_path).exists() else 0
        
        start_time = time.perf_counter()
        
        try:
            if method == "tesseract" and self.tesseract_available:
                result = self._extract_tesseract(image_path)
            elif method == "easyocr" and self.easyocr_available:
                result = self._extract_easyocr(image_path)
            elif method == "google_vision" and self.google_vision_available:
                result = self._extract_google_vision(image_path)
            else:
                # Fallback to mock
                result = self._extract_mock(image_path)
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            result = self._extract_mock(image_path)
        
        processing_time = (time.perf_counter() - start_time) * 1000  # Convert to ms
        
        # Calculate extracted text size
        extracted_size = len(result["text"].encode('utf-8'))
        
        return OCRResult(
            text=result["text"],
            confidence=result["confidence"],
            provider=method,
            processing_time_ms=processing_time,
            metadata=result.get("metadata", {}),
            original_size_bytes=original_size,
            extracted_size_bytes=extracted_size
        )
    
    def _extract_tesseract(self, image_path: str) -> Dict[str, Any]:
        """Extract text using Tesseract OCR."""
        import pytesseract
        from PIL import Image
        
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        
        # Get confidence data
        confidence_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        confidences = [float(c) for c in confidence_data.get("conf", []) if c != "-1"]
        avg_confidence = sum(confidences) / len(confidences) / 100.0 if confidences else 0.5
        
        return {
            "text": text.strip(),
            "confidence": avg_confidence,
            "metadata": {
                "provider": "tesseract",
                "word_count": len(text.split()),
                "char_count": len(text)
            }
        }
    
    def _extract_easyocr(self, image_path: str) -> Dict[str, Any]:
        """Extract text using EasyOCR."""
        results = self.easyocr_reader.readtext(image_path)
        
        # Combine all text
        text_parts = [item[1] for item in results]
        text = ' '.join(text_parts)
        
        # Calculate average confidence
        confidences = [item[2] for item in results]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        return {
            "text": text.strip(),
            "confidence": avg_confidence,
            "metadata": {
                "provider": "easyocr",
                "word_count": len(text.split()),
                "char_count": len(text),
                "detections": len(results)
            }
        }
    
    def _extract_google_vision(self, image_path: str) -> Dict[str, Any]:
        """Extract text using Google Cloud Vision API."""
        from google.cloud import vision
        from PIL import Image
        
        with open(image_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = self.google_vision_client.text_detection(image=image)
        
        if response.error.message:
            raise Exception(f"Google Vision API error: {response.error.message}")
        
        text_annotations = response.text_annotations
        if text_annotations:
            text = text_annotations[0].description
            # Calculate average confidence from all detections
            confidences = []
            for annotation in text_annotations[1:]:  # Skip first (full text)
                if hasattr(annotation, 'confidence'):
                    confidences.append(annotation.confidence)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.9
        else:
            text = ""
            avg_confidence = 0.0
        
        return {
            "text": text.strip(),
            "confidence": avg_confidence,
            "metadata": {
                "provider": "google_vision",
                "word_count": len(text.split()),
                "char_count": len(text),
                "detections": len(text_annotations) - 1 if text_annotations else 0
            }
        }
    
    def _extract_mock(self, image_path: str) -> Dict[str, Any]:
        """Mock OCR extraction for testing."""
        return {
            "text": f"Mock OCR text from {image_path}",
            "confidence": 0.5,
            "metadata": {
                "provider": "mock",
                "word_count": 5,
                "char_count": 30
            }
        }
    
    def compare_with_nbmf(
        self,
        image_path: str,
        nbmf_result: Dict[str, Any],
        ocr_result: Optional[OCRResult] = None
    ) -> Dict[str, Any]:
        """
        Compare OCR extraction with NBMF encoding.
        
        Args:
            image_path: Path to original image
            nbmf_result: NBMF encoding result (from router)
            ocr_result: Optional pre-computed OCR result
        
        Returns:
            Comparison metrics (compression, accuracy, latency, storage)
        """
        if ocr_result is None:
            ocr_result = self.extract_text(image_path)
        
        # Get original size
        original_size = Path(image_path).stat().st_size if Path(image_path).exists() else 0
        
        # NBMF metrics
        nbmf_size = nbmf_result.get("size_bytes", 0)
        nbmf_compression = original_size / nbmf_size if nbmf_size > 0 else 1.0
        nbmf_latency_ms = nbmf_result.get("encode_latency_ms", 0)
        
        # OCR metrics
        ocr_size = ocr_result.extracted_size_bytes
        ocr_compression = original_size / ocr_size if ocr_size > 0 else 1.0
        ocr_latency_ms = ocr_result.processing_time_ms
        
        # Calculate advantages
        compression_advantage = nbmf_compression / ocr_compression if ocr_compression > 0 else nbmf_compression
        latency_advantage = ocr_latency_ms / nbmf_latency_ms if nbmf_latency_ms > 0 else 1.0
        storage_savings = (1 - nbmf_size / ocr_size) * 100 if ocr_size > 0 else 0
        
        return {
            "original_size_bytes": original_size,
            "nbmf": {
                "size_bytes": nbmf_size,
                "compression_ratio": nbmf_compression,
                "latency_ms": nbmf_latency_ms,
                "accuracy": nbmf_result.get("accuracy", 1.0)
            },
            "ocr": {
                "size_bytes": ocr_size,
                "compression_ratio": ocr_compression,
                "latency_ms": ocr_latency_ms,
                "confidence": ocr_result.confidence,
                "provider": ocr_result.provider
            },
            "comparison": {
                "compression_advantage": compression_advantage,
                "latency_advantage": latency_advantage,
                "storage_savings_percent": storage_savings,
                "nbmf_faster_by": f"{latency_advantage:.1f}x",
                "nbmf_smaller_by": f"{compression_advantage:.2f}x"
            }
        }


# Global instance
_default_ocr_service = None


def get_ocr_service(provider: OCRProvider = OCRProvider.TESSERACT) -> OCRService:
    """Get global OCR service instance."""
    global _default_ocr_service
    if _default_ocr_service is None:
        _default_ocr_service = OCRService(provider=provider)
    return _default_ocr_service

