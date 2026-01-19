# Daena AI VP System - Test Runner
import subprocess
import sys
import os
from datetime import datetime

class TestRunner:
    def __init__(self):
        self.test_files = [
            "agent_communication_test.py",
            "cmp_pipeline_test.py", 
            "budget_calculation_test.py",
            "sunflower_architecture_test.py",
            "api_integration_test.py"
        ]
        self.results = {
            "test_suite": "Daena AI VP System Test Suite",
            "timestamp": datetime.now().isoformat(),
            "tests_run": [],
            "summary": {}
        }
    
    def run_test(self, test_file):
        print(f"\n🚀 Running {test_file}...")
        print("=" * 50)
        
        try:
            result = subprocess.run([sys.executable, f"tests/{test_file}"], 
                                  capture_output=True, text=True, timeout=60)
            
            test_result = {
                "test_file": test_file,
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat()
            }
            
            if result.returncode == 0:
                print(f"✅ {test_file} PASSED")
            else:
                print(f"❌ {test_file} FAILED")
                print(f"Error: {result.stderr}")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_file} TIMEOUT")
            return {
                "test_file": test_file,
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": "Test timed out after 60 seconds",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"💥 {test_file} ERROR: {str(e)}")
            return {
                "test_file": test_file,
                "success": False,
                "return_code": -1,
                "stdout": "",
                "stderr": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def run_all_tests(self):
        print("🧠 Daena AI VP System - Test Suite")
        print("=" * 60)
        print(f"📅 Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Test Directory: {os.getcwd()}/tests")
        print("=" * 60)
        
        for test_file in self.test_files:
            test_result = self.run_test(test_file)
            self.results["tests_run"].append(test_result)
        
        self.calculate_summary()
        self.print_summary()
        self.save_results()
        
        return self.results
    
    def calculate_summary(self):
        total_tests = len(self.results["tests_run"])
        passed_tests = len([t for t in self.results["tests_run"] if t["success"]])
        failed_tests = total_tests - passed_tests
        
        self.results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": round(passed_tests / total_tests * 100, 2) if total_tests > 0 else 0,
            "test_duration": "~5 minutes",
            "timestamp": datetime.now().isoformat()
        }
    
    def print_summary(self):
        print("\n" + "=" * 60)
        print("📊 TEST SUITE SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {self.results['summary']['total_tests']}")
        print(f"Passed: {self.results['summary']['passed_tests']}")
        print(f"Failed: {self.results['summary']['failed_tests']}")
        print(f"Success Rate: {self.results['summary']['success_rate']}%")
        print("=" * 60)
        
        if self.results['summary']['failed_tests'] > 0:
            print("\n❌ FAILED TESTS:")
            for test in self.results["tests_run"]:
                if not test["success"]:
                    print(f"  - {test['test_file']}: {test['stderr']}")
        
        print("\n✅ All test results saved to: tests/results/")
        print("📁 Individual test results:")
        for test in self.results["tests_run"]:
            if test["success"]:
                result_file = test["test_file"].replace(".py", "_test_results.json")
                print(f"  - {result_file}")
    
    def save_results(self):
        with open("tests/results/test_suite_summary.json", "w") as f:
            import json
            json.dump(self.results, f, indent=2)

if __name__ == "__main__":
    runner = TestRunner()
    results = runner.run_all_tests()
    
    # Exit with error code if any tests failed
    if results["summary"]["failed_tests"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)
