"""
Production Readiness Test Suite
Comprehensive tests for all system components
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_core_imports():
    """Test all critical imports"""
    print("\n🧪 Testing Core Imports...")
    tests_passed = 0
    tests_total = 0
    
    imports_to_test = [
        ("backend.main", "Main FastAPI application"),
        ("backend.services.change_tracker", "Change tracker service"),
        ("backend.routes.change_control_v2", "Change control V2 API"),
        ("backend.database", "Database connection"),
    ]
    
    for module_name, description in imports_to_test:
        tests_total += 1
        try:
            __import__(module_name)
            print(f"   ✅ {description}")
            tests_passed += 1
        except Exception as e:
            print(f"   ❌ {description}: {str(e)[:50]}")
    
    return tests_passed, tests_total

def test_file_structure():
    """Test that all required files exist"""
    print("\n🧪 Testing File Structure...")
    tests_passed = 0
    tests_total = 0
    
    required_files = [
        "backend/main.py",
        "backend/services/change_tracker.py",
        "backend/routes/change_control_v2.py",
        "frontend/static/js/change-control.js",
        "frontend/static/js/change-audit.js",
        "frontend/static/js/strategic-room.js",
        "frontend/static/js/conference-room.js",
        "frontend/static/js/agent-builder.js",
        "frontend/static/js/websocket-enhanced.js",
        "frontend/static/js/ui-components.js",
    ]
    
    for file_path in required_files:
        tests_total += 1
        if Path(file_path).exists():
            print(f"   ✅ {file_path}")
            tests_passed += 1
        else:
            print(f"   ❌ {file_path} - NOT FOUND")
    
    return tests_passed, tests_total

def test_templates():
    """Test that all HTML templates exist"""
    print("\n🧪 Testing HTML Templates...")
    tests_passed = 0
    tests_total = 0
    
    critical_templates = [
        "departments.html",
        "department_detail.html",
        "conference_room.html",
        "strategic_room.html",
        "agent_builder.html",
        "template_detail.html",
        "user_agent_detail.html",
        "daena_decisions.html",
        "decision_detail.html",
        "strategic_assembly_dashboard.html"
    ]
    
    templates_dir = Path("frontend/templates")
    
    for template in critical_templates:
        tests_total += 1
        template_path = templates_dir / template
        if template_path.exists():
            print(f"   ✅ {template}")
            tests_passed += 1
        else:
            print(f"   ❌ {template} - NOT FOUND")
    
    return tests_passed, tests_total

def test_change_tracker():
    """Test change tracker functionality"""
    print("\n🧪 Testing Change Tracker...")
    tests_passed = 0
    tests_total = 0
    
    try:
        from backend.services.change_tracker import change_tracker
        
        # Test stats
        tests_total += 1
        stats = change_tracker.get_stats()
        if isinstance(stats, dict):
            print(f"   ✅ Stats retrieval (backups: {stats.get('total_backups', 0)})")
            tests_passed += 1
        else:
            print(f"   ❌ Stats retrieval failed")
        
        # Test history
        tests_total += 1
        history = change_tracker.get_history(limit=5)
        if isinstance(history, list):
            print(f"   ✅ History retrieval ({len(history)} records)")
            tests_passed += 1
        else:
            print(f"   ❌ History retrieval failed")
            
    except Exception as e:
        print(f"   ❌ Change tracker test failed: {str(e)[:100]}")
        tests_total += 2
    
    return tests_passed, tests_total

def test_api_availability():
    """Test that API endpoints are registered"""
    print("\n🧪 Testing API Availability...")
    tests_passed = 0
    tests_total = 0
    
    try:
        from backend.main import app
        
        # Get all routes
        routes = [route.path for route in app.routes]
        
        critical_endpoints = [
            "/api/v1/changes/stats",
            "/api/v1/changes/history",
            "/api/v1/changes/prepare",
            "/api/v1/changes/commit",
            "/api/v1/changes/rollback"
        ]
        
        for endpoint in critical_endpoints:
            tests_total += 1
            if endpoint in routes:
                print(f"   ✅ {endpoint}")
                tests_passed += 1
            else:
                print(f"   ❌ {endpoint} - NOT REGISTERED")
                
    except Exception as e:
        print(f"   ❌ API test failed: {str(e)[:100]}")
        tests_total += len(critical_endpoints)
    
    return tests_passed, tests_total

def run_all_tests():
    """Run all production readiness tests"""
    print("=" * 70)
    print("  PRODUCTION READINESS TEST SUITE")
    print("=" * 70)
    
    total_passed = 0
    total_tests = 0
    
    # Run all test suites
    test_suites = [
        test_core_imports,
        test_file_structure,
        test_templates,
        test_change_tracker,
        test_api_availability
    ]
    
    for test_suite in test_suites:
        try:
            passed, total = test_suite()
            total_passed += passed
            total_tests += total
        except Exception as e:
            print(f"\n❌ Test suite crashed: {str(e)}")
    
    # Print summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_tests - total_passed}")
    print(f"Success Rate: {int((total_passed / total_tests) * 100) if total_tests > 0 else 0}%")
    
    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED - PRODUCTION READY!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed - Review required")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
