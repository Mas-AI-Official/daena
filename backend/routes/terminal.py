from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import subprocess
import asyncio
import os
import platform
import logging
from backend.services.file_monitor import get_file_monitor
from backend.routes.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/terminal", tags=["Terminal"])

class CommandRequest(BaseModel):
    command: str
    cwd: Optional[str] = None

class TerminalSession:
    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.history = []
        self.process = None
        self.cwd = os.getcwd()

    async def execute(self, command: str) -> Dict[str, Any]:
        """Execute a command synchronously (for simple API calls)"""
        try:
            # Audit log
            logger.info(f"Terminal Exec ({self.user_id}): {command} in {self.cwd}")
            
            # Handle cd special case
            if command.strip().startswith("cd "):
                target_dir = command.strip()[3:].strip()
                new_cwd = os.path.join(self.cwd, target_dir)
                if os.path.exists(new_cwd) and os.path.isdir(new_cwd):
                    self.cwd = os.path.abspath(new_cwd)
                    return {"stdout": "", "stderr": "", "cwd": self.cwd}
                else:
                    return {"stdout": "", "stderr": f"cd: {target_dir}: No such file or directory", "cwd": self.cwd}
            
            # Run command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
                shell=True
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "stdout": stdout.decode(errors='replace'),
                "stderr": stderr.decode(errors='replace'),
                "cwd": self.cwd,
                "exit_code": process.returncode
            }
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "cwd": self.cwd, "exit_code": 1}

# In-memory session store
sessions: Dict[str, TerminalSession] = {}

@router.post("/execute")
async def execute_command(
    request: CommandRequest,
    current_user: dict = Depends(get_current_user)
):
    """Execute a single shell command."""
    user_id = current_user.get("sub", "unknown")
    
    # Audit: Only allow Founder/VP/Admin
    role = current_user.get("role", "client")
    if role not in ["founder", "daena_vp", "admin"]:
       raise HTTPException(status_code=403, detail="Terminal access denied")

    session_id = f"term_{user_id}"
    if session_id not in sessions:
        sessions[session_id] = TerminalSession(session_id, user_id)
        
    session = sessions[session_id]
    if request.cwd:
        session.cwd = request.cwd
        
    return await session.execute(request.command)

@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """
    WebSocket for persistent terminal session.
    Note: Authentication for WebSocket is handled via query param or handshake.
    For simplicity here, we assume trusted environment or pass token in first message.
    """
    await websocket.accept()
    
    user_id = "websocket_user" # Placeholder until auth handshaking is implemented
    session = TerminalSession(f"ws_{id(websocket)}", user_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            
            if command:
                websocket.send_json({"type": "status", "status": "running"})
                result = await session.execute(command)
                await websocket.send_json({
                    "type": "result",
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "cwd": result["cwd"]
                })
    except WebSocketDisconnect:
        logger.info("Terminal WebSocket disconnected")
