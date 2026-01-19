"""Final verification test"""
import requests
import json

print("\n" + "="*60)
print("FINAL VERIFICATION - All Systems")
print("="*60)

# Test 1: Ping Ollama
print("\n1. Testing Ollama Ping...")
try:
    r = requests.get("http://127.0.0.1:8000/api/v1/brain/ping-ollama", timeout=35)
    data = r.json()
    status = data.get("overall_status")
    if status == "healthy":
        gen_ms = data.get("tests", {}).get("generate", {}).get("duration_ms", 0)
        print(f"   ✅ Ollama healthy ({gen_ms}ms response)")
    else:
        print(f"   ❌ Ollama {status}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Chat
print("\n2. Testing Chat...")
try:
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hello"},
        timeout=20
    )
    if r.status_code == 200:
        data = r.json()
        response = data.get("response", "")[:100]
        print(f"   ✅ Chat working: {response}")
    else:
        print(f"   ❌ Status {r.status_code}")
except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: Brain Status
print("\n3. Testing Brain Status...")
try:
    r = requests.get("http://127.0.0.1:8000/api/v1/brain/status", timeout=5)
    data = r.json()
    connected = data.get("connected")
    model = data.get("active_model", "unknown")
    print(f"   ✅ Connected: {connected}, Model: {model}")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
print("VERIFICATION COMPLETE")
print("="*60 + "\n")
