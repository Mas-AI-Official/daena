#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test that math operations are handled without LLM calls.
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_math():
    """Test math operations"""
    print("=" * 70)
    print("TEST: No-LLM Math Operations")
    print("=" * 70)
    print()
    
    from backend.services.deterministic_gate import get_deterministic_gate
    gate = get_deterministic_gate()
    
    test_cases = [
        ("what is 2*2", "4"),
        ("calculate 12 / 3", "4.0"),
        ("15% of 200", "30.0"),
        ("what is 10 + 5", "15"),
    ]
    
    all_passed = True
    for input_text, expected in test_cases:
        handled, result = gate.try_handle(input_text)
        if handled and expected in result.get("result", ""):
            print(f"[OK] '{input_text}' -> {result.get('result')}")
        else:
            print(f"[FAIL] '{input_text}' -> Expected: {expected}, Got: {result}")
            all_passed = False
    
    print()
    if all_passed:
        print("[SUCCESS] ALL MATH TESTS PASSED")
        return 0
    else:
        print("[FAILURE] SOME TESTS FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(test_math())

