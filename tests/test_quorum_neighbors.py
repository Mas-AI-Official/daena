"""
Tests for quorum neighbor validation (4/6 neighbor logic).
"""

from __future__ import annotations

import pytest

from backend.utils.quorum import QuorumManager, QuorumType


def test_local_quorum_neighbor_validation():
    """Test that LOCAL quorum only counts votes from neighbors."""
    manager = QuorumManager()
    
    # Set up cell with neighbors
    cell_id = "test_cell_1"
    neighbors = ["neighbor_1", "neighbor_2", "neighbor_3", "neighbor_4", "neighbor_5", "neighbor_6"]
    manager.set_cell_neighbors(cell_id, neighbors)
    
    # Start LOCAL quorum
    quorum_id = "test_quorum_1"
    result = manager.start_quorum(
        quorum_id=quorum_id,
        quorum_type=QuorumType.LOCAL,
        cell_id=cell_id
    )
    
    assert result["quorum_type"] == "local"
    assert result["required_votes"] == 4  # 4/6 neighbors
    assert result["neighbor_count"] == 6
    
    # Cast votes from neighbors (3 approve first, check status)
    for i in range(3):
        vote_result = manager.cast_vote(quorum_id, f"neighbor_{i+1}", True)
        assert vote_result["is_neighbor"] is True
    
    # Cast vote from non-neighbor (should not count)
    vote_result = manager.cast_vote(quorum_id, "non_neighbor_1", True)
    assert vote_result["is_neighbor"] is False
    
    # Check status before quorum is reached
    status = manager.get_quorum_status(quorum_id)
    assert status["approve_votes"] == 3  # Only neighbor votes counted
    assert status["quorum_reached"] is False  # Need 4, only have 3
    assert "non_neighbor_1" in status["invalid_voters"]
    
    # Cast 4th neighbor vote (reaches quorum, closes it)
    vote_result = manager.cast_vote(quorum_id, "neighbor_4", True)
    assert vote_result["quorum_reached"] is True  # 4/6 reached


def test_local_quorum_requires_4_neighbors():
    """Test that LOCAL quorum requires exactly 4/6 neighbor votes."""
    manager = QuorumManager()
    
    cell_id = "test_cell_2"
    neighbors = ["n1", "n2", "n3", "n4", "n5", "n6"]
    manager.set_cell_neighbors(cell_id, neighbors)
    
    quorum_id = "test_quorum_2"
    manager.start_quorum(quorum_id, QuorumType.LOCAL, cell_id=cell_id)
    
    # Cast 3 approve votes (not enough)
    for i in range(3):
        manager.cast_vote(quorum_id, f"n{i+1}", True)
    
    status = manager.get_quorum_status(quorum_id)
    assert status["approve_votes"] == 3
    assert status["quorum_reached"] is False  # Need 4, only have 3
    
    # Cast 1 more approve vote (now 4/6, quorum reached and closed)
    vote_result = manager.cast_vote(quorum_id, "n4", True)
    assert vote_result["quorum_reached"] is True  # 4/6 reached


def test_global_quorum_not_neighbor_aware():
    """Test that GLOBAL quorum doesn't require neighbors."""
    manager = QuorumManager()
    
    quorum_id = "test_quorum_3"
    manager.start_quorum(quorum_id, QuorumType.GLOBAL)
    
    # Cast vote from any cell (not neighbor-aware)
    vote_result = manager.cast_vote(quorum_id, "any_cell_1", True)
    assert vote_result["is_neighbor"] is True  # Always true for non-LOCAL
    assert vote_result["quorum_reached"] is True  # GLOBAL only needs 1 vote


def test_quorum_without_neighbors_set():
    """Test LOCAL quorum fallback when neighbors not set."""
    manager = QuorumManager()
    
    quorum_id = "test_quorum_4"
    manager.start_quorum(quorum_id, QuorumType.LOCAL, cell_id="unknown_cell")
    
    # Cast votes (should count all since neighbors not set)
    for i in range(3):
        manager.cast_vote(quorum_id, f"voter_{i+1}", True)
    
    status = manager.get_quorum_status(quorum_id)
    assert status["approve_votes"] == 3
    assert status["quorum_reached"] is False  # Need 4
    
    # Cast 4th vote (reaches quorum)
    vote_result = manager.cast_vote(quorum_id, "voter_4", True)
    assert vote_result["quorum_reached"] is True  # Falls back to counting all votes

