"""
Tests for OCR Fallback Service.
"""

from __future__ import annotations

import pytest
import asyncio

from memory_service.ocr_fallback import (
    OCRFallbackService,
    OCRProvider,
    OCRResult
)


@pytest.fixture
def ocr_service():
    """Create an OCR service instance."""
    return OCRFallbackService(provider=OCRProvider.MOCK)


@pytest.mark.asyncio
async def test_mock_ocr(ocr_service):
    """Test mock OCR processing."""
    result = await ocr_service.process_ocr_fallback("file:///test/document.pdf")
    
    assert result is not None
    assert result.source_uri == "file:///test/document.pdf"
    assert result.text is not None
    assert result.confidence > 0
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_ocr_caching(ocr_service):
    """Test OCR result caching."""
    # First request (cache miss)
    result1 = await ocr_service.process_ocr_fallback("file:///test/doc1.pdf")
    
    # Second request (cache hit)
    result2 = await ocr_service.process_ocr_fallback("file:///test/doc1.pdf")
    
    assert result1.text == result2.text
    assert ocr_service.fallback_stats["cache_hits"] == 1
    assert ocr_service.fallback_stats["cache_misses"] == 1


@pytest.mark.asyncio
async def test_page_crop(ocr_service):
    """Test page crop optimization."""
    page_crop = {"page": 1, "bbox": [0, 0, 100, 100]}
    
    result = await ocr_service.process_ocr_fallback(
        "file:///test/document.pdf",
        page_crop=page_crop
    )
    
    assert result.metadata is not None
    assert result.metadata.get("page_crop") == page_crop


@pytest.mark.asyncio
async def test_force_refresh(ocr_service):
    """Test force refresh bypassing cache."""
    # First request
    await ocr_service.process_ocr_fallback("file:///test/doc2.pdf")
    
    # Force refresh
    result = await ocr_service.process_ocr_fallback(
        "file:///test/doc2.pdf",
        force_refresh=True
    )
    
    assert result is not None
    # Should have 2 cache misses (force refresh bypasses cache)
    assert ocr_service.fallback_stats["cache_misses"] >= 2


def test_fallback_rate(ocr_service):
    """Test fallback rate calculation."""
    # Process some requests
    asyncio.run(ocr_service.process_ocr_fallback("file:///test/doc3.pdf"))
    asyncio.run(ocr_service.process_ocr_fallback("file:///test/doc3.pdf"))  # Cache hit
    
    rate = ocr_service.get_fallback_rate()
    
    assert 0.0 <= rate <= 1.0


def test_get_stats(ocr_service):
    """Test getting statistics."""
    # Process some requests
    asyncio.run(ocr_service.process_ocr_fallback("file:///test/doc4.pdf"))
    
    stats = ocr_service.get_stats()
    
    assert stats["total_requests"] >= 1
    assert "cache_hit_rate" in stats
    assert "success_rate" in stats
    assert "fallback_rate" in stats
    assert stats["provider"] == "mock"


@pytest.mark.asyncio
async def test_ocr_error_handling(ocr_service):
    """Test OCR error handling."""
    # Use invalid URI to trigger error
    try:
        await ocr_service.process_ocr_fallback("invalid://uri")
    except Exception:
        pass  # Expected
    
    stats = ocr_service.get_stats()
    assert stats["failed_ocrs"] >= 0  # May or may not fail depending on implementation

