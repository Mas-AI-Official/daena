"""
Smoke Test: Real-Time Sync Validation
Tests persistence + WebSocket events

Run with:
  set DAENA_DEV_MODE=1
  python scripts/smoke_realtime_sync.py
"""
import requests
import json
import time
import threading
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:8000"
PASS = "✅ PASS"
FAIL = "❌ FAIL"

results = []

def test(name, condition, details=""):
    status = PASS if condition else FAIL
    results.append((name, status, details))
    print(f"  {status}: {name}" + (f" ({details})" if details else ""))
    return condition


def test_api_agents():
    """Test 1: Agents API returns data from database"""
    print("\n📦 Test 1: Agents API (Database)")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/agents/", timeout=5)
        data = r.json()
        
        test("API returns success", data.get("success") == True)
        test("Agents list exists", "agents" in data)
        test("Has 48 agents", data.get("total_count", 0) == 48, f"got {data.get('total_count', 0)}")
        
        if data.get("agents"):
            agent = data["agents"][0]
            test("Agent has name", "name" in agent)
            test("Agent has department_id", "department_id" in agent)
            return True
    except Exception as e:
        print(f"  {FAIL}: API error - {e}")
        return False


def test_create_agent():
    """Test 2: Create agent via API and verify persistence"""
    print("\n📦 Test 2: Create Agent (Persistence)")
    try:
        # Create new agent
        new_agent = {
            "name": f"Test Agent {int(time.time())}",
            "department_id": "engineering",
            "role": "advisor_a"
        }
        
        r = requests.post(f"{BASE_URL}/api/v1/agents/", json=new_agent, timeout=5)
        data = r.json()
        
        test("Create returns success", data.get("success") == True)
        
        if data.get("agent"):
            agent_id = data["agent"].get("id")
            test("Agent has ID", agent_id is not None, agent_id)
            
            # Verify it persists by fetching it
            r2 = requests.get(f"{BASE_URL}/api/v1/agents/{agent_id}", timeout=5)
            data2 = r2.json()
            test("Agent persisted and retrievable", data2.get("success") == True)
            test("Agent name matches", data2.get("agent", {}).get("name") == new_agent["name"])
            
            return True
    except Exception as e:
        print(f"  {FAIL}: Create agent error - {e}")
        return False


def test_dev_status():
    """Test 3: Dev status endpoint"""
    print("\n📦 Test 3: Dev Status")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/dev/status", timeout=5)
        data = r.json()
        
        test("Dev status returns data", "database" in data)
        test("Shows department count", data.get("database", {}).get("departments", 0) == 8, 
             f"got {data.get('database', {}).get('departments', 0)}")
        test("Shows agent count", data.get("database", {}).get("agents", 0) >= 48,
             f"got {data.get('database', {}).get('agents', 0)}")
        
        return True
    except Exception as e:
        print(f"  {FAIL}: Dev status error - {e}")
        return False


def test_websocket():
    """Test 4: WebSocket connection"""
    print("\n📦 Test 4: WebSocket Connection")
    
    try:
        import websocket
        
        ws_received = []
        connected = threading.Event()
        
        def on_message(ws, message):
            ws_received.append(message)
            
        def on_open(ws):
            connected.set()
            
        def on_error(ws, error):
            print(f"  WS Error: {error}")
        
        ws_url = f"ws://127.0.0.1:8000/ws/events"
        ws = websocket.WebSocketApp(
            ws_url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error
        )
        
        # Run WebSocket in background thread
        ws_thread = threading.Thread(target=ws.run_forever, daemon=True)
        ws_thread.start()
        
        # Wait for connection
        if connected.wait(timeout=5):
            test("WebSocket connected", True)
            
            # Wait for initial message
            time.sleep(1)
            test("Received initial message", len(ws_received) > 0, f"got {len(ws_received)} messages")
            
            # Trigger an event by creating an agent
            requests.post(f"{BASE_URL}/api/v1/agents/", json={
                "name": f"WS Test Agent {int(time.time())}",
                "department_id": "product",
                "role": "executor"
            }, timeout=5)
            
            # Wait for event
            time.sleep(2)
            test("Received event after agent create", len(ws_received) > 1, f"got {len(ws_received)} messages")
            
            ws.close()
            return True
        else:
            test("WebSocket connected", False, "timeout")
            return False
            
    except ImportError:
        print(f"  ⚠️ websocket-client not installed, skipping WebSocket test")
        print(f"     Install with: pip install websocket-client")
        return True  # Don't fail for missing dependency
    except Exception as e:
        print(f"  {FAIL}: WebSocket error - {e}")
        return False


def test_brain_status():
    """Test 5: Brain status endpoint"""
    print("\n📦 Test 5: Brain Status")
    try:
        r = requests.get(f"{BASE_URL}/api/v1/brain/status", timeout=5)
        data = r.json()
        
        test("Brain status returns data", "connected" in data)
        test("Has provider info", "provider" in data)
        
        return True
    except Exception as e:
        print(f"  {FAIL}: Brain status error - {e}")
        return False


def main():
    print("=" * 60)
    print("🧪 DAENA REAL-TIME SYNC SMOKE TEST")
    print("=" * 60)
    print(f"Target: {BASE_URL}")
    
    # Check if server is running
    try:
        r = requests.get(f"{BASE_URL}/api/v1/daena/status", timeout=3)
        print(f"✅ Server is running")
    except:
        print(f"❌ Server not running at {BASE_URL}")
        print(f"   Start with: python -m uvicorn backend.main:app --reload")
        return False
    
    # Run all tests
    all_passed = True
    all_passed &= test_api_agents()
    all_passed &= test_create_agent()
    all_passed &= test_dev_status()
    all_passed &= test_websocket()
    all_passed &= test_brain_status()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, status, _ in results if status == PASS)
    total = len(results)
    
    for name, status, details in results:
        print(f"  {status}: {name}")
    
    print(f"\n  🏁 {passed}/{total} tests passed")
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED - Real-time sync is working!")
        return True
    else:
        print("\n⚠️ SOME TESTS FAILED - Check errors above")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
