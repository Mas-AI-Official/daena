"""
UI & API Smoke Test Script

Tests that all critical UI pages and API endpoints are accessible.
Only runs if backend is already running (does not start backend).
"""

from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Install with: pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 5.0
MAX_RETRIES = 3
RETRY_DELAY = 2.0


def check_endpoint(url: str, expected_status: int = 200) -> Tuple[bool, str, int]:
    """
    Check if an endpoint is accessible.
    Returns: (success, message, status_code)
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.get(url, timeout=TIMEOUT, follow_redirects=True)
            status = response.status_code
            
            if status == expected_status:
                return True, f"OK ({status})", status
            elif status == 404:
                return False, f"404 Not Found", status
            elif status == 500:
                return False, f"500 Server Error", status
            elif status in (301, 302, 307, 308):
                return True, f"Redirect ({status})", status
            else:
                return False, f"Unexpected status {status}", status
        except httpx.ConnectError:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            return False, "Connection refused (backend not running?)", 0
        except httpx.TimeoutException:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
                continue
            return False, "Timeout", 0
        except Exception as e:
            return False, f"Error: {str(e)}", 0
    
    return False, "Max retries exceeded", 0


def main() -> int:
    """Run smoke tests"""
    print("=" * 60)
    print("UI & API Smoke Test")
    print("=" * 60)
    print()
    print(f"Testing endpoints at: {BASE_URL}")
    print()
    
    # Test endpoints
    tests: List[Tuple[str, str, int]] = [
        # API endpoints
        ("API Health", "/api/v1/health/", 200),
        ("API Agents", "/api/v1/agents", 200),
        ("API Departments", "/api/v1/departments", 200),
        
        # UI pages
        ("UI Dashboard", "/ui/dashboard", 200),
        ("UI Agents", "/ui/agents", 200),
        ("UI Departments", "/ui/departments", 200),
        ("UI Council", "/ui/council", 200),  # May redirect
        ("UI Memory", "/ui/memory", 200),
        ("UI Health", "/ui/health", 200),
        ("UI Daena Office", "/ui/daena-office", 200),
        ("UI Founder Panel", "/ui/founder-panel", 200),
        ("UI Strategic Meetings", "/ui/strategic-meetings", 200),
        ("UI Task Timeline", "/ui/task-timeline", 200),
    ]
    
    results: List[Tuple[str, bool, str, int]] = []
    
    for name, path, expected_status in tests:
        url = f"{BASE_URL}{path}"
        success, message, status = check_endpoint(url, expected_status)
        results.append((name, success, message, status))
        
        status_icon = "[PASS]" if success else "[FAIL]"
        print(f"{status_icon} {name:30} {message}")
    
    print()
    print("=" * 60)
    
    # Summary
    passed = sum(1 for _, success, _, _ in results if success)
    total = len(results)
    failed = total - passed
    
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print()
    
    if failed > 0:
        print("Failed endpoints:")
        for name, success, message, status in results:
            if not success:
                print(f"  [FAIL] {name}: {message} (status: {status})")
                # Provide hints
                if status == 404:
                    print(f"     → Hint: Route may not be registered or template missing")
                elif status == 500:
                    print(f"     → Hint: Check backend logs for template render errors")
                elif status == 0:
                    print(f"     → Hint: Backend may not be running. Start with: START_DAENA.bat")
        print()
        return 1
    else:
        print("[PASS] All endpoints accessible!")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())

