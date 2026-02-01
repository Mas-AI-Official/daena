"""Test streaming chat endpoint"""
import requests
import json
import time

print("="*60)
print("TESTING STREAMING CHAT ENDPOINT")
print("="*60)

try:
    start = time.time()
    print("\nSending request to /api/v1/daena/chat/stream...")
    
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat/stream",
        json={"message": "Say hello in 3 words"},
        stream=True,
        timeout=30
    )
    
    print(f"Status: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    
    if r.status_code == 200:
        print("\nStreaming response:")
        tokens = []
        for line in r.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                print(f"  {line_str}")
                if line_str.startswith('data: '):
                    try:
                        data = json.loads(line_str[6:])
                        if data.get('type') == 'token':
                            tokens.append(data.get('content', ''))
                    except:
                        pass
                if len(tokens) > 20:
                    print("  ... (stopping after 20 tokens)")
                    break
        
        elapsed = time.time() - start
        print(f"\n✅ Got {len(tokens)} tokens in {elapsed:.1f}s")
        print(f"Response: {''.join(tokens)}")
    else:
        print(f"\n❌ Error: {r.text[:500]}")
        
except requests.Timeout:
    elapsed = time.time() - start
    print(f"\n❌ TIMEOUT after {elapsed:.1f}s")
except Exception as e:
    print(f"\n❌ Error: {e}")

print("\n" + "="*60)
