"""Quick chat test on port 8001"""
import requests

print("Testing chat on port 8001...")
try:
    r = requests.post(
        "http://127.0.0.1:8001/api/v1/daena/chat",
        json={"message": "Hi, say hello in 5 words"},
        timeout=120
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"✅ SUCCESS! Response: {data.get('response', 'No response field')[:300]}")
    else:
        print(f"❌ Error: {r.text[:500]}")
except Exception as e:
    print(f"❌ Failed: {e}")
