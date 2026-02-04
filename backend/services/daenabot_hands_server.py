import asyncio
import json
import logging
import os
import sys
import uuid
import traceback
from logging.handlers import RotatingFileHandler

# Add parent directory to path to import config if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import websockets
except ImportError:
    print("Error: websockets module not found. Please install it: pip install websockets")
    sys.exit(1)

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("Warning: pyautogui not found. Desktop automation will be disabled.")

# Setup Logging
log_file = os.path.join("logs", "daenabot_hands.log")
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DaenaBotHands")

# Configuration
PORT = int(os.getenv("DAENABOT_HANDS_PORT", 18789))
HOST = "127.0.0.1"

# Security
from backend.security.credential_vault import CredentialVault
HANDS_TOKEN = CredentialVault.get_secret("DAENABOT_HANDS_TOKEN") or os.getenv("DAENABOT_HANDS_TOKEN")

if not HANDS_TOKEN:
    logger.warning("DAENABOT_HANDS_TOKEN not set! Security is compromised.")

# Connected clients
clients = set()

async def handle_action(action: dict) -> dict:
    """Execute the requested action."""
    action_type = action.get("action_type") or action.get("type") or action.get("tool_name") or "unknown"
    params = action.get("parameters", {}) or action.get("params", {})
    
    logger.info(f"Executing action: {action_type} with params: {params}")
    
    try:
        if action_type == "desktop.click":
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "error": "pyautogui not available"}
            x = params.get("x")
            y = params.get("y")
            if x is not None and y is not None:
                pyautogui.click(x, y)
                return {"success": True, "message": f"Clicked at {x}, {y}"}
            return {"success": False, "error": "Missing x, y parameters"}
            
        elif action_type == "desktop.type":
            if not PYAUTOGUI_AVAILABLE:
                return {"success": False, "error": "pyautogui not available"}
            text = params.get("text")
            if text:
                pyautogui.write(text)
                return {"success": True, "message": "Typed text"}
            return {"success": False, "error": "Missing text parameter"}
            
        elif action_type == "shell.run" or action_type == "terminal.run":
            command = params.get("command")
            if not command:
                return {"success": False, "error": "Missing command"}
            
            # Simple whitelist check
            whitelist = os.getenv("ALLOWED_SHELL_COMMANDS", "dir,ls,echo,ipconfig").split(",")
            cmd_base = command.split()[0] if command else ""
            if cmd_base not in whitelist:
                 return {"success": False, "error": f"Command '{cmd_base}' not in allowed whitelist"}

            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            return {
                "success": True,
                "stdout": stdout.decode(errors='replace'),
                "stderr": stderr.decode(errors='replace'),
                "returncode": process.returncode
            }
            
        elif action_type == "browser.navigate":
            # Placeholder for browser automation (e.g., using Playwright if added)
            url = params.get("url")
            import webbrowser
            webbrowser.open(url)
            return {"success": True, "message": f"Opened {url} in default browser"}
            
        else:
            return {"success": False, "error": f"Unknown action: {action_type}"}
            
    except Exception as e:
        logger.error(f"Action failed: {e}")
        return {"success": False, "error": str(e)}

async def handler(websocket, path):
    """Handle WebSocket connection."""
    client_id = str(uuid.uuid4())
    logger.info(f"New connection: {client_id}")
    authenticated = False
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                
                # Check for basic message override or JSON-RPC
                msg_id = data.get("id")
                method = data.get("method")
                params = data.get("params", {})
                
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id
                }
                
                # Handshake / Auth
                if method == "connect":
                    auth = params.get("auth", {})
                    token = auth.get("token")
                    
                    if token == HANDS_TOKEN:
                        authenticated = True
                        response["result"] = {"status": "connected", "message": "Authentication successful"}
                        logger.info(f"Client {client_id} authenticated successfully")
                    else:
                        response["error"] = {"code": 401, "message": "Authentication failed"}
                        logger.warning(f"Client {client_id} authentication failed")
                        await websocket.send(json.dumps(response))
                        return
                        
                elif not authenticated:
                    response["error"] = {"code": 401, "message": "Not authenticated"}
                    await websocket.send(json.dumps(response))
                    return
                    
                # Execute Action
                elif method == "execute":
                    result = await handle_action(params)
                    if result.get("success"):
                         response["result"] = result
                    else:
                         response["error"] = {"code": 500, "message": result.get("error", "Execution failed")}
                
                else:
                    response["error"] = {"code": 404, "method": method, "message": "Method not found"}
                
                await websocket.send(json.dumps(response))
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except Exception as e:
                logger.error(f"Internal error: {e}")
                err_response = {"jsonrpc": "2.0", "error": {"code": 500, "message": str(e)}, "id": None}
                await websocket.send(json.dumps(err_response))
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed: {client_id}")
    finally:
        pass

async def main():
    logger.info(f"Starting DaenaBot Hands Server on {HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical(f"Server crashed: {e}")
        traceback.print_exc()
