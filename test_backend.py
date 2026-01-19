"""Test backend chat endpoint directly to verify it works"""
import requests
import json

print("="*70)
print("BACKEND ENDPOINT TEST")
print("="*70)

# Test the exact endpoint the frontend uses
print("\n1. Testing /api/v1/daena/chat (non-streaming):")
try:
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hi"},
        headers={"Content-Type": "application/json"},
        timeout=20
    )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ Response received: {data.get('response', 'No response')[:100]}")
        print(f"   Session ID: {data.get('session_id')}")
    else:
        print(f"   ❌ Error: {r.text[:300]}")
except requests.Timeout:
    print(f"   ❌ TIMEOUT - Backend not responding")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

# Test streaming endpoint
print("\n2. Testing /api/v1/daena/chat/stream (streaming - what UI uses):")
try:
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat/stream",
        json={"message": "Hello"},
        headers={"Content-Type": "application/json"},
        timeout=20,
        stream=True
    )
    print(f"   Status: {r.status_code}")
    
    if r.status_code == 200:
        print(f"   ✅ Streaming response:")
        tokens = []
        for line in r.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'token':
                            tokens.append(data.get('content', ''))
                        print(f"      {line_str[:80]}")
                    except:
                        pass
                if len(tokens) > 5:  # Just show first few tokens
                    print(f"      ... (stopping after {len(tokens)} tokens)")
                    break
        print(f"   ✅ Streaming works! Got {len(tokens)} tokens")
    else:
        print(f"   ❌ Error: {r.text[:300]}")
except requests.Timeout:
    print(f"   ❌ TIMEOUT")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

print("\n" + "="*70)
