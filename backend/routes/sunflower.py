"""Sunflower coordinate endpoints for Daena."""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any
from backend.utils.sunflower import sunflower_coords, sunflower_xy, get_neighbor_indices

router = APIRouter(prefix="/api/v1/sunflower", tags=["sunflower"])

@router.get("/coords")
async def get_sunflower_coordinates(
    k: int = Query(..., description="Sunflower index (1-based)"),
    n: int = Query(1, description="Total number of points"),
    alpha: float = Query(0.5, description="Alpha parameter"),
    format: str = Query("polar", description="Output format: polar, cartesian, grid")
) -> Dict[str, Any]:
    """Get sunflower coordinates for index k."""
    try:
        if k <= 0:
            raise ValueError("Index k must be positive")
            
        if format == "polar":
            r, theta = sunflower_coords(k, n, alpha)
            return {
                "success": True,
                "index": k,
                "format": "polar",
                "coordinates": {
                    "r": round(r, 6),
                    "theta": round(theta, 6),
                    "theta_degrees": round(theta * 180 / 3.14159, 2)
                }
            }
        elif format == "cartesian":
            x, y = sunflower_xy(k, n, alpha)
            return {
                "success": True,
                "index": k,
                "format": "cartesian",
                "coordinates": {
                    "x": round(x, 6),
                    "y": round(y, 6)
                }
            }
        elif format == "grid":
            from ..utils.sunflower import sunflower_grid
            grid_x, grid_y = sunflower_grid(k, n, alpha)
            return {
                "success": True,
                "index": k,
                "format": "grid",
                "coordinates": {
                    "grid_x": grid_x,
                    "grid_y": grid_y
                }
            }
        else:
            raise ValueError("Invalid format. Use: polar, cartesian, or grid")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/neighbors")
async def get_neighbors(
    k: int = Query(..., description="Center index (1-based)"),
    n: int = Query(..., description="Total number of points"),
    max_neighbors: int = Query(6, description="Maximum number of neighbors")
) -> Dict[str, Any]:
    """Get neighbor indices for a given sunflower index."""
    try:
        if k <= 0 or k > n:
            raise ValueError(f"Index k must be between 1 and {n}")
            
        neighbor_indices = get_neighbor_indices(k, n, max_neighbors)
        
        return {
            "success": True,
            "center_index": k,
            "total_points": n,
            "max_neighbors": max_neighbors,
            "neighbors": neighbor_indices,
            "neighbor_count": len(neighbor_indices)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/batch")
async def get_batch_coordinates(
    start: int = Query(1, description="Start index"),
    end: int = Query(8, description="End index"),
    format: str = Query("cartesian", description="Output format"),
    scale: float = Query(1.0, description="Scale factor")
) -> Dict[str, Any]:
    """Get coordinates for a range of indices."""
    try:
        if start <= 0 or end < start:
            raise ValueError("Invalid range: start > 0 and end >= start")
            
        coordinates = []
        for k in range(start, end + 1):
            if format == "cartesian":
                x, y = sunflower_xy(k, n=end, scale=scale)
                coords = {"index": k, "x": round(x, 6), "y": round(y, 6)}
            elif format == "polar":
                r, theta = sunflower_coords(k, n=end)
                coords = {
                    "index": k, 
                    "r": round(r, 6), 
                    "theta": round(theta, 6),
                    "theta_degrees": round(theta * 180 / 3.14159, 2)
                }
            else:
                raise ValueError("Invalid format. Use: polar or cartesian")
                
            coordinates.append(coords)
            
        return {
            "success": True,
            "range": {"start": start, "end": end},
            "format": format,
            "scale": scale,
            "coordinates": coordinates,
            "total_points": len(coordinates)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/spiral")
async def get_spiral_coordinates(
    k: int = Query(..., description="Index (1-based)"),
    n: int = Query(1, description="Total number of points"),
    alpha: float = Query(0.5, description="Alpha parameter")
) -> Dict[str, Any]:
    """Get spiral-adjusted sunflower coordinates."""
    try:
        if k <= 0:
            raise ValueError("Index k must be positive")
            
        from ..utils.sunflower import sunflower_spiral
        r, theta, spiral_radius = sunflower_spiral(k, n, alpha)
        
        return {
            "success": True,
            "index": k,
            "coordinates": {
                "r": round(r, 6),
                "theta": round(theta, 6),
                "theta_degrees": round(theta * 180 / 3.14159, 2),
                "spiral_radius": round(spiral_radius, 6)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 