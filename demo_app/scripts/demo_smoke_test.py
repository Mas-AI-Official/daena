#!/usr/bin/env python3
"""
Demo Smoke Test Script - AI Tinkerers Toronto Jan 2026

Validates demo system is ready for stage:
1. Backend health check
2. Demo endpoint responds
3. One demo request completes
4. Trace is generated and retrievable
5. UI page loads

Usage: python scripts/demo_smoke_test.py
"""

import asyncio
import sys
import time
from typing import Tuple

# Add parent to path for imports
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0].rsplit('/', 2)[0])

import httpx

BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_header():
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}  🐝 DAENA DEMO SMOKE TEST{Colors.END}")
    print(f"{Colors.BOLD}  AI Tinkerers Toronto - Jan 29, 2026{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")


def print_result(test_name: str, passed: bool, details: str = ""):
    icon = f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"
    status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
    print(f"  {icon} {test_name}: {status}")
    if details:
        print(f"      {Colors.BLUE}{details}{Colors.END}")


async def test_backend_health() -> Tuple[bool, str]:
    """Test 1: Backend health check"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/v1/health/")
            if response.status_code == 200:
                data = response.json()
                return True, f"Status: {data.get('status', 'unknown')}"
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


async def test_demo_health() -> Tuple[bool, str]:
    """Test 2: Demo endpoint health"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/v1/demo/health")
            if response.status_code == 200:
                data = response.json()
                demo_mode = data.get('demo_mode', False)
                return True, f"Demo mode: {'enabled' if demo_mode else 'disabled'}"
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


async def test_demo_run() -> Tuple[bool, str, str]:
    """Test 3: Demo run request"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT * 3) as client:
            start = time.time()
            response = await client.post(
                f"{BASE_URL}/api/v1/demo/run",
                json={"prompt": "Explain Daena routing", "use_cloud": False}
            )
            duration = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                data = response.json()
                trace_id = data.get('trace_id', '')
                return True, f"Completed in {duration}ms, trace_id: {trace_id}", trace_id
            return False, f"HTTP {response.status_code}", ""
    except Exception as e:
        return False, str(e), ""


async def test_trace_fetch(trace_id: str) -> Tuple[bool, str]:
    """Test 4: Trace retrieval"""
    if not trace_id:
        return False, "No trace_id from previous test"
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(f"{BASE_URL}/api/v1/demo/trace/{trace_id}")
            if response.status_code == 200:
                data = response.json()
                event_count = len(data.get('events', []))
                return True, f"Retrieved {event_count} events"
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


async def test_ui_page() -> Tuple[bool, str]:
    """Test 5: Demo UI page loads"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            start = time.time()
            response = await client.get(f"{BASE_URL}/demo")
            duration = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                if duration < 3000:
                    return True, f"Loaded in {duration}ms (< 3s requirement)"
                else:
                    return False, f"Loaded in {duration}ms (> 3s requirement)"
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)


async def run_all_tests():
    """Run all smoke tests"""
    print_header()
    
    results = []
    
    # Test 1: Backend health
    print(f"{Colors.YELLOW}Running tests...{Colors.END}\n")
    passed, details = await test_backend_health()
    print_result("Backend Health", passed, details)
    results.append(passed)
    
    # Test 2: Demo health
    passed, details = await test_demo_health()
    print_result("Demo Endpoint", passed, details)
    results.append(passed)
    
    # Test 3: Demo run
    passed, details, trace_id = await test_demo_run()
    print_result("Demo Run", passed, details)
    results.append(passed)
    
    # Test 4: Trace fetch
    passed, details = await test_trace_fetch(trace_id)
    print_result("Trace Retrieval", passed, details)
    results.append(passed)
    
    # Test 5: UI page
    passed, details = await test_ui_page()
    print_result("Demo UI Page", passed, details)
    results.append(passed)
    
    # Summary
    total = len(results)
    passed_count = sum(results)
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    if passed_count == total:
        print(f"{Colors.GREEN}{Colors.BOLD}  ✓ ALL {total} TESTS PASSED - DEMO READY!{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}  ✗ {total - passed_count}/{total} TESTS FAILED{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")
    
    return passed_count == total


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)
