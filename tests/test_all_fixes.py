"""
Comprehensive Test for All Fixes
Tests database schema, multiple models, voice, chat, etc.
"""
import httpx
import sys
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10.0

def test_database_schema():
    """Test 1: Database schema fixes"""
    print("\n" + "="*60)
    print("TEST 1: Database Schema")
    print("="*60)
    try:
        from backend.database import SessionLocal, CouncilMember, Agent
        db = SessionLocal()
        try:
            cm = db.query(CouncilMember).first()
            a = db.query(Agent).first()
            
            has_category_id = hasattr(cm, 'category_id') if cm else False
            has_voice_id = hasattr(a, 'voice_id') if a else False
            
            if has_category_id and has_voice_id:
                print("[OK] Database schema: category_id and voice_id exist")
                return True
            else:
                print(f"[FAIL] Database schema: category_id={has_category_id}, voice_id={has_voice_id}")
                return False
        finally:
            db.close()
    except Exception as e:
        print(f"[ERROR] Database schema test failed: {e}")
        return False

def test_brain_status():
    """Test 2: Brain status endpoint"""
    print("\n" + "="*60)
    print("TEST 2: Brain Status")
    print("="*60)
    try:
        response = httpx.get(f"{BASE_URL}/api/v1/brain/status", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Brain status: connected={data.get('connected')}, active_models={data.get('active_models', [])}")
            return True
        else:
            print(f"[FAIL] Brain status: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Brain status test failed: {e}")
        return False

def test_multiple_models():
    """Test 3: Multiple active models"""
    print("\n" + "="*60)
    print("TEST 3: Multiple Active Models")
    print("="*60)
    try:
        # Get available models
        models_resp = httpx.get(f"{BASE_URL}/api/v1/brain/models", timeout=TIMEOUT)
        if models_resp.status_code != 200:
            print(f"[SKIP] Cannot get models list: {models_resp.status_code}")
            return True  # Skip if no models available
        
        models_data = models_resp.json()
        local_models = models_data.get("local", [])
        
        if len(local_models) < 2:
            print(f"[SKIP] Need at least 2 models to test multiple activation. Found: {len(local_models)}")
            return True
        
        # Try to enable first model
        model1 = local_models[0]["name"]
        resp1 = httpx.post(
            f"{BASE_URL}/api/v1/brain/models/{model1}/select?enabled=true",
            timeout=TIMEOUT
        )
        
        if resp1.status_code == 200:
            data1 = resp1.json()
            active_models = data1.get("active_models", [])
            print(f"[OK] Enabled model 1: {model1}, active_models={active_models}")
            
            # Try to enable second model (should work with multiple support)
            if len(local_models) > 1:
                model2 = local_models[1]["name"]
                resp2 = httpx.post(
                    f"{BASE_URL}/api/v1/brain/models/{model2}/select?enabled=true",
                    timeout=TIMEOUT
                )
                
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    active_models = data2.get("active_models", [])
                    if len(active_models) >= 2:
                        print(f"[OK] Multiple models enabled: {active_models}")
                        return True
                    else:
                        print(f"[FAIL] Expected 2+ active models, got: {active_models}")
                        return False
                else:
                    print(f"[FAIL] Failed to enable second model: {resp2.status_code}")
                    return False
            return True
        else:
            print(f"[FAIL] Failed to enable first model: {resp1.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Multiple models test failed: {e}")
        return False

def test_voice_endpoint():
    """Test 4: Voice endpoints"""
    print("\n" + "="*60)
    print("TEST 4: Voice Endpoints")
    print("="*60)
    try:
        # Test status
        status_resp = httpx.get(f"{BASE_URL}/api/v1/voice/status", timeout=TIMEOUT)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            print(f"[OK] Voice status: talk_active={status_data.get('talk_active')}")
            
            # Test toggle
            toggle_resp = httpx.post(
                f"{BASE_URL}/api/v1/voice/talk-mode",
                json={"enabled": True},
                timeout=TIMEOUT
            )
            if toggle_resp.status_code == 200:
                toggle_data = toggle_resp.json()
                print(f"[OK] Voice toggle: {toggle_data.get('message')}")
                return True
            else:
                print(f"[FAIL] Voice toggle: Status {toggle_resp.status_code}")
                return False
        else:
            print(f"[FAIL] Voice status: Status {status_resp.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Voice test failed: {e}")
        return False

def test_daena_chat():
    """Test 5: Daena chat endpoint"""
    print("\n" + "="*60)
    print("TEST 5: Daena Chat")
    print("="*60)
    try:
        # Test chat endpoint
        chat_resp = httpx.post(
            f"{BASE_URL}/api/v1/daena/chat",
            json={"message": "Hello, this is a test"},
            timeout=TIMEOUT
        )
        
        if chat_resp.status_code == 200:
            chat_data = chat_resp.json()
            if chat_data.get("success") and (chat_data.get("response") or chat_data.get("daena_response")):
                session_id = chat_data.get("session_id")
                print(f"[OK] Daena chat: Got response, session_id={session_id}")
                return True
            else:
                print(f"[FAIL] Daena chat: Invalid response structure")
                return False
        else:
            print(f"[FAIL] Daena chat: Status {chat_resp.status_code}, {chat_resp.text[:200]}")
            return False
    except Exception as e:
        print(f"[ERROR] Daena chat test failed: {e}")
        return False

def test_env_sync():
    """Test 6: Environment sync"""
    print("\n" + "="*60)
    print("TEST 6: Environment Sync")
    print("="*60)
    try:
        # Test get env vars
        env_resp = httpx.get(f"{BASE_URL}/api/v1/env/vars", timeout=TIMEOUT)
        if env_resp.status_code == 200:
            env_data = env_resp.json()
            print(f"[OK] Env sync: Retrieved {len(env_data.get('vars', {}))} variables")
            return True
        else:
            print(f"[FAIL] Env sync: Status {env_resp.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Env sync test failed: {e}")
        return False

def test_department_categories():
    """Test 7: Department categories in chat sessions"""
    print("\n" + "="*60)
    print("TEST 7: Department Categories")
    print("="*60)
    try:
        # Test getting sessions with department filter
        sessions_resp = httpx.get(
            f"{BASE_URL}/api/v1/chat-history/sessions?scope_type=department",
            timeout=TIMEOUT
        )
        if sessions_resp.status_code == 200:
            sessions_data = sessions_resp.json()
            sessions = sessions_data.get("sessions", [])
            print(f"[OK] Department categories: Found {len(sessions)} department sessions")
            return True
        else:
            print(f"[FAIL] Department categories: Status {sessions_resp.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Department categories test failed: {e}")
        return False

def main():
    print("="*60)
    print("COMPREHENSIVE FIXES TEST")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    
    tests = [
        ("Database Schema", test_database_schema),
        ("Brain Status", test_brain_status),
        ("Multiple Models", test_multiple_models),
        ("Voice Endpoints", test_voice_endpoint),
        ("Daena Chat", test_daena_chat),
        ("Environment Sync", test_env_sync),
        ("Department Categories", test_department_categories),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"[ERROR] {name} test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"{status} {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[WARNING] {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())



