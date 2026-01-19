"""
API Tester Tool for Daena AI VP

Gives Daena ability to test and inspect API endpoints.
"""

import httpx
from typing import Dict, Any, List, Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000"


async def test_endpoint(
    path: str, 
    method: str = "GET", 
    body: Optional[Dict] = None,
    timeout: float = 10.0
) -> Dict[str, Any]:
    """
    Test an API endpoint.
    
    Args:
        path: API path (e.g., /api/v1/departments/)
        method: HTTP method (GET, POST, etc.)
        body: Request body for POST/PUT
        timeout: Request timeout in seconds
    
    Returns:
        {success, status_code, response, duration_ms, error}
    """
    try:
        import time
        start = time.time()
        
        url = f"{BASE_URL}{path}" if path.startswith("/") else f"{BASE_URL}/{path}"
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method.upper() == "GET":
                response = await client.get(url)
            elif method.upper() == "POST":
                response = await client.post(url, json=body or {})
            elif method.upper() == "PUT":
                response = await client.put(url, json=body or {})
            elif method.upper() == "DELETE":
                response = await client.delete(url)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}
        
        duration = (time.time() - start) * 1000
        
        # Try to parse JSON
        try:
            response_data = response.json()
        except:
            response_data = response.text[:500]
        
        return {
            "success": True,
            "status_code": response.status_code,
            "response": response_data,
            "duration_ms": round(duration, 2),
            "ok": 200 <= response.status_code < 300
        }
    except httpx.TimeoutException:
        return {"success": False, "error": f"Timeout after {timeout}s"}
    except httpx.ConnectError:
        return {"success": False, "error": "Connection refused - is the server running?"}
    except Exception as e:
        logger.error(f"test_endpoint error: {e}")
        return {"success": False, "error": str(e)}


async def health_check() -> Dict[str, Any]:
    """
    Check the health of all major endpoints.
    
    Returns:
        {success, checks, summary, error}
    """
    endpoints = [
        {"name": "Health", "path": "/health", "method": "GET"},
        {"name": "Brain Status", "path": "/api/v1/brain/status", "method": "GET"},
        {"name": "Departments", "path": "/api/v1/departments/", "method": "GET"},
        {"name": "Agents", "path": "/api/v1/agents/", "method": "GET"},
        {"name": "Daena Status", "path": "/api/v1/daena/status", "method": "GET"},
        {"name": "CMP Tools", "path": "/api/v1/cmp/tools", "method": "GET"},
    ]
    
    checks = []
    passed = 0
    failed = 0
    
    for ep in endpoints:
        result = await test_endpoint(ep["path"], ep["method"])
        
        status = "✅" if result.get("ok") else "❌"
        checks.append({
            "name": ep["name"],
            "path": ep["path"],
            "status": status,
            "status_code": result.get("status_code"),
            "duration_ms": result.get("duration_ms"),
            "error": result.get("error")
        })
        
        if result.get("ok"):
            passed += 1
        else:
            failed += 1
    
    return {
        "success": True,
        "checks": checks,
        "summary": {
            "total": len(endpoints),
            "passed": passed,
            "failed": failed,
            "health_score": f"{(passed / len(endpoints)) * 100:.0f}%"
        }
    }


def list_routes() -> Dict[str, Any]:
    """
    List all registered API routes.
    
    Returns:
        {success, routes, count, error}
    """
    try:
        from backend.main import app
        
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods - {"HEAD", "OPTIONS"}) if route.methods else [],
                    "name": getattr(route, 'name', None)
                })
        
        # Sort by path
        routes.sort(key=lambda x: x["path"])
        
        # Group by prefix
        grouped = {}
        for route in routes:
            prefix = route["path"].split("/")[1] if "/" in route["path"] else "root"
            if prefix not in grouped:
                grouped[prefix] = []
            grouped[prefix].append(route)
        
        return {
            "success": True,
            "routes": routes,
            "count": len(routes),
            "by_prefix": {k: len(v) for k, v in grouped.items()}
        }
    except Exception as e:
        logger.error(f"list_routes error: {e}")
        return {"success": False, "error": str(e)}


# Convenience function for Daena
async def daena_api(command: str) -> Dict[str, Any]:
    """
    Parse a natural language API command and execute.
    
    Examples:
        "test /api/v1/departments/"
        "health check"
        "list routes"
        "post /api/v1/daena/chat {\"message\": \"hello\"}"
    """
    command = command.lower().strip()
    
    if command in ["health", "health check", "check health"]:
        return await health_check()
    
    elif command in ["routes", "list routes", "show routes"]:
        return list_routes()
    
    elif command.startswith("test ") or command.startswith("get "):
        path = command.split(" ", 1)[1].strip()
        return await test_endpoint(path, "GET")
    
    elif command.startswith("post "):
        parts = command[5:].strip().split(" ", 1)
        path = parts[0]
        body = None
        if len(parts) > 1:
            import json
            try:
                body = json.loads(parts[1])
            except:
                body = {"data": parts[1]}
        return await test_endpoint(path, "POST", body)
    
    else:
        return {
            "success": False,
            "error": "Unknown command. Try: health check, list routes, test <path>, post <path> {json}"
        }
