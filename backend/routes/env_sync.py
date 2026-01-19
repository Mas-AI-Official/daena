"""
Environment Variable Sync API
Syncs .env file with backend settings
"""
from fastapi import APIRouter, HTTPException, Body, Depends
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import os
import logging
from pathlib import Path

router = APIRouter(prefix="/api/v1/env", tags=["Environment"])
logger = logging.getLogger(__name__)

ENV_FILE = Path(__file__).parent.parent.parent / ".env"

class EnvVarRequest(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

class EnvVarResponse(BaseModel):
    key: str
    value: str
    description: Optional[str] = None

@router.get("/vars")
async def get_env_vars() -> Dict[str, Any]:
    """Get all environment variables from .env file"""
    env_vars = {}
    
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        env_vars[key] = value
        except Exception as e:
            logger.error(f"Error reading .env file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to read .env file: {e}")
    else:
        # Return default/common env vars structure
        env_vars = {
            "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
            "DAENA_VOICE_ENABLED": "true",
            "DAENA_BRAIN_MODEL": "daena-brain:latest"
        }
    
    return {
        "success": True,
        "env_file": str(ENV_FILE),
        "exists": ENV_FILE.exists(),
        "vars": env_vars
    }

@router.post("/vars")
async def set_env_var(request: EnvVarRequest) -> Dict[str, Any]:
    """Set/update an environment variable in .env file"""
    try:
        # Read existing .env
        env_vars = {}
        comments = {}
        if ENV_FILE.exists():
            with open(ENV_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith('#') and '=' in line_stripped:
                        key, value = line_stripped.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        env_vars[key] = value
                    elif line_stripped.startswith('#'):
                        # Preserve comments
                        if '=' in line_stripped:
                            comment_key = line_stripped.split('=')[0].replace('#', '').strip()
                            comments[comment_key] = line
        
        # Update or add new var
        env_vars[request.key] = request.value
        
        # Write back to .env
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            # Write comments first
            for key, comment in comments.items():
                if key in env_vars:
                    f.write(comment)
            
            # Write all vars
            for key, value in env_vars.items():
                # Quote values that contain spaces or special chars
                if ' ' in value or any(c in value for c in ['#', '=', '$']):
                    f.write(f'{key}="{value}"\n')
                else:
                    f.write(f'{key}={value}\n')
        
        # Also update current process environment
        os.environ[request.key] = request.value
        
        return {
            "success": True,
            "key": request.key,
            "value": request.value,
            "message": f"Environment variable {request.key} updated"
        }
    except Exception as e:
        logger.error(f"Error writing .env file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to write .env file: {e}")

@router.delete("/vars/{key}")
async def delete_env_var(key: str) -> Dict[str, Any]:
    """Delete an environment variable from .env file"""
    try:
        if not ENV_FILE.exists():
            raise HTTPException(status_code=404, detail=".env file not found")
        
        # Read existing .env
        env_vars = {}
        lines = []
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line_stripped = line.strip()
                if line_stripped and not line_stripped.startswith('#') and '=' in line_stripped:
                    var_key = line_stripped.split('=', 1)[0].strip()
                    if var_key != key:
                        lines.append(line)
                        var_value = line_stripped.split('=', 1)[1].strip().strip('"').strip("'")
                        env_vars[var_key] = var_value
                else:
                    lines.append(line)
        
        # Write back without the deleted var
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        # Remove from current process environment
        if key in os.environ:
            del os.environ[key]
        
        return {
            "success": True,
            "key": key,
            "message": f"Environment variable {key} deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting from .env file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete from .env file: {e}")



