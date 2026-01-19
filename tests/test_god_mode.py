"""
Test God Mode System
Verify all god mode components are working correctly
"""

import asyncio
import httpx


async def test_god_mode():
    """Test god mode endpoints"""
    base_url = "http://127.0.0.1:8000"
    
    print("🧪 Testing God Mode System\n")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Test god mode status
        print("1. Testing God Mode Status...")
        try:
            response = await client.get(f"{base_url}/api/v1/god-mode/status")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status OK: {data.get('systems', {}).keys()}")
            else:
                print(f"   ❌ Status failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 2. Test NBMF memory tiers
        print("\n2. Testing NBMF Memory Tiers...")
        try:
            response = await client.get(f"{base_url}/api/v1/god-mode/memory/tiers")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Memory Tiers: {data.get('total_entries')} entries")
            else:
                print(f"   ❌ Memory tiers failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 3. Test Router models
        print("\n3. Testing Router Agent Models...")
        try:
            response = await client.get(f"{base_url}/api/v1/god-mode/router/models")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Models Available: {data.get('count')} models")
            else:
                print(f"   ❌ Router models failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 4. Test DCP Profiles
        print("\n4. Testing DCP Profiles...")
        try:
            response = await client.get(f"{base_url}/api/v1/god-mode/dcp/profiles")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ DCP Profiles: {data.get('count')} archetypes")
            else:
                print(f"   ❌ DCP profiles failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 5. Test Change Control Hard Policies
        print("\n5. Testing Change Control...")
        try:
            response = await client.get(f"{base_url}/api/v1/god-mode/change-control/hard-policies")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Hard Policies: {data.get('count')} HARD LAWS")
            else:
                print(f"   ❌ Change control failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 6. Test Verifier (example claim)
        print("\n6. Testing Verifier Agent...")
        try:
            response = await client.post(
                f"{base_url}/api/v1/god-mode/verify",
                json={
                    "claim": "Python is a programming language created in 1991",
                    "source": "https://docs.python.org",
                    "context": {"type": "factual"}
                }
            )
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Verification: {data.get('verified')}, Score: {data.get('confidence_score')}, Grade: {data.get('grade')}")
            else:
                print(f"   ❌ Verifier failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n✅ God Mode testing complete!")


if __name__ == "__main__":
    asyncio.run(test_god_mode())
