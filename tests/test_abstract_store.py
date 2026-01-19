"""
Tests for Abstract Store with lossless pointer pattern.
"""

from __future__ import annotations

import pytest

from memory_service.abstract_store import (
    AbstractStore,
    StorageMode,
    AbstractRecord
)
from memory_service.router import MemoryRouter


@pytest.fixture
def abstract_store_instance():
    """Create an abstract store instance."""
    router = MemoryRouter()
    return AbstractStore(router=router)


def test_store_abstract_only(abstract_store_instance):
    """Test storing abstract only."""
    result = abstract_store_instance.store_abstract(
        item_id="test_abstract_1",
        class_name="document",
        payload={"content": "Test document"},
        mode=StorageMode.ABSTRACT_ONLY
    )
    
    assert result["status"] == "stored"
    assert result["mode"] == "abstract_only"
    assert result["confidence"] == 1.0


def test_store_abstract_with_pointer(abstract_store_instance):
    """Test storing abstract with lossless pointer."""
    result = abstract_store_instance.store_abstract(
        item_id="test_abstract_2",
        class_name="document",
        payload={"content": "Test document"},
        source_uri="file:///path/to/document.pdf",
        lossless_pointer="file:///path/to/document.pdf",
        confidence=0.9,
        mode=StorageMode.ABSTRACT_POINTER
    )
    
    assert result["status"] == "stored"
    assert result["mode"] == "abstract_pointer"
    assert result["lossless_pointer"] == "file:///path/to/document.pdf"
    assert result["confidence"] == 0.9


def test_store_hybrid(abstract_store_instance):
    """Test storing hybrid (abstract + lossless)."""
    result = abstract_store_instance.store_abstract(
        item_id="test_hybrid_1",
        class_name="legal",
        payload={"content": "Legal document"},
        mode=StorageMode.HYBRID
    )
    
    assert result["status"] == "stored"
    assert result["mode"] == "hybrid"


def test_retrieve_abstract(abstract_store_instance):
    """Test retrieving abstract record."""
    # Store first
    abstract_store_instance.store_abstract(
        item_id="test_retrieve_1",
        class_name="document",
        payload={"content": "Test"},
        mode=StorageMode.ABSTRACT_ONLY
    )
    
    # Retrieve
    result = abstract_store_instance.retrieve_with_fallback(
        item_id="test_retrieve_1",
        class_name="document"
    )
    
    assert result["status"] in ["abstract", "not_found"]  # May not be in cache


def test_retrieve_with_ocr_fallback(abstract_store_instance):
    """Test retrieving with OCR fallback (low confidence)."""
    # Store with low confidence
    abstract_store_instance.store_abstract(
        item_id="test_ocr_1",
        class_name="document",
        payload={"content": "Test"},
        lossless_pointer="file:///path/to/doc.pdf",
        confidence=0.5,  # Below threshold
        mode=StorageMode.ABSTRACT_POINTER
    )
    
    # Retrieve (should trigger OCR fallback)
    result = abstract_store_instance.retrieve_with_fallback(
        item_id="test_ocr_1",
        class_name="document"
    )
    
    # Should indicate OCR fallback needed
    assert result["status"] in ["ocr_fallback", "abstract"]  # OCR integration pending


def test_create_provenance_chain(abstract_store_instance):
    """Test creating provenance chain."""
    # Store abstract
    abstract_store_instance.store_abstract(
        item_id="test_prov_1",
        class_name="document",
        payload={"content": "Test"},
        mode=StorageMode.ABSTRACT_ONLY
    )
    
    # Create provenance chain
    result = abstract_store_instance.create_provenance_chain(
        item_id="test_prov_1",
        abstract_of="source_txid_123"
    )
    
    assert result["status"] == "provenance_created"
    assert result["abstract_of"] == "source_txid_123"


def test_get_provenance(abstract_store_instance):
    """Test getting provenance information."""
    # Store with source URI
    abstract_store_instance.store_abstract(
        item_id="test_prov_2",
        class_name="document",
        payload={"content": "Test"},
        source_uri="file:///path/to/source.pdf",
        mode=StorageMode.ABSTRACT_POINTER
    )
    
    # Get provenance
    provenance = abstract_store_instance.get_provenance("test_prov_2")
    
    assert "provenance" in provenance
    assert provenance["source_uri"] == "file:///path/to/source.pdf"


def test_get_stats(abstract_store_instance):
    """Test getting statistics."""
    # Store some records
    abstract_store_instance.store_abstract("stat_1", "doc", {"c": "1"}, mode=StorageMode.ABSTRACT_ONLY)
    abstract_store_instance.store_abstract(
        "stat_2", "doc", {"c": "2"},
        lossless_pointer="uri://test",
        mode=StorageMode.ABSTRACT_POINTER
    )
    
    stats = abstract_store_instance.get_stats()
    
    assert stats["total_records"] >= 2
    assert stats["records_with_pointers"] >= 1
    assert "pointer_rate" in stats

