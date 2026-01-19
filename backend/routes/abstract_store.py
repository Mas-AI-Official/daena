"""
Abstract Store API Routes.

Provides endpoints for abstract + lossless pointer pattern.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel

from memory_service.abstract_store import abstract_store, StorageMode

router = APIRouter(prefix="/api/v1/abstract", tags=["abstract"])


class StoreAbstractRequest(BaseModel):
    item_id: str
    class_name: str
    payload: Dict[str, Any]
    source_uri: Optional[str] = None
    lossless_pointer: Optional[str] = None
    confidence: float = 1.0
    mode: Optional[str] = None  # "abstract_only", "abstract_pointer", "lossless_only", "hybrid"


@router.post("/store")
async def store_abstract(request: StoreAbstractRequest) -> Dict[str, Any]:
    """Store abstract NBMF with optional lossless pointer."""
    try:
        mode = StorageMode.ABSTRACT_POINTER  # Default
        if request.mode:
            try:
                mode = StorageMode[request.mode.upper()]
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid mode: {request.mode}")
        
        result = abstract_store.store_abstract(
            item_id=request.item_id,
            class_name=request.class_name,
            payload=request.payload,
            source_uri=request.source_uri,
            lossless_pointer=request.lossless_pointer,
            confidence=request.confidence,
            mode=mode
        )
        
        return {
            "success": True,
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store abstract: {str(e)}")


@router.get("/{item_id}/retrieve")
async def retrieve_with_fallback(
    item_id: str,
    class_name: str,
    require_lossless: bool = False
) -> Dict[str, Any]:
    """Retrieve abstract record with OCR fallback if needed."""
    try:
        result = abstract_store.retrieve_with_fallback(
            item_id=item_id,
            class_name=class_name,
            require_lossless=require_lossless
        )
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve: {str(e)}")


@router.post("/{item_id}/provenance")
async def create_provenance_chain(
    item_id: str,
    abstract_of: str
) -> Dict[str, Any]:
    """Create provenance chain linking abstract to source."""
    try:
        result = abstract_store.create_provenance_chain(item_id=item_id, abstract_of=abstract_of)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return {
            "success": True,
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create provenance: {str(e)}")


@router.get("/{item_id}/provenance")
async def get_provenance(item_id: str) -> Dict[str, Any]:
    """Get provenance chain for an item."""
    provenance = abstract_store.get_provenance(item_id)
    
    if "error" in provenance:
        raise HTTPException(status_code=404, detail=provenance["error"])
    
    return {
        "success": True,
        "provenance": provenance
    }


@router.get("/stats")
async def get_abstract_stats() -> Dict[str, Any]:
    """Get abstract store statistics."""
    stats = abstract_store.get_stats()
    
    return {
        "success": True,
        "stats": stats
    }

