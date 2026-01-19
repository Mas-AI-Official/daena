import urllib.request
import urllib.error
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def check_url(path, method="GET", data=None, expected_status=200):
    url = f"{BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method=method)
        if data:
            req.add_header('Content-Type', 'application/json')
            req.data = json.dumps(data).encode('utf-8')
        
        with urllib.request.urlopen(req) as response:
            status = response.status
            if status == expected_status:
                print(f"✅ PASS: {method} {path} -> {status}")
                return True
            else:
                print(f"❌ FAIL: {method} {path} -> Expected {expected_status}, got {status}")
                return False
    except urllib.error.HTTPError as e:
        if e.code == expected_status:
            print(f"✅ PASS: {method} {path} -> {e.code}")
            return True
        print(f"❌ FAIL: {method} {path} -> {e.code} {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"❌ FAIL: {method} {path} -> Connection refused (Backend not running?)")
        return False
    except Exception as e:
        print(f"❌ FAIL: {method} {path} -> {str(e)}")
        return False

def run_tests():
    print("🚀 Starting Frontend Sync Verification...")
    print(f"Target: {BASE_URL}")
    
    # 1. UI Routes (Should be 200 OK, no redirects if auth disabled/mocked)
    ui_routes = [
        "/ui/dashboard",
        "/ui/daena-office",
        "/ui/workspace",
        "/ui/departments",
        "/ui/agents",
        "/ui/founder-panel",
        "/ui/operator"  # Might be 404 if I didn't register it in backend/routes/ui.py yet!
    ]
    
    print("\n--- UI Routes ---")
    for route in ui_routes:
        check_url(route)

    # 2. API Endpoints (Critical for JS Client)
    print("\n--- API Endpoints ---")
    check_url("/api/v1/daena/status")
    check_url("/api/v1/system/executive-metrics")
    check_url("/api/v1/daena/chat/sessions")
    
    # 3. Chat Flow
    print("\n--- Chat Flow ---")
    # Start Chat
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/daena/chat/start", method="POST")
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            session_id = data['session']['session_id']
            print(f"✅ PASS: POST /chat/start -> Session {session_id}")
            
            # Send Message
            msg_data = {"content": "Hello Daena verification"}
            check_url(f"/api/v1/daena/chat/{session_id}/message", method="POST", data=msg_data)
    except Exception as e:
        print(f"❌ FAIL: Chat Flow -> {str(e)}")

    # 4. Workspace Flow
    print("\n--- Workspace Flow ---")
    # Connect to self
    check_url("/api/v1/workspace/connect", method="POST", data={"path": "."})

if __name__ == "__main__":
    run_tests()
