"""Sunflower coordinate utilities for Daena's spatial organization."""
import math
from typing import Tuple, List

def sunflower_coords(k: int, n: int = 8, alpha: float = 0.5) -> Tuple[float, float]:
    """
    Generate sunflower coordinates for index k.
    
    Args:
        k: Index (1-based)
        n: Number of points (default 8 for 8×6 council - 8 departments, 6 agents each)
        alpha: Alpha parameter for distribution (default 0.5)
    
    Returns:
        Tuple of (r, theta) in polar coordinates
    """
    if k <= 0:
        raise ValueError("Index k must be positive")
    
    # Exact golden angle: 137.507° = 2π * (3 - √5)
    golden_angle = 2 * math.pi * (3 - math.sqrt(5))  # ≈ 2.399963 radians ≈ 137.507°
    
    # Calculate radius: r = c * sqrt(k) where c is a scaling constant
    c = 1.0 / math.sqrt(n)  # Normalize to fit in unit circle
    r = c * math.sqrt(k)
    
    # Calculate angle: theta = k * golden_angle
    theta = k * golden_angle
    
    return r, theta

def sunflower_xy(k: int, n: int = 8, alpha: float = 0.5, scale: float = 100.0) -> Tuple[float, float]:
    """
    Generate sunflower coordinates in Cartesian (x, y) format.
    
    Args:
        k: Index (1-based)
        n: Number of points (default 8 for 8×6 council - 8 departments, 6 agents each)
        alpha: Alpha parameter for distribution (default 0.5)
        scale: Scale factor for coordinates (default 100.0 for better visualization)
    
    Returns:
        Tuple of (x, y) in Cartesian coordinates
    """
    r, theta = sunflower_coords(k, n, alpha)
    
    x = r * math.cos(theta) * scale
    y = r * math.sin(theta) * scale
    
    return x, y

def to_xy(k: int, n: int = 8, scale: float = 100.0) -> Tuple[float, float]:
    """
    Alias for sunflower_xy for compatibility.
    
    Args:
        k: Index (1-based)
        n: Number of points (default 8 for 8×6 council - 8 departments, 6 agents each)
        scale: Scale factor for coordinates
    
    Returns:
        Tuple of (x, y) in Cartesian coordinates
    """
    return sunflower_xy(k, n, scale=scale)

def sunflower_grid(k: int, n: int = 1, alpha: float = 0.5, scale: float = 1.0) -> Tuple[int, int]:
    """
    Generate grid-like coordinates for better organization.
    
    Args:
        k: Index (1-based)
        n: Number of points (default 1 for single point)
        alpha: Alpha parameter for distribution (default 0.5)
        scale: Scale factor for coordinates (default 1.0)
    
    Returns:
        Tuple of (grid_x, grid_y) as integer coordinates
    """
    x, y = sunflower_xy(k, n, alpha, scale)
    
    # Convert to grid coordinates
    grid_x = int(round(x * 10))  # Scale by 10 for better precision
    grid_y = int(round(y * 10))
    
    return grid_x, grid_y

def get_neighbor_indices(k: int, n: int = 1, max_neighbors: int = 6) -> List[int]:
    """
    Get indices of neighboring points for a given sunflower index.
    
    Args:
        k: Center index (1-based)
        n: Total number of points
        max_neighbors: Maximum number of neighbors to return
    
    Returns:
        List of neighbor indices (safe empty list if k/n invalid)
    """
    # Guard against invalid k values - return empty list instead of raising
    try:
        k = int(k)
    except (ValueError, TypeError):
        return []

    # If n is 0 or negative, return empty list
    try:
        n = int(n)
    except (ValueError, TypeError):
        return []
    if n <= 0:
        return []

    # Clamp k to valid range
    if k < 1:
        k = 1
    if k > n:
        k = n
    
    # Calculate distances to all other points
    distances = []
    center_x, center_y = sunflower_xy(k, n)
    
    for i in range(1, n + 1):
        if i != k:
            point_x, point_y = sunflower_xy(i, n)
            distance = math.sqrt((center_x - point_x)**2 + (center_y - point_y)**2)
            distances.append((i, distance))
    
    # Sort by distance and return closest neighbors
    distances.sort(key=lambda x: x[1])
    neighbor_indices = [idx for idx, _ in distances[:max_neighbors]]
    
    return neighbor_indices

def sunflower_spiral(k: int, n: int = 1, alpha: float = 0.5) -> Tuple[float, float, float]:
    """
    Generate spiral coordinates for more natural distribution.
    
    Args:
        k: Index (1-based)
        n: Number of points (default 1 for single point)
        alpha: Alpha parameter for distribution (default 0.5)
    
    Returns:
        Tuple of (r, theta, spiral_radius) where spiral_radius is the spiral parameter
    """
    if k <= 0:
        raise ValueError("Index k must be positive")
    
    # Spiral parameter
    spiral_radius = k / n
    
    # Calculate radius and angle with spiral adjustment
    r = math.sqrt(k - alpha) / math.sqrt(n - alpha + 1)
    theta = k * 2 * math.pi * (3 - math.sqrt(5)) + spiral_radius * 2 * math.pi
    
    return r, theta, spiral_radius 