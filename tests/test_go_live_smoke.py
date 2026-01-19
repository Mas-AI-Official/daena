#!/usr/bin/env python3
"""
Go-Live Smoke Test - Verify Daena is alive and responding.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 5.0

def test_endpoint(url: str, expected_status: int = 200) -> tuple[bool, str]:
    """Test an endpoint and return (success, message)"""
    try:
        response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
        if response.status_code == expected_status:
            return True, f"✅ {url} - {response.status_code}"
        else:
            return False, f"❌ {url} - Expected {expected_status}, got {response.status_code}"
    except httpx.ConnectError:
        return False, f"❌ {url} - Connection refused (backend not running?)"
    except Exception as e:
        return False, f"❌ {url} - Error: {e}"

def test_daena_chat() -> tuple[bool, dict]:
    """Test Daena chat endpoint"""
    try:
        # Try the legacy endpoint first (SimpleChatRequest)
        response = httpx.post(
            f"{BASE_URL}/api/v1/daena/chat",
            json={
                "message": "Daena, summarize system status and list active agents.",
                "session_id": "smoke_test_session"
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            return False, {"error": f"Status {response.status_code}", "response": response.text}
        
        data = response.json()
        
        # Check required fields
        required_fields = ["response"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return False, {"error": f"Missing fields: {missing}", "data": data}
        
        # Check if response references brain
        response_text = data.get("response", "").lower()
        brain_indicators = ["brain", "daena", "agent", "system"]
        has_brain_ref = any(indicator in response_text for indicator in brain_indicators)
        
        result = {
            "status": "ok",
            "has_response": True,
            "response_length": len(data.get("response", "")),
            "brain_used": "brain" in response_text or "daena" in response_text,
            "agents_invoked": "agent" in response_text,
            "response_preview": data.get("response", "")[:200] + "..." if len(data.get("response", "")) > 200 else data.get("response", "")
        }
        
        return True, result
        
    except httpx.ConnectError:
        return False, {"error": "Connection refused (backend not running?)"}
    except Exception as e:
        return False, {"error": str(e)}


def test_agent_chat() -> tuple[bool, dict]:
    """
    Test that we can chat with at least one agent and get a response.
    This implicitly verifies that agent chat is wired and the canonical brain path is usable.
    """
    try:
        # 1) Get list of agents (follow redirects in case FastAPI redirects to trailing slash)
        agents_resp = httpx.get(f"{BASE_URL}/api/v1/agents", timeout=TIMEOUT, follow_redirects=True)
        if agents_resp.status_code != 200:
            return False, {"error": f"/api/v1/agents status {agents_resp.status_code}", "body": agents_resp.text}

        agents_data = agents_resp.json()
        agents = agents_data.get("agents") or []
        if not agents:
            return False, {"error": "No agents returned from /api/v1/agents", "data": agents_data}

        first_agent = agents[0]
        # Try multiple possible ID fields
        agent_id = (
            first_agent.get("id") or 
            first_agent.get("agent_id") or 
            first_agent.get("_id") or
            first_agent.get("cell_id")
        )
        if not agent_id:
            return False, {
                "error": "Agent missing id field", 
                "agent": first_agent,
                "available_keys": list(first_agent.keys())
            }
        
        # Ensure agent_id is a string (not numeric)
        agent_id = str(agent_id)

        # 2) Chat with that agent
        chat_resp = httpx.post(
            f"{BASE_URL}/api/v1/agents/{agent_id}/chat",
            json={
                "message": "Daena, via this agent, summarize system status and confirm you are using the shared brain.",
                "context": {"source": "go_live_smoke_test"}
            },
            timeout=30.0,
        )
        if chat_resp.status_code != 200:
            return False, {"error": f"/api/v1/agents/{agent_id}/chat status {chat_resp.status_code}", "body": chat_resp.text}

        data = chat_resp.json()
        if not data.get("success"):
            return False, {"error": "Agent chat returned success = false", "data": data}

        response_text = str(data.get("response", ""))  # brain_response is passed through
        if not response_text:
            return False, {"error": "Empty agent response", "data": data}

        lowered = response_text.lower()
        result = {
            "status": "ok",
            "agent_id": agent_id,
            "response_length": len(response_text),
            "brain_used_hint": any(k in lowered for k in ["brain", "daena", "agent"]),
            "preview": response_text[:200] + ("..." if len(response_text) > 200 else ""),
        }
        return True, result

    except httpx.ConnectError:
        return False, {"error": "Connection refused (backend not running?)"}
    except Exception as e:
        return False, {"error": str(e)}

def main() -> int:
    """Run smoke tests"""
    print("=" * 60)
    print("DAENA GO-LIVE SMOKE TEST")
    print("=" * 60)
    print()
    print(f"Testing: {BASE_URL}")
    print()
    
    # Wait a moment for backend to be ready
    print("Waiting 2 seconds for backend to stabilize...")
    time.sleep(2)
    print()
    
    # Test UI endpoints
    print("Testing UI Endpoints:")
    print("-" * 60)
    
    ui_endpoints = [
        "/ui/dashboard",
        "/ui/departments",
        "/ui/agents",
        "/ui/council-dashboard",
        "/ui/council-debate",
        "/ui/council-synthesis",
        "/ui/voice-panel",
        "/ui/task-timeline",
        "/ui/health",
    ]
    
    ui_results = []
    for endpoint in ui_endpoints:
        url = f"{BASE_URL}{endpoint}"
        success, message = test_endpoint(url)
        print(f"  {message}")
        ui_results.append(success)
    
    print()
    
    # Test Daena chat
    print("Testing Daena Chat Endpoint:")
    print("-" * 60)
    
    chat_success, chat_result = test_daena_chat()
    if chat_success:
        print(f"  ✅ Chat endpoint responded")
        print(f"     Response length: {chat_result.get('response_length', 0)} chars")
        print(f"     Brain used: {chat_result.get('brain_used', False)}")
        print(f"     Agents invoked: {chat_result.get('agents_invoked', False)}")
        print(f"     Preview: {chat_result.get('response_preview', 'N/A')}")
    else:
        print(f"  ❌ Chat endpoint failed: {chat_result.get('error', 'Unknown error')}")
    
    print()

    # Test Agent chat
    print("Testing Agent Chat Endpoint:")
    print("-" * 60)
    agent_success, agent_result = test_agent_chat()
    if agent_success:
        print(f"  ✅ Agent chat responded")
        print(f"     Agent ID: {agent_result.get('agent_id')}")
        print(f"     Response length: {agent_result.get('response_length', 0)} chars")
        print(f"     Brain used hint: {agent_result.get('brain_used_hint', False)}")
        print(f"     Preview: {agent_result.get('preview', 'N/A')}")
    else:
        print(f"  ❌ Agent chat failed: {agent_result.get('error', 'Unknown error')}")

    print()
    
    # Summary
    all_ui_pass = all(ui_results)
    all_pass = all_ui_pass and chat_success and agent_success
    
    print("=" * 60)
    if all_pass:
        print("✅ ALL SMOKE TESTS PASSED")
        print("=" * 60)
        print()
        print("Daena is LIVE and responding correctly (UI + Daena chat + Agent chat)!")
        return 0
    else:
        print("❌ SOME SMOKE TESTS FAILED")
        print("=" * 60)
        print()
        print("Failed tests:")
        if not all_ui_pass:
            failed_ui = [ui_endpoints[i] for i, r in enumerate(ui_results) if not r]
            for endpoint in failed_ui:
                print(f"  - {endpoint}")
        if not chat_success:
            print(f"  - /api/v1/daena/chat: {chat_result.get('error', 'Unknown error')}")
        if not agent_success:
            print(f"  - /api/v1/agents/{{id}}/chat: {agent_result.get('error', 'Unknown error')}")
        print()
        return 1

if __name__ == "__main__":
    sys.exit(main())

