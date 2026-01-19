"""
Daena E2E Reality Pass v2 - Test Suite
Run with: python scripts/e2e_reality_tests.py

Tests all major features that were fixed during the E2E pass.
"""

import asyncio
import httpx
import sys
from typing import Dict, Any, List
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", duration_ms: float = 0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration_ms = duration_ms

async def test_health_endpoint() -> TestResult:
    """Test that /health endpoint returns 200"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/health")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                return TestResult("Health Endpoint", True, "Returns 200 OK", duration)
            else:
                return TestResult("Health Endpoint", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Health Endpoint", False, str(e))

async def test_brain_status() -> TestResult:
    """Test brain/Ollama status"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/api/v1/brain/status")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                connected = data.get("connected", False)
                return TestResult("Brain Status", connected, 
                                  f"Connected: {connected}", duration)
            else:
                return TestResult("Brain Status", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Brain Status", False, str(e))

async def test_voice_status() -> TestResult:
    """Test voice service status endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/api/v1/voice/status")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                return TestResult("Voice Status", True, "Voice service online", duration)
            else:
                return TestResult("Voice Status", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Voice Status", False, str(e))

async def test_voice_toggle() -> TestResult:
    """Test voice toggle endpoint works"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.post(
                f"{BASE_URL}/api/v1/voice/talk-mode",
                json={"enabled": True}
            )
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                return TestResult("Voice Toggle", True, "Toggle works", duration)
            else:
                return TestResult("Voice Toggle", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Voice Toggle", False, str(e))

async def test_chat_send() -> TestResult:
    """Test sending a chat message"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = datetime.now()
            resp = await client.post(
                f"{BASE_URL}/api/v1/daena/chat",
                json={"message": "Hello Daena, this is a test."}
            )
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                has_response = bool(data.get("response") or data.get("daena_response"))
                return TestResult("Chat Send", has_response, 
                                  "Got response" if has_response else "No response", duration)
            else:
                return TestResult("Chat Send", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Chat Send", False, str(e))

async def test_chat_sessions_list() -> TestResult:
    """Test listing chat sessions"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/api/v1/daena/chat/sessions")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                sessions = data.get("sessions", [])
                return TestResult("Chat Sessions List", True, 
                                  f"Found {len(sessions)} sessions", duration)
            else:
                return TestResult("Chat Sessions List", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Chat Sessions List", False, str(e))

async def test_departments_list() -> TestResult:
    """Test listing departments"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/api/v1/departments/")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                depts = data if isinstance(data, list) else data.get("departments", [])
                return TestResult("Departments List", len(depts) > 0, 
                                  f"Found {len(depts)} departments", duration)
            else:
                return TestResult("Departments List", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Departments List", False, str(e))

async def test_agents_list() -> TestResult:
    """Test listing agents"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/api/v1/agents/")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                agents = data if isinstance(data, list) else data.get("agents", [])
                return TestResult("Agents List", True, 
                                  f"Found {len(agents)} agents", duration)
            else:
                return TestResult("Agents List", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Agents List", False, str(e))

async def test_diagnostics_tool() -> TestResult:
    """Test that diagnostics tool works when user says 'run diagnostics'"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = datetime.now()
            resp = await client.post(
                f"{BASE_URL}/api/v1/daena/chat",
                json={"message": "run diagnostics"}
            )
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                response_text = data.get("response", "")
                # Check if it's a real tool response (has structured data)
                is_tool_response = "health" in response_text.lower() or "endpoints" in response_text.lower()
                return TestResult("Diagnostics Tool", is_tool_response, 
                                  "Tool executed" if is_tool_response else "Got generic response", duration)
            else:
                return TestResult("Diagnostics Tool", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Diagnostics Tool", False, str(e))

async def test_model_registry() -> TestResult:
    """Test model registry endpoint"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now()
            resp = await client.get(f"{BASE_URL}/api/v1/models/")
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                return TestResult("Model Registry", True, "Registry accessible", duration)
            else:
                return TestResult("Model Registry", False, f"Status: {resp.status_code}", duration)
    except Exception as e:
        return TestResult("Model Registry", False, str(e))

async def run_all_tests():
    """Run all E2E tests"""
    print("\n" + "="*60)
    print(" Daena E2E Reality Pass v2 - Test Suite")
    print("="*60 + "\n")
    
    tests = [
        test_health_endpoint,
        test_brain_status,
        test_voice_status,
        test_voice_toggle,
        test_chat_send,
        test_chat_sessions_list,
        test_departments_list,
        test_agents_list,
        test_diagnostics_tool,
        test_model_registry,
    ]
    
    results: List[TestResult] = []
    
    for test_func in tests:
        print(f"Running: {test_func.__name__}...", end=" ")
        result = await test_func()
        results.append(result)
        
        status = "✅" if result.passed else "❌"
        print(f"{status} {result.message} ({result.duration_ms:.0f}ms)")
    
    # Summary
    print("\n" + "-"*60)
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\nResults: {passed}/{total} passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print("\nFailed tests:")
        for r in results:
            if not r.passed:
                print(f"  - {r.name}: {r.message}")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
