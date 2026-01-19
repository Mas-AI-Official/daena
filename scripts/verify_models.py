"""
Verify that Ollama models in local_brain are accessible.
"""

import sys
import os
import asyncio
import httpx
from pathlib import Path

# Fix Unicode encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Ensure the project root is in the Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.config.settings import settings
from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL, TRAINED_MODEL, DEFAULT_LOCAL_MODEL

async def verify_models():
    """Verify Ollama models are accessible"""
    print("=" * 60)
    print("OLLAMA MODEL VERIFICATION")
    print("=" * 60)
    print()
    
    # Check Ollama availability
    print("1. Checking Ollama service...")
    ollama_ok = await check_ollama_available()
    if not ollama_ok:
        print("[X] Ollama is not running or not reachable")
        print(f"   Base URL: {OLLAMA_BASE_URL}")
        print("   Please start Ollama service")
        return False
    
    print(f"[OK] Ollama is running at {OLLAMA_BASE_URL}")
    print()
    
    # Check models path
    print("2. Checking models path...")
    models_path = settings.ollama_models_path
    if models_path:
        models_path_obj = Path(models_path)
        if models_path_obj.exists():
            print(f"[OK] Models path exists: {models_path}")
            print(f"   Environment variable OLLAMA_MODELS should be set to: {models_path}")
        else:
            print(f"[WARN] Models path does not exist: {models_path}")
    else:
        print("[WARN] Models path not configured")
    print()
    
    # List available models
    print("3. Listing available models...")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                
                if models:
                    print(f"[OK] Found {len(models)} model(s):")
                    for model in models:
                        marker = ""
                        if model == TRAINED_MODEL:
                            marker = " (TRAINED - Priority 1)"
                        elif model == DEFAULT_LOCAL_MODEL:
                            marker = " (DEFAULT - Priority 2)"
                        print(f"   - {model}{marker}")
                    
                    # Check for expected models
                    print()
                    print("4. Checking expected models...")
                    if TRAINED_MODEL in models:
                        print(f"[OK] Trained model '{TRAINED_MODEL}' is available")
                    else:
                        print(f"[WARN] Trained model '{TRAINED_MODEL}' not found")
                    
                    if DEFAULT_LOCAL_MODEL in models:
                        print(f"[OK] Default model '{DEFAULT_LOCAL_MODEL}' is available")
                    else:
                        print(f"[WARN] Default model '{DEFAULT_LOCAL_MODEL}' not found")
                    
                    # Determine active model
                    print()
                    print("5. Determining active model...")
                    if TRAINED_MODEL in models:
                        active_model = TRAINED_MODEL
                        print(f"[OK] Active model: {active_model} (trained model)")
                    elif DEFAULT_LOCAL_MODEL in models:
                        active_model = DEFAULT_LOCAL_MODEL
                        print(f"[OK] Active model: {active_model} (default model)")
                    else:
                        active_model = models[0]
                        print(f"[WARN] Active model: {active_model} (fallback)")
                    
                    # Test model
                    print()
                    print("6. Testing model response...")
                    try:
                        test_response = await client.post(
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json={
                                "model": active_model,
                                "messages": [{"role": "user", "content": "Say 'Hello'"}],
                                "stream": False
                            },
                            timeout=30
                        )
                        if test_response.status_code == 200:
                            data = test_response.json()
                            response_text = data.get("message", {}).get("content", "")
                            if response_text:
                                print(f"[OK] Model '{active_model}' responded successfully")
                                print(f"   Response preview: {response_text[:50]}...")
                            else:
                                print(f"[WARN] Model '{active_model}' responded but no content")
                        else:
                            print(f"[ERROR] Model '{active_model}' test failed: HTTP {test_response.status_code}")
                    except Exception as e:
                        print(f"[ERROR] Model '{active_model}' test error: {e}")
                    
                else:
                    print("[ERROR] No models found in Ollama")
                    print("   Run: ollama pull qwen2.5:7b-instruct")
                    return False
            else:
                print(f"[ERROR] Failed to list models: HTTP {response.status_code}")
                return False
    except Exception as e:
        print(f"[ERROR] Error listing models: {e}")
        return False
    
    print()
    print("=" * 60)
    print("[OK] VERIFICATION COMPLETE")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(verify_models())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

