"""Final test of chat with model fix"""
import requests
import time

print("Waiting for backend startup...")
time.sleep(5)

print("\n" + "="*60)
print("FINAL CHAT TEST - qwen2.5:14b-instruct")
print("="*60)

try:
    print("\n1. Testing brain status...")
    r = requests.get("http://127.0.0.1:8000/api/v1/brain/status", timeout=5)
    data = r.json()
    print(f"   Connected: {data.get('connected')}")
    print(f"   Active Model: {data.get('active_model', 'N/A')}")
    
    print("\n2. Testing chat (30s timeout)...")
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hello in 5 words"},
        timeout=30
    )
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ SUCCESS!")
        print(f"   Response: {data.get('response', 'No response')[:200]}")
        print(f"\n🎉 BRAIN IS WORKING!")
    else:
        print(f"   ❌ Status {r.status_code}: {r.text[:300]}")
except requests.Timeout:
    print(f"   ❌ Timeout - model might be too slow")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*60)
