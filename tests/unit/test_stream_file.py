"""Test streaming chat endpoint - writes to file"""
import requests
import json
import time
import sys

output_file = "D:/Ideas/Daena_old_upgrade_20251213/stream_test_result.txt"

with open(output_file, 'w') as f:
    f.write("="*60 + "\n")
    f.write("TESTING STREAMING CHAT ENDPOINT\n")
    f.write("="*60 + "\n\n")

    try:
        start = time.time()
        f.write("Sending request to /api/v1/daena/chat/stream...\n")
        f.flush()
        
        r = requests.post(
            "http://127.0.0.1:8000/api/v1/daena/chat/stream",
            json={"message": "Say hello"},
            stream=True,
            timeout=30
        )
        
        f.write(f"Status: {r.status_code}\n")
        f.write(f"Headers: {dict(r.headers)}\n\n")
        
        if r.status_code == 200:
            f.write("Streaming response:\n")
            tokens = []
            for line in r.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    f.write(f"  {line_str}\n")
                    if line_str.startswith('data: '):
                        try:
                            data = json.loads(line_str[6:])
                            if data.get('type') == 'token':
                                tokens.append(data.get('content', ''))
                        except:
                            pass
                    if len(tokens) > 30:
                        f.write("  ... (stopping after 30 tokens)\n")
                        break
            
            elapsed = time.time() - start
            f.write(f"\n✅ Got {len(tokens)} tokens in {elapsed:.1f}s\n")
            f.write(f"Response: {''.join(tokens)}\n")
        else:
            f.write(f"\n❌ Error: {r.text[:500]}\n")
            
    except requests.Timeout:
        elapsed = time.time() - start
        f.write(f"\n❌ TIMEOUT after {elapsed:.1f}s\n")
    except Exception as e:
        f.write(f"\n❌ Error: {e}\n")

    f.write("\n" + "="*60 + "\n")

print(f"Results written to {output_file}")
