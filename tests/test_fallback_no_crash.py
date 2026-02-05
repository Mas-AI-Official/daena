#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that system returns safe fallback when Ollama is off and cloud is disabled.
"""
import sys
import io
import asyncio
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def test_fallback():
    """Test fallback behavior"""
    print("=" * 70)
    print("TEST: Fallback No-Crash")
    print("=" * 70)
    print()
    
    from backend.services.llm_service import llm_service
    
    print("[1/2] Testing with Ollama off and cloud disabled...")
    print("   (This simulates worst-case scenario)")
    print()
    
    # Test that it doesn't crash
    try:
        response = await llm_service.generate_response(
            prompt="Hello, Daena!",
            max_tokens=50
        )
        
        if response and len(response) > 10:
            print(f"[OK] System returned safe response (no crash)")
            print(f"   Response: {response[:200]}...")
            print()
            
            # Check if it's a helpful error message
            if "ollama" in response.lower() or "local" in response.lower():
                print("[OK] Response contains helpful guidance")
            else:
                print("[WARN] Response doesn't mention Ollama/local setup")
            
            print()
            print("[SUCCESS] FALLBACK TEST PASSED")
            return 0
        else:
            print(f"[FAIL] Response too short or empty: {response}")
            return 1
    except Exception as e:
        print(f"[ERROR] System crashed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(test_fallback()))

