"""Test founder API directly"""
import asyncio
import sys
sys.path.insert(0, ".")

async def test_founder():
    print("Testing founder dashboard...")
    
    try:
        from backend.routes.founder_api import get_founder_dashboard
        result = await get_founder_dashboard()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_founder())
