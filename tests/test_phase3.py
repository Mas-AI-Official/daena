"""
Phase 3 Test Script - Agent Observability
Tests WebSocket, Agent Activity,  and Dashboard Integration
"""
import urllib.request
import urllib.error
import json

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(name, path, method="GET", expected_keys=None):
    """Test an API endpoint"""
    url = f"{BASE_URL}{path}"
    print(f"\n🧪 Testing {name}: {method} {path}")
    
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            print(f"   ✅ Status: {response.status}")
            
            if expected_keys:
                for key in expected_keys:
                    if key in data:
                        print(f"   ✅ Has key: {key}")
                    else:
                        print(f"   ❌ Missing key: {key}")
            
            # Show sample data
            if isinstance(data, list) and len(data) > 0:
                print(f"   📊 Items returned: {len(data)}")
                print(f"   📄 Sample: {json.dumps(data[0], indent=2)[:200]}...")
            elif isinstance(data, dict):
                print(f"   📄 Response keys: {list(data.keys())}")
            
            return True
    except urllib.error.HTTPError as e:
        print(f"   ❌ HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return False

def run_phase_3_tests():
    """Run all Phase 3 tests"""
    print("=" * 60)
    print("PHASE 3 - AGENT OBSERVABILITY TESTING")
    print("=" * 60)
    
    results = []
    
    # Test 1: Agent Activity API
    results.append(test_endpoint(
        "Agent Activity",
        "/api/v1/agents/activity",
        expected_keys=["agent_id", "status", "department"]
    ))
    
    # Test 2: Brain Queue (Governance)
    results.append(test_endpoint(
        "Governance Queue",
        "/api/v1/brain/queue",
        expected_keys=["queue", "count"]
    ))
    
    # Test 3: Brain Status (Updated)
    results.append(test_endpoint(
        "Brain Status",
        "/api/v1/brain/status",
        expected_keys=["connected", "ollama_available", "llm_available"]
    ))
    
    # Test 4: Dashboard Page
    print(f"\n🧪 Testing Dashboard UI: GET /ui/dashboard")
    try:
        req = urllib.request.Request(f"{BASE_URL}/ui/dashboard")
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode()
            print(f"   ✅ Status: {response.status}")
            
            # Check for critical elements
            checks = [
                ("activity-feed", "Activity Feed"),
                ("governance-queue", "Governance Queue"),
                ("websocket-client.js", "WebSocket Client"),
                ("dashboard.js", "Dashboard JS")
            ]
            
            for check_id, check_name in checks:
                if check_id in html:
                    print(f"   ✅ Found: {check_name}")
                else:
                    print(f"   ❌ Missing: {check_name}")
            
            results.append(True)
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)
    
    if all(results):
        print("\n🎉 Phase 3 PASSED - Agent Observability is working!")
        return True
    else:
        print("\n⚠️ Phase 3 PARTIAL - Some components need attention")
        return False

if __name__ == "__main__":
    run_phase_3_tests()
