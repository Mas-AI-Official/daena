"""
Mobile Agent API Routes

Provides REST API for AutoGLM-style mobile device control.

Endpoints:
- POST /api/v1/mobile/register - Register a new device
- POST /api/v1/mobile/task - Send a task to a device
- GET /api/v1/mobile/state/{device_id} - Get device state
- POST /api/v1/mobile/action - Execute an action on a device
- GET /api/v1/mobile/devices - List connected devices
- POST /api/v1/mobile/shortcut - Run iOS Shortcut
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from backend.services.mobile_agent import (
    mobile_agent_service,
    SendTaskRequest,
    ExecuteActionRequest,
    RegisterDeviceRequest,
    RunShortcutRequest
)

router = APIRouter(prefix="/api/v1/mobile", tags=["Mobile Agent"])
logger = logging.getLogger(__name__)


@router.post("/register")
async def register_device(request: RegisterDeviceRequest) -> Dict[str, Any]:
    """
    Register a mobile device for automation.
    
    The device agent should call this when connecting.
    """
    return await mobile_agent_service.register_device(
        device_id=request.device_id,
        platform=request.platform,
        screen_width=request.screen_width,
        screen_height=request.screen_height
    )


@router.post("/task")
async def send_task(request: SendTaskRequest) -> Dict[str, Any]:
    """
    Send a high-level task to a mobile agent.
    
    Example: "Open Settings and check battery level"
    
    The device-side agent will break this down into actions.
    """
    return await mobile_agent_service.send_task(
        device_id=request.device_id,
        task_description=request.task_description,
        context=request.context
    )


@router.get("/state/{device_id}")
async def get_device_state(device_id: str) -> Dict[str, Any]:
    """Get current state of a connected device."""
    result = await mobile_agent_service.get_device_state(device_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@router.post("/action")
async def execute_action(request: ExecuteActionRequest) -> Dict[str, Any]:
    """
    Execute a specific action on a device.
    
    Actions: tap, scroll, type, screenshot, get_state
    
    Note: iOS has limited UI automation support. Use /shortcut for iOS.
    """
    return await mobile_agent_service.execute_action(
        device_id=request.device_id,
        action_type=request.action_type,
        target=request.target,
        payload=request.payload
    )


@router.get("/devices")
async def list_devices() -> Dict[str, Any]:
    """List all connected mobile devices."""
    devices = mobile_agent_service.list_connected_devices()
    return {
        "success": True,
        "devices": devices,
        "count": len(devices)
    }


@router.post("/shortcut")
async def run_ios_shortcut(request: RunShortcutRequest) -> Dict[str, Any]:
    """
    Run an iOS Shortcut on a device.
    
    This is the Apple-approved way to automate iOS.
    Create shortcuts on the device, then trigger them from Daena.
    """
    return await mobile_agent_service.run_ios_shortcut(
        device_id=request.device_id,
        shortcut_name=request.shortcut_name,
        input_data=request.input_data
    )


@router.get("/log")
async def get_action_log(limit: int = 50) -> Dict[str, Any]:
    """Get recent mobile agent action log."""
    log = mobile_agent_service.get_action_log(limit=limit)
    return {
        "success": True,
        "log": log,
        "count": len(log)
    }


@router.get("/platforms")
async def get_platform_info() -> Dict[str, Any]:
    """
    Get information about supported mobile platforms and limitations.
    """
    return {
        "success": True,
        "platforms": {
            "android": {
                "fully_supported": True,
                "method": "Accessibility Service + Overlays",
                "capabilities": [
                    "tap", "scroll", "type", "screenshot", 
                    "get_ui_hierarchy", "launch_app", "back", "home"
                ],
                "notes": "Requires Daena Mobile Agent app installed with Accessibility permissions"
            },
            "ios": {
                "fully_supported": False,
                "method": "Shortcuts + SiriKit (limited)",
                "capabilities": [
                    "run_shortcut", "screenshot", "limited_app_control"
                ],
                "limitations": [
                    "Cannot globally automate UI like Android",
                    "Requires creating Shortcuts on device first",
                    "Some actions require user confirmation",
                    "Background automation very limited"
                ],
                "notes": "iOS is locked down. Use pre-defined Shortcuts for automation."
            }
        },
        "recommendations": {
            "android": "Install Daena Mobile Agent from Play Store (coming soon)",
            "ios": "Create Shortcuts for common tasks, then trigger via Daena"
        }
    }
