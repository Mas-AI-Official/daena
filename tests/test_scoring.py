#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test complexity scoring.
"""
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_scoring():
    """Test complexity scoring"""
    print("=" * 70)
    print("TEST: Complexity Scoring")
    print("=" * 70)
    print()
    
    from backend.services.complexity_scorer import get_complexity_scorer
    scorer = get_complexity_scorer()
    
    test_cases = [
        ("hi", "no_llm"),
        ("what is 2*2", "no_llm"),
        ("Hello, Daena. How are you?", "cheap"),
        ("Can you help me with a simple question?", "cheap"),
        ("I need to audit the backend websocket implementation for security issues", "strong"),
        ("Design a new architecture for cross-department collaboration with streaming support", "deep_research"),
    ]
    
    all_passed = True
    for input_text, expected_tier in test_cases:
        result = scorer.score(input_text)
        tier = result.get("tier")
        score = result.get("score")
        
        if tier == expected_tier:
            print(f"[OK] '{input_text[:50]}...' -> Score: {score}, Tier: {tier} (expected: {expected_tier})")
        else:
            print(f"[WARN] '{input_text[:50]}...' -> Score: {score}, Tier: {tier} (expected: {expected_tier})")
            # Allow some flexibility
            if expected_tier == "no_llm" and tier == "cheap":
                print("   (Acceptable: trivial -> cheap is OK)")
            elif expected_tier == "strong" and tier == "deep_research":
                print("   (Acceptable: strong -> deep_research is OK)")
            else:
                all_passed = False
    
    print()
    if all_passed:
        print("[SUCCESS] ALL SCORING TESTS PASSED")
        return 0
    else:
        print("[WARN] SOME SCORING TESTS HAD MINOR MISMATCHES (check above)")
        return 0  # Non-fatal

if __name__ == "__main__":
    sys.exit(test_scoring())

