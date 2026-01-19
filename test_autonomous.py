"""
Test script for Autonomous Execution Engine
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_autonomous():
    try:
        from backend.services.autonomous_executor import autonomous_executor
        print("✅ Autonomous executor imported successfully")
        
        # Test a project execution
        project = await autonomous_executor.execute_project({
            "title": "Test Project - Landing Page",
            "goal": "Create a simple landing page for MAS-AI",
            "constraints": ["Must use verified internal data only"],
            "acceptance": ["Page displays company name and value prop"],
            "deliverables": ["Landing page HTML draft"]
        })
        
        print(f"✅ Project created: {project.project_id}")
        print(f"   Status: {project.status}")
        print(f"   Tasks: {len(project.task_graph)}")
        print(f"   Deliverables: {len(project.produced_deliverables)}")
        
        if project.ledger_entry:
            print(f"   Ledger entry: {project.ledger_entry.get('project_id')}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_memory():
    try:
        from backend.services.nbmf_memory import nbmf_memory, MemoryTier
        print("\n✅ NBMF Memory imported successfully")
        
        # Test T1 memory (working - 24h TTL)
        entry = nbmf_memory.write("test_key", "test_value", MemoryTier.T1_WORKING)
        print(f"   Written: {entry.key} = {entry.value} (tier: {entry.tier.value})")
        
        value = nbmf_memory.read("test_key")
        print(f"   Read back: {value}")
        
        stats = nbmf_memory.get_stats()
        print(f"   Stats: {stats}")
        
        return True
    except Exception as e:
        print(f"❌ Memory error: {e}")
        return False

async def test_verification():
    try:
        from backend.services.verification_gate import verification_gate
        print("\n✅ Verification Gate imported successfully")
        
        # Test claim validation
        result = verification_gate.validate_claim("We have 48 agents")
        print(f"   Claim 'We have 48 agents': valid={result.get('valid')}")
        
        result = verification_gate.validate_claim("We have 500% growth!")
        print(f"   Claim '500% growth': valid={result.get('valid')}, warning={result.get('warning')}")
        
        notes = verification_gate.get_compliance_notes()
        print(f"   Compliance notes count: {len(notes)}")
        
        return True
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

async def test_ledger():
    try:
        from backend.services.decision_ledger import decision_ledger
        print("\n✅ Decision Ledger imported successfully")
        
        entry = await decision_ledger.write_entry({
            "project_id": "test-project",
            "action": "Test entry creation",
            "outcome": "success"
        })
        print(f"   Entry written: {entry.entry_id}")
        
        stats = decision_ledger.get_stats()
        print(f"   Stats: {stats}")
        
        return True
    except Exception as e:
        print(f"❌ Ledger error: {e}")
        return False

async def main():
    print("=" * 60)
    print("DAENA AUTONOMOUS COMPANY MODE - COMPONENT TESTS")
    print("=" * 60)
    
    results = []
    results.append(await test_memory())
    results.append(await test_verification())
    results.append(await test_ledger())
    results.append(await test_autonomous())
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
