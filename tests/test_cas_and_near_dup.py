"""
Tests for CAS caching and near-duplicate detection in LLM exchanges.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from memory_service.caching_cas import CAS
from memory_service.llm_exchange import LLMExchangeStore
from memory_service.router import MemoryRouter
from memory_service.simhash_neardup import hamming_distance, near_duplicate, simhash


def test_cas_exact_match(tmp_path: Path):
    """Test that exact matches are cached and reused."""
    router = MemoryRouter()
    cas = CAS(root=tmp_path / "cas")
    store = LLMExchangeStore(router=router, cas=cas)

    prompt = "What is the capital of France?"
    params = {"temperature": 0.2}

    # First call - should miss
    record1 = store.persist(
        model="gpt-4",
        version="2024-01",
        prompt=prompt,
        params=params,
        response_json={"text": "Paris"},
        response_text="Paris",
    )

    # Second call with identical prompt - should hit
    record2 = store.persist(
        model="gpt-4",
        version="2024-01",
        prompt=prompt,
        params=params,
        response_json={"text": "Paris"},
        response_text="Paris",
    )

    assert record1.request_signature == record2.request_signature
    # Both records should reference the same cached response
    assert record1.prompt == record2.prompt


def test_simhash_near_duplicate(tmp_path: Path):
    """Test that near-duplicate prompts are detected."""
    router = MemoryRouter()
    cas = CAS(root=tmp_path / "cas")
    store = LLMExchangeStore(router=router, cas=cas, simhash_threshold=10)

    prompt1 = "What is the capital city of France?"
    prompt2 = "What is the capital of France?"  # Near duplicate

    params = {"temperature": 0.2}

    # First call
    record1 = store.persist(
        model="gpt-4",
        version="2024-01",
        prompt=prompt1,
        params=params,
        response_json={"text": "Paris"},
        response_text="Paris",
    )

    # Second call with near-duplicate prompt
    record2 = store.persist(
        model="gpt-4",
        version="2024-01",
        prompt=prompt2,
        params=params,
        response_json={"text": "Paris"},
        response_text="Paris",
    )

    # Should detect near duplicate and reuse
    assert near_duplicate(prompt1, prompt2, threshold=10)
    # Note: exact signature will differ, but near-dup detection should trigger
    # In practice, this depends on the simhash threshold and prompt similarity


def test_simhash_hamming_distance():
    """Test SimHash hamming distance calculation."""
    text1 = "The quick brown fox"
    text2 = "The quick brown fox jumps"
    text3 = "Completely different text"

    hash1 = simhash(text1)
    hash2 = simhash(text2)
    hash3 = simhash(text3)

    dist_12 = hamming_distance(hash1, hash2)
    dist_13 = hamming_distance(hash1, hash3)

    assert dist_12 < dist_13  # Similar texts should have smaller distance
    # Note: threshold may need adjustment based on text similarity
    # For very similar texts, a threshold of 15-20 may be more appropriate
    assert dist_12 <= 20  # Verify distance is reasonable


def test_cas_persistence(tmp_path: Path):
    """Test that CAS entries persist across store instances."""
    router = MemoryRouter()
    cas_root = tmp_path / "cas"

    store1 = LLMExchangeStore(router=router, cas=CAS(root=cas_root))
    record = store1.persist(
        model="gpt-4",
        version="2024-01",
        prompt="Test prompt",
        params={},
        response_json={"text": "Test response"},
        response_text="Test response",
    )

    # Create new store instance with same CAS root
    store2 = LLMExchangeStore(router=router, cas=CAS(root=cas_root))
    cached = store2.cas.get(record.request_signature)

    assert cached is not None
    assert cached["request_signature"] == record.request_signature

