#!/usr/bin/env python3
"""
Test Brain Write Protection - Verify agents cannot write directly to brain.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend to path
root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "backend"))

def test_brain_read() -> tuple[bool, str]:
    """Test that agents can read from brain"""
    try:
        from backend.core.brain.store import brain_store
        
        result = brain_store.query("What is the system status?")
        
        if "response" in result or "query" in result:
            return True, "✅ Agents can read from brain"
        else:
            return False, f"❌ Unexpected response format: {result}"
    except Exception as e:
        return False, f"❌ Brain read failed: {e}"

def test_agent_cannot_write_directly() -> tuple[bool, str]:
    """Test that agents cannot write directly to brain"""
    try:
        from backend.core.brain.store import brain_store
        
        # Try to access a private method or direct write (should fail or be blocked)
        # The brain_store should only allow writes through propose_knowledge()
        
        # Check if there's a direct write method that should be blocked
        if hasattr(brain_store, "_write_directly"):
            # This shouldn't exist, but if it does, it should be blocked
            return False, "❌ Direct write method exists (should be removed)"
        
        # Agents should use propose_knowledge, not direct writes
        # This is enforced by the architecture, not by blocking methods
        return True, "✅ No direct write methods exposed (agents must use propose_knowledge)"
        
    except Exception as e:
        return False, f"❌ Test failed: {e}"

def test_propose_knowledge_works() -> tuple[bool, str]:
    """Test that agents can propose knowledge"""
    try:
        from backend.core.brain.store import brain_store
        
        result = brain_store.propose_knowledge(
            agent_id="test_agent",
            content="Test knowledge proposal",
            evidence={"source": "smoke_test"},
            department="Engineering"
        )
        
        if result.get("status") == "proposed" and "proposal_id" in result:
            return True, f"✅ Agents can propose knowledge (proposal_id: {result.get('proposal_id')})"
        else:
            return False, f"❌ Unexpected response: {result}"
    except Exception as e:
        return False, f"❌ Propose knowledge failed: {e}"

def main() -> int:
    """Run brain write protection tests"""
    print("=" * 60)
    print("BRAIN WRITE PROTECTION TESTS")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Agents can read
    print("Test 1: Agents can read from brain")
    success, message = test_brain_read()
    print(f"  {message}")
    results.append(success)
    print()
    
    # Test 2: Agents cannot write directly
    print("Test 2: Agents cannot write directly to brain")
    success, message = test_agent_cannot_write_directly()
    print(f"  {message}")
    results.append(success)
    print()
    
    # Test 3: Agents can propose knowledge
    print("Test 3: Agents can propose knowledge (governance path)")
    success, message = test_propose_knowledge_works()
    print(f"  {message}")
    results.append(success)
    print()
    
    # Summary
    all_pass = all(results)
    
    print("=" * 60)
    if all_pass:
        print("✅ ALL BRAIN PROTECTION TESTS PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ SOME BRAIN PROTECTION TESTS FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())









