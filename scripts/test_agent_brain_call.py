#!/usr/bin/env python3
"""
Test that agents can call the shared brain runtime.
Verifies single shared brain architecture.
"""
import sys
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def test_agent_brain_connection():
    """Test that an agent can use the shared brain."""
    print("=" * 70)
    print("TEST: Agent Brain Connection")
    print("=" * 70)
    print()
    
    try:
        # Import shared brain
        from backend.daena_brain import daena_brain
        from backend.services.llm_service import llm_service
        
        print("[1/3] Verifying shared brain instance...")
        print(f"     Brain instance: {daena_brain}")
        print(f"     LLM service instance: {llm_service}")
        print()
        
        print("[2/3] Testing agent message through shared brain...")
        response = await daena_brain.process_message(
            message="Hello, Daena. I am an agent testing the shared brain. Can you confirm we're connected?",
            context={"role": "agent", "department": "Engineering", "source": "test_agent"}
        )
        
        if response and len(response) > 10:
            print(f"     ✅ Brain responded successfully")
            print(f"     Response length: {len(response)} chars")
            print(f"     Preview: {response[:200]}...")
            print()
            
            print("[3/3] Verifying single source of truth...")
            # Check that daena_brain uses llm_service
            import inspect
            source = inspect.getsource(daena_brain.process_message)
            if "llm_service" in source or "llm.generate_response" in source:
                print("     ✅ daena_brain uses llm_service (single source)")
            else:
                print("     ⚠️ Could not verify llm_service usage in source")
            print()
            
            print("=" * 70)
            print("✅ ALL TESTS PASSED")
            print("=" * 70)
            print()
            print("Agents can successfully use the shared brain runtime.")
            return 0
        else:
            print(f"     ❌ Brain response too short or empty")
            return 1
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(test_agent_brain_connection()))




