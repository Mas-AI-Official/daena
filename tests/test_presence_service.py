"""
Tests for Presence Service.
"""

from __future__ import annotations

import pytest
import asyncio
import time

from backend.services.presence_service import (
    PresenceService,
    PresenceState,
    PresenceBeacon
)


@pytest.fixture
def presence_service():
    """Create a presence service instance."""
    return PresenceService(beacon_interval=0.1, heartbeat_timeout=0.5)


@pytest.mark.asyncio
async def test_register_cell(presence_service):
    """Test registering a cell."""
    await presence_service.start()
    
    try:
        result = await presence_service.register_cell(
            cell_id="cell_A1",
            department="engineering",
            neighbors=["cell_A2", "cell_A3"]
        )
        
        assert result["status"] == "registered"
        assert result["cell_id"] == "cell_A1"
        assert presence_service.cell_states["cell_A1"] == PresenceState.ONLINE
    finally:
        await presence_service.stop()


@pytest.mark.asyncio
async def test_unregister_cell(presence_service):
    """Test unregistering a cell."""
    await presence_service.start()
    
    try:
        await presence_service.register_cell("cell_B1", "product")
        result = await presence_service.unregister_cell("cell_B1")
        
        assert result["status"] == "unregistered"
        assert presence_service.cell_states["cell_B1"] == PresenceState.OFFLINE
    finally:
        await presence_service.stop()


@pytest.mark.asyncio
async def test_beacon_broadcast(presence_service):
    """Test beacon broadcast."""
    await presence_service.start()
    
    try:
        await presence_service.register_cell("cell_C1", "sales")
        
        # Wait for beacon
        await asyncio.sleep(0.2)
        
        beacon = presence_service.cell_beacons.get("cell_C1")
        assert beacon is not None
        assert beacon.cell_id == "cell_C1"
        assert beacon.state in [PresenceState.ONLINE, PresenceState.BUSY, PresenceState.OVERLOADED]
    finally:
        await presence_service.stop()


@pytest.mark.asyncio
async def test_handle_beacon(presence_service):
    """Test handling incoming beacon."""
    await presence_service.start()
    
    try:
        beacon_data = {
            "cell_id": "cell_D1",
            "department": "marketing",
            "state": "online",
            "capacity": 0.8,
            "load": 0.2,
            "neighbors": ["cell_D2"],
            "timestamp": time.time()
        }
        
        await presence_service.handle_beacon(beacon_data, "presence_cell_D1")
        
        assert presence_service.cell_states["cell_D1"] == PresenceState.ONLINE
        assert "cell_D1" in presence_service.cell_beacons
    finally:
        await presence_service.stop()


@pytest.mark.asyncio
async def test_heartbeat_timeout(presence_service):
    """Test heartbeat timeout detection."""
    await presence_service.start()
    
    try:
        await presence_service.register_cell("cell_E1", "finance")
        
        # Manually set old heartbeat
        presence_service.last_heartbeat["cell_E1"] = time.time() - 1.0
        
        # Check heartbeats
        offline = await presence_service.check_heartbeats()
        
        # Should not be offline yet (timeout is 0.5s, we set to 1.0s ago)
        assert "cell_E1" in offline or presence_service.cell_states["cell_E1"] == PresenceState.OFFLINE
    finally:
        await presence_service.stop()


def test_get_neighbors(presence_service):
    """Test getting neighbors."""
    presence_service.neighbor_map["cell_F1"] = {"cell_F2", "cell_F3", "cell_F4"}
    presence_service.cell_states["cell_F2"] = PresenceState.ONLINE
    presence_service.cell_states["cell_F3"] = PresenceState.BUSY
    presence_service.cell_states["cell_F4"] = PresenceState.OFFLINE
    
    neighbors = presence_service.get_neighbors("cell_F1")
    assert len(neighbors) == 3
    
    online_neighbors = presence_service.get_online_neighbors("cell_F1")
    assert len(online_neighbors) == 1
    assert "cell_F2" in online_neighbors


def test_adaptive_fanout(presence_service):
    """Test adaptive fanout calculation."""
    presence_service.neighbor_map["cell_G1"] = {"cell_G2", "cell_G3", "cell_G4", "cell_G5", "cell_G6"}
    
    # All online
    for nid in presence_service.neighbor_map["cell_G1"]:
        presence_service.cell_states[nid] = PresenceState.ONLINE
    
    fanout = presence_service.get_adaptive_fanout("cell_G1", base_fanout=6)
    assert fanout == 5  # Should be limited by available neighbors
    
    # Many busy
    presence_service.cell_states["cell_G2"] = PresenceState.BUSY
    presence_service.cell_states["cell_G3"] = PresenceState.OVERLOADED
    presence_service.cell_states["cell_G4"] = PresenceState.BUSY
    
    fanout = presence_service.get_adaptive_fanout("cell_G1", base_fanout=6)
    assert fanout < 6  # Should be reduced


def test_get_cell_presence(presence_service):
    """Test getting cell presence information."""
    presence_service.cell_states["cell_H1"] = PresenceState.ONLINE
    presence_service.neighbor_map["cell_H1"] = {"cell_H2", "cell_H3"}
    presence_service.last_heartbeat["cell_H1"] = time.time()
    
    presence = presence_service.get_cell_presence("cell_H1")
    
    assert presence["cell_id"] == "cell_H1"
    assert presence["state"] == "online"
    assert len(presence["neighbors"]) == 2


def test_get_stats(presence_service):
    """Test getting statistics."""
    presence_service.cell_states["cell_I1"] = PresenceState.ONLINE
    presence_service.cell_states["cell_I2"] = PresenceState.BUSY
    presence_service.cell_states["cell_I3"] = PresenceState.OFFLINE
    
    stats = presence_service.get_stats()
    
    assert stats["total_cells"] == 3
    assert stats["online_cells"] == 1
    assert stats["busy_cells"] == 1
    assert stats["offline_cells"] == 1

