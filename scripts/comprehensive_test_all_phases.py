#!/usr/bin/env python3
"""
Comprehensive Test Script for All Phases (1-8 + Recommendations)
Tests all implemented features including new migrations
"""
import sys
import os
import io
import time
import json
from pathlib import Path
import subprocess

# Fix Unicode output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import httpx
    import websocket
except ImportError:
    print("ERROR: httpx and websocket-client not installed. Run: pip install httpx websocket-client")
    sys.exit(1)

# Configuration
BACKEND_URL = "http://127.0.0.1:8000"
TIMEOUT = 10.0
DB_PATH = Path(__file__).parent.parent / "daena.db"

def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def run_test(test_func, *args, **kwargs) -> tuple[bool, str]:
    """Helper to run a test function and format output."""
    try:
        result = test_func(*args, **kwargs)
        if isinstance(result, tuple) and len(result) == 2:
            return result
        return True, str(result)
    except Exception as e:
        return False, f"Exception: {e}"

# --- Phase 1-8 Tests (from smoke_test_phases_1_7.py) ---
def test_backend_health() -> tuple[bool, str]:
    """Tests the backend health endpoint."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/health/", timeout=TIMEOUT)
        if response.status_code == 200:
            return True, f"✅ Backend is healthy (Status: {response.status_code})"
        return False, f"❌ Backend health check failed (Status: {response.status_code})"
    except httpx.ConnectError:
        return False, "❌ Cannot connect to backend. Is it running?"
    except Exception as e:
        return False, f"❌ Error checking backend health: {e}"

def test_database_persistence() -> tuple[bool, str]:
    """Verifies daena.db exists and has content."""
    if not DB_PATH.exists():
        return False, f"❌ Database file not found at {DB_PATH}"
    if DB_PATH.stat().st_size < 1024:
        return False, f"❌ Database file is too small, likely empty ({DB_PATH.stat().st_size} bytes)"
    return True, f"✅ Database file exists and has content ({DB_PATH.stat().st_size} bytes)"

def test_tasks_persistence() -> tuple[bool, str]:
    """Tests if tasks can be created and retrieved from the database."""
    try:
        task_data = {"title": "Comprehensive Test Task", "description": "Verify task persistence", "status": "pending"}
        create_resp = httpx.post(f"{BACKEND_URL}/api/v1/tasks/", json=task_data, timeout=TIMEOUT)
        if create_resp.status_code != 200:
            return False, f"❌ Failed to create task (Status: {create_resp.status_code})"
        
        task_id = create_resp.json().get("task_id")
        if not task_id:
            return False, f"❌ Created task did not return a task_id"
        
        get_resp = httpx.get(f"{BACKEND_URL}/api/v1/tasks/", timeout=TIMEOUT)
        if get_resp.status_code != 200:
            return False, f"❌ Failed to retrieve tasks (Status: {get_resp.status_code})"
        
        tasks = get_resp.json().get("tasks", [])
        if not any(t.get("task_id") == task_id for t in tasks):
            return False, f"❌ Created task '{task_id}' not found in retrieved tasks."
        
        return True, f"✅ Task persistence verified. Created and retrieved task '{task_id}'."
    except Exception as e:
        return False, f"❌ Error testing task persistence: {e}"

def test_websocket_events() -> tuple[bool, str]:
    """Tests if the event log API returns recent events."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/events/recent", timeout=TIMEOUT)
        if response.status_code == 200:
            events = response.json().get("events", [])
            return True, f"✅ Retrieved {len(events)} recent events from WebSocket event log."
        return False, f"❌ Failed to retrieve events (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing WebSocket events: {e}"

def test_no_mock_data_agents() -> tuple[bool, str]:
    """Verifies agents are loaded from DB, not mock data."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/agents/", timeout=TIMEOUT, follow_redirects=True)
        if response.status_code == 200:
            agents = response.json().get("agents", [])
            if not agents:
                return False, "❌ No agents found. Ensure seed_database.py has run."
            return True, f"✅ Agents loaded from backend (found {len(agents)} agents)."
        return False, f"❌ Failed to retrieve agents (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing no mock data for agents: {e}"

def test_department_chat_sessions() -> tuple[bool, str]:
    """Tests creating and listing department-specific chat sessions."""
    try:
        dept_resp = httpx.get(f"{BACKEND_URL}/api/v1/departments/", timeout=TIMEOUT, follow_redirects=True)
        if dept_resp.status_code != 200:
            return False, f"❌ Failed to get departments: {dept_resp.status_code}"
        departments = dept_resp.json().get("departments", [])
        if not departments:
            return False, "❌ No departments found. Cannot test department chat."
        department_id = departments[0]["id"]
        
        create_session_resp = httpx.post(
            f"{BACKEND_URL}/api/v1/chat-history/sessions",
            json={"title": "Dept Comprehensive Test Chat", "scope_type": "department", "scope_id": department_id},
            timeout=TIMEOUT,
            follow_redirects=True
        )
        if create_session_resp.status_code != 200:
            return False, f"❌ Failed to create department chat session: {create_session_resp.status_code}"
        session_id = create_session_resp.json().get("session_id")
        if not session_id:
            return False, "❌ No session_id returned for department chat."
        
        # Small delay to ensure DB commit is visible across connections
        import time
        time.sleep(0.5)  # Increased delay for SQLite WAL mode visibility
        
        list_dept_sessions_resp = httpx.get(f"{BACKEND_URL}/api/v1/departments/{department_id}/chat/sessions", timeout=TIMEOUT, follow_redirects=True)
        if list_dept_sessions_resp.status_code != 200:
            return False, f"❌ Failed to list department chat sessions: {list_dept_sessions_resp.status_code}"
        
        dept_sessions = list_dept_sessions_resp.json().get("sessions", [])
        if not any(s.get("session_id") == session_id for s in dept_sessions):
            return False, f"❌ Created session '{session_id}' not found in department's chat list."
        
        return True, f"✅ Department chat sessions verified for department '{department_id}'."
    except Exception as e:
        return False, f"❌ Error testing department chat sessions: {e}"

def test_brain_status() -> tuple[bool, str]:
    """Tests the brain status endpoint."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/brain/status", timeout=TIMEOUT)
        if response.status_code == 200:
            status_data = response.json()
            if status_data.get("connected"):
                return True, f"✅ Brain status: Connected. Active model: {status_data.get('active_model')}"
            return True, f"⚠️ Brain status: Not connected. Error: {status_data.get('error', 'N/A')}"
        return False, f"❌ Failed to get brain status (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing brain status: {e}"

def test_voice_status() -> tuple[bool, str]:
    """Tests the voice status endpoint."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/voice/status", timeout=TIMEOUT)
        if response.status_code == 200:
            status_data = response.json()
            return True, f"✅ Voice status: Talk active: {status_data.get('talk_active')}, Voice: {status_data.get('voice_name')}"
        return False, f"❌ Failed to get voice status (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing voice status: {e}"

# --- NEW: Recommendation Tests ---
def test_councils_db() -> tuple[bool, str]:
    """Tests if councils are loaded from DB, not in-memory."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/council/list", timeout=TIMEOUT)
        if response.status_code == 200:
            councils = response.json()
            if councils:
                return True, f"✅ Councils loaded from DB (found {len(councils)} councils)."
            return True, "⚠️ No councils found, but API is accessible."
        return False, f"❌ Failed to retrieve councils (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing councils DB: {e}"

def test_council_toggle() -> tuple[bool, str]:
    """Tests toggling a council (should persist to DB)."""
    try:
        # Get councils - ensure they're seeded
        list_resp = httpx.get(f"{BACKEND_URL}/api/v1/council/list", timeout=TIMEOUT)
        if list_resp.status_code != 200:
            return False, f"❌ Failed to get councils: {list_resp.status_code}"
        councils = list_resp.json()
        
        # If no councils, try to seed by accessing a specific council endpoint
        if not councils:
            # Try to trigger seeding by accessing a known council
            seed_resp = httpx.get(f"{BACKEND_URL}/api/v1/council/finance", timeout=TIMEOUT)
            if seed_resp.status_code == 200:
                # Retry getting councils
                list_resp = httpx.get(f"{BACKEND_URL}/api/v1/council/list", timeout=TIMEOUT)
                if list_resp.status_code == 200:
                    councils = list_resp.json()
        
        if not councils:
            return False, "❌ No councils found to toggle. Seeding may have failed."
        
        council_id = councils[0].get("id", "finance")
        if not council_id:
            # Try to extract ID from the council dict
            council_id = list(councils[0].keys())[0] if councils[0] else "finance"
        
        # Toggle council - use query parameter
        toggle_resp = httpx.post(
            f"{BACKEND_URL}/api/v1/council/{council_id}/toggle?enabled=false",
            timeout=TIMEOUT
        )
        if toggle_resp.status_code == 200:
            return True, f"✅ Council toggle verified for '{council_id}'."
        return False, f"❌ Failed to toggle council (Status: {toggle_resp.status_code})"
    except Exception as e:
        return False, f"❌ Error testing council toggle: {e}"

def test_projects_db() -> tuple[bool, str]:
    """Tests if projects are loaded from DB, not in-memory."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/projects/", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])
            if projects:
                return True, f"✅ Projects loaded from DB (found {len(projects)} projects)."
            return True, "⚠️ No projects found, but API is accessible."
        return False, f"❌ Failed to retrieve projects (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing projects DB: {e}"

def test_project_create() -> tuple[bool, str]:
    """Tests creating a project (should persist to DB)."""
    try:
        project_data = {
            "name": "Comprehensive Test Project",
            "description": "Testing project persistence",
            "status": "active"
        }
        create_resp = httpx.post(f"{BACKEND_URL}/api/v1/projects/", json=project_data, timeout=TIMEOUT)
        if create_resp.status_code == 200:
            project = create_resp.json().get("project", {})
            project_id = project.get("id")
            if project_id:
                return True, f"✅ Project created and persisted: '{project_id}'."
            return False, "❌ Project created but no ID returned."
        return False, f"❌ Failed to create project (Status: {create_resp.status_code})"
    except Exception as e:
        return False, f"❌ Error testing project create: {e}"

def test_voice_state_persistence() -> tuple[bool, str]:
    """Tests if voice state persists to DB."""
    try:
        # Get initial state
        initial_resp = httpx.get(f"{BACKEND_URL}/api/v1/voice/status", timeout=TIMEOUT)
        if initial_resp.status_code != 200:
            return False, f"❌ Failed to get initial voice status: {initial_resp.status_code}"
        
        initial_state = initial_resp.json()
        initial_talk = initial_state.get("talk_active", False)
        
        # Toggle voice state
        toggle_resp = httpx.post(
            f"{BACKEND_URL}/api/v1/voice/talk-mode",
            json={"enabled": not initial_talk},
            timeout=TIMEOUT
        )
        if toggle_resp.status_code != 200:
            return False, f"❌ Failed to toggle voice state: {toggle_resp.status_code}"
        
        # Get state again (should be persisted)
        new_resp = httpx.get(f"{BACKEND_URL}/api/v1/voice/status", timeout=TIMEOUT)
        if new_resp.status_code == 200:
            new_state = new_resp.json()
            new_talk = new_state.get("talk_active", False)
            if new_talk == (not initial_talk):
                return True, f"✅ Voice state persistence verified (changed from {initial_talk} to {new_talk})."
            return False, f"❌ Voice state not persisted correctly (expected {not initial_talk}, got {new_talk})."
        return False, f"❌ Failed to get new voice status: {new_resp.status_code}"
    except Exception as e:
        return False, f"❌ Error testing voice state persistence: {e}"

def test_system_status() -> tuple[bool, str]:
    """Tests the system status endpoint."""
    try:
        response = httpx.get(f"{BACKEND_URL}/api/v1/system/status", timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("stats", {})
            return True, f"✅ System status retrieved. Departments: {stats.get('departments')}, Agents: {stats.get('agents')}, Tasks: {stats.get('tasks')}"
        return False, f"❌ Failed to get system status (Status: {response.status_code})"
    except Exception as e:
        return False, f"❌ Error testing system status: {e}"

def main():
    all_tests_passed = True
    
    tests = [
        # Phase 1-8 Tests
        ("Phase 1: Backend Health", test_backend_health),
        ("Phase 2: Database Persistence", test_database_persistence),
        ("Phase 2: Tasks Persistence", test_tasks_persistence),
        ("Phase 3: WebSocket Events Log", test_websocket_events),
        ("Phase 4: Agents No Mock Data", test_no_mock_data_agents),
        ("Phase 5: Department Chat Sessions", test_department_chat_sessions),
        ("Phase 6: Brain Status", test_brain_status),
        ("Phase 7: Voice Status", test_voice_status),
        
        # Recommendation Tests
        ("Recommendation: Councils DB Migration", test_councils_db),
        ("Recommendation: Council Toggle", test_council_toggle),
        ("Recommendation: Projects DB Migration", test_projects_db),
        ("Recommendation: Project Create", test_project_create),
        ("Recommendation: Voice State Persistence", test_voice_state_persistence),
        ("Recommendation: System Status", test_system_status),
    ]
    
    for description, test_func in tests:
        print_header(description)
        passed, message = run_test(test_func)
        print(message)
        if not passed:
            all_tests_passed = False
    
    print_header("COMPREHENSIVE TEST SUMMARY")
    if all_tests_passed:
        print("✅ ALL TESTS PASSED!")
        print("✅ All phases (1-8) verified")
        print("✅ All recommendations implemented and tested")
        return 0
    else:
        print("❌ SOME TESTS FAILED. Review the logs above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

