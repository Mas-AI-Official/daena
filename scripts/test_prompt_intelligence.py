"""
Automated test script for Prompt Intelligence Brain + Local LLM connectivity.
Tests all components automatically.
"""

import sys
import asyncio
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Fix encoding for Windows console
import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # Python < 3.7

# Try to import httpx (optional for API tests)
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("WARNING: httpx not available - API tests will be skipped")

async def test_ollama_available():
    """Test if Ollama is reachable"""
    print("🔍 Testing Ollama availability...")
    try:
        from backend.services.local_llm_ollama import check_ollama_available, OLLAMA_BASE_URL
        available = await check_ollama_available()
        if available:
            print(f"✅ Ollama is available at {OLLAMA_BASE_URL}")
            return True
        else:
            print(f"⚠️ Ollama is not reachable at {OLLAMA_BASE_URL}")
            print("   Start Ollama with: ollama serve")
            return False
    except Exception as e:
        print(f"❌ Error checking Ollama: {e}")
        return False

async def test_prompt_intelligence():
    """Test Prompt Intelligence Brain"""
    print("\n🧠 Testing Prompt Intelligence Brain...")
    try:
        from backend.services.prompt_intelligence import get_prompt_intelligence
        prompt_intel = get_prompt_intelligence()
        
        print(f"  Enabled: {prompt_intel.enabled}")
        print(f"  Mode: {prompt_intel.mode.value}")
        print(f"  Complexity Threshold: {prompt_intel.complexity_threshold}")
        
        # Test optimization
        test_prompt = "Hello, Daena! How are you?"
        optimized = prompt_intel.optimize(
            raw_prompt=test_prompt,
            context=None,
            provider="local/ollama",
            role="AI VP",
            department=None
        )
        
        print(f"  Original: {test_prompt}")
        print(f"  Optimized: {optimized.optimized_prompt[:100]}...")
        print(f"  Transformations: {optimized.transformations_applied}")
        print("✅ Prompt Intelligence working")
        return True
    except Exception as e:
        print(f"❌ Prompt Intelligence error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_service():
    """Test LLM Service with Prompt Intelligence"""
    print("\n🤖 Testing LLM Service...")
    try:
        from backend.services.llm_service import llm_service
        
        test_prompt = "Say hello in one sentence."
        print(f"  Testing with prompt: '{test_prompt}'")
        
        response = await llm_service.generate_response(
            prompt=test_prompt,
            max_tokens=50,
            temperature=0.7
        )
        
        print(f"  Response: {response[:100]}...")
        print("✅ LLM Service working")
        return True
    except Exception as e:
        print(f"❌ LLM Service error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_llm_streaming():
    """Test LLM Streaming with Prompt Intelligence"""
    print("\n🌊 Testing LLM Streaming...")
    try:
        from backend.services.llm_service import llm_service
        
        test_prompt = "Count to 5."
        print(f"  Testing streaming with prompt: '{test_prompt}'")
        
        chunks = []
        async for chunk in llm_service.generate_response_stream(
            prompt=test_prompt,
            max_tokens=50,
            temperature=0.7
        ):
            chunks.append(chunk)
            print(f"  Chunk: {chunk[:50]}...")
        
        full_response = "".join(chunks)
        print(f"  Full response: {full_response[:100]}...")
        print(f"  Total chunks: {len(chunks)}")
        print("✅ LLM Streaming working")
        return True
    except Exception as e:
        print(f"❌ LLM Streaming error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_backend_api():
    """Test backend API endpoints"""
    print("\n🌐 Testing Backend API...")
    
    if not HTTPX_AVAILABLE:
        print("⚠️ Skipping API tests (httpx not available)")
        print("   Install with: pip install httpx")
        return None
    
    base_url = "http://127.0.0.1:8000"
    
    # Test 1: Health check
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/docs")
            if response.status_code == 200:
                print("✅ Backend is running")
            else:
                print(f"⚠️ Backend returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        print("   Start backend with: START_DAENA.bat")
        return False
    
    # Test 2: LLM Status endpoint
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base_url}/api/v1/llm/status")
            if response.status_code == 200:
                data = response.json()
                print(f"  Local provider: {data.get('local_provider', {}).get('ok', False)}")
                print(f"  Active provider: {data.get('active_provider', {}).get('type', 'unknown')}")
                print("✅ LLM Status endpoint working")
            else:
                print(f"⚠️ LLM Status returned status {response.status_code}")
    except Exception as e:
        print(f"⚠️ LLM Status endpoint error: {e}")
    
    # Test 3: LLM Test endpoint
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{base_url}/api/v1/llm/test",
                json={"prompt": "Hello, Daena! Say hi in one sentence."}
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  Success: {data.get('success', False)}")
                print(f"  Provider used: {data.get('provider_used', 'unknown')}")
                print(f"  Response: {data.get('response', '')[:100]}...")
                print(f"  Prompt Intelligence: {data.get('prompt_intelligence', {})}")
                print("✅ LLM Test endpoint working")
                return True
            else:
                print(f"⚠️ LLM Test returned status {response.status_code}")
                return False
    except Exception as e:
        print(f"⚠️ LLM Test endpoint error: {e}")
        return False

async def main():
    """Run all tests"""
    print("=" * 60)
    print("PROMPT INTELLIGENCE + LOCAL LLM TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Ollama
    results["ollama"] = await test_ollama_available()
    
    # Test 2: Prompt Intelligence
    results["prompt_intelligence"] = await test_prompt_intelligence()
    
    # Test 3: LLM Service
    if results["ollama"]:
        results["llm_service"] = await test_llm_service()
    else:
        print("\n⚠️ Skipping LLM Service test (Ollama not available)")
        results["llm_service"] = None
    
    # Test 4: LLM Streaming
    if results["ollama"]:
        results["llm_streaming"] = await test_llm_streaming()
    else:
        print("\n⚠️ Skipping LLM Streaming test (Ollama not available)")
        results["llm_streaming"] = None
    
    # Test 5: Backend API
    results["backend_api"] = await test_backend_api()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        if result is True:
            print(f"✅ {test_name}: PASS")
        elif result is False:
            print(f"❌ {test_name}: FAIL")
        else:
            print(f"⚠️ {test_name}: SKIPPED")
    
    all_passed = all(r for r in results.values() if r is not None)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print("\n⚠️ SOME TESTS FAILED - Check output above")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

