#!/usr/bin/env python3
"""
Comprehensive Test Suite for Daena AI VP System

This test suite covers:
- Backend API endpoints
- Frontend functionality
- Integration tests
- End-to-end tests
- System health checks
- Error handling
- Performance tests

Run with: pytest tests/test_comprehensive_suite.py -v
"""

from __future__ import annotations

import sys
import os
import io
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

# Fix Unicode output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import httpx
    import pytest
except ImportError:
    print("ERROR: Required packages not installed. Run: pip install httpx pytest")
    sys.exit(1)

# Test configuration
BASE_URL = os.getenv("DAENA_TEST_URL", "http://127.0.0.1:8000")
TIMEOUT = float(os.getenv("DAENA_TEST_TIMEOUT", "30.0"))
QUICK_TIMEOUT = 5.0


@dataclass
class TestResult:
    """Test result data structure"""
    name: str
    passed: bool
    message: str
    duration: float
    details: Optional[Dict[str, Any]] = None


class ComprehensiveTestSuite:
    """Comprehensive test suite for Daena system"""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.timeout = TIMEOUT
        self.results: List[TestResult] = []
        self.client = httpx.Client(timeout=self.timeout, follow_redirects=True)
    
    def run_test(self, test_func, *args, **kwargs) -> TestResult:
        """Run a test function and record the result"""
        start_time = time.time()
        try:
            passed, message, details = test_func(*args, **kwargs)
            duration = time.time() - start_time
            return TestResult(
                name=test_func.__name__,
                passed=passed,
                message=message,
                duration=duration,
                details=details or {}
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                name=test_func.__name__,
                passed=False,
                message=f"Test exception: {str(e)}",
                duration=duration,
                details={"exception": str(e)}
            )
    
    # ==================== HEALTH & STATUS TESTS ====================
    
    def test_health_endpoint(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/health endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/health/", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return True, "Health endpoint responding", {"status_code": 200, "data": data}
            return False, f"Health endpoint returned {response.status_code}", {"status_code": response.status_code}
        except httpx.ConnectError:
            return False, "Backend not running", {}
        except Exception as e:
            return False, f"Health test error: {str(e)}", {"error": str(e)}
    
    def test_llm_status(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/llm/status endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/llm/status", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return True, "LLM status endpoint responding", {"status_code": 200, "data": data}
            return False, f"LLM status returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"LLM status test error: {str(e)}", {"error": str(e)}
    
    def test_brain_status(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/brain/status endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/brain/status", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return True, "Brain status endpoint responding", {"status_code": 200, "data": data}
            return False, f"Brain status returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Brain status test error: {str(e)}", {"error": str(e)}
    
    def test_voice_status(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/voice/status endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/voice/status", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return True, "Voice status endpoint responding", {"status_code": 200, "data": data}
            return False, f"Voice status returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Voice status test error: {str(e)}", {"error": str(e)}
    
    # ==================== CHAT TESTS ====================
    
    def test_daena_chat(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/daena/chat endpoint"""
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/daena/chat",
                json={
                    "message": "Hello, this is a test message",
                    "session_id": "test_comprehensive_session"
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if "response" in data:
                    return True, "Daena chat responding", {
                        "status_code": 200,
                        "response_length": len(str(data.get("response", ""))),
                        "has_response": True
                    }
                return False, "Daena chat missing 'response' field", {"data": data}
            return False, f"Daena chat returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Daena chat test error: {str(e)}", {"error": str(e)}
    
    def test_agent_chat(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/agents/{id}/chat endpoint"""
        try:
            # First, get list of agents
            agents_resp = self.client.get(f"{self.base_url}/api/v1/agents", timeout=QUICK_TIMEOUT)
            if agents_resp.status_code != 200:
                return False, f"Failed to get agents list: {agents_resp.status_code}", {}
            
            agents_data = agents_resp.json()
            agents = agents_data.get("agents", [])
            if not agents:
                return False, "No agents available", {}
            
            # Get first agent ID
            first_agent = agents[0]
            agent_id = first_agent.get("id") or first_agent.get("agent_id") or str(first_agent.get("id", ""))
            
            if not agent_id:
                return False, "Agent missing ID field", {"agent": first_agent}
            
            # Test chat with agent
            chat_resp = self.client.post(
                f"{self.base_url}/api/v1/agents/{agent_id}/chat",
                json={
                    "message": "Hello, this is a test",
                    "context": {"source": "comprehensive_test"}
                },
                timeout=self.timeout
            )
            
            if chat_resp.status_code == 200:
                data = chat_resp.json()
                return True, f"Agent chat responding", {
                    "status_code": 200,
                    "agent_id": str(agent_id),
                    "has_response": "response" in data or "success" in data
                }
            return False, f"Agent chat returned {chat_resp.status_code}", {"status_code": chat_resp.status_code}
        except Exception as e:
            return False, f"Agent chat test error: {str(e)}", {"error": str(e)}
    
    # ==================== API ENDPOINT TESTS ====================
    
    def test_agents_list(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/agents endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/agents", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                agents = data.get("agents", [])
                return True, f"Agents list retrieved ({len(agents)} agents)", {
                    "status_code": 200,
                    "agent_count": len(agents)
                }
            return False, f"Agents list returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Agents list test error: {str(e)}", {"error": str(e)}
    
    def test_departments_list(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/departments endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/departments", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                departments = data.get("departments", [])
                return True, f"Departments list retrieved ({len(departments)} departments)", {
                    "status_code": 200,
                    "department_count": len(departments)
                }
            return False, f"Departments list returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Departments list test error: {str(e)}", {"error": str(e)}
    
    def test_chat_history_sessions(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/chat-history/sessions endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/chat-history/sessions", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                sessions = data.get("sessions", [])
                return True, f"Chat sessions retrieved ({len(sessions)} sessions)", {
                    "status_code": 200,
                    "session_count": len(sessions)
                }
            return False, f"Chat sessions returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Chat sessions test error: {str(e)}", {"error": str(e)}
    
    def test_analytics_summary(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/analytics/summary endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/analytics/summary", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                return True, "Analytics summary retrieved", {"status_code": 200}
            return False, f"Analytics summary returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Analytics summary test error: {str(e)}", {"error": str(e)}
    
    def test_audit_logs(self) -> Tuple[bool, str, Dict]:
        """Test /api/v1/audit/logs endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/audit/logs?limit=10", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                logs = data.get("logs", [])
                return True, f"Audit logs retrieved ({len(logs)} logs)", {
                    "status_code": 200,
                    "log_count": len(logs)
                }
            return False, f"Audit logs returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Audit logs test error: {str(e)}", {"error": str(e)}
    
    # ==================== FRONTEND TESTS ====================
    
    def test_ui_dashboard(self) -> Tuple[bool, str, Dict]:
        """Test /ui/dashboard page"""
        try:
            response = self.client.get(f"{self.base_url}/ui/dashboard", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                content = response.text
                has_content = len(content) > 1000  # Basic content check
                return True, "Dashboard page accessible", {
                    "status_code": 200,
                    "has_content": has_content,
                    "content_length": len(content)
                }
            return False, f"Dashboard page returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Dashboard page test error: {str(e)}", {"error": str(e)}
    
    def test_ui_daena_office(self) -> Tuple[bool, str, Dict]:
        """Test /ui/daena-office page"""
        try:
            response = self.client.get(f"{self.base_url}/ui/daena-office", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                content = response.text
                has_content = len(content) > 1000
                return True, "Executive Office page accessible", {
                    "status_code": 200,
                    "has_content": has_content,
                    "content_length": len(content)
                }
            return False, f"Executive Office page returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Executive Office page test error: {str(e)}", {"error": str(e)}
    
    def test_static_files(self) -> Tuple[bool, str, Dict]:
        """Test static file serving"""
        try:
            # Test a common static file
            response = self.client.get(f"{self.base_url}/static/js/api-client.js", timeout=QUICK_TIMEOUT)
            if response.status_code == 200:
                return True, "Static files accessible", {"status_code": 200}
            return False, f"Static files returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Static files test error: {str(e)}", {"error": str(e)}
    
    # ==================== ERROR HANDLING TESTS ====================
    
    def test_invalid_endpoint(self) -> Tuple[bool, str, Dict]:
        """Test error handling for invalid endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/api/v1/invalid/endpoint", timeout=QUICK_TIMEOUT)
            # Should return 404, not crash
            if response.status_code == 404:
                return True, "Invalid endpoint returns 404 (correct)", {"status_code": 404}
            return False, f"Invalid endpoint returned {response.status_code} (expected 404)", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Invalid endpoint test error: {str(e)}", {"error": str(e)}
    
    def test_malformed_request(self) -> Tuple[bool, str, Dict]:
        """Test error handling for malformed request"""
        try:
            response = self.client.post(
                f"{self.base_url}/api/v1/daena/chat",
                json={"invalid": "data"},  # Missing required fields
                timeout=QUICK_TIMEOUT
            )
            # Should return 422 or 400, not crash
            if response.status_code in [400, 422]:
                return True, "Malformed request handled correctly", {"status_code": response.status_code}
            return False, f"Malformed request returned {response.status_code} (expected 400/422)", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Malformed request test error: {str(e)}", {"error": str(e)}
    
    # ==================== PERFORMANCE TESTS ====================
    
    def test_response_time(self) -> Tuple[bool, str, Dict]:
        """Test response time for health endpoint"""
        try:
            start = time.time()
            response = self.client.get(f"{self.base_url}/api/v1/health/", timeout=QUICK_TIMEOUT)
            duration = time.time() - start
            
            if response.status_code == 200:
                if duration < 1.0:  # Should respond in under 1 second
                    return True, f"Health endpoint fast ({duration:.3f}s)", {
                        "duration": duration,
                        "status_code": 200
                    }
                return False, f"Health endpoint slow ({duration:.3f}s)", {"duration": duration}
            return False, f"Health endpoint returned {response.status_code}", {"status_code": response.status_code}
        except Exception as e:
            return False, f"Response time test error: {str(e)}", {"error": str(e)}
    
    # ==================== RUN ALL TESTS ====================
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return summary"""
        print("=" * 80)
        print("COMPREHENSIVE TEST SUITE - DAENA AI VP SYSTEM")
        print("=" * 80)
        print(f"Testing: {self.base_url}")
        print()
        
        # Define all test functions
        test_functions = [
            # Health & Status
            self.test_health_endpoint,
            self.test_llm_status,
            self.test_brain_status,
            self.test_voice_status,
            # Chat
            self.test_daena_chat,
            self.test_agent_chat,
            # API Endpoints
            self.test_agents_list,
            self.test_departments_list,
            self.test_chat_history_sessions,
            self.test_analytics_summary,
            self.test_audit_logs,
            # Frontend
            self.test_ui_dashboard,
            self.test_ui_daena_office,
            self.test_static_files,
            # Error Handling
            self.test_invalid_endpoint,
            self.test_malformed_request,
            # Performance
            self.test_response_time,
        ]
        
        # Run all tests
        for test_func in test_functions:
            result = self.run_test(test_func)
            self.results.append(result)
            
            # Print result
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status} {result.name}")
            print(f"     {result.message}")
            if result.duration > 1.0:
                print(f"     Duration: {result.duration:.3f}s")
            print()
        
        # Generate summary
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        failed = total - passed
        
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Success Rate: {(passed/total*100):.1f}%")
        print()
        
        if failed > 0:
            print("Failed Tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  ❌ {result.name}: {result.message}")
            print()
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total * 100,
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "duration": r.duration,
                    "details": r.details
                }
                for r in self.results
            ]
        }
    
    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'client'):
            self.client.close()


def main():
    """Main entry point"""
    suite = ComprehensiveTestSuite()
    summary = suite.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()




