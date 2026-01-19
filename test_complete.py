"""FINAL COMPREHENSIVE TEST - After system restart"""
import requests
import time

print("\n" + "="*70)
print("  DAENA SYSTEM FINAL TEST - All Services")
print("="*70)

# Wait for services to stabilize
time.sleep(3)

# Test 1: Brain with specific model
print("\n[1/4] BRAIN STATUS:")
try:
    r = requests.get("http://127.0.0.1:8000/api/v1/brain/status", timeout=5)
    data = r.json()
    print(f"    ✓ Connected: {data.get('connected')}")
    print(f"    ✓ Active Model: {data.get('active_model', 'Not specified')}")
    print(f"    ✓ Available Models: {len(data.get('models', []))}")
except Exception as e:
    print(f"    ✗ ERROR: {e}")

# Test 2: Voice/Audio
print("\n[2/4] VOICE & AUDIO STATUS:")
try:
    r = requests.get("http://127.0.0.1:8000/api/v1/voice/status", timeout=5)
    data = r.json()
    audio = data.get('audio_service', {})
    print(f"    ✓ Voice: {data.get('status')}")
    print(f"    ✓ STT Loaded: {audio.get('stt_loaded')}")
    print(f"    ✓ TTS Loaded: {audio.get('tts_loaded')}")
except Exception as e:
    print(f"    ✗ ERROR: {e}")

# Test 3: Chat Response
print("\n[3/4] CHAT RESPONSE TEST:")
try:
    print("    Sending message... (15s timeout)")
    start = time.time()
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hi in 3 words"},
        timeout=15
    )
    elapsed = time.time() - start
    
    if r.status_code == 200:
        data = r.json()
        response = data.get('response', 'No response')
        print(f"    ✅ SUCCESS! ({elapsed:.1f}s)")
        print(f"    Response: {response[:150]}")
    else:
        print(f"    ✗ HTTP {r.status_code}: {r.text[:200]}")
except requests.Timeout:
    print(f"    ✗ TIMEOUT after 15s - Model too slow")
except Exception as e:
    print(f"    ✗ ERROR: {e}")

# Test 4: Model in Ollama
print("\n[4/4] OLLAMA MODEL STATUS:")
try:
    import subprocess
    result = subprocess.run(['ollama', 'ps'], capture_output=True, text=True)
    if 'qwen2.5:7b' in result.stdout:
        print(f"    ✅ 7B model loaded in memory")
    elif result.stdout.strip() == 'NAME    ID    SIZE    PROCESSOR    CONTEXT    UNTIL':
        print(f"    ⚠️  No model loaded (will load on first request)")
    else:
        print(f"    Model status: {result.stdout[:100]}")
except:
    print(f"    ⚠️  Could not check Ollama status")

print("\n" + "="*70)
print("  TEST COMPLETE")
print("="*70 + "\n")
