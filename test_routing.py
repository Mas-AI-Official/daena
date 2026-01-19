import urllib.request
import json

def test_routing():
    url = "http://localhost:8000/api/v1/automation/route"
    
    # Test 1: Reasoning Task
    payload = {
        "message": "Solve this logic puzzle: Three people enter a room...",
        "context": {"role": "analyst"}
    }
    
    try:
        print(f"Testing Reasoning Task...")
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        jsondata = json.dumps(payload).encode('utf-8')
        req.add_header('Content-Length', len(jsondata))
        
        response = urllib.request.urlopen(req, jsondata)
        print(f"Status: {response.getcode()}")
        print(f"Response: {json.dumps(json.loads(response.read()), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: Creative Task
    payload = {
        "message": "Write a creative story about a robot",
        "context": {"role": "writer"}
    }
    
    try:
        print(f"\nTesting Creative Task...")
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        jsondata = json.dumps(payload).encode('utf-8')
        req.add_header('Content-Length', len(jsondata))
        
        response = urllib.request.urlopen(req, jsondata)
        print(f"Status: {response.getcode()}")
        print(f"Response: {json.dumps(json.loads(response.read()), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_routing()
