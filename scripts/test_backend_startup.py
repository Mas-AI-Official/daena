#!/usr/bin/env python3
"""
Test script to verify backend can start and connect to trained brain.
"""
import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_imports():
    """Test that all critical modules can be imported."""
    print("=" * 60)
    print("TEST 1: Module Imports")
    print("=" * 60)
    
    errors = []
    
    try:
        import backend.main
        print("✅ backend.main")
    except Exception as e:
        print(f"❌ backend.main: {e}")
        errors.append(f"backend.main: {e}")
    
    try:
        from backend.services.local_llm_ollama import check_ollama_available, TRAINED_MODEL, DEFAULT_LOCAL_MODEL
        print(f"✅ backend.services.local_llm_ollama")
        print(f"   TRAINED_MODEL: {TRAINED_MODEL}")
        print(f"   DEFAULT_LOCAL_MODEL: {DEFAULT_LOCAL_MODEL}")
    except Exception as e:
        print(f"❌ backend.services.local_llm_ollama: {e}")
        errors.append(f"local_llm_ollama: {e}")
    
    try:
        from backend.services.llm_service import LLMService
        print("✅ backend.services.llm_service")
    except Exception as e:
        print(f"❌ backend.services.llm_service: {e}")
        errors.append(f"llm_service: {e}")
    
    try:
        from backend.daena_brain import daena_brain
        print("✅ backend.daena_brain")
    except Exception as e:
        print(f"❌ backend.daena_brain: {e}")
        errors.append(f"daena_brain: {e}")
    
    print()
    return len(errors) == 0, errors

def test_ollama_connection():
    """Test Ollama connection and model availability."""
    print("=" * 60)
    print("TEST 2: Ollama Connection")
    print("=" * 60)
    
    try:
        import asyncio
        from backend.services.local_llm_ollama import check_ollama_available, TRAINED_MODEL, DEFAULT_LOCAL_MODEL
        
        async def check():
            is_available = await check_ollama_available()
            if is_available:
                print(f"✅ Ollama is running")
                
                # Check for trained model
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    response = await client.get("http://localhost:11434/api/tags")
                    if response.status_code == 200:
                        data = response.json()
                        available_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                        print(f"   Available models: {', '.join(available_models)}")
                        
                        if TRAINED_MODEL in available_models:
                            print(f"   ✅ Trained model '{TRAINED_MODEL}' is available")
                            return True, TRAINED_MODEL
                        elif DEFAULT_LOCAL_MODEL in available_models:
                            print(f"   ⚠️ Trained model '{TRAINED_MODEL}' not found, using default '{DEFAULT_LOCAL_MODEL}'")
                            return True, DEFAULT_LOCAL_MODEL
                        else:
                            print(f"   ⚠️ Neither trained nor default model found")
                            if available_models:
                                print(f"   Will use fallback: {available_models[0]}")
                                return True, available_models[0]
                            return False, None
            else:
                print(f"❌ Ollama is not running")
                print(f"   Backend will use fallback responses")
                return False, None
        
        result, model = asyncio.run(check())
        print()
        return result, model
    except Exception as e:
        print(f"❌ Error checking Ollama: {e}")
        print()
        return False, None

def test_brain_connection():
    """Test that daena_brain can process a message."""
    print("=" * 60)
    print("TEST 3: Brain Connection")
    print("=" * 60)
    
    try:
        import asyncio
        from backend.daena_brain import daena_brain
        
        async def test():
            try:
                response = await daena_brain.process_message(
                    message="Hello, Daena. Can you confirm you are connected to the brain?",
                    context={"source": "smoke_test"}
                )
                
                if response and len(response) > 10:
                    print(f"✅ Brain responded successfully")
                    print(f"   Response length: {len(response)} chars")
                    print(f"   Preview: {response[:200]}...")
                    return True
                else:
                    print(f"❌ Brain response too short or empty")
                    return False
            except Exception as e:
                print(f"❌ Brain processing failed: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        result = asyncio.run(test())
        print()
        return result
    except Exception as e:
        print(f"❌ Error testing brain: {e}")
        import traceback
        traceback.print_exc()
        print()
        return False

def main():
    """Run all tests."""
    print()
    print("=" * 60)
    print("DAENA BACKEND STARTUP TEST")
    print("=" * 60)
    print()
    
    all_passed = True
    
    # Test 1: Imports
    imports_ok, import_errors = test_imports()
    if not imports_ok:
        print("❌ Import tests failed. Fix these first:")
        for error in import_errors:
            print(f"   - {error}")
        print()
        return 1
    
    # Test 2: Ollama
    ollama_ok, model = test_ollama_connection()
    if not ollama_ok:
        print("⚠️ Ollama not available - backend will use fallback")
        print()
    
    # Test 3: Brain
    brain_ok = test_brain_connection()
    if not brain_ok:
        all_passed = False
    
    # Summary
    print("=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print()
        print("Backend is ready to start!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        print()
        print("Fix the errors above before starting the backend.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

