"""Test Daena Chat API to diagnose brain connection issues"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"
OLLAMA_URL = "http://127.0.0.1:11434"

print("=" * 60)
print("DAENA BRAIN DIAGNOSTIC")
print("=" * 60)

# Test 1: Check Ollama models
print("\n1. Checking Ollama models...")
try:
    r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
    data = r.json()
    models = [m['name'] for m in data.get('models', [])]
    print(f"   ✅ Ollama models found: {models}")
except Exception as e:
    print(f"   ❌ Ollama error: {e}")
    models = []

# Test 2: Check brain status
print("\n2. Checking brain status...")
try:
    r = requests.get(f"{BASE_URL}/api/v1/brain/status", timeout=5)
    data = r.json()
    print(f"   Connected: {data.get('connected')}")
    print(f"   Ollama Available: {data.get('ollama_available')}")
    print(f"   Active Model: {data.get('active_model', 'N/A')}")
except Exception as e:
    print(f"   ❌ Brain status error: {e}")

# Test 3: Test Ollama directly
print("\n3. Testing Ollama directly...")
if models:
    model_name = models[0]
    print(f"   Using model: {model_name}")
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model_name, "prompt": "Say hello in 5 words", "stream": False},
            timeout=60
        )
        data = r.json()
        if 'response' in data:
            print(f"   ✅ Ollama response: {data['response'][:100]}...")
        else:
            print(f"   ❌ Ollama error: {data}")
    except Exception as e:
        print(f"   ❌ Ollama generate error: {e}")

# Test 4: Test Daena chat
print("\n4. Testing Daena chat API...")
try:
    r = requests.post(
        f"{BASE_URL}/api/v1/daena/chat",
        json={"message": "Hello, are you working?"},
        timeout=60
    )
    print(f"   Status code: {r.status_code}")
    data = r.json()
    if r.status_code == 200:
        print(f"   ✅ Response: {json.dumps(data, indent=2)[:300]}...")
    else:
        print(f"   ❌ Error: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"   ❌ Chat API error: {e}")

# Test 5: Test streaming chat
print("\n5. Testing Daena stream chat API...")
try:
    r = requests.post(
        f"{BASE_URL}/api/v1/daena/chat/stream",
        json={"message": "Say hi"},
        timeout=60,
        stream=True
    )
    print(f"   Status code: {r.status_code}")
    if r.status_code == 200:
        print("   Streaming response tokens:")
        for line in r.iter_lines():
            if line:
                print(f"   -> {line.decode()[:100]}")
                break  # Just show first chunk
        print("   ✅ Stream is working")
    else:
        print(f"   ❌ Error: {r.text[:200]}")
except Exception as e:
    print(f"   ❌ Stream API error: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
