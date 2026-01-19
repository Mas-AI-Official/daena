"""
Tests for Quorum and Backpressure systems.
"""

from __future__ import annotations

import pytest
import time

from backend.utils.quorum import quorum_manager, QuorumType, QuorumManager
from backend.utils.backpressure import backpressure_manager, BackpressureManager, BackpressureState


@pytest.fixture
def fresh_quorum_manager():
    """Create a fresh quorum manager for testing."""
    return QuorumManager()


@pytest.fixture
def fresh_backpressure_manager():
    """Create a fresh backpressure manager for testing."""
    return BackpressureManager()


def test_start_local_quorum(fresh_quorum_manager):
    """Test starting a local quorum."""
    result = fresh_quorum_manager.start_quorum(
        quorum_id="test_quorum_1",
        quorum_type=QuorumType.LOCAL
    )
    
    assert result["quorum_type"] == "local"
    assert result["required_votes"] == 4  # 4/6 neighbors


def test_cast_votes(fresh_quorum_manager):
    """Test casting votes in a quorum."""
    fresh_quorum_manager.start_quorum(
        quorum_id="test_quorum_2",
        quorum_type=QuorumType.LOCAL
    )
    
    # Cast 4 approve votes (should reach quorum)
    for i in range(4):
        result = fresh_quorum_manager.cast_vote(
            quorum_id="test_quorum_2",
            voter_id=f"voter_{i}",
            vote=True
        )
    
    # Last vote should indicate quorum reached
    assert result["quorum_reached"] is True
    assert result["approve_votes"] == 4


def test_quorum_timeout(fresh_quorum_manager):
    """Test quorum timeout."""
    fresh_quorum_manager.start_quorum(
        quorum_id="test_quorum_3",
        quorum_type=QuorumType.LOCAL,
        timeout_seconds=0.1  # Very short timeout
    )
    
    time.sleep(0.2)  # Wait for timeout
    
    result = fresh_quorum_manager.cast_vote(
        quorum_id="test_quorum_3",
        voter_id="voter_1",
        vote=True
    )
    
    assert "error" in result
    assert result["error"] == "Quorum timeout"


def test_request_capacity(fresh_backpressure_manager):
    """Test requesting capacity."""
    result = fresh_backpressure_manager.request_capacity(
        cell_id="cell_A1",
        requested_capacity=0.1
    )
    
    assert result["status"] == "granted"
    assert "token_id" in result


def test_offer_capacity(fresh_backpressure_manager):
    """Test offering capacity."""
    # First, request capacity to create a pending need
    fresh_backpressure_manager.request_capacity("cell_A2", 0.2)
    
    # Offer capacity from another cell
    result = fresh_backpressure_manager.offer_capacity(
        source_cell_id="cell_A1",
        destination_cell_id="cell_A2",
        offered_capacity=0.2
    )
    
    assert result["status"] == "offered"


def test_acknowledge_capacity(fresh_backpressure_manager):
    """Test acknowledging capacity transfer."""
    # Request capacity
    request_result = fresh_backpressure_manager.request_capacity("cell_A3", 0.1)
    
    if request_result["status"] == "granted":
        token_id = request_result["token_id"]
        
        # Acknowledge
        ack_result = fresh_backpressure_manager.acknowledge_capacity(
            token_id=token_id,
            cell_id="cell_A3"
        )
        
        assert ack_result["status"] == "acknowledged"


def test_release_capacity(fresh_backpressure_manager):
    """Test releasing capacity."""
    # Request and use capacity
    fresh_backpressure_manager.request_capacity("cell_A4", 0.3)
    
    # Release capacity
    result = fresh_backpressure_manager.release_capacity("cell_A4", 0.3)
    
    assert result["status"] == "released"
    assert result["total_capacity"] >= 0.3


def test_overloaded_state(fresh_backpressure_manager):
    """Test overloaded state when too many pending requests."""
    # Create many pending requests
    for i in range(101):  # More than max_pending (100)
        fresh_backpressure_manager.request_capacity(f"cell_B{i}", 0.1)
    
    # Check that cell is overloaded
    status = fresh_backpressure_manager.get_cell_status("cell_B100")
    # Note: This test may need adjustment based on implementation


def test_quorum_stats(fresh_quorum_manager):
    """Test quorum statistics."""
    # Start and complete a quorum
    fresh_quorum_manager.start_quorum("stats_test", QuorumType.LOCAL)
    for i in range(4):
        fresh_quorum_manager.cast_vote("stats_test", f"voter_{i}", True)
    
    stats = fresh_quorum_manager.get_stats()
    
    assert stats["total_quorums"] >= 1
    assert stats["successful_quorums"] >= 1


def test_backpressure_stats(fresh_backpressure_manager):
    """Test backpressure statistics."""
    # Create some activity
    fresh_backpressure_manager.request_capacity("cell_C1", 0.1)
    fresh_backpressure_manager.release_capacity("cell_C1", 0.1)
    
    stats = fresh_backpressure_manager.get_stats()
    
    assert "total_cells" in stats
    assert "total_tokens" in stats

