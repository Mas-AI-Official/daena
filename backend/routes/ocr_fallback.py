"""
OCR Fallback API Routes.

Provides endpoints for OCR fallback service.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

from backend.services.ocr_service import ocr_service, OCRProvider

router = APIRouter(prefix="/api/v1/ocr", tags=["ocr"])


class OCRRequest(BaseModel):
    source_uri: str
    page_crop: Optional[Dict[str, Any]] = None
    force_refresh: bool = False


@router.post("/process")
async def process_ocr(request: OCRRequest) -> Dict[str, Any]:
    """Process OCR fallback for a source URI."""
    try:
        result = await ocr_service.process_ocr(
            source_uri=request.source_uri,
            page_crop=request.page_crop,
            force_refresh=request.force_refresh
        )
        
        return {
            "success": True,
            "result": {
                "source_uri": result.source_uri,
                "text": result.text,
                "confidence": result.confidence,
                "processing_time_ms": result.processing_time_ms,
                "provider": result.provider,
                "pages": result.pages,
                "metadata": result.metadata
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


@router.get("/stats")
async def get_ocr_stats() -> Dict[str, Any]:
    """Get OCR fallback statistics."""
    stats = ocr_service.get_stats()
    
    return {
        "success": True,
        "stats": stats
    }


@router.get("/fallback-rate")
async def get_fallback_rate() -> Dict[str, Any]:
    """Get OCR fallback rate."""
    rate = ocr_service.get_fallback_rate()
    
    return {
        "success": True,
        "fallback_rate": rate,
        "target_rate": 0.2,  # Target: <20% fallback rate
        "status": "good" if rate < 0.2 else "needs_optimization"
    }

