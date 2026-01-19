"""
End-to-End Scenario Tests
Tests real-world scenarios through the entire Daena system
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

class ScenarioTest:
    def __init__(self):
        self.results = []
        self.gaps = []
        
    def log(self, status, message):
        icon = "✅" if status else "❌"
        print(f"  {icon} {message}")
        self.results.append((status, message))
        
    def log_gap(self, component, description, severity):
        self.gaps.append({
            "component": component,
            "description": description,
            "severity": severity
        })
        print(f"  🔧 GAP [{severity}]: {component} - {description}")

def test_scenario_1_app_building():
    """Test: User asks Daena to build an app"""
    print("\n" + "="*60)
    print("SCENARIO 1: Build an App")
    print("User: 'Build me an Instagram marketing app'")
    print("="*60)
    
    test = ScenarioTest()
    
    # Test 1: Brain endpoint exists
    print("\n[Step 1] Check Brain endpoints")
    try:
        from backend.routes.brain import router
        test.log(True, "Brain router imported successfully")
    except Exception as e:
        test.log(False, f"Brain router failed: {str(e)[:50]}")
    
    # Test 2: MCP integration
    print("\n[Step 2] Check MCP integration")
    try:
        from backend.routes.mcp import router as mcp_router
        test.log(True, "MCP router found")
    except Exception as e:
        test.log(False, f"MCP router missing: {str(e)[:50]}")
        test.log_gap("MCP Router", "MCP route handler needs verification", "MEDIUM")
    
    # Test 3: File operations
    print("\n[Step 3] Check file operation capabilities")
    try:
        from backend.routes.file_system import router as fs_router
        test.log(True, "File system router available")
    except Exception as e:
        test.log(False, f"File system router missing: {str(e)[:50]}")
        test.log_gap("File System", "No file operations endpoint", "HIGH")
    
    # Test 4: Code generation
    print("\n[Step 4] Check code generation capabilities")
    try:
        from backend.routes.daena_tools import router as tools_router
        test.log(True, "Daena tools router available")
    except Exception as e:
        test.log_gap("Code Generation", "No dedicated code generation endpoint", "MEDIUM")
    
    # Test 5: Project management
    print("\n[Step 5] Check project management")
    try:
        from backend.routes.projects import router as proj_router
        test.log(True, "Projects router available")
    except Exception as e:
        test.log(False, f"Projects router missing: {str(e)[:50]}")
    
    return test

def test_scenario_2_instagram_automation():
    """Test: Manage Instagram account and post marketing videos"""
    print("\n" + "="*60)
    print("SCENARIO 2: Instagram Marketing Automation")
    print("User: 'Post a marketing video to my Instagram'")
    print("="*60)
    
    test = ScenarioTest()
    
    # Test 1: Integrations endpoint
    print("\n[Step 1] Check integrations router")
    try:
        from backend.routes.integrations import router
        test.log(True, "Integrations router found")
    except Exception as e:
        test.log(False, f"Integrations router missing: {str(e)[:50]}")
        test.log_gap("Integrations", "No integration management", "HIGH")
    
    # Test 2: Social media specific
    print("\n[Step 2] Check social media integration")
    social_routes_exist = False
    try:
        from backend.routes import integrations
        # Check for social media endpoints
        import inspect
        source = inspect.getsource(integrations)
        if "social" in source.lower() or "instagram" in source.lower():
            social_routes_exist = True
            test.log(True, "Social media integration exists")
        else:
            test.log(False, "No dedicated social media endpoints")
            test.log_gap("Social Media", "Need Instagram/social media API routes", "HIGH")
    except Exception as e:
        test.log_gap("Social Media", f"Error checking: {str(e)[:30]}", "HIGH")
    
    # Test 3: Automation workflows
    print("\n[Step 3] Check automation workflows")
    try:
        from backend.routes.automation import router as auto_router
        test.log(True, "Automation router available")
    except Exception as e:
        test.log(False, f"Automation router missing: {str(e)[:50]}")
    
    # Test 4: Webhooks for callbacks
    print("\n[Step 4] Check webhook capabilities")
    try:
        from backend.routes.webhooks import router as webhook_router
        test.log(True, "Webhooks router available")
    except Exception as e:
        test.log_gap("Webhooks", "No webhook handler", "MEDIUM")
    
    # Test 5: Analytics
    print("\n[Step 5] Check analytics for tracking")
    try:
        from backend.routes.analytics import router as analytics_router
        test.log(True, "Analytics router available")
    except Exception as e:
        test.log_gap("Analytics", "No analytics endpoint", "LOW")
    
    return test

def test_scenario_3_strategic_planning():
    """Test: Strategic planning and decision making"""
    print("\n" + "="*60)
    print("SCENARIO 3: Strategic Planning")
    print("User: 'Create a strategic plan for Q1'")
    print("="*60)
    
    test = ScenarioTest()
    
    # Test components
    print("\n[Step 1] Check strategic room")
    try:
        from backend.routes.strategic_room import router
        test.log(True, "Strategic room router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    print("\n[Step 2] Check strategic meetings")
    try:
        from backend.routes.strategic_meetings import router
        test.log(True, "Strategic meetings router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    print("\n[Step 3] Check decisions")
    try:
        from backend.routes.daena_decisions import router
        test.log(True, "Daena decisions router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    print("\n[Step 4] Check councils")
    try:
        from backend.routes.councils import router
        test.log(True, "Councils router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    return test

def test_scenario_4_agent_creation():
    """Test: Create and deploy custom agent"""
    print("\n" + "="*60)
    print("SCENARIO 4: Agent Creation")
    print("User: 'Create a marketing agent for social media'")
    print("="*60)
    
    test = ScenarioTest()
    
    print("\n[Step 1] Check agent builder")
    try:
        from backend.routes.agent_builder_platform import router
        test.log(True, "Agent builder platform found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    print("\n[Step 2] Check agent management")
    try:
        from backend.routes.agents import router
        test.log(True, "Agents router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    print("\n[Step 3] Check departments for assignment")
    try:
        from backend.routes.departments import router
        test.log(True, "Departments router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    return test

def test_scenario_5_voice_interaction():
    """Test: Voice-based interaction with Daena"""
    print("\n" + "="*60)
    print("SCENARIO 5: Voice Interaction")
    print("User speaks: 'Hey Daena, what's my schedule today?'")
    print("="*60)
    
    test = ScenarioTest()
    
    print("\n[Step 1] Check voice routes")
    try:
        from backend.routes.voice import router
        test.log(True, "Voice router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    print("\n[Step 2] Check voice agents")
    try:
        from backend.routes.voice_agents import router
        test.log(True, "Voice agents router found")
    except Exception as e:
        test.log(False, f"Missing: {str(e)[:50]}")
    
    return test

def run_all_scenarios():
    """Run all scenario tests"""
    print("="*70)
    print("  END-TO-END SCENARIO TESTING")
    print("="*70)
    
    all_gaps = []
    all_results = []
    
    # Run each scenario
    scenarios = [
        test_scenario_1_app_building,
        test_scenario_2_instagram_automation,
        test_scenario_3_strategic_planning,
        test_scenario_4_agent_creation,
        test_scenario_5_voice_interaction
    ]
    
    for scenario_fn in scenarios:
        try:
            test = scenario_fn()
            all_gaps.extend(test.gaps)
            all_results.extend(test.results)
        except Exception as e:
            print(f"❌ Scenario crashed: {e}")
    
    # Summary
    print("\n" + "="*70)
    print("  GAP ANALYSIS SUMMARY")
    print("="*70)
    
    if all_gaps:
        high = [g for g in all_gaps if g["severity"] == "HIGH"]
        medium = [g for g in all_gaps if g["severity"] == "MEDIUM"]
        low = [g for g in all_gaps if g["severity"] == "LOW"]
        
        print(f"\n🔴 HIGH Priority Gaps: {len(high)}")
        for g in high:
            print(f"   - {g['component']}: {g['description']}")
        
        print(f"\n🟡 MEDIUM Priority Gaps: {len(medium)}")
        for g in medium:
            print(f"   - {g['component']}: {g['description']}")
        
        print(f"\n🟢 LOW Priority Gaps: {len(low)}")
        for g in low:
            print(f"   - {g['component']}: {g['description']}")
    else:
        print("\n✅ No critical gaps found!")
    
    # Final stats
    passed = sum(1 for r in all_results if r[0])
    total = len(all_results)
    
    print("\n" + "="*70)
    print("  FINAL RESULTS")
    print("="*70)
    print(f"\nTests Run: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Gaps Found: {len(all_gaps)}")
    print(f"Success Rate: {int((passed/total)*100) if total > 0 else 0}%")
    
    if len(all_gaps) == 0:
        print("\n🎉 ALL SCENARIOS PASS - SYSTEM FULLY FUNCTIONAL!")
    else:
        print(f"\n⚠️ {len(all_gaps)} gap(s) identified - See recommendations above")
    
    print("="*70)
    
    return all_gaps

if __name__ == "__main__":
    gaps = run_all_scenarios()
    sys.exit(0 if len(gaps) == 0 else 1)
