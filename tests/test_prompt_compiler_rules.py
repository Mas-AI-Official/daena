#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that prompt compiler produces stable deterministic output in rules mode.
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_prompt_compiler():
    """Test prompt compiler rules mode"""
    print("=" * 70)
    print("TEST: Prompt Compiler (Rules Mode)")
    print("=" * 70)
    print()
    
    from backend.services.prompt_intelligence import get_prompt_intelligence
    
    # Force rules mode
    prompt_intel = get_prompt_intelligence()
    prompt_intel.mode = prompt_intel.mode.__class__("rules")  # Ensure rules mode
    
    test_prompt = "Hello, Daena. What is your role?"
    
    # Run twice - should produce same result
    result1 = prompt_intel.optimize(
        raw_prompt=test_prompt,
        context={"role": "user"},
        provider="local/ollama"
    )
    
    result2 = prompt_intel.optimize(
        raw_prompt=test_prompt,
        context={"role": "user"},
        provider="local/ollama"
    )
    
    if result1.optimized_prompt == result2.optimized_prompt:
        print(f"[OK] Deterministic output verified")
        print(f"   Prompt: {test_prompt}")
        print(f"   Optimized: {result1.optimized_prompt[:100]}...")
        print(f"   Transformations: {result1.transformations_applied}")
        print()
        print("[SUCCESS] PROMPT COMPILER TEST PASSED")
        return 0
    else:
        print(f"[FAIL] Non-deterministic output!")
        print(f"   Run 1: {result1.optimized_prompt[:100]}")
        print(f"   Run 2: {result2.optimized_prompt[:100]}")
        print()
        print("[FAILURE] PROMPT COMPILER TEST FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(test_prompt_compiler())

