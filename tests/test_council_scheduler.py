"""
Tests for Council Scheduler with phase-locked rounds.
"""

from __future__ import annotations

import pytest

from backend.services.council_scheduler import CouncilScheduler, CouncilPhase


@pytest.mark.asyncio
async def test_council_round_execution():
    """Test complete council round execution."""
    scheduler = CouncilScheduler()
    await scheduler.start()
    
    try:
        # Execute a council round
        round_summary = await scheduler.council_tick("engineering", "Test topic")
        
        assert round_summary is not None
        assert round_summary["department"] == "engineering"
        assert round_summary["topic"] == "Test topic"
        assert "scout" in round_summary
        assert "debate" in round_summary
        assert "commit" in round_summary
        assert round_summary["duration_sec"] > 0
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_scout_phase():
    """Test scout phase execution."""
    scheduler = CouncilScheduler()
    await scheduler.start()
    
    try:
        scout_results = await scheduler.scout_phase("engineering", "Test topic")
        
        assert scout_results is not None
        assert "summaries" in scout_results
        assert "duration_sec" in scout_results
        assert isinstance(scout_results["summaries"], list)
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_debate_phase():
    """Test debate phase execution."""
    scheduler = CouncilScheduler()
    await scheduler.start()
    
    try:
        scout_results = {"summaries": []}
        debate_results = await scheduler.debate_phase("engineering", "Test topic", scout_results)
        
        assert debate_results is not None
        assert "drafts" in debate_results
        assert "duration_sec" in debate_results
        assert isinstance(debate_results["drafts"], list)
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_commit_phase():
    """Test commit phase execution."""
    scheduler = CouncilScheduler()
    await scheduler.start()
    
    try:
        debate_results = {
            "drafts": [
                {
                    "advisor_id": "advisor_1",
                    "draft": "Test action",
                    "confidence": 0.8
                }
            ]
        }
        
        commit_results = await scheduler.commit_phase("engineering", "Test topic", debate_results)
        
        assert commit_results is not None
        assert "committed" in commit_results
        assert "duration_sec" in commit_results
    finally:
        await scheduler.stop()


def test_get_ring_number():
    """Test ring number calculation."""
    scheduler = CouncilScheduler()
    
    assert scheduler._get_ring_number("engineering") == 1
    assert scheduler._get_ring_number("finance") == 5
    assert scheduler._get_ring_number("unknown") == 1  # Default


def test_get_stats():
    """Test scheduler statistics."""
    scheduler = CouncilScheduler()
    
    stats = scheduler.get_stats()
    
    assert "current_phase" in stats
    assert "total_rounds" in stats
    assert "running" in stats
    assert stats["current_phase"] == CouncilPhase.IDLE.value

