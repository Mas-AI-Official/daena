"""
Real-time Events Router - WebSocket and SSE endpoints
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
import asyncio
import json
from typing import AsyncGenerator

from backend.services.websocket_manager import get_websocket_manager
from backend.services.auth import get_current_user_ws
from backend.services.governance_loop import get_governance_loop

router = APIRouter(prefix="/realtime", tags=["realtime"])

# WebSocket endpoint for bidirectional communication
@router.websocket("/ws")
async def realtime_websocket(websocket: WebSocket):
    """
    WebSocket for real-time updates:
    - Skill status changes
    - Model enable/disable
    - Governance approvals
    - Chat streaming
    - Project updates
    """
    # Accept connection
    await websocket.accept()
    
    # Authenticate
    try:
        auth_msg = await websocket.receive_text()
        auth_data = json.loads(auth_msg)
        token = auth_data.get('token')
        user = await get_current_user_ws(token)
        user_id = str(user.id)
    except:
        await websocket.close(code=4001, reason="Authentication failed")
        return
    
    manager = get_websocket_manager()
    client_id = str(id(websocket))
    
    await manager.connect(websocket, client_id, user_id)
    
    # Send initial connection success
    await websocket.send_json({
        'event': 'connection.established',
        'data': {'client_id': client_id, 'user_id': user_id}
    })
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            event_type = message.get('event')
            payload = message.get('data', {})
            
            # Handle different event types
            if event_type == 'ping':
                await websocket.send_json({'event': 'pong', 'timestamp': payload.get('timestamp')})
            
            elif event_type == 'subscribe':
                # Subscribe to specific channels
                channel = payload.get('channel')
                await websocket.send_json({
                    'event': 'subscribed',
                    'data': {'channel': channel}
                })
            
            elif event_type == 'chat.message':
                # Handle chat message with streaming response
                await handle_chat_stream(websocket, user_id, payload)
            
            elif event_type == 'action.execute':
                # Execute tool action
                result = await handle_action_execute(user_id, payload)
                await websocket.send_json({
                    'event': 'action.completed',
                    'data': result
                })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id, user_id)
    except Exception as e:
        print(f"[WS] Error: {e}")
        manager.disconnect(websocket, client_id, user_id)

async def handle_chat_stream(websocket: WebSocket, user_id: str, payload: Dict):
    """Stream chat response with action execution"""
    from backend.services.daena import get_daena_service
    from backend.services.action_dispatcher import get_action_dispatcher
    
    daena = get_daena_service()
    dispatcher = get_action_dispatcher()
    
    message = payload.get('message', '')
    
    # Stream LLM response chunks
    async for chunk in daena.stream_chat(message, user_id):
        await websocket.send_json({
            'event': 'chat.chunk',
            'data': {'content': chunk}
        })
    
    # Detect and execute actions
    actions = await dispatcher.detect_actions(message)
    if actions:
        await websocket.send_json({
            'event': 'actions.detected',
            'data': {'actions': actions}
        })
        
        results = await dispatcher.execute(actions, user_id)
        await websocket.send_json({
            'event': 'actions.completed',
            'data': {'results': results}
        })

async def handle_action_execute(user_id: str, payload: Dict):
    """Execute single action"""
    from backend.services.action_dispatcher import get_action_dispatcher
    dispatcher = get_action_dispatcher()
    
    action = payload.get('action', {})
    results = await dispatcher.execute([action], user_id)
    return results[0] if results else {'status': 'error'}

# SSE endpoint for server-sent events (fallback)
@router.get("/events")
async def realtime_events():
    """SSE stream for clients that can't use WebSocket"""
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            # Heartbeat every 15 seconds
            await asyncio.sleep(15)
            yield f"data: {json.dumps({'event': 'heartbeat'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )