"""
Workspace API Routes
Manage connections to external tools and file systems
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])

class Connection(BaseModel):
    id: str
    name: str
    type: str  # gcloud, cursor, local, dropbox, etc.
    icon: str
    status: str  # connected, disconnected, error
    last_sync: Optional[datetime]
    path: Optional[str] = None

# Mock Data
CONNECTIONS = [
    Connection(id="gcloud", name="Google Cloud Storage", type="gcloud", icon="fa-cloud", status="connected", last_sync=datetime.now()),
    Connection(id="cursor", name="Cursor IDE", type="cursor", icon="fa-code", status="connected", last_sync=datetime.now()),
    Connection(id="local_c", name="Local Drive (C:)", type="local", icon="fa-hdd", status="connected", last_sync=datetime.now(), path="C:/Users/masou"),
    Connection(id="project_root", name="Project Root", type="local", icon="fa-folder", status="connected", last_sync=datetime.now(), path="D:/Ideas/Daena"),
    Connection(id="dropbox", name="Dropbox", type="dropbox", icon="fa-box", status="disconnected", last_sync=None)
]

@router.get("/list")
async def list_connections() -> List[Connection]:
    """List all workspace connections"""
    return CONNECTIONS

@router.post("/connect/{conn_id}")
async def connect_workspace(conn_id: str):
    """Connect to a workspace"""
    conn = next((c for c in CONNECTIONS if c.id == conn_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    # Simulate connection logic
    conn.status = "connected"
    conn.last_sync = datetime.now()
    return {"success": True, "connection": conn}

@router.post("/disconnect/{conn_id}")
async def disconnect_workspace(conn_id: str):
    """Disconnect a workspace"""
    conn = next((c for c in CONNECTIONS if c.id == conn_id), None)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    conn.status = "disconnected"
    return {"success": True, "connection": conn}

@router.post("/add")
async def add_connection(name: str, type: str, path: str):
    """Add a new local connection"""
    new_conn = Connection(
        id=f"local_{len(CONNECTIONS)}",
        name=name,
        type=type,
        icon="fa-folder",
        status="connected",
        last_sync=datetime.now(),
        path=path
    )
    CONNECTIONS.append(new_conn)
    return {"success": True, "connection": new_conn}
