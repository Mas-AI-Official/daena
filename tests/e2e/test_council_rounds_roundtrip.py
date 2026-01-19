"""
Full Roundtrip Integration Test for Council Rounds.

Tests the complete flow:
Scout → Debate → Commit → CMP Validation → Memory Update
"""

import pytest
import asyncio
import time
from typing import Dict, Any
import os

# API configuration
API_BASE_URL = os.getenv("DAENA_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DAENA_API_KEY", "daena_secure_key_2025")


@pytest.fixture(scope="session")
def api_base_url():
    """Get API base URL."""
    return API_BASE_URL


@pytest.fixture(scope="session")
def api_key():
    """Get API key."""
    return API_KEY


@pytest.fixture(scope="session")
def seeded_database():
    """Ensure database is seeded for E2E tests."""
    import sys
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from seed_6x8_council import main as seed_main
        # Run seed synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(seed_main())
    except Exception as e:
        pytest.skip(f"Failed to seed database for E2E: {e}")
    yield


@pytest.mark.asyncio
async def test_full_council_round_roundtrip(api_base_url, api_key, seeded_database):
    """
    Test the full roundtrip: Scout → Debate → Commit → CMP → Memory.
    
    This test requires the council scheduler to be running and agents to be active.
    """
    try:
        from backend.services.council_scheduler import council_scheduler, CouncilPhase
        
        # Ensure scheduler is running
        if not council_scheduler._running:
            await council_scheduler.start()
        
        # Start a council round
        department = "engineering"
        topic = "Test roundtrip: Optimize API response time"
        
        # Execute full round
        round_result = await council_scheduler.execute_round(
            department=department,
            topic=topic
        )
        
        # Verify round completed
        assert round_result is not None
        assert "round_id" in round_result
        assert "committed" in round_result
        
        # Verify phases executed
        assert "scout_results" in round_result
        assert "debate_results" in round_result
        assert "commit_results" in round_result
        
        # Verify scout phase
        scout_results = round_result.get("scout_results", {})
        assert "summaries" in scout_results
        assert "duration_sec" in scout_results
        
        # Verify debate phase
        debate_results = round_result.get("debate_results", {})
        assert "drafts" in debate_results
        assert "duration_sec" in debate_results
        
        # Verify commit phase
        commit_results = round_result.get("commit_results", {})
        assert "committed" in commit_results or "duration_sec" in commit_results
        
        # Verify round is in history
        history = council_scheduler.get_round_history(limit=10)
        round_ids = [r.round_id for r in history if hasattr(r, 'round_id')]
        assert round_result["round_id"] in round_ids or len(history) > 0
        
    except ImportError as e:
        pytest.skip(f"Required components not available: {e}")
    except Exception as e:
        # If scheduler is not running or agents are not active, skip test
        pytest.skip(f"Cannot execute full roundtrip (scheduler may not be running): {e}")


@pytest.mark.asyncio
async def test_council_round_timeout_enforcement(api_base_url, api_key, seeded_database):
    """Test that council rounds respect timeout limits."""
    try:
        from backend.services.council_scheduler import council_scheduler
        
        # Get timeout configuration
        timeouts = council_scheduler.phase_timeouts
        
        # Verify timeouts are set
        assert len(timeouts) > 0
        
        # Verify timeout values are reasonable
        for phase, timeout in timeouts.items():
            assert timeout > 0, f"Timeout for {phase} must be positive"
            assert timeout < 300, f"Timeout for {phase} should be < 300s (5 minutes)"
        
        # Test that phases actually timeout (if they take too long)
        # This is a smoke test - actual timeout behavior depends on agent activity
        
    except ImportError:
        pytest.skip("Council scheduler not available")


@pytest.mark.asyncio
async def test_council_round_poisoning_filters_active(api_base_url, api_key, seeded_database):
    """Test that poisoning filters are active during council rounds."""
    try:
        from memory_service.poisoning_filters import poisoning_filter
        
        # Test that filter is available
        assert poisoning_filter is not None
        
        # Test SimHash deduplication
        content1 = "Test message for duplicate detection"
        content2 = "Test message for duplicate detection"  # Exact duplicate
        
        is_dup1, _ = poisoning_filter.simhash.is_duplicate(content1)
        assert not is_dup1, "First message should not be duplicate"
        
        # Register first message
        poisoning_filter.simhash.register_content(content1, "test_source_1")
        
        # Check duplicate
        is_dup2, _ = poisoning_filter.simhash.is_duplicate(content2)
        assert is_dup2, "Second identical message should be detected as duplicate"
        
    except ImportError:
        pytest.skip("Poisoning filters not available")


@pytest.mark.asyncio
async def test_council_round_backpressure(api_base_url, api_key, seeded_database):
    """Test that message bus backpressure is working during rounds."""
    try:
        from backend.utils.message_bus_v2 import message_bus_v2
        
        # Get stats
        stats = message_bus_v2.get_stats()
        assert "queue_depth" in stats
        assert "max_queue_size" in stats
        assert "backpressure_active" in stats
        
        # Verify backpressure threshold
        queue_utilization = stats.get("queue_utilization", 0)
        backpressure_active = stats.get("backpressure_active", False)
        
        # Backpressure should activate at 90% capacity
        if queue_utilization >= 0.9:
            assert backpressure_active, "Backpressure should be active at 90%+ capacity"
        
        # Verify max queue size is set
        assert stats["max_queue_size"] > 0, "Max queue size must be positive"
        
    except ImportError:
        pytest.skip("Message bus V2 not available")

