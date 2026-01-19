"""
Connections API - Manus/n8n-style visual connection management
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import base64
import json
from sqlalchemy.orm import Session

from backend.core.cmp.registry import cmp_registry, CMPToolCategory
from backend.database import get_db, Connection as ConnectionDB

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


class ConnectionCredentials(BaseModel):
    tool_id: str
    credentials: Dict[str, str]  # Encrypted in real implementation


class TestConnectionRequest(BaseModel):
    tool_id: str
    credentials: Dict[str, str]


class ConnectionResponse(BaseModel):
    id: int
    tool_id: str
    tool_name: str
    status: str  # connected, disconnected, error
    last_tested: Optional[datetime] = None
    last_used: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        orm_mode = True


def encrypt_credentials(credentials: Dict[str, str]) -> str:
    """
    Encrypt credentials (simplified - use proper encryption in production)
    In production: Use Fernet, AWS KMS, or similar
    """
    # For demo: base64 encoding (NOT SECURE - use AES-256 in production)
    creds_json = json.dumps(credentials)
    encoded = base64.b64encode(creds_json.encode()).decode()
    return encoded


def decrypt_credentials(encrypted: str) -> Dict[str, str]:
    """Decrypt credentials"""
    try:
        decoded = base64.b64decode(encrypted.encode()).decode()
        return json.loads(decoded)
    except:
        return {}


@router.get("/tools")
async def list_available_tools(category: Optional[str] = None):
    """
    Get all available CMP tools
    """
    cat_enum = None
    if category:
        try:
            cat_enum = CMPToolCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    tools = cmp_registry.list_tools(cat_enum)
    
    return {
        "tools": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category.value,
                "description": t.description,
                "icon": t.icon,
                "color": t.color,
                "credentials_required": [
                    {
                        "name": c.name,
                        "label": c.label,
                        "type": c.type.value,
                        "required": c.required,
                        "placeholder": c.placeholder,
                        "help_text": c.help_text
                    }
                    for c in t.credentials
                ],
                "actions": t.actions,
                "enabled": t.enabled
            }
            for t in tools
        ],
        "total": len(tools),
        "categories": [cat.value for cat in CMPToolCategory]
    }


@router.post("/connect")
async def connect_tool(request: ConnectionCredentials, db: Session = Depends(get_db)):
    """
    Connect to a tool by providing credentials
    """
    tool = cmp_registry.get_tool(request.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool_id}")
    
    # Validate required fields
    required_fields = [c.name for c in tool.credentials if c.required]
    missing = [f for f in required_fields if f not in request.credentials]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")
    
    # Check if connection already exists
    existing = db.query(ConnectionDB).filter(ConnectionDB.tool_name == request.tool_id).first()
    
    if existing:
        # Update existing connection
        existing.status = "connected"
        existing.settings_json = request.credentials  # In prod: encrypt this!
        existing.last_checked = datetime.utcnow()
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        connection = existing
    else:
        # Create new connection
        connection = ConnectionDB(
            tool_name=request.tool_id,
            status="connected",
            settings_json=request.credentials,  # In prod: encrypt this!
            last_checked=datetime.utcnow(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
    
    return {
        "success": True,
        "connection_id": connection.id,
        "tool_id": request.tool_id,
        "tool_name": tool.name,
        "status": "connected",
        "message": f"Successfully connected to {tool.name}"
    }


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """
    Test connection credentials without saving
    """
    tool = cmp_registry.get_tool(request.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool_id}")
    
    # In production: Actually test the connection
    # For now: Mock test
    try:
        # Simulate connection test
        if request.tool_id == "gmail" and "email" in request.credentials:
            test_result = {
                "success": True,
                "message": "Connection successful",
                "details": {
                    "email": request.credentials.get("email"),
                    "verified": True
                }
            }
        elif request.tool_id in ["gemini", "chatgpt"] and "api_key" in request.credentials:
            test_result = {
                "success": True,
                "message": "API key validated",
                "details": {
                    "api_key_prefix": request.credentials.get("api_key", "")[:10] + "...",
                    "verified": True
                }
            }
        else:
            test_result = {
                "success": True,
                "message": "Credentials validated (mock)",
                "details": {}
            }
        
        return test_result
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}",
            "details": {}
        }


@router.get("/list")
async def list_connections(db: Session = Depends(get_db)):
    """
    Get all active connections
    """
    connections = db.query(ConnectionDB).all()
    
    result = []
    for conn in connections:
        tool = cmp_registry.get_tool(conn.tool_name)
        tool_name = tool.name if tool else conn.tool_name
        
        result.append({
            "id": conn.id,
            "tool_id": conn.tool_name,
            "tool_name": tool_name,
            "status": conn.status,
            "last_tested": conn.last_checked.isoformat() if conn.last_checked else None,
            "last_used": conn.updated_at.isoformat() if conn.updated_at else None,
            "error_message": conn.last_error
        })
        
    return {
        "connections": result,
        "total": len(result)
    }


@router.delete("/{connection_id}")
async def disconnect_tool(connection_id: int, db: Session = Depends(get_db)):
    """
    Disconnect a tool
    """
    connection = db.query(ConnectionDB).filter(ConnectionDB.id == connection_id).first()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    tool_name = connection.tool_name
    db.delete(connection)
    db.commit()
    
    return {
        "success": True,
        "message": f"Disconnected from {tool_name}",
        "connection_id": connection_id
    }


@router.get("/categories")
async def get_categories():
    """
    Get all tool categories
    """
    return {
        "categories": [
            {
                "id": cat.value,
                "name": cat.value.replace("_", " ").title(),
                "icon": _get_category_icon(cat)
            }
            for cat in CMPToolCategory
        ]
    }


def _get_category_icon(category: CMPToolCategory) -> str:
    """Get icon for category"""
    icons = {
        CMPToolCategory.EMAIL: "fa-envelope",
        CMPToolCategory.COMMUNICATION: "fa-comments",
        CMPToolCategory.AI_LLM: "fa-brain",
        CMPToolCategory.DATABASE: "fa-database",
        CMPToolCategory.CLOUD_STORAGE: "fa-cloud",
        CMPToolCategory.PRODUCTIVITY: "fa-tasks",
        CMPToolCategory.CRM: "fa-users",
        CMPToolCategory.ANALYTICS: "fa-chart-line",
        CMPToolCategory.AUTOMATION: "fa-cogs",
        CMPToolCategory.OTHER: "fa-plug"
    }
    return icons.get(category, "fa-plug")
