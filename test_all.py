"""Test everything - brain, voice, chat"""
import requests

print("="*60)
print("COMPREHENSIVE SYSTEM TEST")
print("="*60)

# Test 1: Brain status
print("\n1. Brain Status:")
try:
    r = requests.get("http://127.0.0.1:8000/api/v1/brain/status", timeout=5)
    data = r.json()
    print(f"   Connected: {data.get('connected')}")
    print(f"   Active Model: {data.get('active_model')}")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 2: Voice status
print("\n2. Voice Status:")
try:
    r = requests.get("http://127.0.0.1:8000/api/v1/voice/status", timeout=5)
    data = r.json()
    print(f"   Status: {data.get('status')}")
    print(f"   Audio Service: {data.get('audio_service', {}).get('status')}")
    print(f"   STT Loaded: {data.get('audio_service', {}).get('stt_loaded')}")
    print(f"   TTS Loaded: {data.get('audio_service', {}).get('tts_loaded')}")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 3: Quick chat test
print("\n3. Chat Test (10s timeout):")
try:
    r = requests.post(
        "http://127.0.0.1:8000/api/v1/daena/chat",
        json={"message": "Say hi"},
        timeout=10
    )
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ Response: {data.get('response', 'No response')[:100]}")
    else:
        print(f"   ❌ Status {r.status_code}: {r.text[:200]}")
except requests.Timeout:
    print(f"   ❌ TIMEOUT - Model responding too slowly")
except Exception as e:
    print(f"   ❌ ERROR: {e}")

print("\n" + "="*60)
