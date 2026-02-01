"""Quick chat test"""
import requests
import json

print("="*50)
print("TESTING CHAT ENDPOINT")
print("="*50)

try:
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hello"},
        timeout=20
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"✅ Response: {data.get('response', '')[:150]}")
    else:
        print(f"❌ Error: {r.text[:200]}")
except Exception as e:
    print(f"❌ Failed: {e}")
