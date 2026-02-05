
import sys
import os
import asyncio
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def evaluate_functionality():
    print("=== DAENA SYSTEM FUNCTIONALITY EVALUATION ===")
    
    # 1. Test Skill Registry
    print("\n[1] Testing Skill Registry...")
    try:
        from backend.services.skill_registry import get_skill_registry
        registry = get_skill_registry()
        skills = registry.list_skills()
        enabled_count = sum(1 for s in skills if s.get('enabled'))
        print(f"Total Skills in Registry: {len(skills)}")
        print(f"Enabled Skills: {enabled_count}")
        if enabled_count == 0 and len(skills) > 0:
            print("❌ FAILURE: No skills are enabled.")
        else:
            print("✅ SUCCESS: Skills are enabled by default.")
    except Exception as e:
        print(f"❌ ERROR in Skill Registry: {e}")

    # 2. Test Governance Loop
    print("\n[2] Testing Governance Loop (Autopilot)...")
    try:
        from backend.services.governance_loop import get_governance_loop
        # Test with autopilot ON
        gov = get_governance_loop(autopilot=True)
        
        low_risk = gov.assess({"risk": "low"})
        med_risk = gov.assess({"risk": "medium"})
        high_risk = gov.assess({"risk": "high"})
        crit_risk = gov.assess({"risk": "critical"})
        
        print(f"Autopilot ON - Low Risk Decision: {low_risk['decision']}")
        print(f"Autopilot ON - Medium Risk Decision: {med_risk['decision']}")
        print(f"Autopilot ON - High Risk Decision: {high_risk['decision']}")
        print(f"Autopilot ON - Critical Risk Decision: {crit_risk['decision']}")
        
        if low_risk['decision'] == 'approve' and crit_risk['decision'] == 'blocked':
            print("✅ SUCCESS: Governance logic respects risk levels and autopilot.")
        else:
            print("❌ FAILURE: Governance logic is incorrect.")
            
    except Exception as e:
        print(f"❌ ERROR in Governance Loop: {e}")

    # 3. Test LLM Router & Autonomous Council
    print("\n[3] Testing LLM Router & Autonomous Council...")
    try:
        from backend.services.llm_router import get_llm_router
        from backend.services.council_autonomous import get_autonomous_council
        
        router = get_llm_router()
        council = get_autonomous_council()
        
        print(f"Router strategy: {router.strategy.value}")
        print(f"Cloud enabled: {router.enable_cloud}")
        
        # Test a quick consultation (will use simulated responses if cloud keys missing)
        # We'll just check if it can run without crashing for now
        print("Running autonomous council consultation (30s timeout)...")
        try:
            result = await asyncio.wait_for(council.consult({
                "action_type": "test_action",
                "description": "Verification of autonomous council",
                "parameters": {}
            }), timeout=30.0)
            print(f"Council Result: {result.get('recommendation')} (Confidence: {result.get('confidence')})")
            print("✅ SUCCESS: LLM Router and Council services are operational.")
        except asyncio.TimeoutError:
            print("❌ TIMEOUT: Council consultation took too long. Check if Ollama is responsive or if models are being pulled.")
        
    except Exception as e:
        print(f"❌ ERROR in Router/Council: {e}")

    # 4. Test Cost Tracker
    print("\n[4] Testing Cost Tracker...")
    try:
        from backend.services.cost_tracker import get_cost_tracker
        tracker = get_cost_tracker()
        tracker.record_usage("claude-3-5-sonnet", 1000, 500)
        stats = tracker.get_stats()
        print(f"Daily Total: ${stats['daily_total_usd']:.4f}")
        print(f"Budget OK: {stats['can_spend']}")
        print("✅ SUCCESS: Cost Tracker is functional.")
    except Exception as e:
        print(f"❌ ERROR in Cost Tracker: {e}")

    print("\n=== EVALUATION COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(evaluate_functionality())
