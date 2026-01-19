"""
Backpressure System for Hex-Mesh Communication.

Implements token-based backpressure to prevent message floods:
- need: Request for processing capacity
- offer: Offer of processing capacity
- ack: Acknowledgment of capacity transfer
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class BackpressureState(Enum):
    """Backpressure state."""
    IDLE = "idle"
    NEED = "need"  # Requesting capacity
    OFFER = "offer"  # Offering capacity
    ACK = "ack"  # Acknowledged capacity transfer
    OVERLOADED = "overloaded"  # Overloaded, rejecting requests


@dataclass
class CapacityToken:
    """A capacity token for backpressure."""
    token_id: str
    source: str  # Cell/agent ID offering capacity
    destination: str  # Cell/agent ID requesting capacity
    capacity: float  # Amount of capacity (0.0 to 1.0)
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class BackpressureManager:
    """
    Manages backpressure using token-based flow control.
    
    Prevents message floods by:
    1. Cells request capacity (need)
    2. Neighbors offer capacity (offer)
    3. Capacity transfer acknowledged (ack)
    4. Messages only sent when capacity available
    """
    
    def __init__(self):
        self.cell_states: Dict[str, BackpressureState] = defaultdict(lambda: BackpressureState.IDLE)
        self.cell_capacity: Dict[str, float] = defaultdict(lambda: 1.0)  # 0.0 to 1.0
        self.pending_needs: Dict[str, deque] = defaultdict(deque)  # cell_id -> deque of need requests
        self.pending_offers: Dict[str, deque] = defaultdict(deque)  # cell_id -> deque of offer requests
        self.active_tokens: Dict[str, CapacityToken] = {}
        self.token_history: List[CapacityToken] = []
        self.max_history = 1000
        self.max_pending = 100  # Max pending requests per cell
        
    def request_capacity(
        self,
        cell_id: str,
        requested_capacity: float = 0.1,
        timeout_seconds: float = 5.0
    ) -> Dict[str, any]:
        """
        Request capacity (need).
        
        Returns:
            Dict with request status and token if available
        """
        if cell_id not in self.cell_states:
            self.cell_states[cell_id] = BackpressureState.IDLE
        
        current_state = self.cell_states[cell_id]
        
        # Check if already overloaded
        if current_state == BackpressureState.OVERLOADED:
            return {
                "status": "overloaded",
                "cell_id": cell_id,
                "message": "Cell is overloaded, request rejected"
            }
        
        # Check if cell has available capacity
        if self.cell_capacity[cell_id] >= requested_capacity:
            # Cell has capacity, grant immediately
            self.cell_capacity[cell_id] -= requested_capacity
            token = CapacityToken(
                token_id=f"{cell_id}_{int(time.time() * 1000)}",
                source=cell_id,
                destination=cell_id,
                capacity=requested_capacity
            )
            self.active_tokens[token.token_id] = token
            
            logger.info(f"Cell {cell_id} granted capacity {requested_capacity} (self)")
            
            return {
                "status": "granted",
                "cell_id": cell_id,
                "token_id": token.token_id,
                "capacity": requested_capacity,
                "source": "self"
            }
        
        # Need to request from neighbors
        self.cell_states[cell_id] = BackpressureState.NEED
        
        need_request = {
            "cell_id": cell_id,
            "requested_capacity": requested_capacity,
            "timeout": timeout_seconds,
            "timestamp": time.time()
        }
        
        # Add to pending needs
        if len(self.pending_needs[cell_id]) < self.max_pending:
            self.pending_needs[cell_id].append(need_request)
        else:
            # Too many pending requests, mark as overloaded
            self.cell_states[cell_id] = BackpressureState.OVERLOADED
            return {
                "status": "overloaded",
                "cell_id": cell_id,
                "message": "Too many pending requests"
            }
        
        logger.info(f"Cell {cell_id} requesting capacity {requested_capacity} from neighbors")
        
        return {
            "status": "pending",
            "cell_id": cell_id,
            "requested_capacity": requested_capacity,
            "pending_requests": len(self.pending_needs[cell_id])
        }
    
    def offer_capacity(
        self,
        source_cell_id: str,
        destination_cell_id: str,
        offered_capacity: float = 0.1
    ) -> Dict[str, any]:
        """
        Offer capacity to a neighbor (offer).
        
        Returns:
            Dict with offer status
        """
        if source_cell_id not in self.cell_states:
            self.cell_states[source_cell_id] = BackpressureState.IDLE
        
        # Check if source has capacity to offer
        if self.cell_capacity[source_cell_id] < offered_capacity:
            return {
                "status": "insufficient_capacity",
                "source": source_cell_id,
                "destination": destination_cell_id,
                "available": self.cell_capacity[source_cell_id],
                "requested": offered_capacity
            }
        
        # Check if destination has pending needs
        if destination_cell_id not in self.pending_needs or not self.pending_needs[destination_cell_id]:
            return {
                "status": "no_pending_need",
                "source": source_cell_id,
                "destination": destination_cell_id
            }
        
        # Create offer
        offer = {
            "source": source_cell_id,
            "destination": destination_cell_id,
            "capacity": offered_capacity,
            "timestamp": time.time()
        }
        
        self.pending_offers[destination_cell_id].append(offer)
        self.cell_states[source_cell_id] = BackpressureState.OFFER
        
        logger.info(f"Cell {source_cell_id} offering capacity {offered_capacity} to {destination_cell_id}")
        
        return {
            "status": "offered",
            "source": source_cell_id,
            "destination": destination_cell_id,
            "capacity": offered_capacity
        }
    
    def acknowledge_capacity(
        self,
        token_id: str,
        cell_id: str
    ) -> Dict[str, any]:
        """
        Acknowledge capacity transfer (ack).
        
        Returns:
            Dict with acknowledgment status
        """
        if token_id not in self.active_tokens:
            return {
                "status": "token_not_found",
                "token_id": token_id
            }
        
        token = self.active_tokens.pop(token_id)
        
        # Update cell states
        if token.source != token.destination:
            # Capacity transferred from another cell
            self.cell_states[token.source] = BackpressureState.IDLE
            self.cell_states[token.destination] = BackpressureState.ACK
        
        # Remove from pending needs
        if token.destination in self.pending_needs and self.pending_needs[token.destination]:
            self.pending_needs[token.destination].popleft()
        
        # Add to history
        self.token_history.append(token)
        if len(self.token_history) > self.max_history:
            self.token_history.pop(0)
        
        logger.info(f"Capacity transfer acknowledged: {token_id} from {token.source} to {token.destination}")
        
        return {
            "status": "acknowledged",
            "token_id": token_id,
            "source": token.source,
            "destination": token.destination,
            "capacity": token.capacity
        }
    
    def release_capacity(
        self,
        cell_id: str,
        capacity: float
    ) -> Dict[str, any]:
        """
        Release capacity back to the pool.
        
        Called when a cell finishes processing and can offer capacity again.
        """
        if cell_id not in self.cell_capacity:
            self.cell_capacity[cell_id] = 0.0
        
        self.cell_capacity[cell_id] = min(1.0, self.cell_capacity[cell_id] + capacity)
        
        # Reset state if not overloaded
        if self.cell_states[cell_id] == BackpressureState.ACK:
            self.cell_states[cell_id] = BackpressureState.IDLE
        
        logger.info(f"Cell {cell_id} released capacity {capacity}, total: {self.cell_capacity[cell_id]}")
        
        return {
            "status": "released",
            "cell_id": cell_id,
            "capacity": capacity,
            "total_capacity": self.cell_capacity[cell_id]
        }
    
    def get_cell_status(self, cell_id: str) -> Dict[str, any]:
        """Get current status of a cell."""
        return {
            "cell_id": cell_id,
            "state": self.cell_states.get(cell_id, BackpressureState.IDLE).value,
            "capacity": self.cell_capacity.get(cell_id, 1.0),
            "pending_needs": len(self.pending_needs.get(cell_id, deque())),
            "pending_offers": len(self.pending_offers.get(cell_id, deque())),
            "active_tokens": sum(1 for t in self.active_tokens.values() if t.destination == cell_id)
        }
    
    def get_stats(self) -> Dict[str, any]:
        """Get backpressure statistics."""
        total_cells = len(self.cell_states)
        overloaded_cells = sum(1 for s in self.cell_states.values() if s == BackpressureState.OVERLOADED)
        total_tokens = len(self.token_history)
        
        return {
            "total_cells": total_cells,
            "overloaded_cells": overloaded_cells,
            "total_tokens": total_tokens,
            "active_tokens": len(self.active_tokens),
            "avg_capacity": sum(self.cell_capacity.values()) / total_cells if total_cells > 0 else 0.0
        }


# Global instance
backpressure_manager = BackpressureManager()

