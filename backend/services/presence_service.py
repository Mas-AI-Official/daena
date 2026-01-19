"""
Presence Service for Hex-Mesh Communication.

Implements presence beacons for neighbor state tracking:
- Periodic broadcasts to announce presence
- Neighbor state tracking (online/offline/busy)
- Adaptive fanout based on load
- Heartbeat monitoring
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from enum import Enum

from backend.utils.message_bus_v2 import message_bus_v2
from backend.utils.backpressure import backpressure_manager

logger = logging.getLogger(__name__)


class PresenceState(Enum):
    """Presence state of a cell/agent."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    OVERLOADED = "overloaded"
    UNKNOWN = "unknown"


@dataclass
class PresenceBeacon:
    """A presence beacon message."""
    cell_id: str
    department: str
    state: PresenceState
    capacity: float  # 0.0 to 1.0
    load: float  # Current load (0.0 to 1.0)
    neighbors: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, any] = field(default_factory=dict)


class PresenceService:
    """
    Manages presence beacons for neighbor state tracking.
    
    Features:
    - Periodic broadcasts (every N seconds)
    - Neighbor state tracking
    - Adaptive fanout based on load
    - Heartbeat monitoring
    """
    
    def __init__(
        self,
        beacon_interval: float = 5.0,
        heartbeat_timeout: float = 15.0,
        max_neighbors: int = 6
    ):
        """
        Initialize presence service.
        
        Args:
            beacon_interval: Seconds between beacons
            heartbeat_timeout: Seconds before marking neighbor as offline
            max_neighbors: Maximum neighbors to track per cell
        """
        self.beacon_interval = beacon_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.max_neighbors = max_neighbors
        
        self.cell_states: Dict[str, PresenceState] = defaultdict(lambda: PresenceState.UNKNOWN)
        self.cell_beacons: Dict[str, PresenceBeacon] = {}
        self.neighbor_map: Dict[str, Set[str]] = defaultdict(set)  # cell_id -> set of neighbor_ids
        self.last_heartbeat: Dict[str, float] = {}
        self._running = False
        self._beacon_tasks: Dict[str, asyncio.Task] = {}
        
    async def start(self):
        """Start the presence service."""
        self._running = True
        await message_bus_v2.start()
        logger.info(f"Presence service started (beacon_interval={self.beacon_interval}s)")
    
    async def stop(self):
        """Stop the presence service."""
        self._running = False
        
        # Cancel all beacon tasks
        for task in self._beacon_tasks.values():
            task.cancel()
        self._beacon_tasks.clear()
        
        logger.info("Presence service stopped")
    
    async def register_cell(
        self,
        cell_id: str,
        department: str,
        neighbors: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Register a cell for presence tracking.
        
        Starts periodic beacon broadcasts.
        """
        if cell_id in self._beacon_tasks:
            return {
                "status": "already_registered",
                "cell_id": cell_id
            }
        
        self.cell_states[cell_id] = PresenceState.ONLINE
        self.last_heartbeat[cell_id] = time.time()
        
        if neighbors:
            self.neighbor_map[cell_id] = set(neighbors[:self.max_neighbors])
        
        # Start beacon task
        task = asyncio.create_task(self._beacon_loop(cell_id, department))
        self._beacon_tasks[cell_id] = task
        
        logger.info(f"Registered cell {cell_id} in {department}")
        
        return {
            "status": "registered",
            "cell_id": cell_id,
            "department": department,
            "neighbors": list(self.neighbor_map[cell_id])
        }
    
    async def unregister_cell(self, cell_id: str) -> Dict[str, any]:
        """Unregister a cell and stop beacons."""
        if cell_id in self._beacon_tasks:
            self._beacon_tasks[cell_id].cancel()
            del self._beacon_tasks[cell_id]
        
        self.cell_states[cell_id] = PresenceState.OFFLINE
        
        # Remove from neighbor maps
        for neighbors in self.neighbor_map.values():
            neighbors.discard(cell_id)
        
        if cell_id in self.neighbor_map:
            del self.neighbor_map[cell_id]
        
        if cell_id in self.cell_beacons:
            del self.cell_beacons[cell_id]
        
        logger.info(f"Unregistered cell {cell_id}")
        
        return {
            "status": "unregistered",
            "cell_id": cell_id
        }
    
    async def _beacon_loop(self, cell_id: str, department: str):
        """Periodic beacon broadcast loop."""
        while self._running:
            try:
                # Get current state and capacity
                bp_status = backpressure_manager.get_cell_status(cell_id)
                capacity = bp_status.get("capacity", 1.0)
                load = 1.0 - capacity
                
                # Determine state based on capacity
                if capacity < 0.1:
                    state = PresenceState.OVERLOADED
                elif capacity < 0.3:
                    state = PresenceState.BUSY
                else:
                    state = PresenceState.ONLINE
                
                self.cell_states[cell_id] = state
                
                # Create beacon
                beacon = PresenceBeacon(
                    cell_id=cell_id,
                    department=department,
                    state=state,
                    capacity=capacity,
                    load=load,
                    neighbors=list(self.neighbor_map.get(cell_id, set())),
                    metadata={
                        "pending_needs": bp_status.get("pending_needs", 0),
                        "pending_offers": bp_status.get("pending_offers", 0)
                    }
                )
                
                self.cell_beacons[cell_id] = beacon
                self.last_heartbeat[cell_id] = time.time()
                
                # Publish beacon to cell topic
                await message_bus_v2.publish_to_cell(
                    department=department,
                    cell_id=cell_id,
                    content={
                        "type": "presence_beacon",
                        "beacon": {
                            "cell_id": beacon.cell_id,
                            "state": beacon.state.value,
                            "capacity": beacon.capacity,
                            "load": beacon.load,
                            "neighbors": beacon.neighbors,
                            "timestamp": beacon.timestamp
                        }
                    },
                    sender=f"presence_{cell_id}",
                    metadata=beacon.metadata
                )
                
                # Also publish to ring topic for neighbor discovery
                ring_number = self._get_ring_number(department)
                await message_bus_v2.publish_to_ring(
                    ring_number=ring_number,
                    content={
                        "type": "presence_beacon",
                        "cell_id": cell_id,
                        "department": department,
                        "state": state.value,
                        "capacity": capacity
                    },
                    sender=f"presence_{cell_id}"
                )
                
                await asyncio.sleep(self.beacon_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in beacon loop for {cell_id}: {e}")
                await asyncio.sleep(self.beacon_interval)
    
    async def handle_beacon(self, beacon_data: Dict[str, any], sender: str):
        """
        Handle incoming presence beacon.
        
        Updates neighbor state and heartbeat.
        """
        cell_id = beacon_data.get("cell_id") or sender.replace("presence_", "")
        
        if not cell_id:
            return
        
        # Update heartbeat
        self.last_heartbeat[cell_id] = time.time()
        
        # Update state
        state_str = beacon_data.get("state", "unknown")
        try:
            state = PresenceState(state_str)
            self.cell_states[cell_id] = state
        except ValueError:
            self.cell_states[cell_id] = PresenceState.UNKNOWN
        
        # Update beacon cache
        beacon = PresenceBeacon(
            cell_id=cell_id,
            department=beacon_data.get("department", "unknown"),
            state=self.cell_states[cell_id],
            capacity=beacon_data.get("capacity", 0.0),
            load=beacon_data.get("load", 1.0),
            neighbors=beacon_data.get("neighbors", []),
            timestamp=beacon_data.get("timestamp", time.time()),
            metadata=beacon_data.get("metadata", {})
        )
        
        self.cell_beacons[cell_id] = beacon
        
        logger.debug(f"Received beacon from {cell_id}, state={state.value}")
    
    async def check_heartbeats(self):
        """Check heartbeats and mark offline neighbors."""
        current_time = time.time()
        offline_cells = []
        
        for cell_id, last_time in self.last_heartbeat.items():
            elapsed = current_time - last_time
            if elapsed > self.heartbeat_timeout:
                if self.cell_states[cell_id] != PresenceState.OFFLINE:
                    self.cell_states[cell_id] = PresenceState.OFFLINE
                    offline_cells.append(cell_id)
                    logger.warning(f"Cell {cell_id} marked offline (no heartbeat for {elapsed:.1f}s)")
        
        return offline_cells
    
    def get_neighbors(self, cell_id: str, state_filter: Optional[PresenceState] = None) -> List[str]:
        """
        Get neighbors of a cell, optionally filtered by state.
        
        Returns:
            List of neighbor cell IDs
        """
        neighbors = list(self.neighbor_map.get(cell_id, set()))
        
        if state_filter:
            neighbors = [
                nid for nid in neighbors
                if self.cell_states.get(nid) == state_filter
            ]
        
        return neighbors
    
    def get_online_neighbors(self, cell_id: str) -> List[str]:
        """Get online neighbors of a cell."""
        return self.get_neighbors(cell_id, PresenceState.ONLINE)
    
    def get_adaptive_fanout(self, cell_id: str, base_fanout: int = 6) -> int:
        """
        Calculate adaptive fanout based on neighbor states.
        
        Returns:
            Number of neighbors to contact (reduced if many are busy/overloaded)
        """
        neighbors = self.get_neighbors(cell_id)
        
        if not neighbors:
            return base_fanout
        
        # Count available neighbors
        available = sum(
            1 for nid in neighbors
            if self.cell_states.get(nid) in [PresenceState.ONLINE]
        )
        
        # Count busy neighbors
        busy = sum(
            1 for nid in neighbors
            if self.cell_states.get(nid) in [PresenceState.BUSY, PresenceState.OVERLOADED]
        )
        
        # Reduce fanout if many neighbors are busy
        if busy > available:
            fanout = max(1, base_fanout - busy // 2)
        else:
            fanout = min(base_fanout, available)
        
        return fanout
    
    def get_cell_presence(self, cell_id: str) -> Dict[str, any]:
        """Get presence information for a cell."""
        beacon = self.cell_beacons.get(cell_id)
        state = self.cell_states.get(cell_id, PresenceState.UNKNOWN)
        last_heartbeat = self.last_heartbeat.get(cell_id)
        
        return {
            "cell_id": cell_id,
            "state": state.value,
            "last_heartbeat": last_heartbeat,
            "beacon": {
                "capacity": beacon.capacity if beacon else 0.0,
                "load": beacon.load if beacon else 1.0,
                "neighbors": beacon.neighbors if beacon else [],
                "timestamp": beacon.timestamp if beacon else None
            } if beacon else None,
            "neighbors": list(self.neighbor_map.get(cell_id, set())),
            "online_neighbors": self.get_online_neighbors(cell_id),
            "adaptive_fanout": self.get_adaptive_fanout(cell_id)
        }
    
    def get_all_presence(self) -> Dict[str, Dict[str, any]]:
        """Get presence information for all cells."""
        return {
            cell_id: self.get_cell_presence(cell_id)
            for cell_id in self.cell_states.keys()
        }
    
    def get_stats(self) -> Dict[str, any]:
        """Get presence service statistics."""
        total_cells = len(self.cell_states)
        online_cells = sum(1 for s in self.cell_states.values() if s == PresenceState.ONLINE)
        busy_cells = sum(1 for s in self.cell_states.values() if s == PresenceState.BUSY)
        overloaded_cells = sum(1 for s in self.cell_states.values() if s == PresenceState.OVERLOADED)
        offline_cells = sum(1 for s in self.cell_states.values() if s == PresenceState.OFFLINE)
        
        return {
            "total_cells": total_cells,
            "online_cells": online_cells,
            "busy_cells": busy_cells,
            "overloaded_cells": overloaded_cells,
            "offline_cells": offline_cells,
            "active_beacons": len(self._beacon_tasks),
            "beacon_interval": self.beacon_interval,
            "heartbeat_timeout": self.heartbeat_timeout
        }
    
    def _get_ring_number(self, department: str) -> int:
        """Get ring number for a department."""
        dept_rings = {
            "engineering": 1,
            "product": 2,
            "sales": 3,
            "marketing": 4,
            "finance": 5,
            "hr": 6,
            "legal": 7,
            "customer": 8
        }
        return dept_rings.get(department, 1)


# Global instance
presence_service = PresenceService()

