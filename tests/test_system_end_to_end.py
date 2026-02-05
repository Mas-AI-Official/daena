#!/usr/bin/env python3
"""
End-to-End System Test
Tests the complete Daena AI system from backend to frontend
"""
import sys
import time
import requests
import json
from typing import Dict, Any, List

BASE_URL = "http://localhost:8000"
TIMEOUT = 10

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_status(message: str, status: str = "info"):
    """Print colored status message"""
    if status == "success":
        print(f"{Colors.GREEN}✓{Colors.NC} {message}")
    elif status == "error":
        print(f"{Colors.RED}✗{Colors.NC} {message}")
    elif status == "warning":
        print(f"{Colors.YELLOW}⚠{Colors.NC} {message}")
    else:
        print(f"{Colors.BLUE}ℹ{Colors.NC} {message}")

def test_endpoint(url: str, method: str = "GET", data: Dict = None, expected_status: int = 200) -> bool:
    """Test an API endpoint"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=TIMEOUT)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=TIMEOUT)
        else:
            return False
        
        if response.status_code == expected_status:
            return True
        else:
            print_status(f"{url} returned {response.status_code}, expected {expected_status}", "error")
            return False
    except Exception as e:
        print_status(f"{url} failed: {str(e)}", "error")
        return False

def test_health():
    """Test health endpoint"""
    print("\n" + "="*60)
    print("Testing Health Endpoint")
    print("="*60)
    
    if test_endpoint(f"{BASE_URL}/health"):
        print_status("Health endpoint working", "success")
        return True
    return False

def test_monitoring():
    """Test monitoring endpoints"""
    print("\n" + "="*60)
    print("Testing Monitoring Endpoints")
    print("="*60)
    
    endpoints = [
        "/monitoring/memory",
        "/monitoring/memory/cas",
        "/monitoring/memory/cost-tracking",
        "/monitoring/memory/prometheus",
    ]
    
    results = []
    for endpoint in endpoints:
        if test_endpoint(f"{BASE_URL}{endpoint}"):
            print_status(f"{endpoint} working", "success")
            results.append(True)
        else:
            results.append(False)
    
    return all(results)

def test_api_endpoints():
    """Test core API endpoints"""
    print("\n" + "="*60)
    print("Testing Core API Endpoints")
    print("="*60)
    
    endpoints = [
        "/api/v1/departments/",
        "/api/v1/agents/",
        "/api/v1/projects/",
        "/api/v1/analytics/summary",
        "/api/v1/analytics/communication-patterns",
        "/api/v1/integrations/",
        "/api/v1/hiring/positions/",
    ]
    
    results = []
    for endpoint in endpoints:
        if test_endpoint(f"{BASE_URL}{endpoint}"):
            print_status(f"{endpoint} working", "success")
            results.append(True)
        else:
            results.append(False)
    
    return all(results)

def test_frontend():
    """Test frontend endpoints"""
    print("\n" + "="*60)
    print("Testing Frontend Endpoints")
    print("="*60)
    
    endpoints = [
        "/command-center",
        "/docs",
        "/",
    ]
    
    results = []
    for endpoint in endpoints:
        if test_endpoint(f"{BASE_URL}{endpoint}"):
            print_status(f"{endpoint} accessible", "success")
            results.append(True)
        else:
            results.append(False)
    
    return all(results)

def test_data_integrity():
    """Test data integrity"""
    print("\n" + "="*60)
    print("Testing Data Integrity")
    print("="*60)
    
    try:
        # Test departments
        response = requests.get(f"{BASE_URL}/api/v1/departments/", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            dept_count = len(data.get("departments", []))
            if dept_count == 8:
                print_status(f"Found {dept_count} departments (expected 8)", "success")
            else:
                print_status(f"Found {dept_count} departments (expected 8)", "warning")
        
        # Test agents
        response = requests.get(f"{BASE_URL}/api/v1/agents/", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            agent_count = len(data.get("agents", []))
            if agent_count == 48:
                print_status(f"Found {agent_count} agents (expected 48)", "success")
            else:
                print_status(f"Found {agent_count} agents (expected 48)", "warning")
        
        return True
    except Exception as e:
        print_status(f"Data integrity test failed: {str(e)}", "error")
        return False

def test_metatron_viz():
    """Test Metatron visualization data"""
    print("\n" + "="*60)
    print("Testing Metatron Visualization Data")
    print("="*60)
    
    try:
        # Test communication patterns (needed for visualization)
        response = requests.get(f"{BASE_URL}/api/v1/analytics/communication-patterns", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print_status("Communication patterns available", "success")
            return True
        else:
            print_status("Communication patterns endpoint failed", "error")
            return False
    except Exception as e:
        print_status(f"Metatron visualization test failed: {str(e)}", "error")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Daena AI - End-to-End System Test")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    print(f"Timeout: {TIMEOUT} seconds")
    
    # Wait for server to be ready
    print("\nWaiting for server to be ready...")
    for i in range(10):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print_status("Server is ready", "success")
                break
        except:
            if i == 9:
                print_status("Server not responding. Make sure it's running on port 8000", "error")
                sys.exit(1)
            time.sleep(1)
    
    # Run tests
    results = {
        "health": test_health(),
        "monitoring": test_monitoring(),
        "api_endpoints": test_api_endpoints(),
        "frontend": test_frontend(),
        "data_integrity": test_data_integrity(),
        "metatron_viz": test_metatron_viz(),
    }
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, result in results.items():
        status = "success" if result else "error"
        print_status(f"{test_name}: {'PASSED' if result else 'FAILED'}", status)
    
    print("\n" + "-"*60)
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    print("-"*60)
    
    if passed_tests == total_tests:
        print_status("\n✅ All tests passed! System is operational.", "success")
        return 0
    else:
        print_status(f"\n⚠️ {total_tests - passed_tests} test(s) failed. Please review.", "warning")
        return 1

if __name__ == "__main__":
    sys.exit(main())

