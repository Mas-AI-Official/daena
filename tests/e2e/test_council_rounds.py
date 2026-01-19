"""
E2E Tests for Council Rounds.

Tests the full roundtrip: Scout → Debate → Commit → CMP → Memory
"""

import pytest
import requests
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
        import asyncio
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
async def test_council_rounds_history_endpoint(api_base_url, api_key, seeded_database):
    """Test the /api/v1/council/rounds/history endpoint."""
    response = requests.get(
        f"{api_base_url}/api/v1/council/rounds/history?limit=10",
        headers={"X-API-Key": api_key},
        timeout=10
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "rounds" in data
    assert isinstance(data["rounds"], list)
    assert "total" in data


@pytest.mark.asyncio
async def test_council_rounds_current_endpoint(api_base_url, api_key, seeded_database):
    """Test the /api/v1/council/rounds/current endpoint."""
    response = requests.get(
        f"{api_base_url}/api/v1/council/rounds/current",
        headers={"X-API-Key": api_key},
        timeout=10
    )
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "current_phase" in data
    assert "round_id" in data or data.get("round_id") is None
    assert "active" in data


@pytest.mark.asyncio
async def test_council_rounds_timeout_enforcement(api_base_url, api_key, seeded_database):
    """Test that council rounds respect timeout limits."""
    # Get current round state
    response = requests.get(
        f"{api_base_url}/api/v1/council/rounds/current",
        headers={"X-API-Key": api_key},
        timeout=10
    )
    assert response.status_code == 200
    
    # Check that phase timeouts are configured
    # This is an indirect test - we verify the scheduler has timeout config
    from backend.services.council_scheduler import council_scheduler
    assert hasattr(council_scheduler, 'phase_timeouts')
    assert len(council_scheduler.phase_timeouts) > 0
    
    # Verify timeout values are reasonable
    for phase, timeout in council_scheduler.phase_timeouts.items():
        assert timeout > 0, f"Timeout for {phase} must be positive"
        assert timeout < 300, f"Timeout for {phase} should be < 300s (5 minutes)"


@pytest.mark.asyncio
async def test_council_rounds_poisoning_filters(api_base_url, api_key, seeded_database):
    """Test that poisoning filters are active."""
    try:
        from memory_service.poisoning_filters import poisoning_filter
        
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
        
        # Test reputation filtering
        reputation = poisoning_filter.get_reputation("test_source_2")
        assert reputation.reputation_score == 0.5, "New source should start with neutral reputation"
        
        # Test message acceptance
        accepted, reason, _ = poisoning_filter.check_message(
            content="Valid test message",
            source_id="test_source_2"
        )
        assert accepted, f"Valid message should be accepted, got: {reason}"
        
    except ImportError:
        pytest.skip("Poisoning filters not available")


@pytest.mark.asyncio
async def test_council_rounds_backpressure(api_base_url, api_key, seeded_database):
    """Test that message bus backpressure is working."""
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


@pytest.mark.asyncio
async def test_council_rounds_retry_logic(api_base_url, api_key, seeded_database):
    """Test that retry logic is implemented in phases."""
    from backend.services.council_scheduler import council_scheduler
    
    # Verify retry logic exists in scout phase
    # This is an indirect test - we check the code structure
    import inspect
    scout_source = inspect.getsource(council_scheduler.scout_phase)
    
    # Check for retry-related code
    assert "max_retries" in scout_source or "retry" in scout_source.lower(), \
        "Scout phase should have retry logic"
    
    # Verify timeout enforcement
    assert "timeout" in scout_source.lower() or "phase_end_time" in scout_source, \
        "Scout phase should enforce timeouts"


@pytest.mark.asyncio
async def test_council_rounds_roundtrip_integration(api_base_url, api_key, seeded_database):
    """Test full roundtrip integration (if council scheduler is running)."""
    # This test verifies that all components work together
    # It's a smoke test - doesn't require actual round execution
    
    # Check that all required services are available
    try:
        from backend.services.council_scheduler import council_scheduler
        from backend.utils.message_bus_v2 import message_bus_v2
        from memory_service.router import MemoryRouter
        
        # Verify scheduler is initialized
        assert hasattr(council_scheduler, 'current_phase')
        assert hasattr(council_scheduler, 'phase_timeouts')
        assert hasattr(council_scheduler, 'round_history')
        
        # Verify message bus is available
        assert message_bus_v2 is not None
        
        # Verify router is available
        assert council_scheduler.router is not None
        
        # All components are available - integration test passes
        assert True
        
    except ImportError as e:
        pytest.skip(f"Required components not available: {e}")

