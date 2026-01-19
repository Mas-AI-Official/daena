import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def make_request(url, method="GET", data=None):
    try:
        req = urllib.request.Request(url, method=method)
        if data:
            req.add_header('Content-Type', 'application/json')
            req.data = json.dumps(data).encode('utf-8')
        
        with urllib.request.urlopen(req) as response:
            return {
                "status": response.status,
                "body": response.read().decode('utf-8'),
                "url": response.geturl()
            }
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode('utf-8'), "error": str(e)}
    except Exception as e:
        return {"status": 0, "error": str(e)}

def test_ui_routes():
    routes = [
        "/ui/dashboard",
        "/ui/daena-office",
        "/ui/workspace",
        "/ui/departments",
        "/ui/agents",
        "/ui/founder-panel",
        "/ui/council"
    ]
    print("Testing UI Routes...")
    for route in routes:
        res = make_request(f"{BASE_URL}{route}")
        if res['status'] == 200:
            print(f"✅ {route} - 200 OK")
        elif res['status'] in [301, 302, 307]:
            print(f"⚠️ {route} - Redirect -> {res.get('url')}")
        else:
            print(f"❌ {route} - {res['status']} {res.get('error', '')}")

def test_chat_flow():
    print("\nTesting Chat Flow...")
    # Start Chat
    res = make_request(f"{BASE_URL}/api/v1/daena/chat/start", method="POST")
    if res['status'] != 200:
        print(f"❌ Start Chat Failed: {res['status']}")
        return
    
    data = json.loads(res['body'])
    session_id = data['session']['session_id']
    print(f"✅ Chat Started (Session: {session_id})")

    # Send Message
    msg_res = make_request(
        f"{BASE_URL}/api/v1/daena/chat/{session_id}/message",
        method="POST",
        data={"content": "Hello Daena, status report."}
    )
    if msg_res['status'] == 200:
        reply = json.loads(msg_res['body'])['daena_response']['content']
        print(f"✅ Message Sent. Reply: {reply[:50]}...")
    else:
        print(f"❌ Send Message Failed: {msg_res['status']}")

def test_workspace_flow():
    print("\nTesting Workspace Flow...")
    # Connect Folder
    res = make_request(
        f"{BASE_URL}/api/v1/workspace/connect",
        method="POST",
        data={"path": "."}
    )
    if res['status'] == 200:
        print(f"✅ Workspace Connect OK")
    else:
        print(f"❌ Workspace Connect Failed: {res['status']}")

    # Get Tree
    tree_res = make_request(f"{BASE_URL}/api/v1/workspace/tree?project_path=.")
    if tree_res['status'] == 200:
        items = json.loads(tree_res['body'])
        print(f"✅ Workspace Tree OK ({len(items)} items)")
    else:
        print(f"❌ Workspace Tree Failed: {tree_res['status']}")

if __name__ == "__main__":
    print("=== Daena Frontend Smoke Test ===")
    test_ui_routes()
    test_chat_flow()
    test_workspace_flow()
