"""Simple stream test - minimal, no file writing"""
import requests
import time

print("Testing streaming...")
start = time.time()

try:
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat/stream",
        json={"message": "hi"},
        stream=True,
        timeout=30
    )
    print(f"Status: {r.status_code}")
    
    count = 0
    for line in r.iter_lines():
        if line:
            count += 1
            text = line.decode('utf-8', errors='replace')
            print(f"Line {count}: {text[:80]}")
            if count >= 10:
                print("... stopping early")
                break
    
    print(f"\nGot {count} lines in {time.time()-start:.1f}s")
except requests.Timeout:
    print(f"TIMEOUT after {time.time()-start:.1f}s")
except Exception as e:
    print(f"Error: {e}")
