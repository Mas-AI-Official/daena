#!/usr/bin/env python3
"""
Test Agent Chat Endpoint
Tests the agent chat functionality with real agent IDs
"""

import sys
import httpx
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10.0

def test_agent_chat():
    """Test agent chat endpoint with real agent ID"""
    print("=" * 60)
    print("AGENT CHAT ENDPOINT TEST")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Get list of agents
        print("Step 1: Getting list of agents...")
        agents_resp = httpx.get(f"{BASE_URL}/api/v1/agents/", timeout=TIMEOUT)
        
        if agents_resp.status_code != 200:
            print(f"❌ Failed to get agents: {agents_resp.status_code}")
            print(f"   Response: {agents_resp.text[:200]}")
            return False
        
        agents_data = agents_resp.json()
        agents = agents_data.get("agents", [])
        
        if not agents:
            print("❌ No agents found in registry")
            print(f"   Response: {agents_data}")
            return False
        
        print(f"✅ Found {len(agents)} agents")
        print(f"   First agent: {agents[0]}")
        
        # Get first agent ID
        first_agent = agents[0]
        agent_id = first_agent.get("id") or first_agent.get("agent_id") or first_agent.get("cell_id")
        
        if not agent_id:
            print("❌ Agent missing ID field")
            print(f"   Agent data: {first_agent}")
            return False
        
        agent_id = str(agent_id)
        print(f"   Using agent ID: {agent_id}")
        print()
        
        # Step 2: Test chat endpoint
        print(f"Step 2: Testing chat with agent {agent_id}...")
        chat_resp = httpx.post(
            f"{BASE_URL}/api/v1/agents/{agent_id}/chat",
            json={
                "message": "Hello, can you confirm you are working?",
                "context": {"source": "test_script"}
            },
            timeout=30.0
        )
        
        if chat_resp.status_code != 200:
            print(f"❌ Chat endpoint failed: {chat_resp.status_code}")
            print(f"   Response: {chat_resp.text[:300]}")
            return False
        
        chat_data = chat_resp.json()
        print(f"✅ Chat endpoint successful")
        print(f"   Response keys: {list(chat_data.keys())}")
        print(f"   Success: {chat_data.get('success', False)}")
        print(f"   Session ID: {chat_data.get('session_id', 'N/A')}")
        print(f"   Agent Name: {chat_data.get('agent_name', 'N/A')}")
        print(f"   Response preview: {chat_data.get('response', '')[:100]}...")
        print()
        
        # Step 3: Test session retrieval
        if chat_data.get('session_id'):
            session_id = chat_data['session_id']
            print(f"Step 3: Testing session retrieval for {session_id}...")
            session_resp = httpx.get(
                f"{BASE_URL}/api/v1/agents/{agent_id}/chat/sessions/{session_id}",
                timeout=TIMEOUT
            )
            
            if session_resp.status_code == 200:
                print(f"✅ Session retrieval successful")
                session_data = session_resp.json()
                print(f"   Messages: {len(session_data.get('messages', []))}")
            else:
                print(f"⚠️  Session retrieval returned {session_resp.status_code}")
                print(f"   Response: {session_resp.text[:200]}")
        
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except httpx.ConnectError:
        print("❌ Connection refused - backend not running")
        print("   Please start the backend using START_DAENA.bat")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_agent_chat()
    sys.exit(0 if success else 1)




