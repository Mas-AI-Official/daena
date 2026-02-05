"""
Test brain connections to departments, agents, and daena
"""

import sys
import os
import asyncio
import httpx
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

async def test_brain_connections():
    """Test all brain connections"""
    print("=" * 60)
    print("BRAIN CONNECTION TEST")
    print("=" * 60)
    print()
    
    base_url = "http://127.0.0.1:8000"
    errors = []
    
    # Test 1: Brain Status
    print("[1/5] Testing brain status endpoint...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/api/v1/brain/status")
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] Brain status: connected={data.get('connected')}, ollama={data.get('ollama_available')}")
                if not data.get('connected'):
                    errors.append("Brain not connected")
                if not data.get('ollama_available'):
                    errors.append("Ollama not available")
            else:
                errors.append(f"Brain status returned {response.status_code}")
                print(f"[ERROR] Brain status: HTTP {response.status_code}")
    except Exception as e:
        errors.append(f"Brain status error: {e}")
        print(f"[ERROR] Brain status: {e}")
    print()
    
    # Test 2: Brain Query
    print("[2/5] Testing brain query endpoint...")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{base_url}/api/v1/brain/query",
                json={"query": "Test query", "context": {}}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] Brain query works: {len(data.get('response', ''))} chars")
            else:
                errors.append(f"Brain query returned {response.status_code}")
                print(f"[ERROR] Brain query: HTTP {response.status_code}")
    except Exception as e:
        errors.append(f"Brain query error: {e}")
        print(f"[ERROR] Brain query: {e}")
    print()
    
    # Test 3: Daena Chat
    print("[3/5] Testing Daena chat endpoint...")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{base_url}/api/v1/chat",
                json={"message": "Hello", "context": {"session_id": "test"}}
            )
            if response.status_code == 200:
                print("[OK] Daena chat endpoint works")
            else:
                errors.append(f"Daena chat returned {response.status_code}")
                print(f"[ERROR] Daena chat: HTTP {response.status_code}")
    except Exception as e:
        errors.append(f"Daena chat error: {e}")
        print(f"[ERROR] Daena chat: {e}")
    print()
    
    # Test 4: Agent Chat
    print("[4/5] Testing agent chat endpoint...")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get first agent
            agents_response = await client.get(f"{base_url}/api/v1/agents/")
            if agents_response.status_code == 200:
                agents_data = agents_response.json()
                if agents_data.get('agents') and len(agents_data['agents']) > 0:
                    first_agent = agents_data['agents'][0]
                    agent_id = first_agent.get('id') or str(first_agent.get('agent_id', '1'))
                    print(f"  Testing with agent: {agent_id}")
                    
                    response = await client.post(
                        f"{base_url}/api/v1/agents/{agent_id}/chat",
                        json={"message": "Hello", "context": {}}
                    )
                    if response.status_code == 200:
                        print("[OK] Agent chat endpoint works")
                    else:
                        errors.append(f"Agent chat returned {response.status_code}")
                        print(f"[ERROR] Agent chat: HTTP {response.status_code}")
                else:
                    print("[WARN] No agents found to test")
            else:
                errors.append(f"Could not get agents list: {agents_response.status_code}")
    except Exception as e:
        errors.append(f"Agent chat error: {e}")
        print(f"[ERROR] Agent chat: {e}")
    print()
    
    # Test 5: Department Chat
    print("[5/5] Testing department chat endpoint...")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Get first department
            dept_response = await client.get(f"{base_url}/api/v1/departments/")
            if dept_response.status_code == 200:
                dept_data = dept_response.json()
                if dept_data.get('departments') and len(dept_data['departments']) > 0:
                    first_dept = dept_data['departments'][0]
                    dept_id = first_dept.get('id', 'engineering')
                    print(f"  Testing with department: {dept_id}")
                    
                    response = await client.post(
                        f"{base_url}/api/v1/departments/{dept_id}/chat",
                        json={"message": "Hello", "context": {}}
                    )
                    if response.status_code == 200:
                        print("[OK] Department chat endpoint works")
                    else:
                        errors.append(f"Department chat returned {response.status_code}")
                        print(f"[ERROR] Department chat: HTTP {response.status_code}")
                else:
                    print("[WARN] No departments found to test")
            else:
                errors.append(f"Could not get departments list: {dept_response.status_code}")
    except Exception as e:
        errors.append(f"Department chat error: {e}")
        print(f"[ERROR] Department chat: {e}")
    print()
    
    # Summary
    print("=" * 60)
    if not errors:
        print("[OK] ALL CONNECTIONS WORKING")
        print("=" * 60)
        return True
    else:
        print("[ERROR] SOME CONNECTIONS FAILED")
        print("=" * 60)
        for error in errors:
            print(f"  - {error}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_brain_connections())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




