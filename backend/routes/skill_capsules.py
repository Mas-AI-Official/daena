"""Skill capsule routes for packing and installation."""
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List
from backend.services.skill_capsules import skill_capsule_service
from backend.middleware.abac_middleware import abac_check

router = APIRouter(prefix="/capsule", tags=["skill_capsules"])

@router.post("/pack")
async def pack_capsule(
    capsule_id: str = Body(..., embed=True),
    include_raw_data: bool = Body(False, embed=True)
):
    """Pack a skill capsule for distribution."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    try:
        pack_data = skill_capsule_service.pack_capsule(capsule_id, include_raw_data)
        return {
            "success": True,
            "pack_data": pack_data
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pack capsule: {str(e)}")

@router.post("/install")
async def install_capsule(
    pack_data: Dict[str, Any] = Body(...),
    token: str = Body(..., embed=True)
):
    """Install a skill capsule from pack data."""
    # Apply ABAC check
    await abac_check("global", "write", "admin")
    
    try:
        result = skill_capsule_service.install_capsule(pack_data, token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to install capsule: {str(e)}")

@router.post("/token")
async def generate_installation_token(
    capsule_id: str = Body(..., embed=True),
    permissions: List[str] = Body(["install"], embed=True),
    expires_in_hours: int = Body(24, embed=True)
):
    """Generate installation token for a capsule."""
    # Apply ABAC check
    await abac_check("global", "write", "admin")
    
    try:
        token = skill_capsule_service.generate_installation_token(
            capsule_id, permissions, expires_in_hours
        )
        return {
            "success": True,
            "token": token,
            "capsule_id": capsule_id,
            "permissions": permissions,
            "expires_in_hours": expires_in_hours
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate token: {str(e)}")

@router.get("/list")
async def list_capsules():
    """List all available skill capsules."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    try:
        capsules = skill_capsule_service.list_capsules()
        return {
            "success": True,
            "capsules": capsules,
            "total_count": len(capsules)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list capsules: {str(e)}")

@router.get("/search")
async def search_capsules(
    query: str,
    tags: str = None
):
    """Search capsules by query and tags."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    try:
        tag_list = tags.split(",") if tags else None
        results = skill_capsule_service.search_capsules(query, tag_list)
        return {
            "success": True,
            "query": query,
            "tags": tag_list,
            "results": results,
            "result_count": len(results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search capsules: {str(e)}")

@router.get("/{capsule_id}")
async def get_capsule(capsule_id: str):
    """Get a specific skill capsule."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    try:
        capsule = skill_capsule_service.get_capsule(capsule_id)
        if not capsule:
            raise HTTPException(status_code=404, detail=f"Capsule {capsule_id} not found")
        
        return {
            "success": True,
            "capsule": {
                "id": capsule.id,
                "name": capsule.name,
                "version": capsule.version,
                "description": capsule.description,
                "skills": capsule.skills,
                "metadata": capsule.metadata,
                "created_at": capsule.created_at,
                "expires_at": capsule.expires_at,
                "encrypted": capsule.encrypted,
                "capsule_hash": capsule.capsule_hash
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get capsule: {str(e)}")

@router.delete("/{capsule_id}")
async def delete_capsule(capsule_id: str):
    """Delete a skill capsule."""
    # Apply ABAC check
    await abac_check("global", "delete", "admin")
    
    try:
        success = skill_capsule_service.delete_capsule(capsule_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Capsule {capsule_id} not found")
        
        return {
            "success": True,
            "message": f"Capsule {capsule_id} deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete capsule: {str(e)}")

@router.get("/stats/overview")
async def get_capsule_stats():
    """Get overview statistics for skill capsules."""
    # Apply ABAC check
    await abac_check("global", "read", "admin")
    
    try:
        capsules = skill_capsule_service.list_capsules()
        
        # Calculate stats
        total_capsules = len(capsules)
        encrypted_count = sum(1 for c in capsules if c["encrypted"])
        total_skills = sum(c["skills_count"] for c in capsules)
        
        # Version distribution
        versions = {}
        for capsule in capsules:
            version = capsule["version"]
            versions[version] = versions.get(version, 0) + 1
        
        # Category distribution
        categories = {}
        for capsule in capsules:
            category = capsule.get("metadata", {}).get("category", "unknown")
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "success": True,
            "stats": {
                "total_capsules": total_capsules,
                "encrypted_capsules": encrypted_count,
                "total_skills": total_skills,
                "average_skills_per_capsule": round(total_skills / total_capsules, 2) if total_capsules > 0 else 0,
                "version_distribution": versions,
                "category_distribution": categories
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}") 