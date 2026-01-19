"""
Comprehensive smoke test for Daena system.
Tests: health, Ollama, DB, chat, WebSocket, voice, models.
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).parent

print("="*70)
print("DAENA SYSTEM SMOKE TEST")
print("="*70)

results = []

def test(name, func):
    """Run a test and record result"""
    print(f"\n{len(results)+1}. Testing {name}...")
    try:
        passed, message = func()
        results.append({"name": name, "passed": passed, "message": message})
        if passed:
            print(f"   ✅ PASS: {message}")
        else:
            print(f"   ❌ FAIL: {message}")
    except Exception as e:
        results.append({"name": name, "passed": False, "message": str(e)})
        print(f"   ❌ ERROR: {e}")

# Test 1: Health endpoint
def test_health():
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    if r.status_code == 200:
        return True, "Backend is responding"
    return False, f"Status {r.status_code}"

# Test 2: Ollama ping
def test_ollama():
    r = requests.get(f"{BASE_URL}/api/v1/brain/ping-ollama", timeout=35)
    data = r.json()
    if data.get("overall_status") == "healthy":
        gen_time = data.get("tests", {}).get("generate", {}).get("duration_ms", 0)
        return True, f"Ollama healthy, response in {gen_time}ms"
    return False, f"Status: {data.get('overall_status')}, errors in tests"

# Test 3: Database write/read
def test_database():
    # Check if database file exists and is writable
    db_path = ROOT / "daena.db"
    if not db_path.exists():
        return False, "daena.db not found"
    if not os.access(db_path, os.W_OK):
        return False, "daena.db not writable"
    return True, "Database file exists and is writable"

# Test 4: Chat response
def test_chat():
    start = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/daena/chat",
        json={"message": "Hi"},
        timeout=20
    )
    elapsed = time.time() - start
    if r.status_code == 200:
        return True, f"Chat responded in {elapsed:.1f}s"
    return False, f"Status {r.status_code}, took {elapsed:.1f}s"

# Test 5: Brain status
def test_brain_status():
    r = requests.get(f"{BASE_URL}/api/v1/brain/status", timeout=5)
    data = r.json()
    if data.get("connected") and data.get("llm_available"):
        model = data.get("active_model", "unknown")
        return True, f"Brain connected, model: {model}"
    return False, "Brain not connected or LLM unavailable"

# Test 6: Voice service
def test_voice():
    r = requests.get(f"{BASE_URL}/api/v1/voice/status", timeout=5)
    data = r.json()
    status = data.get("status")
    if status == "online":
        stt = data.get("audio_service", {}).get("stt_loaded", False)
        tts = data.get("audio_service", {}).get("tts_loaded", False)
        return True, f"Voice online, STT: {stt}, TTS: {tts}"
    return False, f"Voice {status}"

# Test 7: Model files
def test_models():
    models_dir = ROOT / "models"
    if not models_dir.exists():
        return False, "models/ directory not found"
    # Check for Whisper
    whisper = models_dir / "faster-whisper-medium" / ".download_ok"
    xtts = models_dir / "xtts_v2" / ".download_ok"
    
    has_whisper = whisper.exists()
    has_xtts = xtts.exists()
    
    if has_whisper and has_xtts:
        return True, "Both Whisper and XTTS markers found"
    elif has_whisper:
        return True, "Whisper found, XTTS pending"
    else:
        return False, "Model markers not found"

# Run all tests
import os
test("Health Endpoint", test_health)
test("Ollama Connection", test_ollama)
test("Database Access", test_database)
test("Chat Response", test_chat)
test("Brain Status", test_brain_status)
test("Voice Service", test_voice)
test("Model Files", test_models)

# Summary
print("\n" + "="*70)
print("TEST SUMMARY")
print("="*70)

passed = sum(1 for r in results if r["passed"])
total = len(results)
score = (passed / total) * 100

for i, result in enumerate(results, 1):
    icon = "✅" if result["passed"] else "❌"
    print(f"{i}. {icon} {result['name']}")

print(f"\nScore: {passed}/{total} ({score:.0f}%)")

if score == 100:
    print("\n🎉 All tests passed! System is healthy.")
elif score >= 80:
    print("\n⚠️ Most tests passed. Check failures above.")
else:
    print("\n❌ Multiple failures. System needs attention.")

print("="*70)
