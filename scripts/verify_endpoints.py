#!/usr/bin/env python3
"""
Endpoint Verification Script
Verifies that all critical endpoints are properly registered and accessible
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path.parent))

import asyncio
import httpx
from typing import Dict, List, Tuple

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 5.0

# Expected endpoints
EXPECTED_ENDPOINTS = {
    "Health": [
        ("GET", "/api/v1/health/"),
        ("GET", "/health/"),
    ],
    "System": [
        ("GET", "/api/v1/system/stats"),
        ("GET", "/api/v1/daena/status"),
    ],
    "Agents": [
        ("GET", "/api/v1/agents/"),
        ("GET", "/api/v1/agents/?limit=10"),
    ],
    "Departments": [
        ("GET", "/api/v1/departments/"),
    ],
    "Brain": [
        ("GET", "/api/v1/brain/status"),
    ],
    "LLM": [
        ("GET", "/api/v1/llm/status"),
    ],
    "Voice": [
        ("GET", "/api/v1/voice/status"),
    ],
}

async def check_endpoint(client: httpx.AsyncClient, method: str, path: str) -> Tuple[bool, str, int]:
    """Check if an endpoint is accessible"""
    url = f"{BASE_URL}{path}"
    try:
        response = await client.request(method, url, timeout=TIMEOUT, follow_redirects=True)
        status = response.status_code
        if status < 500:  # 2xx, 3xx, 4xx are OK (endpoint exists)
            return True, "OK", status
        else:
            return False, f"Server error: {status}", status
    except httpx.ConnectError:
        return False, "Connection refused (backend not running?)", 0
    except httpx.TimeoutException:
        return False, "Timeout", 0
    except Exception as e:
        return False, f"Error: {str(e)}", 0

async def verify_all_endpoints():
    """Verify all expected endpoints"""
    print("=" * 60)
    print("ENDPOINT VERIFICATION")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}\n")
    
    async with httpx.AsyncClient() as client:
        all_passed = True
        results = {}
        
        for category, endpoints in EXPECTED_ENDPOINTS.items():
            print(f"\n{category} Endpoints:")
            print("-" * 60)
            category_passed = True
            
            for method, path in endpoints:
                success, message, status = await check_endpoint(client, method, path)
                status_icon = "✅" if success else "❌"
                status_text = f"({status})" if status > 0 else ""
                
                print(f"  {status_icon} {method:6} {path:40} {status_text}")
                if not success:
                    print(f"      └─ {message}")
                    category_passed = False
                    all_passed = False
                
                results[f"{method} {path}"] = (success, message, status)
            
            if category_passed:
                print(f"  ✅ All {category} endpoints OK")
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✅ ALL ENDPOINTS VERIFIED")
        else:
            print("❌ SOME ENDPOINTS FAILED")
            print("\nFailed endpoints:")
            for endpoint, (success, message, status) in results.items():
                if not success:
                    print(f"  - {endpoint}: {message}")
        print("=" * 60)
        
        return all_passed

if __name__ == "__main__":
    try:
        result = asyncio.run(verify_all_endpoints())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Verification interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
