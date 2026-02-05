#!/usr/bin/env python3
"""
Backend-Frontend Sync Test for Daena
Tests that chat persistence and department routes work correctly.
"""
from __future__ import annotations

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: pip install httpx")
    sys.exit(1)

import json
import uuid
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 10.0

def test_health() -> tuple[bool, str]:
    """Test backend health"""
    try:
        resp = httpx.get(f"{BASE_URL}/api/v1/health/", timeout=TIMEOUT, follow_redirects=True)
        return resp.status_code == 200, f"Health: {resp.status_code}"
    except Exception as e:
        return False, f"Health failed: {e}"

def test_create_department_session() -> tuple[bool, dict]:
    """Create a department chat session"""
    try:
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat-history/departments/engineering/sessions",
            json={"title": f"Test Session {datetime.utcnow().isoformat()}"},
            timeout=TIMEOUT,
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            return False, {"error": f"Status {resp.status_code}", "body": resp.text[:200]}
        
        data = resp.json()
        session_id = data.get("session_id")
        
        if not session_id:
            return False, {"error": "No session_id returned", "data": data}
        
        return True, {
            "session_id": session_id,
            "department_id": data.get("department_id"),
            "scope_type": data.get("scope_type")
        }
    except Exception as e:
        return False, {"error": str(e)}

def test_add_message(session_id: str) -> tuple[bool, dict]:
    """Add a message to session"""
    try:
        msg_content = f"Test message at {datetime.utcnow().isoformat()}"
        
        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat-history/sessions/{session_id}/messages",
            json={"sender": "user", "content": msg_content},
            timeout=TIMEOUT,
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            return False, {"error": f"Status {resp.status_code}"}
        
        return True, {"message": "Message added", "content": msg_content}
    except Exception as e:
        return False, {"error": str(e)}

def test_get_department_chats(dept_id: str = "engineering") -> tuple[bool, dict]:
    """Get all chats for a department"""
    try:
        resp = httpx.get(
            f"{BASE_URL}/api/v1/chat-history/departments/{dept_id}/chats",
            timeout=TIMEOUT,
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            return False, {"error": f"Status {resp.status_code}"}
        
        data = resp.json()
        return True, {
            "department_id": data.get("department_id"),
            "total_sessions": data.get("total", 0),
            "sessions": len(data.get("sessions", []))
        }
    except Exception as e:
        return False, {"error": str(e)}

def test_get_all_department_chats() -> tuple[bool, dict]:
    """Get all department chats grouped"""
    try:
        resp = httpx.get(
            f"{BASE_URL}/api/v1/chat-history/departments/chats/all",
            timeout=TIMEOUT,
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            return False, {"error": f"Status {resp.status_code}"}
        
        data = resp.json()
        return True, {
            "total_departments": data.get("total_departments", 0),
            "total_sessions": data.get("total_sessions", 0),
            "departments": list(data.get("departments", {}).keys())
        }
    except Exception as e:
        return False, {"error": str(e)}

def test_session_persistence(session_id: str) -> tuple[bool, dict]:
    """Verify session was persisted"""
    try:
        resp = httpx.get(
            f"{BASE_URL}/api/v1/chat-history/sessions/{session_id}",
            timeout=TIMEOUT,
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            return False, {"error": f"Session not found: {resp.status_code}"}
        
        data = resp.json()
        return True, {
            "id": data.get("id"),
            "title": data.get("title"),
            "scope_type": data.get("scope_type"),
            "scope_id": data.get("scope_id"),
            "message_count": len(data.get("messages", []))
        }
    except Exception as e:
        return False, {"error": str(e)}

def test_scope_filter() -> tuple[bool, dict]:
    """Test scope-based filtering"""
    try:
        resp = httpx.get(
            f"{BASE_URL}/api/v1/chat-history/scope/department",
            timeout=TIMEOUT,
            follow_redirects=True
        )
        
        if resp.status_code != 200:
            return False, {"error": f"Status {resp.status_code}"}
        
        data = resp.json()
        return True, {
            "scope_type": data.get("scope_type"),
            "total_sessions": data.get("total", 0)
        }
    except Exception as e:
        return False, {"error": str(e)}

def main() -> int:
    """Run sync tests"""
    print("=" * 60)
    print("  DAENA BACKEND-FRONTEND SYNC TEST")
    print("=" * 60)
    print()
    
    all_passed = True
    session_id = None
    
    # Test 1: Health
    print("[1] Backend Health Check")
    ok, result = test_health()
    print(f"    {'✅' if ok else '❌'} {result}")
    if not ok:
        print("\n❌ Backend not running. Start with: python -m uvicorn backend.main:app")
        return 1
    print()
    
    # Test 2: Create department session
    print("[2] Create Department Session (engineering)")
    ok, result = test_create_department_session()
    if ok:
        session_id = result.get("session_id")
        print(f"    ✅ Session created: {session_id[:8]}...")
        print(f"       scope_type: {result.get('scope_type')}")
    else:
        print(f"    ❌ Failed: {result.get('error')}")
        all_passed = False
    print()
    
    # Test 3: Add message
    if session_id:
        print("[3] Add Message to Session")
        ok, result = test_add_message(session_id)
        if ok:
            print(f"    ✅ Message added")
        else:
            print(f"    ❌ Failed: {result.get('error')}")
            all_passed = False
        print()
    
    # Test 4: Verify persistence
    if session_id:
        print("[4] Verify Session Persistence")
        ok, result = test_session_persistence(session_id)
        if ok:
            print(f"    ✅ Session persisted")
            print(f"       Messages: {result.get('message_count')}")
            print(f"       Scope: {result.get('scope_type')}:{result.get('scope_id')}")
        else:
            print(f"    ❌ Failed: {result.get('error')}")
            all_passed = False
        print()
    
    # Test 5: Get department chats
    print("[5] Get Department Chats")
    ok, result = test_get_department_chats()
    if ok:
        print(f"    ✅ Department: engineering")
        print(f"       Sessions: {result.get('total_sessions')}")
    else:
        print(f"    ❌ Failed: {result.get('error')}")
        all_passed = False
    print()
    
    # Test 6: Get all department chats
    print("[6] Get All Department Chats (grouped)")
    ok, result = test_get_all_department_chats()
    if ok:
        print(f"    ✅ Total departments: {result.get('total_departments')}")
        print(f"       Departments: {', '.join(result.get('departments', []))}")
    else:
        print(f"    ❌ Failed: {result.get('error')}")
        all_passed = False
    print()
    
    # Test 7: Scope filter
    print("[7] Scope-Based Filter")
    ok, result = test_scope_filter()
    if ok:
        print(f"    ✅ Filter by scope_type=department")
        print(f"       Sessions found: {result.get('total_sessions')}")
    else:
        print(f"    ❌ Failed: {result.get('error')}")
        all_passed = False
    print()
    
    # Summary
    print("=" * 60)
    if all_passed:
        print("  ✅ ALL SYNC TESTS PASSED")
        print("=" * 60)
        print()
        print("  Chat persistence: WORKING")
        print("  Department scope: WORKING")
        print("  Frontend can use: /api/v1/chat-history/departments/{dept_id}/chats")
        return 0
    else:
        print("  ❌ SOME TESTS FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
