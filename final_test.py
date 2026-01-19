"""FINAL TEST - After clean restart with model loaded"""
import requests
import time

print("\n" + "="*70)
print("FINAL TEST - Model Loaded, Backend Fresh")
print("="*70)

time.sleep(2)

# Test chat
print("\n[TEST] Chat response with model loaded:")
try:
    start = time.time()
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hello"},
        timeout=15
    )
    elapsed = time.time() - start
    
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ SUCCESS in {elapsed:.1f}s!")
        print(f"   Response: {data.get('response', '')[:150]}")
    else:
        print(f"   ❌ Error {r.status_code}: {r.text[:200]}")
except requests.Timeout:
    print(f"   ❌ TIMEOUT")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

print("\n" + "="*70)
