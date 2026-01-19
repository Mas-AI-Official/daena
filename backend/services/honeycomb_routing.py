"""Honeycomb routing service for Daena's Sunflower × Honeycomb architecture."""
import logging
from typing import Dict, List, Tuple, Optional, Set
from backend.utils.sunflower import sunflower_xy, get_neighbor_indices
from backend.utils.message_bus import message_bus, Message, MessageType

logger = logging.getLogger(__name__)

class HoneycombRouting:
    """Honeycomb routing service with local-first strategy and CMP fallback."""
    
    def __init__(self):
        self.adjacency_cache: Dict[str, List[str]] = {}
        self.cell_positions: Dict[str, Tuple[float, float]] = {}
        self.routing_stats = {
            "local_routes": 0,
            "neighbor_routes": 0,
            "cmp_fallbacks": 0,
            "total_routes": 0
        }
    
    def build_adjacency(self, cells: Dict[str, Dict]) -> Dict[str, List[str]]:
        """
        Build adjacency relationships for cells.
        
        Args:
            cells: Dictionary of cell_id -> cell_data
            
        Returns:
            Dictionary of cell_id -> list of neighbor_ids (up to 6)
        """
        logger.info(f"Building adjacency for {len(cells)} cells")
        
        # Clear existing cache
        self.adjacency_cache.clear()
        self.cell_positions.clear()
        
        # Calculate positions for all cells
        for cell_id, cell_data in cells.items():
            if "sunflower_index" in cell_data:
                k = cell_data["sunflower_index"]
                x, y = sunflower_xy(k, n=len(cells))
                self.cell_positions[cell_id] = (x, y)
        
        # Build adjacency for each cell
        for cell_id, cell_data in cells.items():
            if cell_id in self.cell_positions:
                neighbors = self._find_neighbors(cell_id, cells)
                self.adjacency_cache[cell_id] = neighbors
                logger.debug(f"Cell {cell_id}: {len(neighbors)} neighbors")
        
        logger.info(f"Built adjacency for {len(self.adjacency_cache)} cells")
        return self.adjacency_cache
    
    def _find_neighbors(self, cell_id: str, cells: Dict[str, Dict], max_neighbors: int = 6) -> List[str]:
        """Find neighbors for a specific cell."""
        if cell_id not in self.cell_positions:
            return []
        
        center_pos = self.cell_positions[cell_id]
        distances = []
        
        # Calculate distances to all other cells
        for other_id, other_data in cells.items():
            if other_id != cell_id and other_id in self.cell_positions:
                other_pos = self.cell_positions[other_id]
                distance = self._calculate_distance(center_pos, other_pos)
                distances.append((other_id, distance))
        
        # Sort by distance and return closest neighbors
        distances.sort(key=lambda x: x[1])
        neighbor_ids = [cell_id for cell_id, _ in distances[:max_neighbors]]
        
        return neighbor_ids
    
    def _calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions."""
        x1, y1 = pos1
        x2, y2 = pos2
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    
    async def local_first_route(self, message: Message, source_cell: str, target_cell: str) -> bool:
        """
        Route message using local-first strategy with CMP fallback.
        
        Args:
            message: Message to route
            source_cell: Source cell ID
            target_cell: Target cell ID
            
        Returns:
            True if routing successful, False otherwise
        """
        self.routing_stats["total_routes"] += 1
        
        # Check if target is a direct neighbor
        if source_cell in self.adjacency_cache:
            neighbors = self.adjacency_cache[source_cell]
            if target_cell in neighbors:
                # Local neighbor route
                self.routing_stats["neighbor_routes"] += 1
                logger.info(f"Message {message.id} routed to local neighbor {target_cell}")
                return True
        
        # Check if we can route through neighbors
        if source_cell in self.adjacency_cache:
            neighbors = self.adjacency_cache[source_cell]
            for neighbor in neighbors:
                if neighbor in self.adjacency_cache:
                    neighbor_neighbors = self.adjacency_cache[neighbor]
                    if target_cell in neighbor_neighbors:
                        # Route through neighbor
                        self.routing_stats["neighbor_routes"] += 1
                        logger.info(f"Message {message.id} routed through neighbor {neighbor} to {target_cell}")
                        return True
        
        # CMP fallback via message bus
        self.routing_stats["cmp_fallbacks"] += 1
        logger.info(f"Message {message.id} using CMP fallback to {target_cell}")
        
        # Use message bus CMP fallback
        return await message_bus.send_cmp_fallback(source_cell, message.content, MessageType.CMP_FALLBACK)
    
    def get_neighbors(self, cell_id: str) -> List[str]:
        """Get neighbors for a cell."""
        return self.adjacency_cache.get(cell_id, [])
    
    def get_adjacency_stats(self) -> Dict[str, any]:
        """Get adjacency statistics."""
        total_neighbors = sum(len(neighbors) for neighbors in self.adjacency_cache.values())
        avg_neighbors = total_neighbors / len(self.adjacency_cache) if self.adjacency_cache else 0
        
        return {
            "total_cells": len(self.adjacency_cache),
            "total_neighbors": total_neighbors,
            "average_neighbors": round(avg_neighbors, 2),
            "max_neighbors": max(len(neighbors) for neighbors in self.adjacency_cache.values()) if self.adjacency_cache else 0,
            "routing_stats": self.routing_stats
        }
    
    def rebuild_adjacency(self, cells: Dict[str, Dict]) -> Dict[str, List[str]]:
        """Rebuild adjacency relationships."""
        logger.info("Rebuilding adjacency relationships")
        return self.build_adjacency(cells)
    
    def get_cell_position(self, cell_id: str) -> Optional[Tuple[float, float]]:
        """Get position of a cell."""
        return self.cell_positions.get(cell_id)
    
    def get_all_positions(self) -> Dict[str, Tuple[float, float]]:
        """Get all cell positions."""
        return self.cell_positions.copy()

# Global honeycomb routing instance
honeycomb_routing = HoneycombRouting() 